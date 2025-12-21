from fastapi import APIRouter
from ..schemas.request import ChannelAnalysisRequest
from ..schemas.response import AnalyticsResponse
from ..services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analyze", tags=["analyze"])
service = AnalyticsService()

@router.post("/channel", response_model=AnalyticsResponse)
def analyze_channel(req: ChannelAnalysisRequest):
    return service.run_channel_analysis(req)
