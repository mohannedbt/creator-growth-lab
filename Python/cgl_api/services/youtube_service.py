import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re
import requests
import isodate

from ..core.config import RAW_DIR, YOUTUBE_API_KEY, ensure_dirs


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeApiError(RuntimeError):
    pass


@dataclass
class YouTubeService:
    api_key: str = YOUTUBE_API_KEY

    def _get(self, endpoint: str, params: Dict) -> Dict:
        if not self.api_key:
            raise YouTubeApiError("Missing YOUTUBE_API_KEY. Put it in .env")

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
            raise YouTubeApiError("Channel not found or no contentDetails returned.")

        self._cache_write(cache_path, data)
        return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def list_playlist_video_ids(
        self, playlist_id: str, n: int, use_cache: bool = True
    ) -> List[str]:
        ensure_dirs()
        cache_path = RAW_DIR / f"{playlist_id}_playlistItems_{n}.json"
        if use_cache:
            cached = self._cache_read(cache_path)
            if cached:
                return [it["contentDetails"]["videoId"] for it in cached.get("items", [])]

        video_ids: List[str] = []
        page_token: Optional[str] = None

        # fetch until we collect n
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

            time.sleep(0.05)  # small politeness

        # cache the first n results (contract: playlist id + n)
        self._cache_write(cache_path, {"items": [{"contentDetails": {"videoId": vid}} for vid in video_ids]})
        return video_ids

    def get_videos_details(self, video_ids: List[str], use_cache: bool = True) -> Dict[str, Dict]:
        """
        Returns dict keyed by video_id with fields:
        title, published_at (datetime), duration_seconds, views, likes, comments
        """
        ensure_dirs()
        if not video_ids:
            return {}

        joined = "_".join(video_ids[:10])
        cache_path = RAW_DIR / f"videos_{len(video_ids)}_{joined}.json"
        if use_cache:
            cached = self._cache_read(cache_path)
            if cached:
                return cached["parsed"]

        parsed: Dict[str, Dict] = {}

        # YouTube videos.list supports up to 50 ids per request
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i : i + 50]
            data = self._get(
                "videos",
                {
                    "part": "snippet,contentDetails,statistics",
                    "id": ",".join(chunk),
                    "maxResults": 50,
                },
            )

            for it in data.get("items", []):
                vid = it["id"]
                snippet = it.get("snippet", {})
                stats = it.get("statistics", {})
                content = it.get("contentDetails", {})

                published_at_str = snippet.get("publishedAt")
                published_at = (
                    datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                    if published_at_str
                    else datetime.now(timezone.utc)
                )

                duration_iso = content.get("duration", "PT0S")
                duration_seconds = int(isodate.parse_duration(duration_iso).total_seconds())

                def _int(x) -> int:
                    try:
                        return int(x)
                    except Exception:
                        return 0

                parsed[vid] = {
                    "video_id": vid,
                    "title": snippet.get("title", ""),
                    "published_at": published_at,
                    "duration_seconds": duration_seconds,
                    "views": _int(stats.get("viewCount")),
                    "likes": _int(stats.get("likeCount")),
                    "comments": _int(stats.get("commentCount")),
                }

            time.sleep(0.05)

        # cache raw + parsed separately for debug convenience
        cache_blob = {
            "video_ids": video_ids,
            "parsed": self._jsonify_parsed(parsed),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._cache_write(cache_path, cache_blob)

        # restore datetimes after cache (cache stores iso strings)
        return self._dejsonify_parsed(cache_blob["parsed"])

    def _jsonify_parsed(self, parsed: Dict[str, Dict]) -> Dict[str, Dict]:
        out = {}
        for vid, row in parsed.items():
            row2 = dict(row)
            if isinstance(row2.get("published_at"), datetime):
                row2["published_at"] = row2["published_at"].isoformat()
            out[vid] = row2
        return out

    def _dejsonify_parsed(self, parsed: Dict[str, Dict]) -> Dict[str, Dict]:
        out = {}
        for vid, row in parsed.items():
            row2 = dict(row)
            pa = row2.get("published_at")
            if isinstance(pa, str):
                row2["published_at"] = datetime.fromisoformat(pa)
            out[vid] = row2
        return out
    import re

    def resolve_channel_id(self, url_or_handle: str) -> str:
        s = url_or_handle.strip()

        # 1) Already a channel id
        if s.startswith("UC") and len(s) >= 10:
            return s

        # 2) Extract handle from URL if present
        # examples:
        #  https://www.youtube.com/@veritasium
        #  @veritasium
        m = re.search(r"@([A-Za-z0-9._-]+)", s)
        if m:
            handle = m.group(1)
            # YouTube Data API: search endpoint can locate channel by query
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
                raise YouTubeApiError(f"Could not resolve handle @{handle} to a channel.")
            return items[0]["snippet"]["channelId"]

        # 3) Fallback: treat as a query (custom name or random url)
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
            raise YouTubeApiError("Could not resolve input to a channel id.")
        return items[0]["snippet"]["channelId"]

