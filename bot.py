import os
import time
import uuid
from flask import Flask, request, make_response
from twilio.twiml.messaging_response import MessagingResponse
from gtts import gTTS
import google.generativeai as genai
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# --- 1. CONFIGURATION ---
SUPABASE_URL = "https://ijfowsrtiqifdbcwgllt.supabase.co"
SUPABASE_KEY = "sb_secret_tHlIGiZpqtuOqV5mWHR3lg__QR-GcpW"
GEMINI_API_KEY = "AIzaSyAgNUZjyxSMDBVizQFR_d7VK29hQUSzkn0"

genai.configure(api_key=GEMINI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
@app.route("/whatsapp", methods=['GET', 'POST'])
def whatsapp_bot():
    user_query = request.values.get('Body', '').strip()
    
    print(f"\n--- New Request Received ---", flush=True)
    print(f"User Message: '{user_query}'", flush=True)

    if not user_query:
        return "Medical AI Server is LIVE!", 200

    try:
        print("Consulting Gemini AI...", flush=True)
        system_instruction = "You are a professional medical assistant. Provide concise first-aid advice."
        prompt = f"{system_instruction}\n\nUser Question: {user_query}"
        
        gemini_response = model.generate_content(prompt)
        ai_text = gemini_response.text
        print(f"AI Response Generated.", flush=True)

        print("Generating Voice Note...", flush=True)
        audio_filename = f"{uuid.uuid4()}.mp3"
        tts = gTTS(text=ai_text, lang='en', slow=False) 
        tts.save(audio_filename)

        print("Uploading to Supabase...", flush=True)
        with open(audio_filename, 'rb') as f:
            supabase.storage.from_('medical-voice').upload(
                path=audio_filename, 
                file=f,
                file_options={"content-type": "audio/mpeg", "upsert": "true"}
            )
        
        voice_url = supabase.storage.from_('medical-voice').get_public_url(audio_filename)

        twiml_resp = MessagingResponse()
        timestamp = int(time.time())
        final_voice_url = f"{voice_url}?t={timestamp}"
        
        twiml_resp.message(ai_text)
        twiml_resp.message("").media(final_voice_url)
        
        print(f"Success! Sending response to Twilio.", flush=True)
        
        response = make_response(str(twiml_resp))
        response.headers['Content-Type'] = 'text/xml'
        
        if os.path.exists(audio_filename):
            os.remove(audio_filename)
            
        return response

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}", flush=True)
        error_resp = MessagingResponse()
        error_resp.message("I'm sorry, I encountered a technical error. Please try again.")
        return make_response(str(error_resp))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
