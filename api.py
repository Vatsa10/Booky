# ---------------------------------
# 1. SETUP AND DEPENDENCIES
# ---------------------------------
import os
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta, datetime
from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
# --- ADDED IMPORT FOR PROTOBUF ---
# This is a stable way to construct complex data types for the API
from google.protobuf.struct_pb2 import Struct
# --- END ADDITION ---
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
import sys
import base64
import json

load_dotenv()

app = Flask(__name__, static_folder='public', template_folder='public')

# ---------------------------------
# 2. CONFIGURATION & INITIALIZATION
# ---------------------------------

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not found in .env file.")
    sys.exit(1)
genai.configure(api_key=GEMINI_API_KEY)

# Database setup
DB_FILE = 'appointments.db'

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Initializes the database schema and seeds it with time slots."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_time TEXT NOT NULL UNIQUE,
            is_booked INTEGER DEFAULT 0,
            booked_by_name TEXT,
            booked_by_email TEXT
        );
    ''')

    # Check if the table is empty before seeding
    cursor.execute('SELECT COUNT(*) FROM time_slots')
    count = cursor.fetchone()[0]

    if count == 0:
        print("Seeding database with initial time slots...")
        today = date.today()
        for i in range(1, 8):  # Seed for the next 7 days
            day = today + timedelta(days=i)
            # Seed from 9 AM to 4 PM (16:00)
            for j in range(9, 17):
                slot_time = f"{day.isoformat()}T{j:02d}:00:00"
                cursor.execute('INSERT INTO time_slots (slot_time) VALUES (?)', (slot_time,))
        print("Database seeding complete.")

    conn.commit()
    conn.close()
    
# Google Sheets API setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID')

creds = None

# Option 1: Local dev (use JSON file)
KEY_FILE_LOCATION = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
if KEY_FILE_LOCATION and os.path.exists(KEY_FILE_LOCATION):
    creds = Credentials.from_service_account_file(KEY_FILE_LOCATION, scopes=SCOPES)

# Option 2: Base64 encoded creds (Render / cloud deploy)
if creds is None:
    creds_b64 = os.getenv("GOOGLE_SHEETS_CREDENTIALS_B64")
    if creds_b64:
        try:
            creds_json = base64.b64decode(creds_b64).decode("utf-8")
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        except Exception as e:
            print(f"Failed to parse GOOGLE_SHEETS_CREDENTIALS_B64: {e}")
            sys.exit(1)

if creds is None:
    print("ERROR: Google Sheets credentials not found. Please set GOOGLE_SHEETS_CREDENTIALS (file path) or GOOGLE_SHEETS_CREDENTIALS_B64 (base64 string).")
    sys.exit(1)

sheets_service = build('sheets', 'v4', credentials=creds)

# ---------------------------------
# 3. WORKER AGENTS (TOOLS)
# These functions are the "tools" our Gemini agent can use.
# ---------------------------------

def get_available_slots(date: str) -> str:
    """
    Worker Agent: Time Slot Checker.
    Checks the database for available appointment slots on a given date.
    Args:
        date: The date to check in 'YYYY-MM-DD' format.
    Returns:
        A JSON string of available slots or an error message.
    """
    print(f"[Tool] Checking available slots for: {date}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT slot_time FROM time_slots WHERE date(slot_time) = ? AND is_booked = 0"
        cursor.execute(query, (date,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"No available slots on {date}. Please ask the user to try another date."

        return str([row['slot_time'] for row in rows])
    except Exception as e:
        print(f"Error in get_available_slots: {e}")
        return "Failed to retrieve slots due to an internal error."


def book_appointment(slot_time: str, name: str, email: str) -> str:
    """
    Worker Agent: Appointment Booker.
    Books an appointment, updates DB, adds to Google Sheets, and sends an email.
    Args:
        slot_time: The full ISO 8601 datetime string for the appointment.
        name: The name of the person booking.
        email: The email of the person booking.
    Returns:
        A JSON string with a confirmation message.
    """
    print(f"[Tool] Attempting to book appointment for {name} at {slot_time}")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. Database Agent: Check availability and update the database
        cursor.execute("SELECT is_booked FROM time_slots WHERE slot_time = ?", (slot_time,))
        slot = cursor.fetchone()
        if slot is None or slot['is_booked']:
            return "This time slot is no longer available. Please ask the user to select another time."

        cursor.execute(
            'UPDATE time_slots SET is_booked = 1, booked_by_name = ?, booked_by_email = ? WHERE slot_time = ?',
            (name, email, slot_time)
        )
        conn.commit()

        # 2. Google Sheets Agent: Append to the sheet
        values = [[str(datetime.now()), slot_time, name, email]]
        body = {'values': values}
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range='Sheet1!A:D',
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        print("[Tool] Added to Google Sheets.")

        # 3. Email Agent: Send confirmation email
        msg = MIMEMultipart()
        msg['From'] = f'"{os.getenv("BUSINESS_NAME")}" <{os.getenv("EMAIL_ADDRESS")}>'
        msg['To'] = email
        msg['Subject'] = f'Appointment Confirmed: {os.getenv("BUSINESS_NAME")}'
        
        formatted_date = datetime.fromisoformat(slot_time).strftime('%A, %B %d, %Y at %I:%M %p')
        
        body = f"""
        <h1>Appointment Confirmed!</h1>
        <p>Hello {name},</p>
        <p>Your appointment with <strong>{os.getenv("BUSINESS_NAME")}</strong> is confirmed for:</p>
        <h2>{formatted_date}</h2>
        <p>We look forward to seeing you!</p>
        """
        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(os.getenv("EMAIL_ADDRESS"), os.getenv("EMAIL_PASSWORD"))
            server.send_message(msg)
        print(f"[Tool] Confirmation email sent to {email}.")

        return f"Successfully booked appointment for {name} at {formatted_date}. I have already informed the user that a confirmation email has been sent."

    except Exception as e:
        conn.rollback()
        print(f"Error in book_appointment: {e}")
        return "An internal error occurred while booking. Please apologize to the user and ask them to try again."
    finally:
        conn.close()


# ---------------------------------
# 4. ORCHESTRATOR AGENT (GEMINI)
# ---------------------------------
model = genai.GenerativeModel(
    'gemini-1.5-flash',
    tools=[get_available_slots, book_appointment]
)
chat_session = model.start_chat()


@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handles the chat logic with the Gemini model."""
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    print(f"User Message: {user_message}")
    
    try:
        # Send message to Gemini
        response = chat_session.send_message(user_message)
        
        # Handle potential function calls from the model
        for part in response.candidates[0].content.parts:
            if part.function_call:
                func_name = part.function_call.name
                # Convert the model's arguments to a Python dictionary
                args = dict(part.function_call.args)
                
                print(f"Gemini wants to call function: {func_name} with args: {args}")

                # Find and execute the corresponding Python function
                if func_name == "get_available_slots":
                    result = get_available_slots(date=args['date'])
                elif func_name == "book_appointment":
                    result = book_appointment(slot_time=args['slot_time'], name=args['name'], email=args['email'])
                else:
                    result = f"Error: Function {func_name} not found."
                
                # --- MODIFIED BLOCK ---
                # Create a protobuf Struct to hold the response dictionary
                s = Struct()
                s.update({'result': result})

                # Send the function's result back to Gemini using the lower-level protos
                # This is more stable across different library versions
                response = chat_session.send_message(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=func_name,
                            response=s
                        )
                    )
                )
                # --- END MODIFICATION ---

        # Extract the final text response from Gemini
        final_response = response.candidates[0].content.parts[0].text
        print(f"Gemini Response: {final_response}")
        return jsonify({"reply": final_response})

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "An error occurred while processing your request."}), 500


# ---------------------------------
# 5. APPLICATION START
# ---------------------------------
if __name__ == '__main__':
    initialize_database()
    app.run(port=5000, debug=True)

