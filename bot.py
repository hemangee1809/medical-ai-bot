import os
import time
import uuid
from flask import Flask, request, make_response
from twilio.twiml.messaging_response import MessagingResponse
from gtts import gTTS
import google.generativeai as genai
from supabase import create_client
from dotenv import load_dotenv

# Load local .env if it exists
load_dotenv()

# --- 1. CONFIGURATION ---
# Replace these with your actual keys if not using Render Env Variables
SUPABASE_URL = "https://ijfowsrtiqifdbcwgllt.supabase.co"
SUPABASE_KEY = "sb_secret_tHlIGiZpqtuOqV5mWHR3lg__QR-GcpW"
GEMINI_API_KEY = "AIzaSyAgNUZjyxSMDBVizQFR_d7VK29hQUSzkn0"

# Initialize External Services
genai.configure(api_key=GEMINI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Use Gemini 1.5 Flash
model = genai.GenerativeModel('gemini-1.5-flash')

# Initialize Flask App
app = Flask(__name__)

# --- 2. THE MAIN BOT ROUTE ---
@app.route("/", methods=['GET', 'POST'])
@app.route("/whatsapp", methods=['GET', 'POST'])
def whatsapp_bot():
    # Capture the message from WhatsApp
    user_query = request.values.get('Body', '').strip()
    
    print(f"\n--- New Request Received ---", flush=True)
    print(f"User Message: '{user_query}'", flush=True)

    # Health Check for Browser
    if not user_query:
        return "Medical AI Server is LIVE and waiting for WhatsApp messages!", 200

    try:
        # A. Get Response from Gemini AI
        print("Consulting Gemini AI...", flush=True)
        system_instruction = "You are a professional medical assistant. Provide concise, accurate first-aid advice in English."
        prompt = f"{system_instruction}\n\nUser Question: {user_query}"
        
        gemini_response = model.generate_content(prompt)
        ai_text = gemini_response.text
        print(f"AI Response Generated.", flush=True)

        # B. Convert Text to Audio (gTTS)
        print("Generating Voice Note...", flush=True)
        audio_filename = f"{uuid.uuid4()}.mp3"
        tts = gTTS(text=ai_text, lang='en', slow=False) 
        tts.save(audio_filename) # RE-ENABLED THIS

        # C. Upload to Supabase Storage
        print("Uploading to Supabase...", flush=True)
        with open(audio_filename, 'rb') as f:
            supabase.storage.from_('medical-voice').upload(
                path=audio_filename, 
                file=f,
                file_options={
                    "content-type": "audio/mpeg",
                    "upsert": "true"
                }
            )
        
        # D. Get Public URL
        voice_url = supabase.storage.from_('medical-voice').get_public_url(audio_filename)

        # E. Twilio Response Construction
        twiml_resp = MessagingResponse() # RE-ENABLED THIS
        
        # Add a timestamp to bypass Twilio media caching
        timestamp = int(time.time())
        final_voice_url = f"{voice_url}?t={timestamp}"
        
        # 1. Send the text explanation
        twiml_resp.message(ai_text)
        
        # 2. Send the audio file
        twiml_resp.message("").media(final_voice_url)
        
        print(f"Success! Sending response to Twilio.", flush=True)
        
        # Build the final XML response
        response = make_response(str(twiml_resp))
        response.headers['Content-Type'] = 'text/xml'
        
        # Clean up the local file after upload
        if os.path.exists(audio_filename):
            os.remove(audio_filename)
            
        return response

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}", flush=True)
        error_resp = MessagingResponse()
        error_resp.message("I'm sorry, I encountered a technical error. Please try again.")
        return make_response(str(error_resp))

# --- 3. START THE SERVER ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
