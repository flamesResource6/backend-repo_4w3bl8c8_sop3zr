"""
TriTrack Database Schemas

Each Pydantic model corresponds to a MongoDB collection.
Collection name is the lowercase of the class name.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

# Core user profile
class Profile(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user (email or UUID)")
    name: Optional[str] = Field(None, description="Display name")
    age: int = Field(..., ge=5, le=120)
    sex: Literal["male", "female"]
    height_cm: float = Field(..., gt=0)
    weight_kg: float = Field(..., gt=0)
    activity_level: Literal[
        "sedentary", "light", "moderate", "active", "very_active"
    ] = "sedentary"
    goal: Optional[Literal["lose", "maintain", "gain"]] = None

# Health / Food
class FoodNutrients(BaseModel):
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    fiber_g: float = 0
    sodium_mg: Optional[float] = None
    sugar_g: Optional[float] = None
    calcium_mg: Optional[float] = None
    iron_mg: Optional[float] = None

class FoodEntry(BaseModel):
    user_id: str
    source: Literal["text", "search", "barcode", "photo"] = "text"
    query: str = Field("", description="Raw user input or barcode")
    description: str = Field("", description="Human readable food name")
    nutrients: FoodNutrients
    eaten_at: Optional[datetime] = None
    meal: Optional[Literal["breakfast", "lunch", "dinner", "snack"]] = None

# Education
class ExamPlanItem(BaseModel):
    topic: str
    hours: float
    due_date: Optional[datetime] = None
    repetitions: List[int] = Field(default_factory=list, description="Spaced repetition days")
    status: Literal["pending", "in_progress", "done"] = "pending"

class ExamPlan(BaseModel):
    user_id: str
    exam: str
    weeks: int = 8
    items: List[ExamPlanItem]

class StudyProgress(BaseModel):
    user_id: str
    exam: str
    topic: str
    status: Literal["pending", "in_progress", "done"] = "in_progress"
    score: Optional[float] = None

class MockTest(BaseModel):
    user_id: str
    exam: str
    title: str
    score: Optional[float] = None
    taken_at: Optional[datetime] = None

# Money
class Hustle(BaseModel):
    user_id: str
    name: str
    type: Literal["SaaS", "Instagram", "Gig", "Other"] = "Other"

class Transaction(BaseModel):
    user_id: str
    hustle_name: str
    amount: float
    type: Literal["income", "expense"]
    category: Optional[str] = None
    note: Optional[str] = None
    occurred_at: Optional[datetime] = None
