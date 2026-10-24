import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))


class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'replace_with_a_long_random_secret')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').strip().lower() in {'1', 'true', 'yes', 'on'}
    DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(BASE_DIR, 'database', 'chatbot.db'))
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.6-flash')
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    MAX_MESSAGE_LENGTH = 4000
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = not DEBUG
    PERMANENT_SESSION_LIFETIME = 3600
