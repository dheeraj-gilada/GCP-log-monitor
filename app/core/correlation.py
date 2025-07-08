def correlate(rule_result, ml_result):
    """
    Combine rule-based and ML-based anomaly results.
    Args:
        rule_result (dict or None): Result from rule engine (None if not flagged)
        ml_result (dict or None): Result from ML engine (None if not flagged)
    Returns:
        dict: {
            'is_anomaly': bool,
            'confidence': float,
            'source': str,  # 'rule', 'ml', or 'hybrid'
            'details': {'rule': rule_result, 'ml': ml_result}
        }
    """
    is_rule = rule_result is not None
    is_ml = ml_result is not None
    if is_rule and is_ml:
        return {'is_anomaly': True, 'confidence': 0.9, 'source': 'hybrid', 'details': {'rule': rule_result, 'ml': ml_result}}
    elif is_rule:
        return {'is_anomaly': True, 'confidence': 0.5, 'source': 'rule', 'details': {'rule': rule_result, 'ml': ml_result}}
    elif is_ml:
        return {'is_anomaly': True, 'confidence': 0.5, 'source': 'ml', 'details': {'rule': rule_result, 'ml': ml_result}}
    else:
        return {'is_anomaly': False, 'confidence': 0.0, 'source': 'none', 'details': {'rule': rule_result, 'ml': ml_result}}
# TODO: Add more advanced correlation, prioritization, and scoring logic. 