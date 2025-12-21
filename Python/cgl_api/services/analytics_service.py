import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List
from .youtube_service import YouTubeService

from ..core.config import ensure_dirs, RESULTS_DIR
from ..schemas.request import ChannelAnalysisRequest
from ..schemas.response import (
    AnalyticsResponse, MetaInfo, Kpis, TrendPoint, DriverEffect, Recommendation
)

@dataclass
class AnalyticsService:
    """
    Orchestrates the pipeline.
    For Step A: returns deterministic dummy data that matches the contract.
    Later: will call youtube_service, feature_service, model_service, recommendation.
    """

    def run_channel_analysis(self, req: ChannelAnalysisRequest) -> AnalyticsResponse:
        ensure_dirs()
        now = datetime.now(timezone.utc)

        #---- Fetch video data from YouTube ----

        yt = YouTubeService()
        uploads_pid = yt.get_uploads_playlist_id(req.channel_id)
        video_ids = yt.list_playlist_video_ids(uploads_pid, req.n_videos)
        details = yt.get_videos_details(video_ids)

        now = datetime.now(timezone.utc)
        # build views_per_day + relative_performance later (baseline not computed yet)
        # For Step B: we compute views_per_day using age_days and a temporary baseline (median later)
        rows = list(details.values())

        # compute views_per_day
        for r in rows:
            age_days = max((now - r["published_at"]).days, 1)
            r["views_per_day"] = r["views"] / age_days

        # baseline (median) for MVP
        vpd_sorted = sorted([r["views_per_day"] for r in rows if r["views_per_day"] is not None])
        baseline = vpd_sorted[len(vpd_sorted)//2] if vpd_sorted else 1.0

        trends = []
        for r in rows[: min(len(rows), 30)]:  # limit payload size for UI
            rel = (r["views_per_day"] / baseline) if baseline else 0.0
            trends.append(
                TrendPoint(
                    published_at=r["published_at"],
                    views=r["views"],
                    views_per_day=round(r["views_per_day"], 3),
                    relative_performance=round(rel, 3),
                )
            )


        # ---- Dummy drivers ----
        drivers = [
            DriverEffect(
                feature="title_word_count",
                effect_percent=-9.0,
                unit_change="-5 words",
                direction="decrease",
            ),
            DriverEffect(
                feature="has_number",
                effect_percent=6.0,
                unit_change="+1 (false→true)",
                direction="increase",
            ),
        ]

        # ---- Dummy recommendations ----
        recs = [
            Recommendation(
                title="Shorten titles slightly",
                detail="For your channel, shorter titles are associated with higher relative performance.",
                expected_impact_percent=9.0,
                confidence="medium",
            ),
            Recommendation(
                title="Use numbers in titles occasionally",
                detail="Titles containing numbers are associated with improved relative performance in your recent uploads.",
                expected_impact_percent=6.0,
                confidence="low",
            ),
        ]

        # ---- Dummy KPIs ----
        kpis = Kpis(
            videos_analyzed=len(rows),
            baseline_views_per_day=float(baseline),
            median_relative_performance=1.0,  # temporary; we’ll compute properly in Step C
            avg_engagement_rate=0.0,          # temporary; next step
        )


        resp = AnalyticsResponse(
            meta=MetaInfo(
                channel_id=req.channel_id,
                n_videos=req.n_videos,
                baseline_window=req.baseline_window,
                generated_at=now,
            ),
            kpis=kpis,
            trends=trends,
            drivers=drivers,
            recommendations=recs,
            warnings=[],
        )

        self._save_result(resp)
        return resp

    def _save_result(self, resp: AnalyticsResponse) -> Path:
        # Save the response as a JSON file in RESULTS_DIR
        ts = resp.meta.generated_at.strftime("%Y%m%dT%H%M%SZ")
        out_path = RESULTS_DIR / f"{resp.meta.channel_id}_{ts}.json"
        out_path.write_text(json.dumps(resp.model_dump(mode="json"), indent=2), encoding="utf-8")
        return out_path
