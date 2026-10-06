from typing import List, Optional

from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    message: str = Field(..., min_length=1, examples=["성수동 파스타 맛집 알려줘"])
    limit: int = Field(5, ge=1, le=10)


class ParsedQuery(BaseModel):
    area: Optional[str] = None
    food: Optional[str] = None
    conditions: List[str] = Field(default_factory=list)
    sort_intent: str = "balanced"


class RestaurantItem(BaseModel):
    name: str
    category: Optional[str] = None
    address: Optional[str] = None
    roadAddress: Optional[str] = None
    phone: Optional[str] = None
    link: Optional[str] = None
    mapUrl: Optional[str] = None
    distanceMeters: Optional[float] = None
    score: float
    reason: str


class RecommendResponse(BaseModel):
    query: str
    area: Optional[str]
    food: Optional[str]
    items: List[RestaurantItem]
    followUpSuggestions: List[str]
    message: str
    degraded: bool = False
    warnings: List[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str
    code: str
