import smtplib
import ssl
from email.message import EmailMessage

from core.config import settings


def send_verification_email(recipient_email: str, recipient_name: str, verification_code: str) -> None:
    subject = "Verify your Jobful email"
    body = (
        f"Hi {recipient_name},\n\n"
        f"Your Jobful verification code is: {verification_code}\n\n"
        f"This code expires in {settings.email_verification_code_minutes} minutes.\n\n"
        "If you did not request this, you can ignore this email."
    )

    if not settings.smtp_host:
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email or settings.smtp_username or "no-reply@jobful.local"
    message["To"] = recipient_email
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls(context=context)
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)