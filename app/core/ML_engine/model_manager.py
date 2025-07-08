import joblib
from sklearn.ensemble import IsolationForest
from typing import List, Dict, Any

class ModelManager:
    """
    Handles model training, saving, loading, and retraining.
    """
    def train(self, X: List[Dict[str, Any]], model_type: str = 'isolation_forest'):
        """Train a new anomaly detection model."""
        if model_type == 'isolation_forest':
            model = IsolationForest(contamination=0.05, random_state=42)
            X_mat = [list(x.values()) for x in X]
            model.fit(X_mat)
            return model
        else:
            raise NotImplementedError(f"Model type {model_type} not supported.")

    def save(self, model, path: str):
        """Save a trained model to disk."""
        joblib.dump(model, path)

    def load(self, path: str):
        """Load a trained model from disk."""
        return joblib.load(path)

    def retrain(self, X: List[Dict[str, Any]], old_model_path: str):
        """Retrain model using new data and save over old model."""
        model = self.train(X)
        self.save(model, old_model_path)
        return model

    # TODO: Add support for more model types, hyperparameter tuning, etc. 