import os
from datetime import datetime
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import db, create_document, get_documents
from schemas import Profile, FoodEntry, FoodNutrients, ExamPlan, ExamPlanItem, StudyProgress, MockTest, Hustle, Transaction

app = FastAPI(title="TriTrack API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------- Utilities -------------------
activity_factors = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

def calc_bmi(height_cm: float, weight_kg: float) -> float:
    h_m = height_cm / 100
    return round(weight_kg / (h_m * h_m), 2)


def calc_bmr_mifflin(sex: str, height_cm: float, weight_kg: float, age: int) -> float:
    if sex == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    return round(bmr, 1)


def calc_tdee(bmr: float, activity_level: str) -> float:
    factor = activity_factors.get(activity_level, 1.2)
    return round(bmr * factor, 1)


def calorie_target(tdee: float, goal: Optional[str]) -> float:
    if goal == "lose":
        return round(tdee - 500, 0)
    if goal == "gain":
        return round(tdee + 300, 0)
    return round(tdee, 0)

# ------------------- Health Endpoints -------------------
class ProfileCreate(Profile):
    pass

class ProfileResponse(BaseModel):
    bmi: float
    bmr: float
    tdee: float
    calorie_target: float

@app.post("/health/profile", response_model=ProfileResponse)
def create_or_update_profile(profile: ProfileCreate):
    """Upsert user profile and return calculated metrics."""
    # Upsert profile
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    prof_dict = profile.model_dump()
    prof_dict["updated_at"] = datetime.utcnow()
    prof_dict["created_at"] = datetime.utcnow()
    db["profile"].update_one({"user_id": profile.user_id}, {"$set": prof_dict}, upsert=True)

    bmi = calc_bmi(profile.height_cm, profile.weight_kg)
    bmr = calc_bmr_mifflin(profile.sex, profile.height_cm, profile.weight_kg, profile.age)
    tdee = calc_tdee(bmr, profile.activity_level)
    target = calorie_target(tdee, profile.goal)

    return ProfileResponse(bmi=bmi, bmr=bmr, tdee=tdee, calorie_target=target)


class FoodTextRequest(BaseModel):
    user_id: str
    input: str
    source: Literal["text", "search", "barcode", "photo"] = "text"

class FoodSearchResponse(BaseModel):
    items: List[FoodEntry]

@app.post("/health/food/parse", response_model=FoodEntry)
def parse_food(request: FoodTextRequest):
    """A lightweight heuristic food parser (no external API)."""
    text = request.input.lower()
    # Basic heuristics for demo
    db_items = {
        "banana": FoodNutrients(calories=105, carbs_g=27, protein_g=1.3, fat_g=0.3, fiber_g=3.1, potassium_mg=422 if False else None),
        "egg": FoodNutrients(calories=78, protein_g=6, fat_g=5, carbs_g=0.6),
        "rice": FoodNutrients(calories=206, carbs_g=45, protein_g=4.3, fat_g=0.4),
        "chicken": FoodNutrients(calories=165, protein_g=31, fat_g=3.6),
        "milk": FoodNutrients(calories=103, protein_g=8, carbs_g=12, fat_g=2.4, calcium_mg=300),
        "apple": FoodNutrients(calories=95, carbs_g=25, fiber_g=4.4, protein_g=0.5, fat_g=0.3)
    }
    chosen_key = None
    for k in db_items.keys():
        if k in text:
            chosen_key = k
            break

    nutrients = db_items.get(chosen_key, FoodNutrients(calories=150, carbs_g=20, protein_g=5, fat_g=5, fiber_g=2))
    entry = FoodEntry(
        user_id=request.user_id,
        source=request.source,
        query=request.input,
        description=chosen_key or "food item",
        nutrients=nutrients,
        eaten_at=datetime.utcnow()
    )
    create_document("foodentry", entry)
    return entry


@app.get("/health/food/logs", response_model=List[FoodEntry])
def get_food_logs(user_id: str = Query(...)):
    docs = get_documents("foodentry", {"user_id": user_id}, limit=100)
    # Convert Mongo types to Pydantic
    results: List[FoodEntry] = []
    for d in docs:
        try:
            d.pop("_id", None)
            results.append(FoodEntry(**d))
        except Exception:
            continue
    return results

# ------------------- Education Endpoints -------------------
class PlanRequest(BaseModel):
    user_id: str
    exam: str
    hours_per_day: float = 2
    weeks: int = 8

@app.post("/education/plan", response_model=ExamPlan)
def generate_study_plan(req: PlanRequest):
    topics_by_exam = {
        "UPSC": ["Polity", "History", "Geography", "Economy", "Environment", "Science"],
        "SSC": ["Quant", "Reasoning", "English", "GK"],
        "NEET": ["Physics", "Chemistry", "Biology"],
        "GRE": ["Quant", "Verbal", "AWA"],
    }
    topics = topics_by_exam.get(req.exam.upper(), ["Core Concepts", "Practice", "Revision"])
    hours_total = req.hours_per_day * 7 * req.weeks
    per_topic = max(hours_total / len(topics), 1)
    items = [ExamPlanItem(topic=t, hours=round(per_topic, 1), repetitions=[1,3,7,14]) for t in topics]
    plan = ExamPlan(user_id=req.user_id, exam=req.exam.upper(), weeks=req.weeks, items=items)
    create_document("examplan", plan)
    return plan


@app.post("/education/progress", response_model=StudyProgress)
def update_progress(p: StudyProgress):
    create_document("studyprogress", p)
    return p


@app.post("/education/mock", response_model=MockTest)
def add_mock_test(m: MockTest):
    create_document("mocktest", m)
    return m


@app.get("/education/progress", response_model=List[StudyProgress])
def list_progress(user_id: str, exam: Optional[str] = None):
    q: Dict[str, Any] = {"user_id": user_id}
    if exam:
        q["exam"] = exam
    docs = get_documents("studyprogress", q, limit=200)
    for d in docs:
        d.pop("_id", None)
    return [StudyProgress(**d) for d in docs]

# ------------------- Money Endpoints -------------------
@app.post("/money/hustle", response_model=Hustle)
def add_hustle(h: Hustle):
    create_document("hustle", h)
    return h


@app.post("/money/tx", response_model=Transaction)
def add_transaction(t: Transaction):
    # Simple auto-category
    if not t.category:
        if t.type == "income":
            t.category = "Revenue"
        else:
            t.category = "General"
    create_document("transaction", t)
    return t


class MoneySummary(BaseModel):
    per_hustle: Dict[str, Dict[str, float]]
    monthly_forecast: Dict[str, float]

@app.get("/money/summary", response_model=MoneySummary)
def money_summary(user_id: str):
    txs = get_documents("transaction", {"user_id": user_id}, limit=1000)
    per_hustle: Dict[str, Dict[str, float]] = {}
    monthly_income = 0.0
    monthly_expense = 0.0
    for tx in txs:
        name = tx.get("hustle_name", "General")
        amt = float(tx.get("amount", 0))
        ttype = tx.get("type", "expense")
        if name not in per_hustle:
            per_hustle[name] = {"income": 0.0, "expense": 0.0, "profit": 0.0}
        if ttype == "income":
            per_hustle[name]["income"] += amt
            monthly_income += amt
        else:
            per_hustle[name]["expense"] += amt
            monthly_expense += amt
        per_hustle[name]["profit"] = per_hustle[name]["income"] - per_hustle[name]["expense"]

    growth_rate = 0.05
    forecast_income = monthly_income * (1 + growth_rate)
    forecast_expense = monthly_expense
    forecast_profit = forecast_income - forecast_expense

    return MoneySummary(
        per_hustle={k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in per_hustle.items()},
        monthly_forecast={
            "income": round(forecast_income, 2),
            "expense": round(forecast_expense, 2),
            "profit": round(forecast_profit, 2),
        },
    )


@app.get("/")
def read_root():
    return {"message": "TriTrack API running"}

@app.get("/test")
def test_database():
    info = {
        "backend": "running",
        "database": "connected" if db is not None else "not_connected",
    }
    try:
        if db is not None:
            info["collections"] = db.list_collection_names()[:10]
    except Exception as e:
        info["error"] = str(e)
    return info

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
