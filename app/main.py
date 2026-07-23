import logging
import uuid
from datetime import date as date_type, timedelta
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
import app.auth as auth

import app.gemini_client as gemini
import app.health_api as health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Calorie Tracker - Google Health API v4")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/service-worker.js")
async def service_worker():
    return FileResponse("static/service-worker.js", media_type="application/javascript")

_jinja_env = Environment(loader=FileSystemLoader("templates"), cache_size=0)
templates = Jinja2Templates(env=_jinja_env)

STATE_STORE = {}

def _get_token(user: dict) -> str:
    token = user.get("access_token", "")
    if not token and user.get("refresh_token"):
        try:
            refreshed = auth.refresh_access_token(user["refresh_token"])
            token = refreshed.get("access_token", "")
        except Exception:
            pass
    return token

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, date: str = None):
    user = auth.get_logged_in_user(request)
    if not user:
        return templates.TemplateResponse("index.html", {"request": request, "user": None})

    today = date_type.today()
    try:
        current_date = date_type.fromisoformat(date) if date else today
    except (ValueError, TypeError):
        current_date = today

    access_token = _get_token(user)
    daily = health.get_daily_rollup(access_token, current_date.isoformat())
    history = health.get_nutrition_history(access_token, current_date.isoformat())
    connection = health.check_connection(access_token)
    weekly = health.get_weekly_trend(access_token, today)

    prev_date = (current_date - timedelta(days=1)).isoformat()
    next_date = (current_date + timedelta(days=1)).isoformat() if current_date < today else None

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "daily": daily,
        "history": history,
        "connection": connection,
        "current_date": current_date.isoformat(),
        "prev_date": prev_date,
        "next_date": next_date,
        "is_today": current_date == today,
        "weekly": weekly,
    })

@app.get("/auth/login")
async def login():
    state = str(uuid.uuid4())
    STATE_STORE[state] = True
    redirect_url = auth.get_authorization_url(state)
    return RedirectResponse(url=redirect_url)

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = None, state: str = None, error: str = None):
    if error:
        return HTMLResponse(f"<h3>Auth error: {error}</h3>")

    if not code or state not in STATE_STORE:
        raise HTTPException(status_code=400, detail="Invalid state or missing code")

    STATE_STORE.pop(state, None)
    token_data = auth.exchange_code(code)
    user_info = auth.get_user_info(token_data["access_token"])

    user_info["access_token"] = token_data["access_token"]
    user_info["refresh_token"] = token_data.get("refresh_token")

    session_token = auth.create_session_token(user_info)

    response = RedirectResponse(url="/")
    response.set_cookie(key="session", value=session_token, httponly=True, max_age=604800)
    return response

@app.get("/auth/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("session")
    return response

@app.post("/api/analyze")
async def analyze_food(
    file: UploadFile = File(...),
    text_note: str = Form(""),
    request: Request = None,
):
    user = auth.get_logged_in_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    contents = await file.read()

    result = gemini.analyze_food_image(contents, file.content_type or "image/jpeg", text_note)
    result["source"] = "gemini"

    return result

@app.post("/api/log-meal")
async def log_meal(data: dict, request: Request = None):
    user = auth.get_logged_in_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    access_token = _get_token(user)
    status, response = health.post_nutrition_log(
        access_token=access_token,
        food_name=data.get("food_name", "Unknown"),
        calories=float(data.get("calories", 0)),
        protein_g=float(data.get("protein_g", 0)),
        fat_g=float(data.get("fat_g", 0)),
        carbs_g=float(data.get("carbs_g", 0)),
        meal_type=data.get("meal_type", "meal"),
        portion_grams=data.get("portion_grams"),
        text_note=data.get("text_note", ""),
    )
    return {"status": status, "response": response}

@app.get("/api/daily-rollup")
async def daily_rollup(date: str = None, request: Request = None):
    user = auth.get_logged_in_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    access_token = _get_token(user)
    return health.get_daily_rollup(access_token, date)

@app.get("/api/history")
async def nutrition_history(date: str = None, request: Request = None):
    user = auth.get_logged_in_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    access_token = _get_token(user)
    return health.get_nutrition_history(access_token, date)

@app.delete("/api/history/{data_point_name:path}")
async def delete_nutrition(data_point_name: str, request: Request = None):
    user = auth.get_logged_in_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    access_token = _get_token(user)
    ok = health.delete_nutrition_entry(access_token, data_point_name)
    return {"deleted": ok}

@app.get("/api/connection-status")
async def connection_status(request: Request):
    user = auth.get_logged_in_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    access_token = _get_token(user)
    return health.check_connection(access_token)


@app.get("/api/day/{date}")
async def get_day_data(date: str, request: Request):
    user = auth.get_logged_in_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    access_token = _get_token(user)
    daily = health.get_daily_rollup(access_token, date)
    history = health.get_nutrition_history(access_token, date)
    return {"daily": daily, "history": history}


@app.get("/api/weekly")
async def get_weekly_data(request: Request):
    user = auth.get_logged_in_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    access_token = _get_token(user)
    return health.get_weekly_trend(access_token)
