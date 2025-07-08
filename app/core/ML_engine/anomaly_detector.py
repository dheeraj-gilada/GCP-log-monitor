import joblib
from typing import Dict, Any

class AnomalyDetector:
    """
    Loads ML model, performs real-time anomaly scoring on logs.
    """
    def __init__(self, model_path: str):
        self.model = self.load_model(model_path)

    def load_model(self, path: str):
        """Load a trained ML model from disk."""
        return joblib.load(path)

    def score(self, features: Dict[str, Any]) -> float:
        """Return anomaly score (higher = more anomalous)."""
        # IsolationForest: lower scores = more anomalous, so invert
        raw_score = self.model.decision_function([list(features.values())])[0]
        # return 1.0 - raw_score  # Normalize to [0,1] (approx)
        return raw_score  # Return raw score for now

    def is_anomaly(self, score: float, threshold: float = 0.7) -> bool:
        """Return True if score exceeds threshold."""
        return score > threshold

    # TODO: Add batch scoring, model versioning, etc. 