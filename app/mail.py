import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template

EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #2563eb; color: white; padding: 20px; border-radius: 8px 8px 0 0; }
        .header h1 { margin: 0; font-size: 22px; }
        .content { background: #f8fafc; padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px; }
        .lead { background: white; padding: 15px; margin: 10px 0; border-radius: 6px; border-left: 4px solid #2563eb; }
        .lead h3 { margin: 0 0 5px 0; font-size: 16px; }
        .lead p { margin: 5px 0; color: #64748b; font-size: 14px; }
        .lead a { color: #2563eb; text-decoration: none; }
        .footer { margin-top: 20px; font-size: 12px; color: #94a3b8; text-align: center; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; margin-left: 8px; }
        .badge-new { background: #dcfce7; color: #166534; }
        .badge-job { background: #fef3c7; color: #92400e; }
        .badge-news { background: #dbeafe; color: #1e40af; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📡 LeadRadar Daily Report</h1>
        <p>{{ date }} — {{ lead_count }} new leads found</p>
    </div>
    <div class="content">
        {% for lead in leads %}
        <div class="lead">
            <h3>
                {{ lead.title }}
                <span class="badge badge-{{ lead.badge }}">{{ lead.badge }}</span>
            </h3>
            <p><strong>{{ lead.company }}</strong> — {{ lead.location }}</p>
            <p>{{ lead.description }}</p>
            {% if lead.url and lead.url != '#' %}
            <p><a href="{{ lead.url }}">View source →</a></p>
            {% endif %}
        </div>
        {% endfor %}
        
        {% if leads|length == 0 %}
        <p style="text-align: center; color: #94a3b8; padding: 20px;">No new leads today. Your sources are being monitored.</p>
        {% endif %}
        
        <div class="footer">
            <p>You're receiving this because you signed up for LeadRadar.</p>
            <p><a href="{{ dashboard_url }}">View Dashboard</a></p>
        </div>
    </div>
</body>
</html>
"""

def send_daily_report(to_email: str, leads: list, dashboard_url: str = "#"):
    """Send daily email report via SMTP (Gmail/Resend/etc)"""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    
    if not smtp_user or not smtp_pass:
        print("SMTP not configured. Would send to", to_email)
        return False
    
    try:
        template = Template(EMAIL_TEMPLATE)
        html = template.render(
            leads=leads,
            lead_count=len(leads),
            date=__import__('datetime').datetime.now().strftime("%B %d, %Y"),
            dashboard_url=dashboard_url
        )
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"LeadRadar Daily — {len(leads)} New Leads"
        msg['From'] = smtp_user
        msg['To'] = to_email
        
        msg.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False
