import logging
from datetime import datetime, timedelta, timezone, date as date_type
import requests
from app.config import HEALTH_API_BASE

logger = logging.getLogger(__name__)
API_BASE = HEALTH_API_BASE


def _headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def check_connection(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(f"{API_BASE}/users/me/identity", headers=headers, timeout=10)
    return {
        "connected": resp.status_code == 200,
        "status_code": resp.status_code,
        "detail": resp.json() if resp.status_code == 200 else resp.text[:300],
    }


def post_nutrition_log(access_token: str, food_name: str, calories: float,
                       protein_g: float, fat_g: float, carbs_g: float,
                       meal_type: str = "meal", portion_grams: float = None,
                       text_note: str = ""):
    now = datetime.now(timezone.utc)
    start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "nutritionLog": {
            "interval": {
                "startTime": start,
                "endTime": end,
            },
            "energy": {"kcal": calories},
            "totalFat": {"grams": fat_g},
            "totalCarbohydrate": {"grams": carbs_g},
            "nutrients": [
                {"quantity": {"grams": protein_g}, "nutrient": "PROTEIN"}
            ],
            "mealType": meal_type.upper(),
            "foodDisplayName": food_name + (f" ({text_note})" if text_note.strip() else ""),
        }
    }

    resp = requests.post(
        f"{API_BASE}/users/me/dataTypes/nutrition-log/dataPoints",
        json=payload,
        headers=_headers(access_token),
    )
    logger.info(f"Nutrition POST {resp.status_code}: {resp.text[:500]}")
    return resp.status_code, resp.json()


