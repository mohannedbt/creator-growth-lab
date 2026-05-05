from typing import List
from google import genai
from .topic_label_cache import TopicLabelCache

class HybridTopicLabeler:
    def __init__(self, gemini_api_key: str | None = None):
        self.cache = TopicLabelCache()

        self.gemini = None
        if gemini_api_key:
            try:
                self.gemini = genai.Client(api_key=gemini_api_key)
            except Exception:
                self.gemini = None

        self._hf = True  # ✅ lazy

    def _get_hf(self):
        if self._hf is False:
            from transformers import pipeline
            # small model
            self._hf = pipeline("text2text-generation", model="google/flan-t5-base", max_new_tokens=16)
        return self._hf

    def label(self, titles: List[str]) -> str:
        if len(titles) <= 1:
            return titles[0]

        cached = self.cache.get(titles)
        if cached:
            return cached

        # Try Gemini first
        label = self._try_gemini(titles)
        if label:
            self.cache.set(titles, label)
            return label

        # Fallback to HF ONLY now (this is where download happens)
        label = self._try_hf(titles)
        if label:
            self.cache.set(titles, label)
            return label

        fallback = titles[0]
        self.cache.set(titles, fallback)
        return fallback

    def _prompt(self, titles: List[str]) -> str:
        lines = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles[:5]))
        return f"""
You are labeling groups of YouTube video titles.
Output a SHORT, GENERIC label (2–5 words). Be literal. No quotes. No explanation.

Titles:
{lines}

Label:
""".strip()

    def _try_gemini(self, titles: List[str]) -> str | None:
        if not self.gemini:
            return None
        try:
            resp = self.gemini.models.generate_content(
                model="gemini-1.5-flash",
                contents=self._prompt(titles),
            )
            return (resp.text or "").strip()
        except Exception:
            return None

    def _try_hf(self, titles: List[str]) -> str | None:
        try:
            hf = self._get_hf()
            out = hf(self._prompt(titles))[0]["generated_text"]
            return out.strip()
        except Exception:
            return None
