import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from datetime import datetime, timezone

from .youtube_service import YouTubeService
from .feature_service import FeatureService

from ..core.config import ensure_dirs, RESULTS_DIR
from ..schemas.request import ChannelAnalysisRequest
from ..schemas.response import (
    AnalyticsResponse, MetaInfo, Kpis, TrendPoint, DriverEffect, Recommendation
)

@dataclass
class AnalyticsService:
    """
    Orchestrates the pipeline.
    Step C: real YouTube data + feature engineering + real KPIs/baseline/relative_performance.
    Drivers/recommendations still dummy until Step D (modeling).
    """
    @staticmethod
    def _to_dt(x):
        if isinstance(x, datetime):
            return x
        if isinstance(x, str):
            # handles "2025-12-21T18:30:00+00:00" and "....Z"
            return datetime.fromisoformat(x.replace("Z", "+00:00"))
        raise TypeError(f"published_at unexpected type: {type(x)}")
    def run_channel_analysis(self, req: ChannelAnalysisRequest) -> AnalyticsResponse:
        ensure_dirs()
        now = datetime.now(timezone.utc)

        # ---- 1) Fetch video data from YouTube (cache-first) ----
        yt = YouTubeService()
        uploads_pid = yt.get_uploads_playlist_id(req.channel_id)
        video_ids = yt.list_playlist_video_ids(uploads_pid, req.n_videos)
        details = yt.get_videos_details(video_ids)

        rows = list(details.values())

        # ---- 2) Compute views_per_day (needs age_days) ----
        for r in rows:
            r["published_at"] = self._to_dt(r["published_at"])
            age_days = max((now - r["published_at"]).days, 1)
            r["views_per_day"] = r["views"] / age_days

        # ---- 3) Feature engineering (title/time + rates) ----
        fs = FeatureService()
        for r in rows:
            r.update(fs.numeric_rates(r["views"], r["likes"], r["comments"]))
            r.update(fs.title_features(r["title"]))
            r.update(fs.time_features(r["published_at"]))

        # ---- 4) Sort videos newest -> oldest (important for baseline window + trends) ----
        rows_sorted = sorted(rows, key=lambda x: x["published_at"], reverse=True)

        # ---- 5) Baseline = median(views_per_day) over last baseline_window videos ----
        window = rows_sorted[: min(req.baseline_window, len(rows_sorted))]
        vpd_window = sorted([r["views_per_day"] for r in window])
        baseline = vpd_window[len(vpd_window) // 2] if vpd_window else 1.0

        # ---- 6) relative_performance for every row ----
        for r in rows_sorted:
            r["relative_performance"] = (r["views_per_day"] / baseline) if baseline else 0.0

        # ---- 7) KPIs: avg engagement + median relative performance ----
        eng_rates = [r["engagement_rate"] for r in rows_sorted]
        rel_perf = [r["relative_performance"] for r in rows_sorted]

        avg_engagement = (sum(eng_rates) / len(eng_rates)) if eng_rates else 0.0

        rel_sorted = sorted(rel_perf)
        if not rel_sorted:
            med_rel = 0.0
        else:
            mid = len(rel_sorted) // 2
            med_rel = rel_sorted[mid] if len(rel_sorted) % 2 == 1 else (rel_sorted[mid - 1] + rel_sorted[mid]) / 2

        kpis = Kpis(
            videos_analyzed=len(rows_sorted),
            baseline_views_per_day=float(baseline),
            median_relative_performance=float(med_rel),
            avg_engagement_rate=float(avg_engagement),
        )

        # ---- 8) Trends (keep payload limited, but date-consistent) ----
        trends: List[TrendPoint] = []
        for r in rows_sorted[: min(len(rows_sorted), 30)]:
            trends.append(
                TrendPoint(
                    published_at=r["published_at"],
                    views=r["views"],
                    views_per_day=round(r["views_per_day"], 3),
                    relative_performance=round(r["relative_performance"], 3),
                )
            )

        # ---- Dummy drivers (until Step D) ----
        drivers = [
            DriverEffect(feature="title_word_count", effect_percent=-9.0, unit_change="-5 words", direction="decrease"),
            DriverEffect(feature="has_number", effect_percent=6.0, unit_change="+1 (false→true)", direction="increase"),
        ]

        # ---- Dummy recommendations (until Step D) ----
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
        ts = resp.meta.generated_at.strftime("%Y%m%dT%H%M%SZ")
        out_path = RESULTS_DIR / f"{resp.meta.channel_id}_{ts}.json"
        out_path.write_text(json.dumps(resp.model_dump(mode="json"), indent=2), encoding="utf-8")
        return out_path
