from dotenv import load_dotenv
load_dotenv()  # This loads the variables from the .env file
import os
import time
import uuid
from flask import Flask, request, make_response
from twilio.twiml.messaging_response import MessagingResponse
from gtts import gTTS
import google.generativeai as genai
from supabase import create_client

# --- 1. CONFIGURATION (Grabbing from Render Env Variables) ---
# This ensures 
# your keys are secure and not hardcoded
SUPABASE_URL = ("https://ijfowsrtiqifdbcwgllt.supabase.co")
SUPABASE_KEY = ("sb_secret_tHlIGiZpqtuOqV5mWHR3lg__QR-GcpW")
GEMINI_API_KEY =("AIzaSyAgNUZjyxSMDBVizQFR_d7VK29hQUSzkn0")

# Initialize External Services
genai.configure(api_key=GEMINI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. MODEL INITIALIZATION ---
# Using 1.5-flash for a much higher free-tier quota (1500 requests/day)
model = genai.GenerativeModel('gemini-1.5-flash')

# Initialize Flask App
app = Flask(__name__)

# --- 3. THE MAIN BOT ROUTE ---
@app.route("/", methods=['GET', 'POST'])
@app.route("/whatsapp", methods=['GET', 'POST'])
def whatsapp_bot():
    # Capture the message from WhatsApp
    user_query = request.values.get('Body', '').strip()
    
    print(f"\n--- New Request Received ---")
    print(f"User Message: '{user_query}'")

    # Health Check (If you open the Render URL in a browser)
    if not user_query:
        return "Medical AI Server is LIVE and waiting for WhatsApp messages!", 200

    try:
        # A. Get Response from Gemini AI
        print("Consulting Gemini AI...")
        system_instruction = "You are a professional medical assistant. Provide concise, accurate, and easy-to-understand first-aid advice in English."
        prompt = f"{system_instruction}\n\nUser Question: {user_query}"
        
        gemini_response = model.generate_content(prompt)
        ai_text = gemini_response.text
        print(f"AI Response Generated.")

        # B. Convert Text to Audio (gTTS)
        print("Generating Voice Note...")
        audio_filename = f"{uuid.uuid4()}.mp3"
        tts = gTTS(text=ai_text, lang='en', slow=False) 
        tts.save(audio_filename)

        # C. Upload to Supabase Storage
        print("Uploading to Supabase...")
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
        twiml_resp = MessagingResponse()
        
        # Add a timestamp to bypass Twilio media caching
        timestamp = int(time.time())
        final_voice_url = f"{voice_url}?t={timestamp}"
        
        # 1. Send the text explanation
        twiml_resp.message(ai_text)
        
        # 2. Send the audio file
        twiml_resp.message("").media(final_voice_url)
        
        print(f"Success! Sending response to Twilio.")
        
        # Build the final XML response
        response = make_response(str(twiml_resp))
        response.headers['Content-Type'] = 'text/xml'
        
        # Clean up the local file after upload to save server space
        if os.path.exists(audio_filename):
            os.remove(audio_filename)
            
        return response

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        # Return a friendly error message to the user instead of crashing
        error_resp = MessagingResponse()
        error_resp.message("I'm sorry, I encountered a technical error. Please try again in a moment.")
        return make_response(str(error_resp))

# --- 4. START THE SERVER ---
if __name__ == "__main__":
    # Render dynamic port logic: uses Render's assigned port or defaults to 5000
    port = int(os.environ.get("PORT", 5000))
    # host='0.0.0.0' is required for cloud deployment
    app.run(host='0.0.0.0', port=port)