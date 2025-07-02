"""
Hybrid anomaly detection service combining statistical rules, pattern detection,
and AI-powered analysis using OpenAI GPT-4O via the Agents SDK.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum
import re
import statistics

from app.config import get_settings
from app.models.schemas import LogEntry, LogSeverity, ResourceType, Anomaly, AnomalyType, AnomalySeverity, DetectionMethod
from app.core.metrics_calculator import MetricsCalculator
from app.services.gpt_reasoning import GPTReasoningService


class AnomalyRule(Enum):
    """Statistical anomaly detection rules."""
    ERROR_RATE_SPIKE = "error_rate_spike"
    LATENCY_SPIKE = "latency_spike"
    VOLUME_SPIKE = "volume_spike"
    REPEATED_ERRORS = "repeated_errors"
    UNUSUAL_PATTERNS = "unusual_patterns"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SECURITY_ANOMALY = "security_anomaly"


@dataclass
class DetectionThresholds:
    """Configurable thresholds for anomaly detection."""
    error_rate_threshold: float = 0.05  # 5% error rate
    latency_threshold_ms: float = 5000  # 5 seconds
    volume_spike_multiplier: float = 3.0  # 3x normal volume
    min_events_for_pattern: int = 5
    time_window_minutes: int = 10
    pattern_confidence_threshold: float = 0.7


@dataclass
class AnomalyContext:
    """Context information for detected anomalies."""
    affected_resources: List[str]
    error_patterns: List[str]
    time_window: Tuple[datetime, datetime]
    sample_logs: List[LogEntry]
    metrics: Dict[str, Any]


class PatternDetector:
    """Detect unusual patterns in log messages."""
    
    def __init__(self):
        self.known_patterns = set()
        self.error_signatures = []
        self.metrics_calculator = MetricsCalculator()
    
    def analyze_patterns(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Analyze logs for unusual patterns."""
        if not logs:
            return {}
        
        # Extract error patterns
        error_logs = [log for log in logs if log.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL]]
        error_patterns = self._extract_error_patterns(error_logs)
        
        # Detect repeated error messages
        repeated_errors = self._detect_repeated_errors(error_logs)
        
        # Analyze HTTP patterns if available
        http_patterns = self._analyze_http_patterns(logs)
        
        # Detect resource-specific patterns
        resource_patterns = self._analyze_resource_patterns(logs)
        
        return {
            "error_patterns": error_patterns,
            "repeated_errors": repeated_errors,
            "http_patterns": http_patterns,
            "resource_patterns": resource_patterns,
            "pattern_confidence": self._calculate_pattern_confidence(error_patterns, repeated_errors)
        }
    
    def _extract_error_patterns(self, error_logs: List[LogEntry]) -> List[Dict[str, Any]]:
        """Extract common error patterns from error logs."""
        if not error_logs:
            return []
        
        # Group similar error messages
        error_groups = defaultdict(list)
        
        for log in error_logs:
            # Normalize error message for grouping
            normalized = self._normalize_error_message(log.message)
            error_groups[normalized].append(log)
        
        patterns = []
        for normalized_msg, logs in error_groups.items():
            if len(logs) >= 3:  # At least 3 occurrences
                patterns.append({
                    "pattern": normalized_msg,
                    "count": len(logs),
                    "first_seen": min(log.timestamp for log in logs),
                    "last_seen": max(log.timestamp for log in logs),
                    "affected_resources": list(set(log.resource.type.value for log in logs)),
                    "sample_message": logs[0].message
                })
        
        return sorted(patterns, key=lambda x: x["count"], reverse=True)
    
    def _normalize_error_message(self, message: str) -> str:
        """Normalize error message for pattern matching."""
        # Remove timestamps, IDs, and specific values
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', '[TIMESTAMP]', message)
        normalized = re.sub(r'\b\d+\b', '[NUMBER]', normalized)
        normalized = re.sub(r'\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b', '[UUID]', normalized)
        normalized = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]', normalized)
        normalized = re.sub(r'["\']([^"\']*)["\']', '[STRING]', normalized)
        
        return normalized.strip()
    
    def _detect_repeated_errors(self, error_logs: List[LogEntry]) -> List[Dict[str, Any]]:
        """Detect repeated error messages within a short time frame."""
        if not error_logs:
            return []
        
        # Group by normalized message and time windows
        time_windows = defaultdict(list)
        window_size = timedelta(minutes=5)
        
        for log in error_logs:
            window_key = int(log.timestamp.timestamp() // (window_size.total_seconds()))
            time_windows[window_key].append(log)
        
        repeated_patterns = []
        for window_logs in time_windows.values():
            if len(window_logs) < 5:  # Less than 5 errors in window
                continue
            
            message_counts = Counter(self._normalize_error_message(log.message) for log in window_logs)
            for message, count in message_counts.items():
                if count >= 5:  # Same error 5+ times in 5 minutes
                    repeated_patterns.append({
                        "pattern": message,
                        "count": count,
                        "time_window": window_size,
                        "severity": "HIGH" if count >= 10 else "MEDIUM"
                    })
        
        return repeated_patterns
    
    def _analyze_http_patterns(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Analyze HTTP request patterns for anomalies."""
        return self.metrics_calculator.calculate_http_metrics(logs)
    
    def _analyze_resource_patterns(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Analyze resource-specific patterns."""
        return self.metrics_calculator.calculate_resource_metrics(logs)
    
    def _calculate_pattern_confidence(self, error_patterns: List[Dict], repeated_errors: List[Dict]) -> float:
        """Calculate confidence score for detected patterns."""
        return self.metrics_calculator.calculate_pattern_confidence(error_patterns, repeated_errors)


class StatisticalDetector:
    """Statistical anomaly detection using thresholds and statistical analysis."""
    
    def __init__(self, thresholds: DetectionThresholds):
        self.thresholds = thresholds
        self.metrics_calculator = MetricsCalculator()
    
    def detect_anomalies(self, logs: List[LogEntry], baseline_metrics: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Detect statistical anomalies in logs."""
        if not logs:
            return []
        
        anomalies = []
        
        # Error rate anomaly
        error_rate_anomaly = self._detect_error_rate_spike(logs)
        if error_rate_anomaly:
            anomalies.append(error_rate_anomaly)
        
        # Volume spike anomaly
        volume_anomaly = self._detect_volume_spike(logs, baseline_metrics)
        if volume_anomaly:
            anomalies.append(volume_anomaly)
        
        # Latency anomaly (if HTTP data available)
        latency_anomaly = self._detect_latency_spike(logs)
        if latency_anomaly:
            anomalies.append(latency_anomaly)
        
        # Resource exhaustion patterns
        resource_anomaly = self._detect_resource_exhaustion(logs)
        if resource_anomaly:
            anomalies.append(resource_anomaly)
        
        return anomalies
    
    def _detect_error_rate_spike(self, logs: List[LogEntry]) -> Optional[Dict[str, Any]]:
        """Detect spikes in error rate."""
        error_metrics = self.metrics_calculator.calculate_error_rate(logs)
        
        if error_metrics["total_logs"] == 0:
            return None
        
        error_rate = error_metrics["error_rate"]
        
        if error_rate > self.thresholds.error_rate_threshold:
            confidence = self.metrics_calculator.calculate_anomaly_confidence(
                error_rate, self.thresholds.error_rate_threshold, "threshold"
            )
            
            return {
                "rule": AnomalyRule.ERROR_RATE_SPIKE,
                "severity": AnomalySeverity.HIGH if error_rate > 0.2 else AnomalySeverity.MEDIUM,
                "confidence": confidence,
                "metrics": {
                    "current_error_rate": error_rate,
                    "threshold": self.thresholds.error_rate_threshold,
                    "total_logs": error_metrics["total_logs"],
                    "error_logs": error_metrics["error_logs"]
                },
                "description": f"Error rate spike detected: {error_rate:.2%} (threshold: {self.thresholds.error_rate_threshold:.2%})"
            }
        
        return None
    
    def _detect_volume_spike(self, logs: List[LogEntry], baseline_metrics: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """Detect volume spikes compared to baseline."""
        current_volume = len(logs)
        
        if not baseline_metrics or "average_volume" not in baseline_metrics:
            return None
        
        baseline_volume = baseline_metrics["average_volume"]
        
        volume_spike = self.metrics_calculator.detect_volume_spike(
            current_volume, baseline_volume, self.thresholds.volume_spike_multiplier
        )
        
        if volume_spike:
            spike_ratio = volume_spike["spike_ratio"]
            
            return {
                "rule": AnomalyRule.VOLUME_SPIKE,
                "severity": AnomalySeverity.HIGH if spike_ratio > 5.0 else AnomalySeverity.MEDIUM,
                "confidence": volume_spike["confidence"],
                "metrics": volume_spike,
                "description": f"Log volume spike detected: {spike_ratio:.1f}x baseline volume"
            }
        
        return None
    
    def _detect_latency_spike(self, logs: List[LogEntry]) -> Optional[Dict[str, Any]]:
        """Detect latency spikes in HTTP requests."""
        latency_spike = self.metrics_calculator.detect_latency_spike(logs, self.thresholds.latency_threshold_ms)
        
        if latency_spike:
            p95_latency = latency_spike["p95_latency_ms"]
            
            return {
                "rule": AnomalyRule.LATENCY_SPIKE,
                "severity": AnomalySeverity.HIGH if p95_latency > self.thresholds.latency_threshold_ms * 2 else AnomalySeverity.MEDIUM,
                "confidence": latency_spike["confidence"],
                "metrics": latency_spike,
                "description": f"Latency spike detected: P95 latency {p95_latency:.0f}ms (threshold: {self.thresholds.latency_threshold_ms:.0f}ms)"
            }
        
        return None
    
    def _detect_resource_exhaustion(self, logs: List[LogEntry]) -> Optional[Dict[str, Any]]:
        """Detect resource exhaustion patterns."""
        exhaustion_keywords = [
            "out of memory", "memory exhausted", "disk full", "no space left",
            "connection pool exhausted", "too many connections", "resource limit",
            "quota exceeded", "rate limit exceeded"
        ]
        
        exhaustion_logs = []
        for log in logs:
            message_lower = log.message.lower()
            if any(keyword in message_lower for keyword in exhaustion_keywords):
                exhaustion_logs.append(log)
        
        if len(exhaustion_logs) >= 3:  # Multiple resource exhaustion indicators
            return {
                "rule": AnomalyRule.RESOURCE_EXHAUSTION,
                "severity": AnomalySeverity.HIGH,
                "confidence": min(len(exhaustion_logs) / 10.0, 1.0),
                "metrics": {
                    "exhaustion_indicators": len(exhaustion_logs),
                    "affected_resources": list(set(log.resource.type.value for log in exhaustion_logs))
                },
                "description": f"Resource exhaustion detected: {len(exhaustion_logs)} indicators found"
            }
        
        return None


class AnomalyDetectionService:
    """Main service for anomaly detection using multiple detection strategies."""
    
    def __init__(self):
        self.settings = get_settings()
        self.thresholds = DetectionThresholds()
        self.statistical_detector = StatisticalDetector(self.thresholds)
        self.pattern_detector = PatternDetector()
        self.gpt_service = GPTReasoningService()
        self.metrics_calculator = MetricsCalculator()
        
        # Baseline metrics for comparison
        self.baseline_metrics = {}
        self._processing = False
    
    async def analyze_logs(self, logs: List[LogEntry], use_ai_analysis: bool = True) -> List[Anomaly]:
        """Perform comprehensive anomaly analysis on logs."""
        if not logs:
            return []
        
        logging.info(f"Analyzing {len(logs)} logs for anomalies")
        
        # Step 1: Statistical anomaly detection
        statistical_anomalies = self.statistical_detector.detect_anomalies(logs, self.baseline_metrics)
        
        # Step 2: Pattern-based detection
        pattern_analysis = self.pattern_detector.analyze_patterns(logs)
        
        # Step 3: Combine results and create anomaly objects
        detected_anomalies = []
        
        # Process statistical anomalies
        for stat_anomaly in statistical_anomalies:
            anomaly = await self._create_anomaly_from_statistical(stat_anomaly, logs)
            if anomaly:
                detected_anomalies.append(anomaly)
        
        # Process pattern anomalies
        pattern_anomalies = self._create_anomalies_from_patterns(pattern_analysis, logs)
        detected_anomalies.extend(pattern_anomalies)
        
        # Step 4: AI-powered analysis for complex anomalies
        if use_ai_analysis and detected_anomalies:
            try:
                ai_enhanced_anomalies = await self._enhance_with_ai_analysis(detected_anomalies, logs)
                detected_anomalies = ai_enhanced_anomalies
            except Exception as e:
                logging.warning(f"AI analysis failed, using base analysis: {e}")
        
        logging.info(f"Detected {len(detected_anomalies)} anomalies")
        return detected_anomalies
    
    async def _create_anomaly_from_statistical(self, stat_anomaly: Dict[str, Any], logs: List[LogEntry]) -> Optional[Anomaly]:
        """Create an Anomaly object from statistical detection result."""
        try:
            # Map rule to anomaly type
            rule_to_type = {
                AnomalyRule.ERROR_RATE_SPIKE: AnomalyType.HIGH_ERROR_RATE,
                AnomalyRule.VOLUME_SPIKE: AnomalyType.UNUSUAL_PATTERN,
                AnomalyRule.LATENCY_SPIKE: AnomalyType.HIGH_LATENCY,
                AnomalyRule.RESOURCE_EXHAUSTION: AnomalyType.RESOURCE_EXHAUSTION
            }
            
            anomaly_type = rule_to_type.get(stat_anomaly["rule"], AnomalyType.UNUSUAL_PATTERN)
            
            # Get sample logs for context
            sample_logs = logs[:10] if anomaly_type == AnomalyType.VOLUME_SPIKE else [
                log for log in logs if log.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL]
            ][:10]
            
            # Extract metric and threshold values based on anomaly type
            metrics = stat_anomaly.get("metrics", {})
            metric_value = None
            threshold_value = None
            
            if stat_anomaly["rule"] == AnomalyRule.ERROR_RATE_SPIKE:
                metric_value = metrics.get("current_error_rate")
                threshold_value = metrics.get("threshold")
            elif stat_anomaly["rule"] == AnomalyRule.VOLUME_SPIKE:
                metric_value = metrics.get("current_volume")
                threshold_value = metrics.get("baseline_volume")
            elif stat_anomaly["rule"] == AnomalyRule.LATENCY_SPIKE:
                metric_value = metrics.get("p95_latency_ms")
                threshold_value = metrics.get("threshold_ms")
            
            return Anomaly(
                id=f"{anomaly_type.value}_{int(datetime.now(timezone.utc).timestamp())}",
                type=anomaly_type,
                severity=stat_anomaly["severity"],
                detection_method=DetectionMethod.STATISTICAL,
                title=f"{anomaly_type.value.replace('_', ' ').title()}",
                description=stat_anomaly["description"],
                timestamp=min(log.timestamp for log in logs) if logs else datetime.now(timezone.utc),
                affected_logs_count=len(sample_logs),
                metric_value=metric_value,
                threshold_value=threshold_value,
                confidence=stat_anomaly.get("confidence", 0.8),
                resource_type=sample_logs[0].resource.type if sample_logs else ResourceType.UNKNOWN,
                resource_labels=sample_logs[0].resource.labels if sample_logs else {},
                affected_resources=[log.resource.type.value for log in sample_logs],
                sample_logs=sample_logs[:5]
            )
            
        except Exception as e:
            logging.error(f"Error creating anomaly from statistical result: {e}")
            return None
    
    def _create_anomalies_from_patterns(self, pattern_analysis: Dict[str, Any], logs: List[LogEntry]) -> List[Anomaly]:
        """Create anomaly objects from pattern analysis."""
        anomalies = []
        
        # Error pattern anomalies - use configurable threshold
        min_pattern_occurrences = self.thresholds.min_events_for_pattern
        for error_pattern in pattern_analysis.get("error_patterns", []):
            if error_pattern["count"] >= min_pattern_occurrences:  # Use configurable threshold
                pattern_logs = [log for log in logs if error_pattern['pattern'] in log.message]
                severity = AnomalySeverity.HIGH if error_pattern["count"] >= 10 else AnomalySeverity.MEDIUM
                
                # Calculate confidence based on how much the count exceeds threshold
                confidence = min(error_pattern["count"] / min_pattern_occurrences, 1.0)
                
                anomaly = Anomaly(
                    id=f"pattern_{hash(error_pattern['pattern'])}_{int(datetime.now(timezone.utc).timestamp())}",
                    type=AnomalyType.REPEATED_ERRORS,
                    severity=severity,
                    detection_method=DetectionMethod.PATTERN,
                    title=f"Repeated Error Pattern",
                    description=f"Repeated error pattern detected: {error_pattern['pattern']} ({error_pattern['count']} occurrences)",
                    timestamp=error_pattern["first_seen"],
                    affected_logs_count=error_pattern["count"],
                    metric_value=float(error_pattern["count"]),
                    threshold_value=float(min_pattern_occurrences),
                    confidence=confidence,
                    resource_type=pattern_logs[0].resource.type if pattern_logs else ResourceType.UNKNOWN,
                    resource_labels=pattern_logs[0].resource.labels if pattern_logs else {},
                    affected_resources=list(set(log.resource.type.value for log in pattern_logs)),
                    sample_logs=pattern_logs[:5]
                )
                anomalies.append(anomaly)
        
        # HTTP anomalies - use configurable error rate threshold
        http_patterns = pattern_analysis.get("http_patterns", {})
        server_error_rate = http_patterns.get("server_error_rate", 0)
        if server_error_rate > self.thresholds.error_rate_threshold:
            error_logs = [log for log in logs if log.http_request and log.http_request.status >= 500]
            
            # Calculate confidence based on how much error rate exceeds threshold
            confidence = min(server_error_rate / self.thresholds.error_rate_threshold, 1.0)
            
            anomaly = Anomaly(
                id=f"http_error_{int(datetime.now(timezone.utc).timestamp())}",
                type=AnomalyType.HIGH_ERROR_RATE,
                severity=AnomalySeverity.HIGH,
                detection_method=DetectionMethod.PATTERN,
                title=f"High HTTP Error Rate",
                description=f"High server error rate detected: {http_patterns['server_error_rate']:.2%}",
                timestamp=min(log.timestamp for log in logs) if logs else datetime.now(timezone.utc),
                affected_logs_count=len(error_logs),
                metric_value=server_error_rate,
                threshold_value=self.thresholds.error_rate_threshold,
                confidence=confidence,
                resource_type=logs[0].resource.type if logs else ResourceType.UNKNOWN,
                resource_labels=logs[0].resource.labels if logs else {},
                affected_resources=list(set(log.resource.type.value for log in error_logs)),
                sample_logs=error_logs[:5]
            )
            anomalies.append(anomaly)
        
        return anomalies
    
    async def _enhance_with_ai_analysis(self, anomalies: List[Anomaly], logs: List[LogEntry]) -> List[Anomaly]:
        """Enhance anomalies with AI-powered root cause analysis."""
        try:
            # Prepare context for AI analysis
            context = {
                "anomaly_count": len(anomalies),
                "log_count": len(logs),
                "time_window": {
                    "start": min(log.timestamp for log in logs).isoformat(),
                    "end": max(log.timestamp for log in logs).isoformat()
                },
                "anomaly_summary": [
                    {
                        "type": anomaly.type.value,
                        "severity": anomaly.severity.value,
                        "description": anomaly.description,
                        "confidence": anomaly.confidence
                    }
                    for anomaly in anomalies
                ]
            }
            
            # Get AI analysis
            ai_analysis = await self.gpt_service.analyze_anomalies(anomalies, logs, context)
            
            # Enhance anomalies with AI insights
            for i, anomaly in enumerate(anomalies):
                if i < len(ai_analysis.get("enhanced_anomalies", [])):
                    ai_insight = ai_analysis["enhanced_anomalies"][i]
                    anomaly.ai_analysis = ai_insight
                    
                    # Update description with AI insights
                    if "root_cause" in ai_insight:
                        anomaly.description += f" | AI Analysis: {ai_insight['root_cause']}"
                    
                    # Adjust confidence based on AI analysis
                    if "confidence_adjustment" in ai_insight:
                        anomaly.confidence = min(anomaly.confidence * ai_insight["confidence_adjustment"], 1.0)
            
            return anomalies
            
        except Exception as e:
            logging.error(f"Error in AI enhancement: {e}")
            return anomalies
    
    def update_baseline_metrics(self, logs: List[LogEntry]):
        """Update baseline metrics for comparison."""
        if not logs:
            return
        
        self.baseline_metrics = self.metrics_calculator.calculate_baseline_metrics(logs)
    
    def configure_thresholds(self, **threshold_updates):
        """Update detection thresholds."""
        for key, value in threshold_updates.items():
            if hasattr(self.thresholds, key):
                setattr(self.thresholds, key, value)
        
        # Recreate detector with new thresholds
        self.statistical_detector = StatisticalDetector(self.thresholds)
    
    async def start_processing(self):
        """Start background processing tasks."""
        self._processing = True
        # Could add background tasks for baseline updates, etc.
    
    async def stop_processing(self):
        """Stop background processing tasks."""
        self._processing = False
    
    def is_processing(self) -> bool:
        """Check if service is currently processing."""
        return self._processing
