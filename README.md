# Booky - The Multi Agentic Appointment Booking System

Booky is an intelligent, multi-agent AI-powered appointment booking system designed to streamline scheduling through a conversational interface. It leverages advanced AI models to understand user intent, check availability, book appointments, update records, and send confirmation emails—automating the entire appointment management process.

---

## Features

- AI-driven conversational booking powered by Google Gemini model
- Real-time availability checking of appointment slots in a SQLite database
- Automated booking that updates the database and Google Sheets
- Email confirmation sent to users upon successful booking
- Web interface built with Flask for user interaction
- Modular, multi-agent architecture for clear separation of concerns

---

## Architecture Overview

```
START
  |
  |-- Load Configuration & .env
  |
  |-- Initialize Flask App
  |
  |-- Initialize Database
  |        |
  |        '--- Seed time slots if empty
  |
  |-- Initialize Google Sheets API
  |
  |-- User Opens Website (Serves index.html)
  |
  |-- User Sends Chat Message
           |
           '-- Gemini Model Processes Message
                    |
                    '-- Check Intent: [Availability] or [Booking]
                           |                      |
             [get_available_slots(date)]    [book_appointment(slot_time, name, email)]
                           |                      |
              Return available slots    Update DB, Log to Sheets, Send Email
                           |                      |
                 User picks a slot? <------------+
                           |
                   Proceed to booking
                           |
                     Booking confirmation
                           |
                      Send final reply
                           |
                          END

    
```

---

## Getting Started

### Prerequisites

- Python 3.8 or higher
- SQLite (usually included with Python)
- Google Cloud project with Google Sheets API enabled
- Gmail account (or another SMTP-enabled email) for sending confirmation emails
- `.env` file with API keys and credentials

---

### Installation and Setup

1. **Clone the repository**

   ```
   git clone https://github.com/Vatsa10/Booky.git
   cd Booky
   ```

2. **Create and activate a Python virtual environment**

   ```
   python -m venv venv
   source venv/bin/activate      # For Linux/macOS
   venv\Scripts\activate         # For Windows
   ```

3. **Install dependencies**

   ```
   pip install -r req.txt
   ```

4. **Google Cloud and API configuration**

   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create/select a project
   - Enable **Google Sheets API** and **Gmail API**
   - Create a **Service Account** with Editor permission
   - Download the JSON key file for the Service Account

5. **Set up Google Sheets**

   - Create a new spreadsheet
   - Share it with the service account’s email address with Editor permission
   - Copy the spreadsheet ID from the Google Sheets URL

6. **Create a `.env` file in the root directory with the following**

   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   GOOGLE_SHEETS_CREDENTIALS=path/to/service-account-credentials.json
   GOOGLE_SPREADSHEET_ID=your_spreadsheet_id_here
   EMAIL_ADDRESS=your_email@example.com
   EMAIL_PASSWORD=your_email_password_or_app_password
   BUSINESS_NAME=YourBusinessName
   ```

---

### Running the Application

Run the Flask web server and initialize the database seed:

```
python app.py
```

This will start the server on:

```
http://localhost:5000
```

---

### Usage

- Access the URL in your browser
- Type messages in the chat interface to:
  - Check available appointment slots
  - Book an appointment by providing name and email
- Receive booking confirmation emails automatically

---

### Project Structure

```
booky/
│
├── app.py                  # Main Flask app with AI agent logic
├── appointments.db         # SQLite database file (auto-created)
├── public/
│   ├── index.html          # Frontend UI for chat
│   └── ...                 # Static assets (CSS, JS)
├── credentials.json        # Google API service account credentials
├── requirements.txt        # Python dependencies
└── .env                    # Environment variables, not included in repo
```

---


Enjoy effortless AI-powered appointment scheduling with **Booky**!
