from pydantic import BaseModel, Field

class ChannelAnalysisRequest(BaseModel):
    channel_id: str = Field(..., min_length=3, description="YouTube channel id (UC...)")
    n_videos: int = Field(default=50, ge=1, le=200)
    baseline_window: int = Field(default=20, ge=5, le=100)
