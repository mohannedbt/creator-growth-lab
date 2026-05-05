import json
import hashlib
from pathlib import Path

class TopicLabelCache:
    def __init__(self, path="topic_label_cache.json"):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        else:
            self.data = {}

    def _key(self, titles):
        norm = [t.lower().strip() for t in titles]
        joined = "||".join(sorted(norm))
        return hashlib.sha256(joined.encode()).hexdigest()

    def get(self, titles):
        return self.data.get(self._key(titles))

    def set(self, titles, label):
        key = self._key(titles)
        self.data[key] = label
        self.path.write_text(json.dumps(self.data, indent=2))
