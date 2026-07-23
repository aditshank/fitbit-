from pydantic import BaseModel
from typing import Optional

class NutritionData(BaseModel):
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    food_name: str
    meal_type: str = "meal"
    portion_grams: Optional[float] = None

class DailyRollUp(BaseModel):
    date: str
    calories_consumed: float = 0
    calories_burned: float = 0

class UserSession(BaseModel):
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    access_token: str
    refresh_token: Optional[str] = None
