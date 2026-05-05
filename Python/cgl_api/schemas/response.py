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

class PerceptionSignal(BaseModel):
    signal: str                  # Human-readable name
    category: str                # Credibility / Clarity / Intent / Context
    tendency: str                # "Often present", "Often absent", "Inconclusive"
    confidence: str              # "low", "medium", "high"
    description: str             # One-sentence explanation


class Recommendation(BaseModel):
    title: str
    detail: str
    expected_impact_percent: float | None = None
    confidence: Literal["low", "medium", "high"] = "medium"


class TopicAssignment(BaseModel):
    video_id: str
    topic_id: int
    topic_label: str


class TopicSummary(BaseModel):
    # identity
    topic_id: int
    label: str
    n_videos: int

    # overall performance
    avg_relative_performance: float
    median_relative_performance: float
    avg_views_per_day: float
    volatility: float

    # 🧠 HUMAN-READABLE PERFORMANCE SIGNALS
    hit_rate: float = 0.0          # % of videos >= baseline
    best_recent: float = 0.0
    worst_recent: float = 0.0
    verdict: str = "Neutral"      # "Strong", "Positive", "Neutral", "Negative", "Avoid"
    verdict_confidence: str = "low"  # "low", "medium", "high"



    # 🆕 temporal intelligence
    recent_avg_relative_performance: float = 0.0
    older_avg_relative_performance: float = 0.0
    momentum: float = 0.0
    trend_slope: float = 0.0
    fatigue: bool = False
    confidence: float = 0.0

    # examples
    top_examples: List[str] = Field(default_factory=list)


class TopicAnalysis(BaseModel):
    assignments: List[TopicAssignment] = Field(default_factory=list)
    topics: List[TopicSummary] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)


class AnalyticsResponse(BaseModel):
    meta: MetaInfo
    channel: ChannelIdentity
    kpis: Kpis
    trends: List[TrendPoint]
    recommendations: List[Recommendation]
    warnings: List[str]
    topics: List[TopicSummary]
    topic_assignments: List[TopicAssignment]
    topic_insights: List[str]
    perception_signals: List[PerceptionSignal]