def _get_float(d, *keys):
    """Safely traverse nested dict to get a float."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, {})
        else:
            return 0.0
    return float(d) if isinstance(d, (int, float)) else 0.0


def _get_str(d, *keys):
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, {})
        else:
            return ""
    return str(d) if d else ""


def get_daily_calories_burned(access_token: str, dt: date_type = None) -> float:
    if dt is None:
        dt = date_type.today()

    body = {
        "range": {
            "start": {
                "date": {"year": dt.year, "month": dt.month, "day": dt.day},
                "time": {"hours": 0, "minutes": 0, "seconds": 0, "nanos": 0},
            },
            "end": {
                "date": {"year": dt.year, "month": dt.month, "day": dt.day},
                "time": {"hours": 23, "minutes": 59, "seconds": 59, "nanos": 0},
            },
        },
        "windowSizeDays": 1,
    }

    # Strategy 1: total-calories dailyRollUp (active + basal combined, derived type)
    try:
        url = f"{API_BASE}/users/me/dataTypes/total-calories/dataPoints:dailyRollUp"
        resp = requests.post(url, json=body, headers=_headers(access_token), timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            points = data.get("rollupDataPoints", [])
            if points:
                val = points[0].get("totalCalories", {})
                total = float(val.get("kcalSum", val.get("kcalAvg", val.get("kcal", 0))))
                if total > 0:
                    logger.info(f"total-calories dailyRollUp: {total}")
                    return round(total, 1)
    except Exception as e:
        logger.warning(f"total-calories dailyRollUp failed: {e}")

    # Strategy 2: sum active-energy-burned + basal-energy-burned (list endpoints)
    total = 0.0
    for data_type in ["active-energy-burned", "basal-energy-burned"]:
        try:
            url = f"{API_BASE}/users/me/dataTypes/{data_type}/dataPoints"
            resp = requests.get(url, headers=_headers(access_token), params={"pageSize": 1000}, timeout=15)
            if resp.status_code == 200:
                pts = resp.json().get("dataPoints", [])
                subtotal = 0.0
                for pt in pts:
                    for field in ("activeEnergyBurned", "basalEnergyBurned"):
                        subtotal += float(pt.get(field, {}).get("kcal", 0))
                logger.info(f"{data_type} list total: {subtotal}")
                total += subtotal
            else:
                logger.info(f"{data_type} list returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"Failed {data_type} list: {e}")

    if total > 0:
        logger.info(f"Summed active+basal total: {total}")
        return round(total, 1)

    return 0.0


def get_daily_calories_consumed(access_token: str, dt: date_type = None) -> float:
    if dt is None:
        dt = date_type.today()

    date_str = dt.strftime("%Y-%m-%d")
    url = f"{API_BASE}/users/me/dataTypes/nutrition-log/dataPoints"
    resp = requests.get(url, headers=_headers(access_token), timeout=15)

    if resp.status_code != 200:
        logger.warning(f"Nutrition list failed: {resp.status_code} {resp.text[:300]}")
        return 0.0

    data = resp.json()
    points = data.get("dataPoints", [])
    logger.info(f"Got {len(points)} total nutrition entries")

    total_calories = 0.0
    for p in points:
        nl = p.get("nutritionLog", {})
        civ = nl.get("interval", {}).get("civilStartTime", {}).get("date", {})
        entry_date = f"{civ.get('year')}-{civ.get('month'):02d}-{civ.get('day'):02d}"

        if entry_date == date_str:
            energy = nl.get("energy", {})
            if isinstance(energy, dict):
                total_calories += float(energy.get("kcal", 0))
            else:
                total_calories += float(energy) if energy else 0.0

    logger.info(f"Total calories consumed for {date_str}: {total_calories}")
    return round(total_calories, 1)


def get_daily_macros(access_token: str, dt: date_type = None) -> dict:
    if dt is None:
        dt = date_type.today()
    date_str = dt.strftime("%Y-%m-%d")
    url = f"{API_BASE}/users/me/dataTypes/nutrition-log/dataPoints"
    resp = requests.get(url, headers=_headers(access_token), params={"pageSize": 50}, timeout=15)
    if resp.status_code != 200:
        return {"protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}
    protein = 0.0
    fat = 0.0
    carbs = 0.0
    for p in resp.json().get("dataPoints", []):
        nl = p.get("nutritionLog", {})
        civ = nl.get("interval", {}).get("civilStartTime", {}).get("date", {})
        entry_date = f"{civ.get('year')}-{civ.get('month'):02d}-{civ.get('day'):02d}"
        if entry_date != date_str:
            continue
        for n in nl.get("nutrients", []):
            if n.get("nutrient") == "PROTEIN":
                protein += float(n.get("quantity", {}).get("grams", 0))
        tp = nl.get("totalProtein", {})
        if isinstance(tp, dict):
            protein += float(tp.get("grams", 0))
        tf = nl.get("totalFat", {})
        if isinstance(tf, dict):
            fat += float(tf.get("grams", 0))
        tc = nl.get("totalCarbohydrate", {})
        if isinstance(tc, dict):
            carbs += float(tc.get("grams", 0))
    return {"protein_g": round(protein, 1), "fat_g": round(fat, 1), "carbs_g": round(carbs, 1)}


def get_daily_rollup(access_token: str, date_str: str = None) -> dict:
    if date_str:
        dt = date_type.fromisoformat(date_str)
    else:
        dt = date_type.today()
        date_str = dt.isoformat()

    consumed = get_daily_calories_consumed(access_token, dt)
    burned = get_daily_calories_burned(access_token, dt)
    macros = get_daily_macros(access_token, dt)
    pcal = macros["protein_g"] * 4
    fcal = macros["fat_g"] * 9
    ccal = macros["carbs_g"] * 4
    total = pcal + fcal + ccal or 1

    return {
        "date": date_str,
        "calories_consumed": consumed,
        "calories_burned": burned,
        "macros": {
            "protein_g": macros["protein_g"],
            "fat_g": macros["fat_g"],
            "carbs_g": macros["carbs_g"],
            "protein_cal": round(pcal, 1),
            "fat_cal": round(fcal, 1),
            "carbs_cal": round(ccal, 1),
            "protein_pct": round(pcal / total * 100),
            "fat_pct": round(fcal / total * 100),
            "carbs_pct": round(ccal / total * 100),
        },
    }


def get_nutrition_history(access_token: str, date_str: str = None) -> list:
    if not date_str:
        date_str = date_type.today().strftime("%Y-%m-%d")

    url = f"{API_BASE}/users/me/dataTypes/nutrition-log/dataPoints"
    resp = requests.get(url, headers=_headers(access_token), params={"pageSize": 50}, timeout=15)

    if resp.status_code != 200:
        return []

    history = []
    for p in resp.json().get("dataPoints", []):
        nl = p.get("nutritionLog", {})
        civ = nl.get("interval", {}).get("civilStartTime", {}).get("date", {})
        entry_date = f"{civ.get('year')}-{civ.get('month'):02d}-{civ.get('day'):02d}"

        if entry_date != date_str:
            continue

        energy = nl.get("energy", {})
        cal = float(energy.get("kcal", 0)) if isinstance(energy, dict) else (float(energy) if energy else 0.0)

        history.append({
            "name": p.get("name", ""),
            "values": {
                "food_item": {"stringValue": nl.get("foodDisplayName", "Unknown")},
                "calories": {"fp64Value": cal},
                "meal_type": {"stringValue": nl.get("mealType", "MEAL").lower()},
                "protein": {"fp64Value": float(nl.get("totalProtein", {}).get("grams", 0)) if isinstance(nl.get("totalProtein"), dict) else (float(nl.get("totalProtein", 0)) if nl.get("totalProtein") else 0.0)},
                "fat": {"fp64Value": float(nl.get("totalFat", {}).get("grams", 0)) if isinstance(nl.get("totalFat"), dict) else (float(nl.get("totalFat", 0)) if nl.get("totalFat") else 0.0)},
                "carbohydrates": {"fp64Value": float(nl.get("totalCarbohydrate", {}).get("grams", 0)) if isinstance(nl.get("totalCarbohydrate"), dict) else (float(nl.get("totalCarbohydrate", 0)) if nl.get("totalCarbohydrate") else 0.0)},
            }
        })

    return history


def delete_nutrition_entry(access_token: str, data_point_name: str) -> bool:
    url = f"{API_BASE}/users/me/dataTypes/nutrition-log/dataPoints:batchDelete"
    payload = {"names": [data_point_name]}
    resp = requests.post(url, json=payload, headers=_headers(access_token), timeout=15)
    logger.info(f"Delete nutrition entry {resp.status_code}: {resp.text[:300]}")
    return resp.status_code == 200


def get_weekly_trend(access_token: str, end_date: date_type = None) -> list:
    if end_date is None:
        end_date = date_type.today()
    results = []
    for i in range(6, -1, -1):
        dt = end_date - timedelta(days=i)
        consumed = get_daily_calories_consumed(access_token, dt)
        burned = get_daily_calories_burned(access_token, dt)
        net = consumed - burned
        results.append({
            "date": dt.isoformat(),
            "day": dt.strftime("%a"),
            "calories_consumed": consumed,
            "calories_burned": burned,
            "net": net,
        })
    return results
