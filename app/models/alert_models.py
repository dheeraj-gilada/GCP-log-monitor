"""
Alert-specific models for formatting and delivery.
Handles alert templates, email content, and notification preferences.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field

from app.models.schemas import AnomalySeverity, AnomalyType


class AlertChannel(str, Enum):
    """Available alert delivery channels."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"  # Future implementation
    PAGERDUTY = "pagerduty"  # Future implementation


class AlertTemplate(str, Enum):
    """Predefined alert templates."""
    HIGH_ERROR_RATE = "high_error_rate"
    HIGH_LATENCY = "high_latency"
    REPEATED_ERRORS = "repeated_errors"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DEPLOYMENT_ISSUE = "deployment_issue"
    CUSTOM = "custom"


class EmailFormat(str, Enum):
    """Email content formats."""
    HTML = "html"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"


class AlertRule(BaseModel):
    """Alert rule configuration."""
    id: str
    name: str
    description: str
    
    # Trigger conditions
    anomaly_types: List[AnomalyType]
    min_severity: AnomalySeverity
    
    # Notification settings
    channels: List[AlertChannel]
    recipients: List[str]
    template: AlertTemplate
    
    # Rate limiting
    cooldown_minutes: int = Field(default=15, description="Minutes between similar alerts")
    max_alerts_per_hour: int = Field(default=4, description="Maximum alerts per hour")
    
    # Filters
    resource_filters: Dict[str, str] = Field(default_factory=dict)
    
    # Status
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AlertContent(BaseModel):
    """Structured alert content for different formats."""
    title: str
    summary: str
    
    # Sections
    problem_description: str
    impact_assessment: str
    root_cause_analysis: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)
    
    # Metadata
    anomaly_details: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    
    # Timeline
    detected_at: datetime
    window_start: datetime
    window_end: datetime
    
    # Resources
    affected_resources: List[str] = Field(default_factory=list)
    log_samples: List[str] = Field(default_factory=list)


class EmailTemplate(BaseModel):
    """Email template configuration."""
    template_id: AlertTemplate
    subject_template: str
    
    # Content templates
    html_template: Optional[str] = None
    markdown_template: Optional[str] = None
    text_template: Optional[str] = None
    
    # Styling
    css_styles: Optional[str] = None
    header_color: str = Field(default="#ff6b6b")
    
    # Variables that can be used in templates
    available_variables: List[str] = Field(default_factory=list)


class AlertDelivery(BaseModel):
    """Alert delivery tracking."""
    id: str
    alert_id: str
    channel: AlertChannel
    recipient: str
    
    # Content
    subject: str
    content: str
    format: EmailFormat
    
    # Delivery status
    status: str = "pending"  # pending, sent, failed, bounced
    attempts: int = 0
    max_attempts: int = 3
    
    # Timestamps
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    
    # Error tracking
    error_message: Optional[str] = None
    bounce_reason: Optional[str] = None


class AlertMetrics(BaseModel):
    """Metrics for alert performance tracking."""
    alert_id: str
    
    # Timing metrics
    detection_to_alert_seconds: float
    alert_to_delivery_seconds: float
    
    # Effectiveness
    was_actionable: Optional[bool] = None
    was_resolved: Optional[bool] = None
    resolution_time_minutes: Optional[int] = None
    
    # Feedback
    recipient_feedback: Optional[str] = None
    feedback_score: Optional[int] = None  # 1-5 scale


