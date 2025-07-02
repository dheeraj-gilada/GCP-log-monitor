"""
AI-powered monitoring supervisor using OpenAI Agents SDK.

This module implements an intelligent supervisory layer that enhances the monitoring
engine with AI-driven decision making, threshold tuning, and incident analysis.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict

try:
    from agents import Agent, Runner, function_tool, RunContextWrapper
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    logging.warning("OpenAI Agents SDK not available. Supervisor will be disabled.")

from app.config import get_settings
from app.models.schemas import LogEntry, Anomaly, AnomalySeverity, AnomalyType
from app.services.anomaly_detection import DetectionThresholds


def _determine_incident_severity(context) -> str:
    """Determine incident severity based on context."""
    if context.error_rate > 0.3 or context.anomaly_count > 5:
        return "CRITICAL"
    elif context.error_rate > 0.15 or context.anomaly_count > 3:
        return "HIGH"
    elif context.error_rate > 0.05 or context.anomaly_count > 1:
        return "MEDIUM"
    else:
        return "LOW"


def _generate_incident_title(anomalies_description: str) -> str:
    """Generate a concise incident title."""
    if "error rate" in anomalies_description.lower():
        return "High Error Rate Detected"
    elif "repeated" in anomalies_description.lower():
        return "Repeated Error Pattern Detected"
    elif "latency" in anomalies_description.lower():
        return "Latency Spike Detected"
    elif "volume" in anomalies_description.lower():
        return "Traffic Volume Anomaly"
    else:
        return "System Anomaly Detected"


def _estimate_resolution_time(anomaly_type: str, severity_level: str) -> str:
    """Estimate resolution time based on anomaly type and severity."""
    base_times = {
        "high_error_rate": "15-30 minutes",
        "repeated_errors": "30-60 minutes", 
        "latency_spike": "10-20 minutes",
        "volume_spike": "5-15 minutes"
    }
    
    base_time = base_times.get(anomaly_type.lower(), "20-40 minutes")
    
    if severity_level.lower() in ['high', 'critical']:
        return f"Priority: {base_time}"
    else:
        return f"Standard: {base_time}"


@dataclass
class MonitoringContext:
    """Context information passed to the supervisor for decision making."""
    total_logs: int
    window_minutes: int
    error_rate: float
    anomaly_count: int
    previous_anomalies: List[Dict[str, Any]]
    system_load: Optional[Dict[str, Any]] = None
    recent_threshold_changes: Optional[List[Dict[str, Any]]] = None


@dataclass
class SupervisorDecision:
    """Decision output from the supervisor."""
    severity_adjustment: Optional[str] = None  # "increase", "decrease", "maintain"
    threshold_adjustments: Optional[Dict[str, float]] = None
    escalate_to_human: bool = False
    auto_remediation: Optional[str] = None
    confidence: float = 0.8
    reasoning: str = ""
    incident_summary: Optional[str] = None
    suggested_actions: List[str] = None


class MonitoringSupervisor:
    """AI-powered supervisor for intelligent monitoring orchestration."""
    
    def __init__(self):
        self.settings = get_settings()
        self.is_available = AGENTS_SDK_AVAILABLE and bool(self.settings.openai_api_key)
        
        if not self.is_available:
            logging.warning("Monitoring supervisor disabled: OpenAI API key not configured or Agents SDK not available")
            return
        
        # Initialize the supervisor agent with function tools
        self.agent = self._create_supervisor_agent()
        self._decision_history = []
        
        logging.info("✅ Monitoring Supervisor initialized with AI capabilities")
    
    def _create_supervisor_agent(self) -> Optional[Agent]:
        """Create the OpenAI agent with monitoring-specific tools."""
        if not self.is_available:
            return None
        
        try:
            agent = Agent(
                name="Monitoring Supervisor",
                instructions="""You are an AI supervisor for a GCP log monitoring system. Your role is to:

