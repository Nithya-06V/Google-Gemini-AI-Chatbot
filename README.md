# Google Gemini AI Assistant

A Flask-based AI chatbot that uses the official Google Gen AI SDK to answer user questions with conversation history, persistent chat storage, and a responsive Bootstrap 5 dashboard.

## Features

- Secure admin login using Flask sessions
- Google Gemini API integration via the official SDK
- Persistent SQLite conversation history
- Dark mode and light mode options
- Suggested question cards
- New chat, clear chat, rename, and delete conversation controls
- Responsive UI for desktop, tablet, and mobile devices
- Friendly validation and error handling
- Backend tests using pytest

## Technology Stack

- Python 3
- Flask
- SQLite
- Bootstrap 5
- JavaScript (Fetch API)
- Google Gen AI Python SDK
- python-dotenv

## Folder Structure

```text
.
├── app.py
├── config.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── README.md
├── database/
│   └── chatbot.db
├── services/
│   ├── __init__.py
│   └── gemini_service.py
├── templates/
│   ├── 404.html
│   ├── base.html
│   ├── chatbot.html
│   ├── login.html
│   └── settings.html
├── static/
│   ├── css/
│   │   ├── chatbot.css
│   │   ├── login.css
│   │   └── style.css
│   ├── js/
│   │   ├── chatbot.js
│   │   └── login.js
│   └── images/
│       └── logo.svg
└── tests/
    └── test_app.py
```

## Prerequisites

- Python 3.10 or newer
- VS Code
- A Google AI Studio API key

## Google Gemini API Key Setup

1. Visit Google AI Studio.
2. Create or sign into your Google account.
3. Generate a Gemini API key.
4. Save the key in your local `.env` file as `GEMINI_API_KEY`.

Never paste your API key into public chat messages, frontend JavaScript, or source control.

## Environment Variables

Create a `.env` file in the project root, based on `.env.example`.

```env
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-3.6-flash
FLASK_SECRET_KEY=replace_with_a_long_random_secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
DATABASE_PATH=database/chatbot.db
FLASK_DEBUG=True
```

`FLASK_DEBUG=True` is only for local development. Disable it in production.

### Windows setup

```powershell
copy .env.example .env
```

Then edit `.env` and replace placeholders with your real values.

## Local Development Setup

### 1. Create the virtual environment

```powershell
python -m venv venv
```

### 2. Activate the environment

```powershell
venv\Scripts\activate
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Initialize the database

The application creates the SQLite database automatically when it starts.

### 5. Start the app

```powershell
python app.py
```

Open the app at:

```text
http://127.0.0.1:5000
```

## Login Credentials

The default development credentials are:

- Username: `admin`
- Password: `admin123`

These are intended only for local development and should be changed before deployment.

## Usage

1. Open the application in a browser.
2. Sign in with the admin credentials.
3. Ask questions in the chat box.
4. Use suggested questions or enter your own.
5. Create, rename, or delete conversations from the sidebar.
6. Use the dark mode toggle and the settings page.

## Testing

Install test dependencies from `requirements.txt` and run:

```powershell
pytest
```

## Troubleshooting

- If `ModuleNotFoundError` appears, run `python -m pip install -r requirements.txt`.
- If Gemini calls fail, ensure `GEMINI_API_KEY` is valid and your account has access to the selected model.
- If the database is not created, make sure the project can write to the `database/` folder.
- If the app does not start, check the terminal output for missing environment variables or port issues.

## Security Notes

- Keep secrets in `.env` and do not commit `.env` to Git.
- Use a strong `FLASK_SECRET_KEY` in production.
- Do not store secrets in frontend JavaScript.
- Use secure cookie settings in production with HTTPS enabled.
- Keep the default admin password only for local testing.

## Future Enhancements

- User registration and account management
- Chat export and import
- Conversation summaries
- Enhanced model configuration
- Deployment to Render, Railway, or Azure
