"""
Main monitoring engine that orchestrates log ingestion, anomaly detection,
and alert generation for the GCP log monitoring system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

from app.config import get_settings
from app.services.log_ingestion import LogIngestionService
from app.services.gcp_service import GCPService, GCPLogStreamConfig
from app.services.anomaly_detection import AnomalyDetectionService, DetectionThresholds
from app.services.email_service import EmailService
from app.services.monitoring_supervisor import MonitoringSupervisor, MonitoringContext, SupervisorDecision
from app.models.schemas import LogEntry, Anomaly, Alert, AnomalySeverity, AlertType, AlertStatus, AnomalyType
from app.api.websockets import broadcast_stats_update, broadcast_alert_generated


@dataclass
class MonitoringConfig:
    """Configuration for the monitoring engine."""
    analysis_interval_seconds: int = 60  # Analyze logs every minute
    window_minutes: int = 10  # Analyze logs from last 10 minutes
    enable_gcp_streaming: bool = True
    enable_email_alerts: bool = True
    enable_ai_analysis: bool = True
    enable_ai_supervisor: bool = True  # AI-powered supervisory layer
    min_logs_for_analysis: int = 10
    alert_cooldown_minutes: int = 30  # Avoid spam alerts


class MonitoringEngine:
    """Main engine for coordinating log monitoring, anomaly detection, and alerting."""
    
    def __init__(self):
        self.settings = get_settings()
        self.config = MonitoringConfig()
        
        # Initialize services
        self.log_service = LogIngestionService()
        self.gcp_service = GCPService()
        self.anomaly_service = AnomalyDetectionService()
        self.email_service = EmailService()
        self.supervisor = MonitoringSupervisor() if self.config.enable_ai_supervisor else None
        
        # Engine state
        self._running = False
        self._analysis_task = None
        self._gcp_streaming_task = None
        self._last_analysis_time = None
        self._recent_alerts = {}  # For cooldown tracking
        
        # Metrics
        self.stats = {
            "total_logs_processed": 0,
            "total_anomalies_detected": 0,
            "total_alerts_sent": 0,
            "uptime_start": datetime.utcnow(),
            "last_analysis": None,
            "gcp_streaming_active": False
        }
        
        logging.info("Monitoring Engine initialized")
    
    async def start(self):
        """Start the monitoring engine."""
        if self._running:
            logging.warning("Monitoring engine already running")
            return
        
        self._running = True
        self.stats["uptime_start"] = datetime.utcnow()
        
        logging.info("Starting monitoring engine...")
        
        # Start all services
        await self.log_service.start_processing()
        await self.anomaly_service.start_processing()
        
        # Start background tasks
        self._analysis_task = asyncio.create_task(self._analysis_loop())
        
        # Start GCP streaming if enabled and connected
        if self.config.enable_gcp_streaming and self.gcp_service.is_connected():
            await self._start_gcp_streaming()
        
        logging.info("✅ Monitoring engine started successfully")
        
        # Broadcast status update
        await broadcast_stats_update({
            "status": "started",
            "timestamp": datetime.utcnow().isoformat(),
            "gcp_streaming": self.stats["gcp_streaming_active"]
        })
    
    async def stop(self):
        """Stop the monitoring engine."""
        if not self._running:
            return
        
        self._running = False
        logging.info("Stopping monitoring engine...")
        
        # Stop background tasks
        if self._analysis_task:
            self._analysis_task.cancel()
            try:
                await self._analysis_task
            except asyncio.CancelledError:
                pass
        
        if self._gcp_streaming_task:
            await self.gcp_service.stop_log_streaming()
            self._gcp_streaming_task = None
        
        # Stop services
        await self.log_service.stop_processing()
        await self.anomaly_service.stop_processing()
        
        logging.info("✅ Monitoring engine stopped")
        
        # Broadcast status update
        await broadcast_stats_update({
            "status": "stopped",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _analysis_loop(self):
        """Main analysis loop that runs continuously."""
        logging.info("Starting analysis loop")
        
        while self._running:
            try:
                await self._perform_analysis_cycle()
                await asyncio.sleep(self.config.analysis_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in analysis loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _perform_analysis_cycle(self):
        """Perform one cycle of log analysis and anomaly detection."""
        cycle_start = datetime.utcnow()
        
        try:
            # Get recent logs from buffer
            logs = await self.log_service.get_logs_in_window(self.config.window_minutes)
            
            if len(logs) < self.config.min_logs_for_analysis:
                logging.debug(f"Insufficient logs for analysis: {len(logs)}")
                return
            
            logging.info(f"Analyzing {len(logs)} logs from last {self.config.window_minutes} minutes")
            
            # Update baseline metrics
            self.anomaly_service.update_baseline_metrics(logs)
            
            # Detect anomalies
            anomalies = await self.anomaly_service.analyze_logs(
                logs, 
                use_ai_analysis=self.config.enable_ai_analysis
            )
            
            # Update stats
            self.stats["total_logs_processed"] += len(logs)
            self.stats["total_anomalies_detected"] += len(anomalies)
            self.stats["last_analysis"] = cycle_start
            
            # Process detected anomalies
            if anomalies:
                await self._process_detected_anomalies(anomalies, logs)
            
            # Broadcast monitoring update
            await broadcast_stats_update({
                "status": "analysis_complete",
                "timestamp": cycle_start.isoformat(),
                "logs_analyzed": len(logs),
                "anomalies_detected": len(anomalies),
                "analysis_duration_ms": (datetime.utcnow() - cycle_start).total_seconds() * 1000
            })
            
            logging.info(f"Analysis cycle completed: {len(anomalies)} anomalies detected")
            
        except Exception as e:
            logging.error(f"Error in analysis cycle: {e}")
    
    async def _process_detected_anomalies(self, anomalies: List[Anomaly], logs: List[LogEntry]):
        """Process detected anomalies with AI supervisor and generate alerts."""
        
        # Apply AI supervisor analysis if enabled
        if self.config.enable_ai_supervisor and self.supervisor and self.supervisor.is_supervisor_available():
            try:
                # Create monitoring context
                error_rate = len([log for log in logs if log.severity.value in ['ERROR', 'CRITICAL']]) / len(logs) if logs else 0.0
                context = MonitoringContext(
                    total_logs=len(logs),
                    window_minutes=self.config.window_minutes,
                    error_rate=error_rate,
                    anomaly_count=len(anomalies),
                    previous_anomalies=[]  # Could be enhanced with historical data
                )
                
                # Get current detection thresholds
                current_thresholds = self.anomaly_service.get_detection_thresholds()
                
                # Run supervisor analysis
                supervisor_decision = await self.supervisor.analyze_monitoring_situation(
                    anomalies, logs, context, current_thresholds
                )
                
                if supervisor_decision:
                    await self._apply_supervisor_decision(supervisor_decision, anomalies)
                    
            except Exception as e:
                logging.error(f"Supervisor analysis failed: {e}")
        
        # Process each anomaly for alert generation
        for anomaly in anomalies:
            try:
                # Check cooldown for this type of anomaly
                if self._is_alert_on_cooldown(anomaly):
                    logging.debug(f"Anomaly {anomaly.type.value} on cooldown, skipping alert")
                    continue
                
                # Create alert
                alert = await self._create_alert_from_anomaly(anomaly, logs)
                
                # Send email alert if enabled
                if self.config.enable_email_alerts and anomaly.severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]:
                    await self._send_email_alert(alert, anomaly)
                
                # Broadcast alert via WebSocket
                await broadcast_alert_generated(alert.dict())
                
                # Track alert for cooldown
                self._track_alert_for_cooldown(anomaly)
                
                self.stats["total_alerts_sent"] += 1
                
                logging.info(f"Alert generated for {anomaly.type.value} anomaly")
                
            except Exception as e:
                logging.error(f"Error processing anomaly {anomaly.type.value}: {e}")
    
    async def _apply_supervisor_decision(self, decision: SupervisorDecision, anomalies: List[Anomaly]):
        """Apply supervisor recommendations to the monitoring system."""
        try:
            logging.info(f"Applying supervisor decision: {decision.reasoning[:100]}...")
            
            # Apply threshold adjustments
            if decision.threshold_adjustments:
                logging.info(f"Supervisor recommending threshold adjustments: {decision.threshold_adjustments}")
                await self.anomaly_service.update_detection_thresholds(decision.threshold_adjustments)
            
            # Apply severity adjustments
            if decision.severity_adjustment and decision.severity_adjustment != "maintain":
                for anomaly in anomalies:
                    original_severity = anomaly.severity
                    if decision.severity_adjustment == "increase":
                        anomaly.severity = self._increase_severity(anomaly.severity)
                    elif decision.severity_adjustment == "decrease":
                        anomaly.severity = self._decrease_severity(anomaly.severity)
                    
                    if anomaly.severity != original_severity:
                        logging.info(f"Supervisor adjusted anomaly severity: {original_severity.value} -> {anomaly.severity.value}")
            
            # Log incident summary if provided
            if decision.incident_summary:
                logging.info(f"Supervisor incident summary:\n{decision.incident_summary}")
                
                # Broadcast enhanced incident information
                await broadcast_stats_update({
                    "type": "supervisor_incident_summary",
                    "timestamp": datetime.utcnow().isoformat(),
                    "summary": decision.incident_summary,
                    "confidence": decision.confidence,
                    "escalation_needed": decision.escalate_to_human
                })
            
            # Log remediation actions
            if decision.suggested_actions:
                logging.info(f"Supervisor suggested actions: {', '.join(decision.suggested_actions[:3])}...")
                
                # Broadcast actionable recommendations
                await broadcast_stats_update({
                    "type": "supervisor_recommendations",
                    "timestamp": datetime.utcnow().isoformat(),
                    "actions": decision.suggested_actions,
                    "escalate_to_human": decision.escalate_to_human,
                    "confidence": decision.confidence
                })
            
            # Track supervisor involvement
            self.stats["supervisor_decisions"] = self.stats.get("supervisor_decisions", 0) + 1
            
        except Exception as e:
            logging.error(f"Error applying supervisor decision: {e}")
    
    def _increase_severity(self, severity: AnomalySeverity) -> AnomalySeverity:
        """Increase anomaly severity level."""
        severity_order = [AnomalySeverity.LOW, AnomalySeverity.MEDIUM, AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]
        current_index = severity_order.index(severity)
        return severity_order[min(current_index + 1, len(severity_order) - 1)]
    
    def _decrease_severity(self, severity: AnomalySeverity) -> AnomalySeverity:
        """Decrease anomaly severity level."""
        severity_order = [AnomalySeverity.LOW, AnomalySeverity.MEDIUM, AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]
        current_index = severity_order.index(severity)
        return severity_order[max(current_index - 1, 0)]
    
    async def _create_alert_from_anomaly(self, anomaly: Anomaly, logs: List[LogEntry]) -> Alert:
        """Create an Alert object from an detected anomaly."""
        
        # Determine alert type based on anomaly
        alert_type_mapping = {
            AnomalyType.HIGH_ERROR_RATE: AlertType.ERROR_RATE,
            AnomalyType.HIGH_LATENCY: AlertType.LATENCY_SPIKE,
            AnomalyType.REPEATED_ERRORS: AlertType.REPEATED_ERRORS,
            AnomalyType.RESOURCE_EXHAUSTION: AlertType.RESOURCE_EXHAUSTION,
            AnomalyType.UNUSUAL_PATTERN: AlertType.GENERAL
        }
        
        alert_type = alert_type_mapping.get(anomaly.type, AlertType.GENERAL)
        
        # Create alert
        alert = Alert(
            id=f"alert_{anomaly.id}_{int(datetime.utcnow().timestamp())}",
            anomaly_id=anomaly.id,
            alert_type=alert_type,
            title=f"{anomaly.type.value.replace('_', ' ').title()} Detected",
            summary=anomaly.description,
            severity=anomaly.severity,
            created_at=datetime.utcnow(),
            status=AlertStatus.PENDING
        )
        
        return alert
    
    async def _send_email_alert(self, alert: Alert, anomaly: Anomaly):
        """Send email alert for critical anomalies."""
        try:
            # Prepare email context
            email_context = {
                "alert": alert,
                "anomaly": anomaly,
                "monitoring_url": f"{self.settings.base_url}/monitoring",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            }
            
            await self.email_service.send_anomaly_alert(email_context)
            
        except Exception as e:
            logging.error(f"Failed to send email alert: {e}")
    
    def _is_alert_on_cooldown(self, anomaly: Anomaly) -> bool:
        """Check if this type of anomaly is on cooldown."""
        alert_key = f"{anomaly.type.value}:{'-'.join(anomaly.affected_resources)}"
        
        if alert_key in self._recent_alerts:
            last_alert_time = self._recent_alerts[alert_key]
            cooldown_end = last_alert_time + timedelta(minutes=self.config.alert_cooldown_minutes)
            
            return datetime.utcnow() < cooldown_end
        
        return False
    
    def _track_alert_for_cooldown(self, anomaly: Anomaly):
        """Track alert for cooldown management."""
        alert_key = f"{anomaly.type.value}:{'-'.join(anomaly.affected_resources)}"
        self._recent_alerts[alert_key] = datetime.utcnow()
        
        # Clean up old entries (older than 2x cooldown period)
        cleanup_threshold = datetime.utcnow() - timedelta(minutes=self.config.alert_cooldown_minutes * 2)
        self._recent_alerts = {
            key: timestamp for key, timestamp in self._recent_alerts.items()
            if timestamp > cleanup_threshold
        }
    
    async def _start_gcp_streaming(self):
        """Start GCP log streaming."""
        try:
            # Configure GCP streaming
            stream_config = GCPLogStreamConfig(
                time_window_minutes=self.config.window_minutes,
                max_entries=500
            )
            
            # Start streaming with callback
            await self.gcp_service.start_log_streaming(
                stream_config,
                self._handle_gcp_log_entry
            )
            
            self.stats["gcp_streaming_active"] = True
            logging.info("✅ GCP log streaming started")
            
        except Exception as e:
            logging.error(f"Failed to start GCP streaming: {e}")
            self.stats["gcp_streaming_active"] = False
    
    async def _handle_gcp_log_entry(self, log_entry: LogEntry):
        """Handle incoming GCP log entry."""
        try:
            # Add to ingestion buffer
            await self.log_service.ingest_real_time_log(log_entry.dict(), "gcp_stream")
            
        except Exception as e:
            logging.error(f"Error handling GCP log entry: {e}")
    
    async def ingest_file(self, file_content: str, filename: str, log_format: str = "auto") -> Dict[str, Any]:
        """Ingest logs from uploaded file."""
        return await self.log_service.ingest_file(file_content, filename, log_format)
    
    async def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent logs."""
        logs = await self.log_service.get_recent_logs(limit)
        return [log.dict() for log in logs]
    
    async def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get current monitoring statistics."""
        # Get buffer stats
        buffer_stats = await self.log_service.get_buffer_stats()
        
        # Calculate uptime
        uptime_seconds = (datetime.utcnow() - self.stats["uptime_start"]).total_seconds()
        
        # Get supervisor status
        supervisor_status = {
            "enabled": self.config.enable_ai_supervisor,
            "available": self.supervisor.is_supervisor_available() if self.supervisor else False,
            "decision_count": len(self.supervisor.get_decision_history()) if self.supervisor else 0
        }
        
        return {
            **self.stats,
            "uptime_seconds": uptime_seconds,
            "running": self._running,
            "buffer_stats": buffer_stats,
            "gcp_connected": self.gcp_service.is_connected(),
            "supervisor": supervisor_status,
            "services": {
                "log_ingestion": self.log_service.is_processing(),
                "anomaly_detection": self.anomaly_service.is_processing(),
                "gcp_streaming": self.gcp_service.is_streaming(),
                "email_service": self.email_service.is_configured(),
                "ai_supervisor": supervisor_status["available"]
            }
        }
    
    async def configure_monitoring(self, **config_updates):
        """Update monitoring configuration."""
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logging.info(f"Updated monitoring config: {key} = {value}")
        
        # If thresholds are updated, pass them to anomaly service
        if any(key.endswith('_threshold') for key in config_updates.keys()):
            threshold_updates = {k: v for k, v in config_updates.items() if k.endswith('_threshold')}
            self.anomaly_service.configure_thresholds(**threshold_updates)
    
    async def test_services(self) -> Dict[str, Any]:
        """Test all service connections."""
        results = {}
        
        # Test GCP connection
        try:
            gcp_test = await self.gcp_service.test_connection()
            results["gcp"] = gcp_test
        except Exception as e:
            results["gcp"] = {"connected": False, "error": str(e)}
        
        # Test email service
        try:
            email_test = await self.email_service.test_connection()
            results["email"] = email_test
        except Exception as e:
            results["email"] = {"configured": False, "error": str(e)}
        
        # Test GPT service
        try:
            results["gpt"] = {
                "available": self.anomaly_service.gpt_service.is_available(),
                "api_key_configured": bool(self.settings.openai_api_key)
            }
        except Exception as e:
            results["gpt"] = {"available": False, "error": str(e)}
        
        return results
    
    def is_running(self) -> bool:
        """Check if monitoring engine is running."""
        return self._running
    
    async def force_analysis(self) -> Dict[str, Any]:
        """Force immediate analysis cycle (for testing/manual trigger)."""
        if not self._running:
            raise Exception("Monitoring engine not running")
        
        logging.info("Forcing immediate analysis cycle")
        
        start_time = datetime.utcnow()
        await self._perform_analysis_cycle()
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            "success": True,
            "analysis_duration_seconds": duration,
            "timestamp": start_time.isoformat()
        }
    
    def get_supervisor_decision_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent supervisor decisions for analysis."""
        if not self.supervisor:
            return []
        return self.supervisor.get_decision_history(limit)
    
    def get_supervisor_status(self) -> Dict[str, Any]:
        """Get detailed supervisor status and capabilities."""
        if not self.supervisor:
            return {
                "enabled": self.config.enable_ai_supervisor,
                "available": False,
                "reason": "Supervisor not initialized"
            }
        
        return {
            "enabled": self.config.enable_ai_supervisor,
            "available": self.supervisor.is_supervisor_available(),
            "decision_count": len(self.supervisor.get_decision_history()),
            "recent_decisions": self.supervisor.get_decision_history(3),
            "capabilities": [
                "Anomaly context analysis",
                "Dynamic threshold adjustment", 
                "Incident summary generation",
                "Remediation action suggestions"
            ]
        }
