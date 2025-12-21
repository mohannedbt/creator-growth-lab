import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict

@dataclass
class FeatureService:
    """
    Converts raw video fields into engineered features.
    Pure functions: no API calls, no file IO.
    """

    def title_features(self, title: str) -> Dict:
        title = title or ""
        words = re.findall(r"\b\w+\b", title)

        title_length_chars = len(title)
        title_word_count = len(words)

        has_number = bool(re.search(r"\d", title))
        has_question = "?" in title
        has_brackets = bool(re.search(r"[\[\]\(\)\{\}]", title))

        # caps ratio: fraction of letters that are uppercase
        letters = [c for c in title if c.isalpha()]
        if letters:
            caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        else:
            caps_ratio = 0.0

        # emoji count (simple heuristic: count non-ascii symbols)
        emoji_count = sum(1 for c in title if ord(c) > 10000)

        return {
            "title_length_chars": title_length_chars,
            "title_word_count": title_word_count,
            "has_number": has_number,
            "has_question": has_question,
            "has_brackets": has_brackets,
            "caps_ratio": round(caps_ratio, 5),
            "emoji_count": emoji_count,
        }

    def time_features(self, published_at: datetime) -> Dict:
        # published_at is timezone-aware; keep UTC for consistency
        publish_hour = published_at.hour
        publish_day_of_week = published_at.weekday()  # Mon=0 ... Sun=6
        is_weekend = publish_day_of_week >= 5

        return {
            "publish_hour": publish_hour,
            "publish_day_of_week": publish_day_of_week,
            "is_weekend": is_weekend,
        }

    def numeric_rates(self, views: int, likes: int, comments: int) -> Dict:
        views = max(int(views), 0)
        likes = max(int(likes), 0)
        comments = max(int(comments), 0)

        if views <= 0:
            return {
                "engagement_rate": 0.0,
                "likes_rate": 0.0,
                "comments_rate": 0.0,
            }

        engagement_rate = (likes + comments) / views
        likes_rate = likes / views
        comments_rate = comments / views

        return {
            "engagement_rate": round(engagement_rate, 8),
            "likes_rate": round(likes_rate, 8),
            "comments_rate": round(comments_rate, 8),
        }
