import os
import numpy as np
import hdbscan
from collections import defaultdict
from statistics import median, pstdev
from typing import List, Dict
from tabulate import tabulate
from sklearn.metrics.pairwise import cosine_distances

from ..schemas.response import TopicAssignment, TopicSummary, TopicAnalysis
from .topic_labeler import HybridTopicLabeler


class TopicService:
    """
    Discovers content topics using sentence embeddings + clustering,
    then evaluates topic-level performance.
    """

    def __init__(self):
        self._model = None  # lazy-load
        self.labeler = HybridTopicLabeler(
            gemini_api_key=os.getenv("GEMINI_API_KEY")
        )

    # -------------------------------
    # Lazy model loader
    # -------------------------------
    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except Exception as ex:
                raise RuntimeError(
                    "Failed to import sentence-transformers (topic modeling disabled). "
                    "Fix by recreating a venv and installing Python/cgl_api/requirements.txt. "
                    f"Original error: {type(ex).__name__}: {ex}"
                )

            # fast + good enough
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

    # -------------------------------
    # Public API
    # -------------------------------
    def analyze(self, rows: List[Dict]) -> TopicAnalysis:
        if not rows:
            return TopicAnalysis(assignments=[], topics=[], insights=[])

        titles = [r["title"] for r in rows]

        try:
            embeddings = self._embed(titles)
            topic_ids = self._cluster(embeddings)

            labels = self._compute_labels(rows, topic_ids, embeddings)
            self._display_clusters(titles, topic_ids, labels)

            assignments = self._build_assignments(rows, topic_ids, labels)
            topics = self._build_topic_summaries(rows, topic_ids, labels)
            insights = self._build_insights(topics)

            return TopicAnalysis(
                assignments=assignments,
                topics=topics,
                insights=insights,
            )
        except Exception as ex:
            # Graceful degradation: keep the rest of the analytics pipeline working
            # even when local ML deps are broken.
            return TopicAnalysis(
                assignments=[],
                topics=[],
                insights=[
                    "Topic modeling disabled due to a local ML dependency error. "
                    f"Details: {type(ex).__name__}: {ex}"
                ],
            )

    # -------------------------------
    # Embedding
    # -------------------------------
    def _embed(self, texts: List[str]) -> np.ndarray:
        model = self._get_model()
        return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    # -------------------------------
    # Clustering
    # -------------------------------
    def _cluster(self, embeddings: np.ndarray) -> List[int]:
        cosine_dist_matrix = cosine_distances(embeddings).astype(np.float64)

        clusterer = hdbscan.HDBSCAN(
            min_samples=1,
            min_cluster_size=3,
            metric="precomputed"
        )
        raw_labels = clusterer.fit_predict(cosine_dist_matrix)

        # Convert noise (-1) to singleton topics
        next_topic_id = max(raw_labels) + 1 if max(raw_labels) >= 0 else 0
        resolved = []
        for lbl in raw_labels:
            if lbl == -1:
                resolved.append(next_topic_id)
                next_topic_id += 1
            else:
                resolved.append(int(lbl))

        # Remap to sequential ids
        unique = sorted(set(resolved))
        id_map = {old: i for i, old in enumerate(unique)}
        return [id_map[x] for x in resolved]

    # -------------------------------
    # Label computation (ONCE)
    # -------------------------------
    def _compute_labels(
        self,
        rows: List[Dict],
        topic_ids: List[int],
        embeddings: np.ndarray
    ) -> Dict[int, str]:
        topic_titles = defaultdict(list)
        topic_embs = defaultdict(list)

        for r, tid, emb in zip(rows, topic_ids, embeddings):
            topic_titles[tid].append(r["title"])
            topic_embs[tid].append(emb)

        labels: Dict[int, str] = {}
        for tid in topic_titles:
            titles = topic_titles[tid]
            embs = np.vstack(topic_embs[tid])
            labels[tid] = self._label_topic(titles, embs)

        return labels

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
                topic_label=labels.get(tid, "Misc"),
            )
            for r, tid in zip(rows, topic_ids)
        ]

    # -----------------------------------------------------------------
    # Topic scoring (used for sorting)
    # -----------------------------------------------------------------
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
            items = sorted(items, key=lambda r: r["published_at"])

            rel = [r["relative_performance"] for r in items]
            vpd = [r["views_per_day"] for r in items]

            n = len(items)
            k = min(3, max(1, n // 2))

            older = rel[:k]
            recent = rel[-k:]

            older_avg = float(np.mean(older))
            recent_avg = float(np.mean(recent))
            momentum = recent_avg - older_avg

            x = np.arange(n)
            y = np.array(rel)
            denom = np.sum((x - x.mean()) ** 2)
            slope = float(np.sum((x - x.mean()) * (y - y.mean())) / denom) if denom > 0 else 0.0

            volatility = float(pstdev(rel)) if n > 1 else 0.0
            fatigue = momentum < -0.15 and n >= 4

            confidence = float(min(1.0, n / 10) * np.exp(-volatility))

            hit_rate = sum(1 for v in rel if v >= 1.0) / n
            best_recent = max(recent) if recent else rel[-1]
            worst_recent = min(recent) if recent else rel[-1]

            summary = TopicSummary(
                topic_id=tid,
                label=labels.get(tid, "Misc"),
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
                best_recent=float(best_recent),
                worst_recent=float(worst_recent),
            )

            verdict = self._build_verdict(summary)
            summary.verdict = verdict["verdict"]
            summary.verdict_confidence = verdict["verdict_confidence"]

            summaries.append(summary)

        # Optional: keep singletons, or group them into one misc bucket
        return sorted(summaries, key=self._topic_score, reverse=True)

    # -------------------------------
    # Debug view
    # -------------------------------
    def _display_clusters(self, titles, topic_ids, labels):
        table_data = []
        for title, tid in zip(titles, topic_ids):
            table_data.append([title, tid, labels.get(tid, "Misc")])
        print("\nClustered Topics:\n")
        print(tabulate(table_data, headers=["Title", "Topic ID", "Label"], tablefmt="pretty"))

    # -------------------------------
    # Labeling (Representative + LLM general label)
    # -------------------------------
    def _label_topic(self, titles: List[str], embeddings: np.ndarray) -> str:
        if not titles:
            return "Misc"

        # Representative title (centroid)
        centroid = embeddings.mean(axis=0)
        sims = embeddings @ centroid
        rep = titles[int(np.argmax(sims))]

        # General label (cached LLM; falls back internally)
        general = self.labeler.label(titles)

        # Keep it readable
        return f"{general} — e.g. {rep}"

    # -------------------------------
    # Insights
    # -------------------------------
    def _build_insights(self, topics: List[TopicSummary]) -> List[str]:
        if not topics:
            return []

        insights = []

        rising = [t for t in topics if t.verdict == "Rising Bet"]
        fading = [t for t in topics if t.verdict == "Fading Idea"]
        reliable = [t for t in topics if t.verdict in ("Reliable Performer", "Reliable but Capped")]
        risky = [t for t in topics if t.verdict == "High-Risk / High-Reward"]
        unproven = [t for t in topics if t.verdict == "Unproven Experiment"]

        for t in rising[:2]:
            insights.append(
                f"Topic '{t.label}' is a Rising Bet. Recent uploads outperform older ones; lean in carefully."
            )

        for t in fading[:2]:
            insights.append(
                f"Topic '{t.label}' shows fatigue. Consider pausing repetition or refreshing the angle."
            )

        if reliable:
            top = reliable[0]
            insights.append(
                f"Topic '{top.label}' is a reliable stabilizer—use it between experiments."
            )

        if risky:
            t = risky[0]
            insights.append(
                f"Topic '{t.label}' is high-risk/high-reward. Use sparingly if you need consistency."
            )

        if len(unproven) >= 3:
            insights.append(
                "You’re running several unproven experiments—mix in reliable topics to stabilize performance."
            )

        return insights

    # -------------------------------
    # Verdict rules
    # -------------------------------
    def _build_verdict(self, t: TopicSummary) -> dict:
        if t.n_videos < 3:
            verdict = "Unproven Experiment"
            confidence = "low"
        elif t.fatigue:
            verdict = "Fading Idea"
            confidence = "high"
        elif t.volatility < 0.35 and t.hit_rate >= 0.6:
            verdict = "Reliable Performer" if t.avg_relative_performance >= 1.1 else "Reliable but Capped"
            confidence = "high"
        elif t.volatility >= 0.5 and t.avg_relative_performance >= 1.2:
            verdict = "High-Risk / High-Reward"
            confidence = "medium"
        elif t.momentum > 0.15:
            verdict = "Rising Bet"
            confidence = "medium"
        elif t.momentum < -0.15:
            verdict = "Declining"
            confidence = "medium"
        else:
            verdict = "Neutral"
            confidence = "low"

        return {"verdict": verdict, "verdict_confidence": confidence}
