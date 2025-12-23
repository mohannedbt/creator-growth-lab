import numpy as np
import hdbscan
from collections import defaultdict
from statistics import median, pstdev
from typing import List, Dict
from sentence_transformers import SentenceTransformer

from ..schemas.response import (
    TopicAssignment,
    TopicSummary,
    TopicAnalysis,
)


class TopicService:
    """
    Discovers content topics using sentence embeddings + clustering,
    then evaluates topic-level performance.
    """

    def __init__(self):
        # Loaded once per process (important for performance)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    # -------------------------------
    # Public API
    # -------------------------------
    def analyze(self, rows: List[Dict]) -> TopicAnalysis:
        if not rows:
            return TopicAnalysis(assignments=[], topics=[], insights=[])

        titles = [r["title"] for r in rows]

        embeddings = self._embed(titles)
        topic_ids = self._cluster(embeddings)

        # 🔑 single source of truth for labels
        labels = self._compute_labels(rows, topic_ids)

        assignments = self._build_assignments(rows, topic_ids, labels)
        topics = self._build_topic_summaries(rows, topic_ids, labels)
        insights = self._build_insights(topics)

        return TopicAnalysis(
            assignments=assignments,
            topics=topics,
            insights=insights,
        )

    # -------------------------------
    # Embedding
    # -------------------------------
    def _embed(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    # -------------------------------
    # Clustering
    # -------------------------------
    def _cluster(self, embeddings: np.ndarray) -> List[int]:
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=3,
            min_samples=2,
            metric="euclidean",
        )

        raw_labels = clusterer.fit_predict(embeddings)

        # Convert noise (-1) to unique singleton topics
        next_topic_id = max(raw_labels) + 1 if max(raw_labels) >= 0 else 0
        resolved = []

        for lbl in raw_labels:
            if lbl == -1:
                resolved.append(next_topic_id)
                next_topic_id += 1
            else:
                resolved.append(int(lbl))

        # Remap topic IDs to sequential [0, 1, 2, ...]
        unique = sorted(set(resolved))
        id_map = {old: i for i, old in enumerate(unique)}

        return [id_map[x] for x in resolved]

    # -------------------------------
    # Topic label computation (ONCE)
    # -------------------------------
    def _compute_labels(
        self,
        rows: List[Dict],
        topic_ids: List[int],
    ) -> Dict[int, str]:
        topic_titles = defaultdict(list)

        for r, tid in zip(rows, topic_ids):
            topic_titles[tid].append(r["title"])

        return {
            tid: self._label_topic(titles)
            for tid, titles in topic_titles.items()
        }

    # -------------------------------
    # Assignments
    # -------------------------------
    def _build_assignments(
        self,
        rows: List[Dict],
        topic_ids: List[int],
        labels: Dict[int, str],
    ) -> List[TopicAssignment]:
        return [
            TopicAssignment(
                video_id=r["video_id"],
                topic_id=tid,
                topic_label=labels[tid],
            )
            for r, tid in zip(rows, topic_ids)
        ]
    # -------------------------------
    # Topic scoring 
    # -------------------------------
    @staticmethod
    def _topic_score(t: TopicSummary) -> float:
        recency_boost = 1.0 if t.momentum > 0 else 0.0
        stability = np.log1p(t.n_videos)
        return (0.6 * t.momentum) + (0.3 * recency_boost) + (0.1 * stability)

    # -------------------------------
    # Topic summaries
    # -------------------------------
    def _build_topic_summaries(
        self,
        rows: List[Dict],
        topic_ids: List[int],
        labels: Dict[int, str],
    ) -> List[TopicSummary]:
        grouped = defaultdict(list)

        for r, tid in zip(rows, topic_ids):
            grouped[tid].append(r)

        summaries: List[TopicSummary] = []

        for tid, items in grouped.items():
            # sort by time (old → recent)
            items = sorted(items, key=lambda r: r["published_at"])

            rel = [r["relative_performance"] for r in items]
            vpd = [r["views_per_day"] for r in items]

            n = len(items)
            k = min(3, max(1, n // 2))  # adaptive window

            older = rel[:k]
            recent = rel[-k:]

            older_avg = float(np.mean(older))
            recent_avg = float(np.mean(recent))
            momentum = recent_avg - older_avg

            # trend slope (simple linear regression)
            x = np.arange(n)
            y = np.array(rel)
            x_mean = x.mean()
            y_mean = y.mean()
            denom = np.sum((x - x_mean) ** 2)
            slope = float(np.sum((x - x_mean) * (y - y_mean)) / denom) if denom > 0 else 0.0

            volatility = float(pstdev(rel)) if n > 1 else 0.0

            # fatigue rule (simple & explainable)
            fatigue = momentum < -0.15 and n >= 4

            # confidence: more data + lower volatility
            confidence = min(1.0, n / 10) * np.exp(-volatility)
            confidence = float(confidence)

            # 🧠 HUMAN-READABLE PERFORMANCE SIGNALS
            hits = [r for r in rel if r >= 1.0]
            hit_rate = len(hits) / n

            best_recent = max(recent) if recent else rel[-1]
            worst_recent = min(recent) if recent else rel[-1]



            summaries.append(
                TopicSummary(
                    topic_id=tid,
                    label=labels[tid],
                    n_videos=n,

                    avg_relative_performance=float(np.mean(rel)),
                    median_relative_performance=float(median(rel)),
                    avg_views_per_day=float(np.mean(vpd)),
                    volatility=volatility,

                    recent_avg_relative_performance=recent_avg,
                    older_avg_relative_performance=older_avg,
                    momentum=momentum,
                    trend_slope=slope,
                    fatigue=fatigue,
                    confidence=confidence,

                    top_examples=[r["title"] for r in items[:3]],
                    hit_rate=hit_rate,
                    best_recent=best_recent,
                    worst_recent=worst_recent
                )
            )
        real_topics = [t for t in summaries if t.n_videos >= 2]
        singletons = [t for t in summaries if t.n_videos < 2]
        if singletons:
            misc_rel = []
            misc_vpd = []
            examples = []

            for t in singletons:
                misc_rel.append(t.avg_relative_performance)
                misc_vpd.append(t.avg_views_per_day)
                examples.extend(t.top_examples)

            real_topics.append(
                TopicSummary(
                    topic_id=-1,
                    label="Misc / One-offs",
                    n_videos=len(singletons),
                    avg_relative_performance=float(np.mean(misc_rel)),
                    median_relative_performance=float(median(misc_rel)),
                    avg_views_per_day=float(np.mean(misc_vpd)),
                    volatility=float(pstdev(misc_rel)) if len(misc_rel) > 1 else 0.0,
                    recent_avg_relative_performance=0.0,
                    older_avg_relative_performance=0.0,
                    momentum=0.0,
                    trend_slope=0.0,
                    fatigue=False,
                    confidence=0.3,
                    hit_rate=0.0,
                    best_recent=max(misc_rel),
                    worst_recent=min(misc_rel),
                    top_examples=examples[:5],
                )
            )

        return sorted(
            real_topics,
            key=self._topic_score,
            reverse=True,
        )


    # -------------------------------
    # Topic labeling heuristic (v1)
    # -------------------------------
    def _label_topic(self, titles: List[str]) -> str:
        if not titles:
            return "Misc"

        # Shortest informative title as label (simple but effective)
        return min(titles, key=len)[:60]

    # -------------------------------
    # Insights
    # -------------------------------
    def _build_insights(self, topics: List[TopicSummary]) -> List[str]:
        if not topics:
            return []

        insights = []

        improving = [t for t in topics if t.momentum > 0.15]
        fatigued = [t for t in topics if t.fatigue]

        if improving:
            t = improving[0]
            insights.append(
                f"Topic '{t.label}' is improving lately "
                f"(+{t.momentum:.2f} vs older videos)."
            )

        if fatigued:
            t = fatigued[0]
            insights.append(
                f"Topic '{t.label}' shows signs of fatigue "
                f"({t.momentum:.2f} decline recently)."
            )

        stable = [t for t in topics if abs(t.momentum) < 0.05 and t.volatility < 0.3]
        if stable:
            insights.append(
                f"{len(stable)} topic(s) are stable and predictable."
            )

        return insights