class AlertFormatter:
    """Formats alerts for different delivery channels."""
    
    def __init__(self):
        self.default_templates = self._load_default_templates()
    
    def format_email_html(self, content: AlertContent, severity: AnomalySeverity) -> str:
        """Format alert as HTML email."""
        severity_colors = {
            AnomalySeverity.LOW: "#28a745",
            AnomalySeverity.MEDIUM: "#ffc107", 
            AnomalySeverity.HIGH: "#fd7e14",
            AnomalySeverity.CRITICAL: "#dc3545"
        }
        
        color = severity_colors.get(severity, "#6c757d")
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{content.title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; }}
                .alert-container {{ max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; }}
                .alert-header {{ background-color: {color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .alert-content {{ padding: 20px; }}
                .severity-badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                .metrics {{ background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin: 15px 0; }}
                .actions {{ background-color: #e3f2fd; padding: 15px; border-radius: 4px; margin: 15px 0; }}
                .log-sample {{ background-color: #2d3748; color: #e2e8f0; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 12px; margin: 10px 0; }}
                .footer {{ background-color: #f8f9fa; padding: 15px; border-radius: 0 0 8px 8px; text-align: center; color: #6c757d; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="alert-container">
                <div class="alert-header">
                    <h1 style="margin: 0; font-size: 24px;">🚨 {content.title}</h1>
                    <span class="severity-badge" style="background-color: rgba(255,255,255,0.2);">{severity.upper()}</span>
                </div>
                
                <div class="alert-content">
                    <p><strong>Summary:</strong> {content.summary}</p>
                    
                    <div class="metrics">
                        <h3>📊 Details</h3>
                        <p><strong>Problem:</strong> {content.problem_description}</p>
                        <p><strong>Impact:</strong> {content.impact_assessment}</p>
                        <p><strong>Detection Time:</strong> {content.detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                        <p><strong>Time Window:</strong> {content.window_start.strftime('%H:%M')} - {content.window_end.strftime('%H:%M UTC')}</p>
                    </div>
        """
        
        if content.root_cause_analysis:
            html += f"""
                    <div class="metrics">
                        <h3>🔍 Root Cause Analysis</h3>
                        <p>{content.root_cause_analysis}</p>
                    </div>
            """
        
        if content.recommended_actions:
            html += f"""
                    <div class="actions">
                        <h3>⚡ Recommended Actions</h3>
                        <ul>
                            {''.join(f'<li>{action}</li>' for action in content.recommended_actions)}
                        </ul>
                    </div>
            """
        
        if content.log_samples:
            html += """
                    <div>
                        <h3>📝 Sample Logs</h3>
            """
            for log in content.log_samples[:3]:  # Show max 3 samples
                html += f'<div class="log-sample">{log}</div>'
            html += "</div>"
        
        html += f"""
                </div>
                
                <div class="footer">
                    Generated by GCP Log Monitoring System<br>
                    <small>Alert ID: {content.anomaly_details.get('id', 'unknown')}</small>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def format_email_markdown(self, content: AlertContent, severity: AnomalySeverity) -> str:
        """Format alert as Markdown."""
        severity_emoji = {
            AnomalySeverity.LOW: "🟢",
            AnomalySeverity.MEDIUM: "🟡",
            AnomalySeverity.HIGH: "🟠", 
            AnomalySeverity.CRITICAL: "🔴"
        }
        
        emoji = severity_emoji.get(severity, "⚪")
        
        markdown = f"""# {emoji} {content.title}

**Severity:** {severity.upper()}  
**Detection Time:** {content.detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}  
**Time Window:** {content.window_start.strftime('%H:%M')} - {content.window_end.strftime('%H:%M UTC')}

## 📋 Summary
{content.summary}

## 🔍 Problem Description
{content.problem_description}

## 📊 Impact Assessment
{content.impact_assessment}
"""

        if content.root_cause_analysis:
            markdown += f"""
## 🕵️ Root Cause Analysis
{content.root_cause_analysis}
"""

        if content.recommended_actions:
            markdown += """
## ⚡ Recommended Actions
"""
            for action in content.recommended_actions:
                markdown += f"- {action}\n"

        if content.affected_resources:
            markdown += """
## 🎯 Affected Resources
"""
            for resource in content.affected_resources:
                markdown += f"- {resource}\n"

        if content.log_samples:
            markdown += """
## 📝 Sample Logs
"""
            for i, log in enumerate(content.log_samples[:3], 1):
                markdown += f"""
### Sample {i}
```
{log}
```
"""

        markdown += f"""
---
*Generated by GCP Log Monitoring System*  
*Alert ID: {content.anomaly_details.get('id', 'unknown')}*
"""
        
        return markdown
    
    def _load_default_templates(self) -> Dict[AlertTemplate, EmailTemplate]:
        """Load default email templates."""
        # This would typically load from configuration or database
        return {
            AlertTemplate.HIGH_ERROR_RATE: EmailTemplate(
                template_id=AlertTemplate.HIGH_ERROR_RATE,
                subject_template="🚨 High Error Rate Detected - {resource_type}",
                available_variables=["resource_type", "error_rate", "threshold", "time_window"]
            ),
            AlertTemplate.HIGH_LATENCY: EmailTemplate(
                template_id=AlertTemplate.HIGH_LATENCY,
                subject_template="⏱️ High Latency Alert - {resource_type}",
                available_variables=["resource_type", "avg_latency", "threshold", "affected_requests"]
            ),
            AlertTemplate.REPEATED_ERRORS: EmailTemplate(
                template_id=AlertTemplate.REPEATED_ERRORS,
                subject_template="🔄 Repeated Errors Detected - {error_type}",
                available_variables=["error_type", "occurrence_count", "time_window"]
            )
        }
