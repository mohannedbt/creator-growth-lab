from dataclasses import dataclass
from typing import Dict, List, Tuple
import math

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, cross_val_score
from sklearn.preprocessing import StandardScaler


@dataclass
class ModelOutput:
    drivers: List[Dict]
    recommendations: List[Dict]
    warnings: List[str]
    metrics: Dict



class ModelService:
    """
    Trains an interpretable linear model and converts coefficients to user-facing effects.
    We do NOT change Step C output. We only read rows and produce drivers + recs.
    """

    # Feature list (must exist in rows)
    FEATURES = [
        "duration_seconds",
        "title_length_chars",
        "title_word_count",
        "has_number",
        "has_question",
        "has_brackets",
        "caps_ratio",
        "emoji_count",
        "publish_hour",
        "publish_day_of_week",
        "is_weekend",
    ]

    # Unit changes for user-facing explanations
    UNIT_CHANGES: Dict[str, Tuple[float, str]] = {
        "duration_seconds": (60.0, "+60s"),
        "title_length_chars": (-15.0, "-15 chars"),
        "title_word_count": (-5.0, "-5 words"),
        "caps_ratio": (0.10, "+0.10"),
        "emoji_count": (1.0, "+1"),
        "publish_hour": (2.0, "+2 hours"),
        "publish_day_of_week": (1.0, "+1 day"),
        "has_number": (1.0, "+1 (false→true)"),
        "has_question": (1.0, "+1 (false→true)"),
        "has_brackets": (1.0, "+1 (false→true)"),
        "is_weekend": (1.0, "+1 (false→true)"),
    }

    def train_and_explain(self, rows: List[Dict]) -> ModelOutput:
        warnings: List[str] = []
        if len(rows) < 8:
            warnings.append("Too few videos for stable modeling. Driver effects may be unreliable.")

        df = pd.DataFrame(rows)

        # Keep only rows where target exists and is > 0
        if "relative_performance" not in df.columns:
            return ModelOutput(
                drivers=[],
                recommendations=[],
                warnings=["Missing relative_performance; Step C must compute it before Step D."],
                metrics={}
            )

        df = df.dropna(subset=["relative_performance"])
        df = df[df["relative_performance"] > 0]

        if len(df) < 5:
            return ModelOutput(
                drivers=[],
                recommendations=[],
                warnings=warnings + ["Not enough valid rows after filtering (relative_performance <= 0 or missing)."],
                metrics={}
            )

        # Build X, y
        missing = [f for f in self.FEATURES if f not in df.columns]
        if missing:
            return ModelOutput(
                drivers=[],
                recommendations=[],
                warnings=warnings + [f"Missing feature columns: {missing}"],
                metrics={}
            )

        X = df[self.FEATURES].copy()

        # Ensure booleans become 0/1
        for col in ["has_number", "has_question", "has_brackets", "is_weekend"]:
            X[col] = X[col].astype(int)

        # Target: use log(relative_performance) for stability (still derived from Step C)
        y = np.log(df["relative_performance"].astype(float).values)

        if np.allclose(y, y[0]):
            return ModelOutput(
                drivers=[],
                recommendations=[],
                warnings=warnings + ["Target has near-zero variance; cannot learn meaningful drivers."],
                metrics={}
            )

        # Standardize features
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X.values)

        # Model: Ridge (stable, interpretable)
        model = Ridge(alpha=1.0, random_state=42)
        model.fit(Xs, y)

        # CV score (R^2) as a rough reliability indicator
        # For tiny datasets, R^2 can be noisy; we use it just to set confidence.
        k = min(5, len(df))
        cv = KFold(n_splits=k, shuffle=True, random_state=42)
        scores = cross_val_score(model, Xs, y, cv=cv, scoring="r2")
        r2_mean = float(np.mean(scores))
        r2_std = float(np.std(scores))

        # Convert coefficients -> driver effects using unit changes
        coefs = model.coef_
        sigmas = scaler.scale_

        drivers = []
        for i, feat in enumerate(self.FEATURES):
            delta, unit_label = self.UNIT_CHANGES.get(feat, (1.0, "+1"))
            sigma = sigmas[i] if sigmas[i] != 0 else 1.0

            # change in standardized units for that delta
            delta_z = delta / sigma

            # effect on log(relative_performance)
            delta_log = float(coefs[i] * delta_z)

            # convert back to percent effect on relative_performance
            effect_percent = (math.exp(delta_log) - 1.0) * 100.0

            direction = "increase" if effect_percent >= 0 else "decrease"

            drivers.append({
                "feature": feat,
                "effect_percent": round(effect_percent, 2),
                "unit_change": unit_label,
                "direction": direction,
                "abs_effect": abs(effect_percent),
            })

        # rank by absolute effect
        drivers_sorted = sorted(drivers, key=lambda d: d["abs_effect"], reverse=True)
        # remove helper key
        for d in drivers_sorted:
            d.pop("abs_effect", None)

        # Build recommendations from top effects (simple MVP rules)
        recommendations = self._make_recommendations(drivers_sorted, r2_mean)

        metrics = {
            "model": "Ridge + StandardScaler",
            "target": "log(relative_performance)",
            "cv_r2_mean": round(r2_mean, 3),
            "cv_r2_std": round(r2_std, 3),
            "n_train": int(len(df)),
        }
        # Warn if target is very spiky (helps interpret huge effects)
        if "relative_performance" in df.columns:
            rp = df["relative_performance"].astype(float).values
            if len(rp) > 0 and np.nanmax(rp) > 10:
                warnings.append("Target has extreme spikes (relative_performance > 10). Effects may be dominated by outliers.")


        if r2_mean < 0.05:
            warnings.append("Low CV R²: drivers may be weak/noisy for this channel’s recent videos.")

        return ModelOutput(
            drivers=drivers_sorted[:8],  # keep response compact
            recommendations=recommendations,
            warnings=warnings,
            metrics=metrics
        )

    def _confidence_label(self, r2_mean: float) -> str:
        if r2_mean >= 0.30:
            return "high"
        if r2_mean >= 0.10:
            return "medium"
        return "low"

    def _make_recommendations(self, drivers_sorted: List[Dict], r2_mean: float) -> List[Dict]:
        confidence = self._confidence_label(r2_mean)
        recs: List[Dict] = []

        # map a few known features to human text
        templates = {
            "title_word_count": (
                "Adjust title length",
                "Reducing title word count (e.g., by ~5 words) is associated with a change in relative performance in your recent uploads."
            ),
            "title_length_chars": (
                "Refine title length",
                "Changing title length (characters) shows an association with relative performance in your recent uploads."
            ),
            "has_number": (
                "Use numbers strategically",
                "Titles containing numbers show an association with different performance; test using numbers on some uploads."
            ),
            "publish_hour": (
                "Experiment with upload time",
                "Upload hour shows an association with performance; try shifting upload time slightly and compare outcomes."
            ),
            "duration_seconds": (
                "Tune video length",
                "Video duration shows an association with performance; try small length adjustments and track impact."
            ),
            "caps_ratio": (
                "Adjust capitalization style",
                "Title capitalization intensity (caps ratio) shows an association with performance; test slightly more/less emphasis."
            ),
            "has_question": (
                "Use question marks carefully",
                "Question marks in titles show an association with performance; test fewer/more question-style titles."
            ),
            "is_weekend": (
                "Test weekday vs weekend uploads",
                "Weekend publishing shows an association with performance; test shifting some uploads to weekdays."
            ),
            "has_brackets": (
                "Try bracketed hooks",
                "Bracketed phrases (e.g., [NEW], (Guide)) show an association with performance; test this packaging style."
            ),
        }



        for d in drivers_sorted:
            feat = d["feature"]
            if feat in templates:
                title, detail = templates[feat]
                recs.append({
                    "title": title,
                    "detail": detail,
                    "expected_impact_percent": d["effect_percent"],
                    "confidence": confidence
                })
            if len(recs) == 3:
                break

        if not recs and drivers_sorted:
            top = drivers_sorted[0]
            recs.append({
                "title": "Focus on top driver",
                "detail": f"The feature '{top['feature']}' shows the strongest association in your recent data.",
                "expected_impact_percent": top["effect_percent"],
                "confidence": confidence
            })

        return recs
