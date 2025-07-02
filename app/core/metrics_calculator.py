"""
Core metrics calculation functionality.

This module contains reusable metrics calculation logic for log analysis,
anomaly detection, and system monitoring.
"""

import statistics
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict

from app.models.schemas import LogEntry, LogSeverity, ResourceType


class MetricsCalculator:
    """Core metrics calculation utilities for log analysis."""
    
    def __init__(self):
        pass
    
    def calculate_error_rate(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Calculate error rate from logs."""
        if not logs:
            return {
                "total_logs": 0,
                "error_logs": 0,
                "error_rate": 0.0,
                "severity_distribution": {}
            }
        
        total_logs = len(logs)
        error_logs = len([log for log in logs if log.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL]])
        
        # Count by severity
        severity_counts = Counter(log.severity.value for log in logs)
        
        return {
            "total_logs": total_logs,
            "error_logs": error_logs,
            "error_rate": error_logs / total_logs,
            "severity_distribution": dict(severity_counts)
        }
    
    def calculate_latency_stats(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Calculate latency statistics from HTTP logs."""
        http_logs = [log for log in logs if log.http_request and hasattr(log.http_request, 'latency')]
        
        if not http_logs:
            return {
                "sample_size": 0,
                "avg_latency_ms": 0,
                "p50_latency_ms": 0,
                "p95_latency_ms": 0,
                "p99_latency_ms": 0,
                "max_latency_ms": 0
            }
        
        latencies = [log.http_request.latency for log in http_logs if log.http_request.latency]
        
        if not latencies:
            return {
                "sample_size": 0,
                "avg_latency_ms": 0,
                "p50_latency_ms": 0,
                "p95_latency_ms": 0,
                "p99_latency_ms": 0,
                "max_latency_ms": 0
            }
        
        sorted_latencies = sorted(latencies)
        
        return {
            "sample_size": len(latencies),
            "avg_latency_ms": statistics.mean(latencies),
            "p50_latency_ms": statistics.median(latencies),
            "p95_latency_ms": self._percentile(sorted_latencies, 0.95),
            "p99_latency_ms": self._percentile(sorted_latencies, 0.99),
            "max_latency_ms": max(latencies)
        }
    
    def calculate_volume_metrics(self, logs: List[LogEntry], window_minutes: int = 10) -> Dict[str, Any]:
        """Calculate volume metrics and trends."""
        if not logs:
            return {
                "total_volume": 0,
                "logs_per_minute": 0,
                "peak_minute_volume": 0,
                "time_distribution": {}
            }
        
        # Group logs by minute
        minute_buckets = defaultdict(int)
        for log in logs:
            minute_key = log.timestamp.replace(second=0, microsecond=0)
            minute_buckets[minute_key] += 1
        
        total_volume = len(logs)
        time_span_minutes = max(1, window_minutes)
        logs_per_minute = total_volume / time_span_minutes
        peak_minute_volume = max(minute_buckets.values()) if minute_buckets else 0
        
        return {
            "total_volume": total_volume,
            "logs_per_minute": logs_per_minute,
            "peak_minute_volume": peak_minute_volume,
            "time_distribution": dict(minute_buckets)
        }
    
    def calculate_resource_metrics(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Calculate per-resource metrics."""
        resource_stats = defaultdict(lambda: {
            "total_logs": 0,
            "error_logs": 0,
            "error_rate": 0.0,
            "resource_type": ResourceType.UNKNOWN.value
        })
        
        for log in logs:
            resource_key = f"{log.resource.type.value}:{log.resource.labels.get('instance_id', 'unknown')}"
            resource_stats[resource_key]["total_logs"] += 1
            resource_stats[resource_key]["resource_type"] = log.resource.type.value
            
            if log.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL]:
                resource_stats[resource_key]["error_logs"] += 1
        
        # Calculate error rates
        for resource_key, stats in resource_stats.items():
            if stats["total_logs"] > 0:
                stats["error_rate"] = stats["error_logs"] / stats["total_logs"]
        
        return dict(resource_stats)
    
    def calculate_pattern_confidence(self, error_patterns: List[Dict], repeated_errors: List[Dict]) -> float:
        """Calculate confidence score for detected patterns."""
        if not error_patterns and not repeated_errors:
            return 0.0
        
        pattern_score = min(len(error_patterns) / 5.0, 1.0)  # Up to 5 patterns = 100%
        repetition_score = min(len(repeated_errors) / 3.0, 1.0)  # Up to 3 repeated patterns = 100%
        
        return (pattern_score + repetition_score) / 2.0
    
    def calculate_baseline_metrics(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Calculate baseline metrics for comparison."""
        if not logs:
            return {
                "average_volume": 0,
                "average_error_rate": 0,
                "common_resources": {},
                "updated_at": datetime.now(timezone.utc)
            }
        
        error_rate_metrics = self.calculate_error_rate(logs)
        resource_metrics = self.calculate_resource_metrics(logs)
        volume_metrics = self.calculate_volume_metrics(logs)
        
        return {
            "average_volume": volume_metrics["total_volume"],
            "average_error_rate": error_rate_metrics["error_rate"],
            "logs_per_minute": volume_metrics["logs_per_minute"],
            "common_resources": Counter(log.resource.type.value for log in logs),
            "severity_distribution": error_rate_metrics["severity_distribution"],
            "updated_at": datetime.now(timezone.utc)
        }
    
    def calculate_anomaly_confidence(self, metric_value: float, threshold_value: float, 
                                   detection_type: str = "threshold") -> float:
        """Calculate confidence score for anomaly detection."""
        if threshold_value <= 0:
            return 0.0
        
        if detection_type == "threshold":
            # Confidence based on how much metric exceeds threshold
            return min(metric_value / threshold_value, 1.0)
        elif detection_type == "pattern":
            # For pattern-based detection, use occurrence count vs minimum threshold
            return min(metric_value / threshold_value, 1.0)
        elif detection_type == "statistical":
            # For statistical anomalies, use standard deviation based confidence
            excess_ratio = metric_value / threshold_value
            return min(excess_ratio * 0.5, 1.0)  # Scale down for statistical methods
        
        return 0.8  # Default confidence
    
    def calculate_http_metrics(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Calculate HTTP-specific metrics."""
        http_logs = [log for log in logs if log.http_request]
        
        if not http_logs:
            return {
                "total_requests": 0,
                "error_rate": 0,
                "server_error_rate": 0,
                "status_distribution": {},
                "method_distribution": {},
                "anomalous_status_codes": []
            }
        
        total_requests = len(http_logs)
        error_requests = len([log for log in http_logs if log.http_request.status >= 400])
        server_errors = len([log for log in http_logs if log.http_request.status >= 500])
        
        status_codes = Counter(log.http_request.status for log in http_logs)
        methods = Counter(log.http_request.method for log in http_logs)
        
        return {
            "total_requests": total_requests,
            "error_rate": error_requests / total_requests if total_requests > 0 else 0,
            "server_error_rate": server_errors / total_requests if total_requests > 0 else 0,
            "status_distribution": dict(status_codes),
            "method_distribution": dict(methods),
            "anomalous_status_codes": [
                code for code, count in status_codes.items() 
                if code >= 500 and count > total_requests * 0.01
            ]
        }
    
    def detect_volume_spike(self, current_volume: int, baseline_volume: int, 
                          spike_multiplier: float = 3.0) -> Optional[Dict[str, Any]]:
        """Detect volume spikes against baseline."""
        if baseline_volume <= 0:
            return None
        
        spike_ratio = current_volume / baseline_volume
        
        if spike_ratio > spike_multiplier:
            return {
                "current_volume": current_volume,
                "baseline_volume": baseline_volume,
                "spike_ratio": spike_ratio,
                "threshold_multiplier": spike_multiplier,
                "confidence": min(spike_ratio / spike_multiplier, 1.0)
            }
        
        return None
    
    def detect_latency_spike(self, logs: List[LogEntry], threshold_ms: float = 5000) -> Optional[Dict[str, Any]]:
        """Detect latency spikes in HTTP requests."""
        latency_stats = self.calculate_latency_stats(logs)
        
        if latency_stats["sample_size"] < 10:  # Need sufficient data
            return None
        
        p95_latency = latency_stats["p95_latency_ms"]
        
        if p95_latency > threshold_ms:
            return {
                "p95_latency_ms": p95_latency,
                "avg_latency_ms": latency_stats["avg_latency_ms"],
                "threshold_ms": threshold_ms,
                "sample_size": latency_stats["sample_size"],
                "confidence": min(p95_latency / threshold_ms, 1.0)
            }
        
        return None
    
    def calculate_time_window_stats(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Calculate time window statistics."""
        if not logs:
            return {
                "start_time": None,
                "end_time": None,
                "duration_minutes": 0,
                "logs_distribution": {}
            }
        
        timestamps = [log.timestamp for log in logs]
        start_time = min(timestamps)
        end_time = max(timestamps)
        duration = end_time - start_time
        
        # Group logs by 5-minute intervals
        interval_minutes = 5
        interval_buckets = defaultdict(int)
        
        for log in logs:
            # Round timestamp to nearest interval
            minutes_since_start = (log.timestamp - start_time).total_seconds() / 60
            interval_key = int(minutes_since_start // interval_minutes) * interval_minutes
            interval_buckets[interval_key] += 1
        
        return {
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration.total_seconds() / 60,
            "logs_distribution": dict(interval_buckets)
        }
    
    def _percentile(self, sorted_data: List[float], percentile: float) -> float:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0.0
        
        if percentile <= 0:
            return sorted_data[0]
        if percentile >= 1:
            return sorted_data[-1]
        
        index = percentile * (len(sorted_data) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_data) - 1)
        
        if lower_index == upper_index:
            return sorted_data[lower_index]
        
        # Linear interpolation
        weight = index - lower_index
        return sorted_data[lower_index] * (1 - weight) + sorted_data[upper_index] * weight