1. Analyze detected anomalies and system context intelligently
2. Make decisions about severity adjustments and threshold tuning
3. Determine when to escalate incidents to human operators
4. Provide clear reasoning for all decisions
5. Generate actionable incident summaries and remediation suggestions

You have access to monitoring context including logs, anomalies, error rates, and historical data.
Always provide specific, actionable recommendations based on the data patterns you observe.
Consider both immediate impact and long-term system health in your decisions.

Your responses should be precise, data-driven, and focused on operational excellence.""",
                model="gpt-4o-mini",  # Use efficient model for monitoring decisions
                tools=[
                    self._analyze_anomaly_context,
                    self._adjust_detection_thresholds,
                    self._generate_incident_summary,
                    self._suggest_remediation_actions
                ]
            )
            return agent
            
        except Exception as e:
            logging.error(f"Failed to create supervisor agent: {e}")
            return None
    
    @function_tool
    async def _analyze_anomaly_context(
        ctx: RunContextWrapper[MonitoringContext],
        anomaly_type: str,
        current_severity: str,
        error_rate: float,
        anomaly_count: int,
        recent_patterns: str
    ) -> str:
        """Analyze anomaly context and decide on severity adjustment.
        
        Args:
            anomaly_type: Type of anomaly detected (e.g., 'high_error_rate', 'repeated_errors')
            current_severity: Current severity level ('low', 'medium', 'high', 'critical')
            error_rate: Current system error rate as a percentage
            anomaly_count: Number of anomalies in current window
            recent_patterns: Description of recent anomaly patterns
        """
        try:
            context = ctx.context
            
            # Analyze severity based on context
            severity_analysis = {
                "current_severity": current_severity,
                "recommended_adjustment": "maintain",
                "reasoning": [],
                "confidence": 0.8
            }
            
            # High error rate indicates more severe situation
            if error_rate > 0.2:  # >20% error rate
                if current_severity in ["low", "medium"]:
                    severity_analysis["recommended_adjustment"] = "increase"
                    severity_analysis["reasoning"].append(f"High error rate ({error_rate:.1%}) warrants increased severity")
            
            # Multiple anomalies suggest systemic issues
            if anomaly_count > 3:
                if current_severity != "critical":
                    severity_analysis["recommended_adjustment"] = "increase"
                    severity_analysis["reasoning"].append(f"Multiple anomalies ({anomaly_count}) indicate systemic issues")
            
            # Low impact situations
            if error_rate < 0.05 and anomaly_count == 1:  # <5% error rate, single anomaly
                if current_severity in ["high", "critical"]:
                    severity_analysis["recommended_adjustment"] = "decrease"
                    severity_analysis["reasoning"].append("Low error rate and isolated anomaly suggest reduced severity")
            
            # Pattern-based analysis
            if "repeated_errors" in recent_patterns.lower() and "authentication" in recent_patterns.lower():
                severity_analysis["recommended_adjustment"] = "increase"
                severity_analysis["reasoning"].append("Authentication-related repeated errors suggest security concern")
            
            reasoning = ". ".join(severity_analysis["reasoning"]) or "No significant severity adjustment needed based on current metrics"
            
            return json.dumps({
                "severity_adjustment": severity_analysis["recommended_adjustment"],
                "confidence": severity_analysis["confidence"],
                "reasoning": reasoning,
                "metrics_considered": {
                    "error_rate": error_rate,
                    "anomaly_count": anomaly_count,
                    "window_minutes": context.window_minutes
                }
            })
            
        except Exception as e:
            logging.error(f"Error in anomaly context analysis: {e}")
            return json.dumps({"error": str(e), "severity_adjustment": "maintain"})
    
    @function_tool
    async def _adjust_detection_thresholds(
        ctx: RunContextWrapper[MonitoringContext],
        current_error_rate_threshold: float,
        current_volume_threshold: float,
        system_baseline_error_rate: float,
        false_positive_rate: str
    ) -> str:
        """Suggest threshold adjustments based on system behavior.
        
        Args:
            current_error_rate_threshold: Current error rate threshold (0.0-1.0)
            current_volume_threshold: Current volume spike threshold multiplier
            system_baseline_error_rate: Historical baseline error rate
            false_positive_rate: Estimated false positive rate ("low", "medium", "high")
        """
        try:
            context = ctx.context
            adjustments = {}
            reasoning = []
            
            # Adjust error rate threshold based on baseline
            if system_baseline_error_rate > current_error_rate_threshold * 1.5:
                # Baseline much higher than threshold - may need to relax
                new_threshold = min(system_baseline_error_rate * 1.2, 0.3)  # Cap at 30%
                adjustments["error_rate_threshold"] = new_threshold
                reasoning.append(f"Raised error threshold to {new_threshold:.1%} based on baseline of {system_baseline_error_rate:.1%}")
            
            elif system_baseline_error_rate < current_error_rate_threshold * 0.5:
                # Baseline much lower than threshold - can be more sensitive
                new_threshold = max(system_baseline_error_rate * 2, 0.01)  # Floor at 1%
                adjustments["error_rate_threshold"] = new_threshold
                reasoning.append(f"Lowered error threshold to {new_threshold:.1%} for better sensitivity")
            
            # Adjust volume threshold based on false positive rate
            if false_positive_rate == "high":
                new_volume_threshold = min(current_volume_threshold * 1.3, 5.0)  # Increase, cap at 5x
                adjustments["volume_spike_multiplier"] = new_volume_threshold
                reasoning.append(f"Increased volume threshold to {new_volume_threshold:.1f}x to reduce false positives")
            
            elif false_positive_rate == "low" and context.anomaly_count == 0:
                new_volume_threshold = max(current_volume_threshold * 0.8, 2.0)  # Decrease, floor at 2x
                adjustments["volume_spike_multiplier"] = new_volume_threshold
                reasoning.append(f"Decreased volume threshold to {new_volume_threshold:.1f}x for better detection")
            
            # Latency threshold adjustments based on error correlation
            if context.error_rate > 0.1 and len(adjustments) == 0:
                # High error rate but no other adjustments - check latency sensitivity
                adjustments["latency_threshold_ms"] = 3000  # 3 seconds - more sensitive
                reasoning.append("Reduced latency threshold due to high error rate correlation")
            
            reasoning_text = ". ".join(reasoning) or "No threshold adjustments recommended at this time"
            
            return json.dumps({
                "threshold_adjustments": adjustments,
                "reasoning": reasoning_text,
                "confidence": 0.9 if len(adjustments) > 0 else 0.7,
                "baseline_metrics": {
                    "error_rate": system_baseline_error_rate,
                    "current_thresholds": {
                        "error_rate": current_error_rate_threshold,
                        "volume": current_volume_threshold
                    }
                }
            })
            
        except Exception as e:
            logging.error(f"Error in threshold adjustment: {e}")
            return json.dumps({"error": str(e), "threshold_adjustments": {}})
    
    @function_tool
    async def _generate_incident_summary(
        ctx: RunContextWrapper[MonitoringContext],
        anomalies_description: str,
        affected_resources: str,
        time_window: str,
        impact_assessment: str
    ) -> str:
        """Generate a human-readable incident summary.
        
        Args:
            anomalies_description: Description of detected anomalies
            affected_resources: List of affected resources/services
            time_window: Time window of the incident
            impact_assessment: Assessment of user/system impact
        """
        try:
            context = ctx.context
            timestamp = datetime.now(timezone.utc)
            
            # Create structured incident summary
            summary = {
                "incident_id": f"INC-{timestamp.strftime('%Y%m%d-%H%M%S')}",
                "timestamp": timestamp.isoformat(),
                "severity": _determine_incident_severity(context),
                "title": _generate_incident_title(anomalies_description),
                "description": anomalies_description,
                "affected_resources": affected_resources.split(", ") if affected_resources else [],
                "time_window": time_window,
                "impact": impact_assessment,
                "metrics": {
                    "total_logs": context.total_logs,
                    "error_rate": f"{context.error_rate:.1%}",
                    "anomaly_count": context.anomaly_count
                },
                "detection_time": timestamp.isoformat(),
                "auto_generated": True
            }
            
            # Generate human-readable summary
            readable_summary = f"""
