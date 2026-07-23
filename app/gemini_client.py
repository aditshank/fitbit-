import base64
import json
import logging
import requests
from app.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={GEMINI_API_KEY}"


def _build_prompt(text_note: str = "") -> str:
    base = (
        "Analyze this food image THOROUGHLY. Identify EVERY food item on the plate (main dish, "
        "sides, garnishes, sauces, drinks). Estimate portions in grams for each item, then SUM "
        "them into a single combined result. "
        "Return a JSON object with: food_name (a short description listing all items, e.g. "
        "'Grilled chicken with rice, salad and roasted potatoes'), calories, protein_g, fat_g, "
        "carbs_g, and portion_grams (total grams). "
        "Be comprehensive - don't miss side dishes, vegetables, starches, or sauces. "
        "Respond with ONLY valid JSON, no markdown, no commentary."
    )
    if text_note.strip():
        base += f"\n\nThe user provided this additional context about the meal: '{text_note.strip()}'. "
        base += "Use this to improve your estimate (e.g., account for cooking oils, butter, sauces)."
    return base


def analyze_food_image(image_bytes: bytes, mime_type: str = "image/jpeg", text_note: str = "") -> dict:
    if not GEMINI_API_KEY:
        return {
            "food_name": "Demo Meal",
            "calories": 450.0,
            "protein_g": 25.0,
            "fat_g": 15.0,
            "carbs_g": 50.0,
            "portion_grams": 250.0,
        }

    encoded = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [{
            "parts": [
                {"text": _build_prompt(text_note)},
                {"inline_data": {"mime_type": mime_type, "data": encoded}}
            ]
        }],
        "generationConfig": {"temperature": 0.2},
    }

    resp = requests.post(GEMINI_URL, json=payload, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Gemini API error: {resp.status_code} {resp.text}")

    result = resp.json()
    text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

    cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
    parsed = json.loads(cleaned)
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}
    return parsed
