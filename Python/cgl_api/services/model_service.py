from dataclasses import dataclass
from typing import Dict, List

@dataclass
class ModelOutput:
    recommendations: List[Dict]
    warnings: List[str]
    metrics: Dict

class ModelService:
    def train_and_explain(self, rows: List[Dict]) -> ModelOutput:
        return ModelOutput(
            recommendations=[],
            warnings=["ModelService disabled (no drivers; topics + perception signals are primary)."],
            metrics={}
        )