🚨 INCIDENT DETECTED: {summary['title']}

📊 OVERVIEW:
- Incident ID: {summary['incident_id']}
- Severity: {summary['severity']}
- Detection Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
- Time Window: {time_window}

🔍 DETAILS:
{anomalies_description}

🎯 AFFECTED RESOURCES:
{affected_resources or 'General system impact'}

📈 METRICS:
- Total Logs Analyzed: {context.total_logs:,}
- Current Error Rate: {context.error_rate:.1%}
- Anomalies Detected: {context.anomaly_count}

⚠️ IMPACT ASSESSMENT:
{impact_assessment}
            """.strip()
            
            return json.dumps({
                "incident_summary": readable_summary,
                "structured_data": summary,
                "requires_human_attention": summary['severity'] in ['HIGH', 'CRITICAL']
            })
            
        except Exception as e:
            logging.error(f"Error generating incident summary: {e}")
            return json.dumps({"error": str(e), "incident_summary": "Error generating summary"})
    
    @function_tool
    async def _suggest_remediation_actions(
        ctx: RunContextWrapper[MonitoringContext],
        anomaly_type: str,
        severity_level: str,
        error_patterns: str,
        resource_impact: str
    ) -> str:
        """Suggest specific remediation actions based on the anomaly context.
        
        Args:
            anomaly_type: Type of anomaly (e.g., 'high_error_rate', 'latency_spike')
            severity_level: Severity level of the incident
            error_patterns: Description of error patterns observed
            resource_impact: Description of resource impact
        """
        try:
            actions = []
            
            # Type-specific remediation actions
            if anomaly_type.lower() in ['high_error_rate', 'error_rate_spike']:
                actions.extend([
                    "🔍 Investigate application logs for root cause of error spike",
                    "📊 Check database connection pool status and query performance",
                    "🔄 Consider scaling application instances if load-related",
                    "⚡ Review recent deployments for potential regression issues"
                ])
            
            elif anomaly_type.lower() in ['repeated_errors', 'pattern_anomaly']:
                actions.extend([
                    "🔍 Analyze repeated error patterns for systematic issues",
                    "🔧 Check configuration files and environment variables",
                    "🛡️ Review authentication and authorization systems",
                    "📝 Update error handling and retry mechanisms"
                ])
            
            elif anomaly_type.lower() in ['latency_spike', 'high_latency']:
                actions.extend([
                    "⚡ Investigate slow database queries and optimize indexes",
                    "🌐 Check network connectivity and external service dependencies",
                    "💾 Review memory usage and garbage collection patterns",
                    "📈 Scale up resources if performance degradation is confirmed"
                ])
            
            elif anomaly_type.lower() in ['volume_spike', 'unusual_pattern']:
                actions.extend([
                    "📊 Analyze traffic patterns for legitimate vs. malicious activity",
                    "🔄 Implement rate limiting if necessary",
                    "📈 Scale infrastructure to handle increased load",
                    "🛡️ Check for potential DDoS or bot activity"
                ])
            
            # Severity-based actions
            if severity_level.lower() in ['high', 'critical']:
                actions.extend([
                    "🚨 Notify on-call engineering team immediately",
                    "📞 Prepare for potential customer communication",
                    "📋 Document all investigation steps and findings",
                    "🔄 Prepare rollback procedures if deployment-related"
                ])
            
            # Resource-specific actions
            if 'database' in resource_impact.lower():
                actions.extend([
                    "🗄️ Check database health and connection status",
                    "📊 Review slow query logs and execution plans",
                    "💾 Monitor database memory and disk usage"
                ])
            
            if 'authentication' in error_patterns.lower():
                actions.extend([
                    "🔐 Review authentication service logs and health",
                    "🛡️ Check for credential stuffing or brute force attacks",
                    "🔑 Verify identity provider connectivity and configuration"
                ])
            
            # General monitoring actions
            actions.extend([
                "📊 Continue monitoring for pattern evolution",
                "🔄 Update monitoring thresholds if false positive confirmed",
                "📝 Document incident for post-mortem analysis"
            ])
            
            # Remove duplicates while preserving order
            unique_actions = []
            seen = set()
            for action in actions:
                if action not in seen:
                    unique_actions.append(action)
                    seen.add(action)
            
            return json.dumps({
                "remediation_actions": unique_actions,
                "immediate_actions": unique_actions[:3],  # Top 3 priority actions
                "monitoring_actions": [a for a in unique_actions if "monitor" in a.lower()],
                "escalation_needed": severity_level.lower() in ['high', 'critical'],
                "estimated_resolution_time": _estimate_resolution_time(anomaly_type, severity_level)
            })
            
        except Exception as e:
            logging.error(f"Error suggesting remediation actions: {e}")
            return json.dumps({"error": str(e), "remediation_actions": []})
    

    
    async def analyze_monitoring_situation(
        self,
        anomalies: List[Anomaly],
        logs: List[LogEntry],
        context: MonitoringContext,
        current_thresholds: DetectionThresholds
    ) -> Optional[SupervisorDecision]:
        """
        Main entry point for supervisor analysis.
        
        Args:
            anomalies: List of detected anomalies
            logs: Recent log entries
            context: Monitoring context and metrics
            current_thresholds: Current detection thresholds
            
        Returns:
            SupervisorDecision with recommendations, or None if supervisor unavailable
        """
        if not self.is_available or not self.agent:
            return None
        
        try:
            # Prepare analysis input
            anomalies_description = self._format_anomalies_for_analysis(anomalies)
            affected_resources = self._extract_affected_resources(anomalies)
            error_patterns = self._extract_error_patterns(logs)
            
            # Create supervisor input
            supervisor_input = f"""
            MONITORING SITUATION ANALYSIS REQUIRED
            
            Context:
            - Total logs in window: {context.total_logs}
            - Window: {context.window_minutes} minutes
            - Current error rate: {context.error_rate:.1%}
            - Anomalies detected: {context.anomaly_count}
            
            Detected Anomalies:
            {anomalies_description}
            
            Affected Resources:
            {affected_resources}
            
            Error Patterns:
            {error_patterns}
            
            Current Thresholds:
            - Error rate threshold: {current_thresholds.error_rate_threshold:.1%}
            - Volume spike multiplier: {current_thresholds.volume_spike_multiplier}x
            - Latency threshold: {current_thresholds.latency_threshold_ms}ms
            
            Please analyze this situation and provide:
            1. Severity assessment and any adjustments needed
            2. Threshold tuning recommendations
            3. Incident summary for human operators
            4. Specific remediation actions
            
            Use the available tools to provide comprehensive analysis.
            """
            
            # Run the supervisor agent
            result = await Runner.run(
                self.agent,
                input=supervisor_input,
                context=context,
                max_turns=5  # Allow multiple tool calls
            )
            
            # Parse the supervisor's response and tool outputs
            decision = self._parse_supervisor_result(result, anomalies, context)
            
            # Store decision for history tracking
            self._decision_history.append({
                "timestamp": datetime.now(timezone.utc),
                "decision": asdict(decision),
                "anomaly_count": len(anomalies),
                "context": asdict(context)
            })
            
            # Keep only last 50 decisions for memory management
            if len(self._decision_history) > 50:
                self._decision_history = self._decision_history[-50:]
            
            logging.info(f"Supervisor analysis complete: {decision.reasoning[:100]}...")
            return decision
            
        except Exception as e:
            logging.error(f"Error in supervisor analysis: {e}")
            return SupervisorDecision(
                reasoning=f"Supervisor analysis failed: {str(e)}",
                confidence=0.1,
                escalate_to_human=True
            )
    
    def _format_anomalies_for_analysis(self, anomalies: List[Anomaly]) -> str:
        """Format anomalies for AI analysis."""
        if not anomalies:
            return "No anomalies detected"
        
        formatted = []
        for anomaly in anomalies:
            formatted.append(f"- {anomaly.type.value}: {anomaly.description} (Confidence: {anomaly.confidence:.1%})")
        
        return "\n".join(formatted)
    
    def _extract_affected_resources(self, anomalies: List[Anomaly]) -> str:
        """Extract affected resources from anomalies."""
        resources = set()
        for anomaly in anomalies:
            if anomaly.affected_resources:
                resources.update(anomaly.affected_resources)
        
        return ", ".join(sorted(resources)) or "General system impact"
    
    def _extract_error_patterns(self, logs: List[LogEntry]) -> str:
        """Extract error patterns from logs for analysis."""
        error_logs = [log for log in logs if log.severity.value in ['ERROR', 'CRITICAL']]
        
        if not error_logs:
            return "No significant error patterns"
        
        # Simple pattern extraction - could be enhanced
        error_messages = [log.message[:100] for log in error_logs[-10:]]  # Last 10 errors
        return "; ".join(error_messages)
    
    def _parse_supervisor_result(self, result, anomalies: List[Anomaly], context: MonitoringContext) -> SupervisorDecision:
        """Parse the supervisor agent result into a structured decision."""
        try:
            # Extract information from the result
            final_output = str(result.final_output) if result.final_output else ""
            
            # Initialize decision with defaults
            decision = SupervisorDecision(
                reasoning=final_output or "Analysis completed",
                confidence=0.8,
                suggested_actions=[]
            )
            
            # Parse tool outputs from the agent run
            for item in result.new_items:
                if hasattr(item, 'type') and item.type == 'tool_call_output_item':
                    try:
                        tool_output = json.loads(item.output)
                        
                        # Extract severity adjustments
                        if 'severity_adjustment' in tool_output:
                            decision.severity_adjustment = tool_output['severity_adjustment']
                        
                        # Extract threshold adjustments  
                        if 'threshold_adjustments' in tool_output:
                            decision.threshold_adjustments = tool_output['threshold_adjustments']
                        
                        # Extract incident summary
                        if 'incident_summary' in tool_output:
                            decision.incident_summary = tool_output['incident_summary']
                        
                        # Extract remediation actions
                        if 'remediation_actions' in tool_output:
                            decision.suggested_actions = tool_output['remediation_actions']
                        
                        # Extract escalation decision
                        if 'escalation_needed' in tool_output:
                            decision.escalate_to_human = tool_output['escalation_needed']
                        
                        # Update confidence if provided
                        if 'confidence' in tool_output:
                            decision.confidence = tool_output['confidence']
                            
                    except (json.JSONDecodeError, AttributeError):
                        continue
            
            # Set escalation based on severity
            if len(anomalies) > 3 or context.error_rate > 0.2:
                decision.escalate_to_human = True
            
            return decision
            
        except Exception as e:
            logging.error(f"Error parsing supervisor result: {e}")
            return SupervisorDecision(
                reasoning=f"Error parsing analysis: {str(e)}",
                confidence=0.1,
                escalate_to_human=True
            )
    
    def get_decision_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent supervisor decisions for analysis."""
        return self._decision_history[-limit:] if self._decision_history else []
    
    def is_supervisor_available(self) -> bool:
        """Check if the supervisor is available for analysis."""
        return self.is_available and self.agent is not None 