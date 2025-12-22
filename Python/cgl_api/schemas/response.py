from datetime import datetime
from typing import List, Literal
from pydantic import BaseModel, Field

class MetaInfo(BaseModel):
    channel_id: str
    n_videos: int
    baseline_window: int
    generated_at: datetime
class ChannelIdentity(BaseModel):
    channel_id: str
    title: str
    thumbnail_url: str

class Kpis(BaseModel):
    videos_analyzed: int
    baseline_views_per_day: float
    median_relative_performance: float
    avg_engagement_rate: float

class TrendPoint(BaseModel):
    published_at: datetime
    views: int
    views_per_day: float
    relative_performance: float

class DriverEffect(BaseModel):
    feature: str
    effect_percent: float
    unit_change: str
    direction: Literal["increase", "decrease"]

class Recommendation(BaseModel):
    title: str
    detail: str
    expected_impact_percent: float | None = None
    confidence: Literal["low", "medium", "high"] = "medium"

class AnalyticsResponse(BaseModel):
    meta: MetaInfo
    kpis: Kpis
    trends: List[TrendPoint] = Field(default_factory=list)
    drivers: List[DriverEffect] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    channel: ChannelIdentity

