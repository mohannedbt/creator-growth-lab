import json
import time
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
import isodate

from ..core.config import RAW_DIR, YOUTUBE_API_KEY, ensure_dirs

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeApiError(RuntimeError):
    pass


@dataclass
class YouTubeService:
    api_key: str = YOUTUBE_API_KEY

    # ------------------ LOW LEVEL ------------------

    def _get(self, endpoint: str, params: Dict) -> Dict:
        if not self.api_key:
            raise YouTubeApiError("Missing YOUTUBE_API_KEY")

        params = {**params, "key": self.api_key}
        url = f"{YOUTUBE_API_BASE}/{endpoint}"

        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            raise YouTubeApiError(f"YouTube API error {r.status_code}: {r.text}")

        return r.json()

    def _cache_write(self, path: Path, data: Dict) -> None:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _cache_read(self, path: Path) -> Optional[Dict]:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    # ------------------ CHANNEL ID RESOLUTION ------------------

    def resolve_channel_id(self, url_or_handle: str) -> str:
        s = url_or_handle.strip()

        if s.startswith("UC") and len(s) >= 10:
            return s

        m = re.search(r"@([A-Za-z0-9._-]+)", s)
        if m:
            handle = m.group(1)
            data = self._get(
                "search",
                {
                    "part": "snippet",
                    "q": f"@{handle}",
                    "type": "channel",
                    "maxResults": 1,
                },
            )
            items = data.get("items", [])
            if not items:
                raise YouTubeApiError(f"Could not resolve @{handle}")
            return items[0]["snippet"]["channelId"]

        data = self._get(
            "search",
            {
                "part": "snippet",
                "q": s,
                "type": "channel",
                "maxResults": 1,
            },
        )
        items = data.get("items", [])
        if not items:
            raise YouTubeApiError("Could not resolve input to channel")
        return items[0]["snippet"]["channelId"]

    # ------------------ CHANNEL IDENTITY ------------------

    def get_channel_identity(self, channel_id: str, use_cache: bool = True) -> Dict:
        """
        Returns:
        {
            channel_id,
            title,
            thumbnail_url
        }
        """
        ensure_dirs()
        cache_path = RAW_DIR / f"{channel_id}_identity.json"

        if use_cache:
            cached = self._cache_read(cache_path)
            if cached:
                return cached

        data = self._get(
            "channels",
            {
                "part": "snippet",
                "id": channel_id,
                "maxResults": 1,
            },
        )

        if not data.get("items"):
            raise YouTubeApiError("Channel not found")

        snippet = data["items"][0]["snippet"]
        identity = {
            "channel_id": channel_id,
            "title": snippet.get("title", ""),
            "thumbnail_url": snippet.get("thumbnails", {})
                .get("high", {})
                .get("url", ""),
        }

        self._cache_write(cache_path, identity)
        return identity

    # ------------------ UPLOADS + VIDEOS ------------------

    def get_uploads_playlist_id(self, channel_id: str, use_cache: bool = True) -> str:
        ensure_dirs()
        cache_path = RAW_DIR / f"{channel_id}_channel.json"

        if use_cache:
            cached = self._cache_read(cache_path)
            if cached:
                return cached["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        data = self._get(
            "channels",
            {
                "part": "contentDetails",
                "id": channel_id,
                "maxResults": 1,
            },
        )

        if not data.get("items"):
            raise YouTubeApiError("Channel not found")

        self._cache_write(cache_path, data)
        return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def list_playlist_video_ids(self, playlist_id: str, n: int) -> List[str]:
        video_ids: List[str] = []
        page_token: Optional[str] = None

        while len(video_ids) < n:
            data = self._get(
                "playlistItems",
                {
                    "part": "contentDetails",
                    "playlistId": playlist_id,
                    "maxResults": 50,
                    "pageToken": page_token or "",
                },
            )

            for it in data.get("items", []):
                video_ids.append(it["contentDetails"]["videoId"])
                if len(video_ids) >= n:
                    break

            page_token = data.get("nextPageToken")
            if not page_token:
                break

            time.sleep(0.05)

        return video_ids

    def get_videos_details(self, video_ids: List[str]) -> Dict[str, Dict]:
        parsed: Dict[str, Dict] = {}

        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i : i + 50]
            data = self._get(
                "videos",
                {
                    "part": "snippet,contentDetails,statistics",
                    "id": ",".join(chunk),
                },
            )

            for it in data.get("items", []):
                snippet = it["snippet"]
                stats = it["statistics"]
                content = it["contentDetails"]

                published_at = datetime.fromisoformat(
                    snippet["publishedAt"].replace("Z", "+00:00")
                )

                duration_seconds = int(
                    isodate.parse_duration(content["duration"]).total_seconds()
                )

                parsed[it["id"]] = {
                    "video_id": it["id"],
                    "title": snippet["title"],
                    "published_at": published_at,
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0)),
                    "duration_seconds": duration_seconds,
                }

            time.sleep(0.05)

        return parsed
