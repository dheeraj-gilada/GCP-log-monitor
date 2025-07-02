"""
Email service for sending alerts via SendGrid.
Handles email formatting, delivery, and configuration validation.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import json

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content, Email, To
from python_http_client.exceptions import HTTPError

from app.config import get_settings


class EmailService:
    """Service for sending email alerts via SendGrid."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize SendGrid client."""
        if self.settings.sendgrid_api_key:
            try:
                self.client = SendGridAPIClient(api_key=self.settings.sendgrid_api_key)
                logging.info("SendGrid client initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize SendGrid client: {e}")
                self.client = None
        else:
            logging.warning("SendGrid API key not provided - email service disabled")
    
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return (self.client is not None and 
                bool(self.settings.sendgrid_api_key) and 
                bool(self.settings.alert_email_from))
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test SendGrid connection and configuration."""
        if not self.client:
            return {
                "configured": False,
                "error": "SendGrid client not initialized",
                "api_key_provided": bool(self.settings.sendgrid_api_key),
                "from_email_provided": bool(self.settings.alert_email_from)
            }
        
        try:
            # Test by getting API key info (lightweight call)
            response = self.client.api_keys.get()
            
            return {
                "configured": True,
                "status": "healthy",
                "api_key_provided": True,
                "from_email_provided": bool(self.settings.alert_email_from),
                "from_email": self.settings.alert_email_from
            }
            
        except Exception as e:
            return {
                "configured": False,
                "error": str(e),
                "api_key_provided": bool(self.settings.sendgrid_api_key),
                "from_email_provided": bool(self.settings.alert_email_from)
            }
    
    async def send_anomaly_alert(self, email_context: Dict[str, Any]) -> bool:
        """Send anomaly alert email."""
        if not self.is_configured():
            logging.error("Email service not configured - cannot send alert")
            return False
        
        try:
            # Extract context
            alert = email_context.get('alert')
            anomaly = email_context.get('anomaly')
            monitoring_url = email_context.get('monitoring_url', 'N/A')
            timestamp = email_context.get('timestamp', datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
            
            # Create email content
            subject = f"🚨 {alert.get('title', 'Anomaly Detected')} - {alert.get('severity', 'UNKNOWN')} Severity"
            
            html_content = self._create_alert_html(alert, anomaly, monitoring_url, timestamp)
            text_content = self._create_alert_text(alert, anomaly, monitoring_url, timestamp)
            
            # Create and send email
            message = Mail(
                from_email=Email(self.settings.alert_email_from),
                to_emails=[To(self.settings.alert_email_to)],
                subject=subject,
                html_content=Content("text/html", html_content),
                plain_text_content=Content("text/plain", text_content)
            )
            
            response = self.client.send(message)
            
            if response.status_code in [200, 201, 202]:
                logging.info(f"Alert email sent successfully: {subject}")
                return True
            else:
                logging.error(f"Failed to send alert email: {response.status_code} - {response.body}")
                return False
                
        except HTTPError as e:
            logging.error(f"SendGrid API error: {e}")
            return False
        except Exception as e:
            logging.error(f"Error sending alert email: {e}")
            return False
    
    async def send_test_alert(self, test_context: Dict[str, Any]) -> bool:
        """Send a test email alert."""
        if not self.is_configured():
            logging.error("Email service not configured - cannot send test alert")
            return False
        
        try:
            subject = "🧪 Test Alert - GCP Log Monitoring System"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h1 style="color: #2563eb; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">
                        🧪 Test Alert
                    </h1>
                    
                    <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h2 style="color: #059669; margin-top: 0;">Test Successful!</h2>
                        <p>This is a test email to verify that your GCP Log Monitoring System email configuration is working correctly.</p>
                    </div>
                    
                    <div style="margin: 20px 0;">
                        <h3>Test Details:</h3>
                        <ul>
                            <li><strong>Timestamp:</strong> {test_context.get('timestamp', 'N/A')}</li>
                            <li><strong>From Email:</strong> {self.settings.alert_email_from}</li>
                            <li><strong>To Email:</strong> {self.settings.alert_email_to}</li>
                            <li><strong>SendGrid Status:</strong> ✅ Configured</li>
                        </ul>
                    </div>
                    
                    <div style="background-color: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <p><strong>🎉 Congratulations!</strong> Your email alerts are properly configured and working.</p>
                    </div>
                    
                    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280;">
                        <p>Generated by GCP Log Monitoring System</p>
                        <p>Monitoring URL: {test_context.get('monitoring_url', 'N/A')}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            TEST ALERT - GCP Log Monitoring System
            
            Test Successful!
            This is a test email to verify that your email configuration is working correctly.
            
            Test Details:
            - Timestamp: {test_context.get('timestamp', 'N/A')}
            - From Email: {self.settings.alert_email_from}
            - To Email: {self.settings.alert_email_to}
            - SendGrid Status: Configured
            
            Congratulations! Your email alerts are properly configured and working.
            
            Generated by GCP Log Monitoring System
            Monitoring URL: {test_context.get('monitoring_url', 'N/A')}
            """
            
            # Create and send email
            message = Mail(
                from_email=Email(self.settings.alert_email_from),
                to_emails=[To(self.settings.alert_email_to)],
                subject=subject,
                html_content=Content("text/html", html_content),
                plain_text_content=Content("text/plain", text_content)
            )
            
            response = self.client.send(message)
            
            if response.status_code in [200, 201, 202]:
                logging.info("Test email sent successfully")
                return True
            else:
                logging.error(f"Failed to send test email: {response.status_code}")
                return False
                
        except Exception as e:
            logging.error(f"Error sending test email: {e}")
            return False
    
    def _create_alert_html(self, alert: Dict, anomaly: Dict, monitoring_url: str, timestamp: str) -> str:
        """Create HTML content for alert email."""
        severity_colors = {
            "LOW": "#10b981",     # Green
            "MEDIUM": "#f59e0b",  # Yellow
            "HIGH": "#ef4444",    # Red
            "CRITICAL": "#dc2626" # Dark red
        }
        
        severity = alert.get('severity', 'UNKNOWN')
        severity_color = severity_colors.get(severity, "#6b7280")
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: {severity_color}; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">
                    🚨 {alert.get('title', 'Anomaly Detected')}
                </h1>
                
                <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h2 style="color: {severity_color}; margin-top: 0;">
                        Severity: {severity}
                    </h2>
                    <p><strong>Description:</strong> {alert.get('description', 'No description available')}</p>
                    <p><strong>Detection Time:</strong> {timestamp}</p>
                </div>
                
                <div style="margin: 20px 0;">
                    <h3>Affected Resources:</h3>
                    <ul>
                        {''.join(f'<li>{resource}</li>' for resource in alert.get('affected_resources', []))}
                    </ul>
                </div>
                
                {self._create_metrics_section_html(alert.get('metrics', {}))}
                
                <div style="background-color: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Recommended Actions:</h3>
                    <ol>
                        <li>Review the anomaly details in the monitoring dashboard</li>
                        <li>Check affected resources for any ongoing issues</li>
                        <li>Investigate root cause using the provided metrics</li>
                        <li>Take appropriate remediation actions</li>
                    </ol>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{monitoring_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                        View in Monitoring Dashboard
                    </a>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280;">
                    <p>This alert was generated by the GCP Log Monitoring System</p>
                    <p>Alert ID: {alert.get('id', 'N/A')} | Detection Method: {anomaly.get('detection_method', 'N/A') if anomaly else 'N/A'}</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_alert_text(self, alert: Dict, anomaly: Dict, monitoring_url: str, timestamp: str) -> str:
        """Create plain text content for alert email."""
        return f"""
        ALERT: {alert.get('title', 'Anomaly Detected')}
        Severity: {alert.get('severity', 'UNKNOWN')}
        
        Description: {alert.get('description', 'No description available')}
        Detection Time: {timestamp}
        
        Affected Resources:
        {chr(10).join(f'- {resource}' for resource in alert.get('affected_resources', []))}
        
        Metrics:
        {self._format_metrics_text(alert.get('metrics', {}))}
        
        Recommended Actions:
        1. Review the anomaly details in the monitoring dashboard
        2. Check affected resources for any ongoing issues
        3. Investigate root cause using the provided metrics
        4. Take appropriate remediation actions
        
        View in Dashboard: {monitoring_url}
        
        ---
        This alert was generated by the GCP Log Monitoring System
        Alert ID: {alert.get('id', 'N/A')} | Detection Method: {anomaly.get('detection_method', 'N/A') if anomaly else 'N/A'}
        """
    
    def _create_metrics_section_html(self, metrics: Dict[str, Any]) -> str:
        """Create HTML section for metrics."""
        if not metrics:
            return ""
        
        metrics_html = "<div style='margin: 20px 0;'><h3>Metrics:</h3><ul>"
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                if key.endswith('_rate'):
                    formatted_value = f"{value:.2%}"
                elif key.endswith('_ms'):
                    formatted_value = f"{value:.0f}ms"
                else:
                    formatted_value = str(value)
            else:
                formatted_value = str(value)
            
            metrics_html += f"<li><strong>{key.replace('_', ' ').title()}:</strong> {formatted_value}</li>"
        
        metrics_html += "</ul></div>"
        return metrics_html
    
    def _format_metrics_text(self, metrics: Dict[str, Any]) -> str:
        """Format metrics for plain text email."""
        if not metrics:
            return "No metrics available"
        
        formatted_metrics = []
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                if key.endswith('_rate'):
                    formatted_value = f"{value:.2%}"
                elif key.endswith('_ms'):
                    formatted_value = f"{value:.0f}ms"
                else:
                    formatted_value = str(value)
            else:
                formatted_value = str(value)
            
            formatted_metrics.append(f"- {key.replace('_', ' ').title()}: {formatted_value}")
        
        return chr(10).join(formatted_metrics)
