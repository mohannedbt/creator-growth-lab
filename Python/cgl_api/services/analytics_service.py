import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .youtube_service import YouTubeService
from .feature_service import FeatureService
from .topic_service import TopicService
from .perception_service import PerceptionService

from ..core.config import ensure_dirs, RESULTS_DIR
from ..schemas.request import ChannelAnalysisRequest
from ..schemas.response import (
    AnalyticsResponse,
    MetaInfo,
    Kpis,
    TrendPoint,
)

# Reuse service instances across requests (important on Windows)
_TOPIC_SERVICE = None
_PERCEPTION_SERVICE = None


@dataclass
class AnalyticsService:

    @staticmethod
    def _to_dt(x):
        if isinstance(x, datetime):
            return x
        return datetime.fromisoformat(x.replace("Z", "+00:00"))

    def run_channel_analysis(self, req: ChannelAnalysisRequest) -> AnalyticsResponse:
        ensure_dirs()
        now = datetime.now(timezone.utc)

        yt = YouTubeService()

        # ✅ channel identity
        channel_identity = yt.get_channel_identity(req.channel_id)

        # ✅ fetch videos
        uploads_pid = yt.get_uploads_playlist_id(req.channel_id)
        video_ids = yt.list_playlist_video_ids(uploads_pid, req.n_videos)
        details = yt.get_videos_details(video_ids)
        rows = list(details.values())

        # ---- views/day with capped window ----
        for r in rows:
            r["published_at"] = self._to_dt(r["published_at"])
            age_days = max((now - r["published_at"]).days, 1)
            window = max(1, min(age_days, 14))
            r["views_per_day"] = r["views"] / window

        # ---- features ----
        fs = FeatureService()
        for r in rows:
            r.update(fs.numeric_rates(r["views"], r["likes"], r["comments"]))
            r.update(fs.title_features(r["title"]))
            r.update(fs.time_features(r["published_at"]))

        rows_sorted = sorted(rows, key=lambda x: x["published_at"], reverse=True)

        # ---- baseline (median views/day in baseline window) ----
        baseline_window = rows_sorted[: req.baseline_window]
        vpd_sorted = sorted(r["views_per_day"] for r in baseline_window)
        baseline = vpd_sorted[len(vpd_sorted) // 2] if vpd_sorted else 1.0

        for r in rows_sorted:
            r["relative_performance"] = r["views_per_day"] / baseline

        eng_rates = [r["engagement_rate"] for r in rows_sorted] or [0.0]
        rel_perf = [r["relative_performance"] for r in rows_sorted] or [1.0]

        kpis = Kpis(
            videos_analyzed=len(rows_sorted),
            baseline_views_per_day=float(baseline),
            median_relative_performance=float(sorted(rel_perf)[len(rel_perf) // 2]),
            avg_engagement_rate=float(sum(eng_rates) / len(eng_rates)),
        )

        trends: List[TrendPoint] = [
            TrendPoint(
                published_at=r["published_at"],
                views=int(r["views"]),
                views_per_day=float(round(r["views_per_day"], 3)),
                relative_performance=float(round(r["relative_performance"], 3)),
            )
            for r in rows_sorted[:30]
        ]

        # ---- Topic analysis + Perception signals (reused singletons) ----
        global _TOPIC_SERVICE, _PERCEPTION_SERVICE
        if _TOPIC_SERVICE is None:
            _TOPIC_SERVICE = TopicService()
        if _PERCEPTION_SERVICE is None:
            _PERCEPTION_SERVICE = PerceptionService()

        topic_analysis = _TOPIC_SERVICE.analyze(rows_sorted)
        perception_signals = _PERCEPTION_SERVICE.analyze(rows_sorted)
        print(f"Perception signals: {perception_signals}")

        resp = AnalyticsResponse(
            meta=MetaInfo(
                channel_id=req.channel_id,
                n_videos=req.n_videos,
                baseline_window=req.baseline_window,
                generated_at=now,
            ),
            channel=channel_identity,
            kpis=kpis,
            trends=trends,

            # ✅ ModelService removed for now (keep schema satisfied)
            recommendations=[],
            warnings=[],

            topics=topic_analysis.topics,
            topic_assignments=topic_analysis.assignments,
            topic_insights=topic_analysis.insights,
            perception_signals=perception_signals,
        )

        self._save_result(resp)
        return resp

    def _save_result(self, resp: AnalyticsResponse) -> Path:
        ts = resp.meta.generated_at.strftime("%Y%m%dT%H%M%SZ")
        out = RESULTS_DIR / f"{resp.meta.channel_id}_{ts}.json"
        out.write_text(
            json.dumps(resp.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return out
