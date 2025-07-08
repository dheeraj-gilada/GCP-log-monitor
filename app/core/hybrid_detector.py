from app.core.correlation import correlate

class HybridDetector:
    """
    Orchestrates rule-based (D1), ML-based (D2), and correlation (D3) detection.
    """
    def __init__(self, rule_engine, ml_detector, feature_extractor, feature_list=None):
        self.rule_engine = rule_engine
        self.ml_detector = ml_detector
        self.feature_extractor = feature_extractor
        self.feature_list = feature_list or []

    def detect(self, log, features_vec=None):
        # Rule-based detection
        rule_matches = self.rule_engine.match(log)
        print(f"[DEBUG][HybridDetector] rule_matches: {rule_matches}")
        rule_result = rule_matches[0] if rule_matches else None
        print(f"[DEBUG][HybridDetector] rule_result: {rule_result}")
        # ML-based detection (DISABLED)
        # import logging
        # if features_vec is not None:
        #     logging.info("[ML DEBUG] Normalized log: %s", log)
        #     logging.info("[ML DEBUG] Feature vector: %s", features_vec)
        #     ml_score = self.ml_detector.score(features_vec) if self.ml_detector else None
        #     ml_is_anomaly = self.ml_detector.is_anomaly(ml_score) if self.ml_detector else False
        #     ml_result = {'score': ml_score, 'features': features_vec} if ml_is_anomaly else None
        # else:
        #     features = self.feature_extractor.extract_features(log)
        #     logging.info("[ML DEBUG] Normalized log: %s", log)
        #     logging.info("[ML DEBUG] Feature vector: %s", features)
        #     ml_score = self.ml_detector.score(features) if self.ml_detector else None
        #     ml_is_anomaly = self.ml_detector.is_anomaly(ml_score) if self.ml_detector else False
        #     ml_result = {'score': ml_score, 'features': features} if ml_is_anomaly else None
        ml_result = None  # ML detection disabled
        # Correlation
        detection = correlate(rule_result, ml_result)
        print(f"[DEBUG][HybridDetector] correlate output: {detection}")
        return detection

    # TODO: Add batch detection, feedback, and prioritization methods. 