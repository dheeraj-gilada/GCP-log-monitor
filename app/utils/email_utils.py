import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import json

SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
SMTP_SENDER = os.getenv('SMTP_SENDER', SMTP_USER)


def send_alert_email(recipient, anomalies, rca_results):
    print(f"[EMAIL] Attempting to send alert email to {recipient} with {len(rca_results)} RCA groups.")
    subject = "[GCP Log Monitor] Incident Analysis & RCA Report"
    body = f"<h2>Incident Analysis & RCA Report</h2><p>Total Reports: <b>{len(rca_results)}</b></p>"
    for idx, rca in enumerate(rca_results, 1):
        # Defensive: fallback for missing fields
        title = rca.get('title', f'Report #{idx}')
        severity = rca.get('severity', 'N/A')
        affected_services = ', '.join(rca.get('affected_services', []))
        issue_summary = rca.get('issue_summary', 'N/A')
        root_cause = rca.get('root_cause_analysis', 'N/A')
        impact = rca.get('impact_assessment', 'N/A')
        actions = rca.get('suggested_actions', [])
        anomaly_count = rca.get('anomaly_count', 'N/A')
        log_index_range = rca.get('log_index_range', {})
        confidence = rca.get('confidence_score', 'N/A')
        timeline = rca.get('timeline', [])
        report_html = f"""
        <div style='border:1px solid #e5e7eb; border-radius:8px; margin-bottom:1.5em; padding:1em; background:#f9fafb;'>
          <h3 style='margin-top:0;'>Report #{idx}: {title}</h3>
          <b>Severity:</b> <span style='color:{'red' if severity in ['HIGH','CRITICAL'] else 'orange' if severity=='MEDIUM' else 'green'}'>{severity}</span><br>
          <b>Affected Services:</b> {affected_services}<br>
          <b>Summary:</b> {issue_summary}<br>
          <b>Root Cause:</b> {root_cause}<br>
          <b>Impact:</b> {impact}<br>
          <b>Suggested Actions:</b> <ul>{''.join(f'<li>{a}</li>' for a in actions)}</ul>
          <b>Anomaly Count:</b> {anomaly_count}<br>
          <b>Log Index Range:</b> {log_index_range.get('start','?')} - {log_index_range.get('end','?')}<br>
          <b>Confidence Score:</b> {confidence}<br>
        """
        # Timeline table
        if timeline:
            report_html += "<b>Timeline:</b><table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;margin-top:0.5em;margin-bottom:0.5em;'>"
            report_html += "<tr style='background:#f3f4f6;'><th>Index</th><th>Timestamp</th><th>Service/Component</th><th>Message</th><th>Anomaly?</th></tr>"
            for entry in timeline:
                report_html += f"<tr><td>{entry.get('log_index','')}</td><td>{entry.get('timestamp','')}</td><td>{entry.get('service_or_component','')}</td><td>{entry.get('message','')}</td><td>{'✅' if entry.get('is_anomaly') else ''}</td></tr>"
            report_html += "</table>"
        report_html += "</div>"
        body += report_html
    body += "<p>--<br>GCP Log Monitoring System</p>"
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