from typing import List, Dict
from collections import Counter
from ..schemas.response import PerceptionSignal

class PerceptionService:

    def analyze(self, rows: List[Dict]) -> List[PerceptionSignal]:
        signals = []

        titles = [r["title"] for r in rows]

        # ---- Credibility: excessive capitalization ----
        
        caps_ratios = [
            sum(1 for c in t if c.isupper()) / max(1, len(t))
            for t in titles
        ]

        if sum(c > 0.3 for c in caps_ratios) > len(caps_ratios) * 0.3:
            signals.append(
                PerceptionSignal(
                    signal="Spam-like capitalization",
                    category="Credibility",
                    tendency="Often present in lower-performing videos",
                    confidence="medium",
                    description="Heavy use of capital letters can reduce perceived trust."
                )
            )

        # ---- Credibility: money bait ----

        dollar_titles = sum("$" in t for t in titles)
        if dollar_titles >= len(titles) * 0.25:
            signals.append(
                PerceptionSignal(
                    signal="Money-bait formatting",
                    category="Credibility",
                    tendency="Often present in lower-performing videos",
                    confidence="medium",
                    description="Excessive monetary symbols may signal inauthentic content."
                )
            )

        # ---- Clarity: long titles ----

        avg_len = sum(len(t) for t in titles) / len(titles)
        if avg_len > 70:
            signals.append(
                PerceptionSignal(
                    signal="Overly long titles",
                    category="Clarity",
                    tendency="Often present in weaker-performing videos",
                    confidence="high",
                    description="Long titles increase cognitive load and reduce clarity."
                )
            )

        return signals
