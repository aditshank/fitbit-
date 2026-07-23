import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FATSECRET_CONSUMER_KEY = os.getenv("FATSECRET_CONSUMER_KEY", "")
FATSECRET_CONSUMER_SECRET = os.getenv("FATSECRET_CONSUMER_SECRET", "")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production")
APP_NAME = os.getenv("APP_NAME", "Calorie Tracker")

HEALTH_API_BASE = "https://health.googleapis.com/v4"
HEALTH_SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.nutrition.writeonly",
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.nutrition.readonly",
]
