from fastapi import APIRouter, Query
from ..services.youtube_service import YouTubeService

router = APIRouter(prefix="/resolve", tags=["resolve"])
yt = YouTubeService()

@router.get("/channel-id")
def resolve_channel_id(url_or_handle: str = Query(..., description="Channel URL, @handle, or custom name")):
    """
    Accepts:
      - UC... channel id (returns it)
      - @handle
      - full youtube url (channel/@handle/custom)
    Returns channel_id
    """
    return {"channel_id": yt.resolve_channel_id(url_or_handle)}
