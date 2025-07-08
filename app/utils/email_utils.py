import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
SMTP_SENDER = os.getenv('SMTP_SENDER', SMTP_USER)


def send_alert_email(recipient, anomalies, rca_results):
    print(f"[EMAIL] Attempting to send alert email to {recipient} with {len(anomalies)} anomalies.")
    # Convert RCA results to dicts if needed
    def to_dict_safe(obj):
        if hasattr(obj, 'dict'):
            return obj.dict()
        elif hasattr(obj, '__dict__'):
            return dict(obj.__dict__)
        return obj
    rca_results = [to_dict_safe(r) for r in rca_results]
    for anomaly in anomalies:
        if 'rca' in anomaly:
            anomaly['rca'] = to_dict_safe(anomaly['rca'])
    subject = "[GCP Log Monitor] Anomalies Detected & RCA Report"
    body = f"""
    <h2>Anomalies Detected</h2>
    <ul>
    """
    for idx, anomaly in enumerate(anomalies, 1):
        log = anomaly.get('log', {})
        detection = anomaly.get('detection', {})
        body += f"<li><b>Log {idx}:</b> Severity: {log.get('severity', 'N/A')}, Message: {log.get('message', log.get('json_payload', {}).get('message', ''))}<br>"
        body += f"Detection: {detection.get('reason', 'N/A')}" \
            if 'reason' in detection else ''
        if 'rca' in anomaly:
            rca = anomaly['rca']
            body += f"<br><b>Root Cause:</b> {rca.get('root_cause', 'N/A')}<br>"
            body += f"<b>Impact:</b> {rca.get('impact', 'N/A')}<br>"
            body += f"<b>Remediation:</b> {rca.get('remediation', 'N/A')}<br>"
        body += "</li>"
    body += "</ul>"
    if rca_results:
        body += "<h3>RCA Summary</h3><ul>"
        for rca in rca_results:
            body += f"<li><b>Root Cause:</b> {rca.get('root_cause', 'N/A')}<br>"
            body += f"<b>Impact:</b> {rca.get('impact', 'N/A')}<br>"
            body += f"<b>Remediation:</b> {rca.get('remediation', 'N/A')}</li>"
        body += "</ul>"
    msg = MIMEMultipart()
    msg['From'] = formataddr(("GCP Log Monitor", SMTP_SENDER))
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_SENDER, recipient, msg.as_string())
        print(f"[EMAIL] Alert email sent successfully to {recipient}.")
    except Exception as e:
        print(f"[EMAIL] Error sending alert email: {e}")
        raise 