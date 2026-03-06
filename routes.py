import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field, PositiveInt

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import (
    WaitlistEntry,
    User,
    Restaurant,
    PredictedWaitTime,
    get_db,
)
from ai_service import ai_service

router = APIRouter()


class JoinQueueRequest(BaseModel):
    restaurant_id: uuid.UUID = Field(..., description="UUID of the restaurant")
    name: str = Field(..., min_length=1, max_length=100)
    party_size: PositiveInt = Field(..., description="Number of people in the party")
    phone_number: Optional[str] = Field(
        None, description="E.164 formatted phone for SMS fallback"
    )
    device_token: Optional[str] = Field(
        None, description="Push-notification token for the client device"
    )


class JoinQueueResponse(BaseModel):
    queue_id: uuid.UUID
    position: int
    estimated_wait_minutes: Optional[int]
    created_at: datetime


class StatusResponse(BaseModel):
    current_position: int
    estimated_wait_minutes: Optional[int]
    updated_at: datetime
    ai_confidence: Optional[float]


class PredictWaitTimeRequest(BaseModel):
    restaurant_id: uuid.UUID
    party_size: PositiveInt
    current_queue_length: int = Field(..., ge=0)
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    time_of_day: str = Field(
        ..., pattern=r"^\d{2}:\d{2}$", description="HH:MM 24-hour clock"
    )


class PredictWaitTimeResponse(BaseModel):
    predicted_wait_minutes: int
    confidence: float


class ForecastDemandRequest(BaseModel):
    restaurant_id: uuid.UUID
    past_7_days_footfall: List[int] = Field(..., min_length=7, max_length=7)
    local_events: List[str] = Field(default_factory=list)
    weather: str = Field(
        ..., description="Simple weather description, e.g., 'rainy', 'clear'"
    )


class ForecastDemandResponse(BaseModel):
    peak_hour: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    expected_party_increase_percent: int


def _get_restaurant(session: Session, restaurant_id: uuid.UUID) -> Restaurant:
    result = session.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


def _get_user(session: Session, name: str, phone: Optional[str]) -> User:
    stmt = select(User).where(User.email == name)
    result = session.execute(stmt)
    user = result.scalar_one_or_none()
    if user:
        return user
    new_user = User(role="customer", email=name, phone=phone)
    session.add(new_user)
    session.flush()
    return new_user


@router.post(
    "/customers/join",
    response_model=JoinQueueResponse,
    status_code=status.HTTP_201_CREATED,
)
async def join_queue(request: JoinQueueRequest, session: Session = Depends(get_db)):
    restaurant = _get_restaurant(session, request.restaurant_id)
    user = _get_user(session, request.name, request.phone_number)

    result = session.execute(
        select(WaitlistEntry.queue_position)
        .where(WaitlistEntry.restaurant_id == restaurant.id)
        .order_by(WaitlistEntry.queue_position.desc())
        .limit(1)
    )
    max_position = result.scalar_one_or_none() or 0
    new_position = max_position + 1

    entry = WaitlistEntry(
        restaurant_id=restaurant.id,
        user_id=user.id,
        party_size=request.party_size,
        queue_position=new_position,
    )
    session.add(entry)
    session.flush()

    features = {
        "restaurant_id": str(restaurant.id),
        "party_size": request.party_size,
        "current_queue_length": new_position - 1,
        "day_of_week": datetime.utcnow().weekday(),
        "time_of_day": datetime.utcnow().strftime("%H:%M"),
    }
    try:
        ai_result = await ai_service.predict_wait_time(features)
        prediction = PredictedWaitTime(
            restaurant_id=restaurant.id,
            waitlist_entry_id=entry.id,
            predicted_wait=ai_result["predicted_wait_minutes"],
            confidence_score=ai_result["confidence"],
            model_version=restaurant.ai_model_version,
            prediction_factors=None,
        )
        session.add(prediction)
        entry.estimated_wait_minutes = ai_result["predicted_wait_minutes"]
    except Exception:
        entry.estimated_wait_minutes = None

    session.commit()

    return JoinQueueResponse(
        queue_id=entry.id,
        position=entry.queue_position,
        estimated_wait_minutes=entry.estimated_wait_minutes,
        created_at=entry.created_at,
    )


@router.get("/customers/{queue_id}/status", response_model=StatusResponse)
async def get_status(
    queue_id: uuid.UUID = Path(..., description="UUID of the waitlist entry"),
    session: Session = Depends(get_db),
):
    result = session.execute(select(WaitlistEntry).where(WaitlistEntry.id == queue_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    result = session.execute(
        select(WaitlistEntry).where(
            WaitlistEntry.restaurant_id == entry.restaurant_id,
            WaitlistEntry.queue_position <= entry.queue_position,
        )
    )
    current_position = len(result.scalars().all())

    confidence: Optional[float] = None
    if entry.estimated_wait_minutes is None:
        features = {
            "restaurant_id": str(entry.restaurant_id),
            "party_size": entry.party_size,
            "current_queue_length": current_position - 1,
            "day_of_week": datetime.utcnow().weekday(),
            "time_of_day": datetime.utcnow().strftime("%H:%M"),
        }
        try:
            ai_result = await ai_service.predict_wait_time(features)
            entry.estimated_wait_minutes = ai_result["predicted_wait_minutes"]
            confidence = ai_result["confidence"]
            session.commit()
        except Exception:
            entry.estimated_wait_minutes = None
            confidence = None
    else:
        if entry.prediction:
            confidence = entry.prediction.confidence_score

    return StatusResponse(
        current_position=current_position,
        estimated_wait_minutes=entry.estimated_wait_minutes,
        updated_at=datetime.utcnow(),
        ai_confidence=confidence,
    )


@router.post("/ai/predict-wait-time", response_model=PredictWaitTimeResponse)
async def api_predict_wait_time(
    request: PredictWaitTimeRequest, session: Session = Depends(get_db)
):
    _get_restaurant(session, request.restaurant_id)
    features = request.model_dump()
    features.pop("restaurant_id", None)
    ai_result = await ai_service.predict_wait_time(features)
    return PredictWaitTimeResponse(**ai_result)


@router.post("/ai/forecast-demand", response_model=ForecastDemandResponse)
async def api_forecast_demand(
    request: ForecastDemandRequest, session: Session = Depends(get_db)
):
    _get_restaurant(session, request.restaurant_id)
    features = request.model_dump()
    features.pop("restaurant_id", None)
    ai_result = await ai_service.forecast_demand(features)
    return ForecastDemandResponse(**ai_result)
