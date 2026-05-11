from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


async def send_verification_email(email: str, name: str, token: str) -> bool:
    verify_url = f"{settings.frontend_url}/verify-email?token={token}"
    body = f"""
    <h2>Welcome to GEOCopilot, {name}!</h2>
    <p>Please verify your email address by clicking the link below:</p>
    <a href="{verify_url}" style="background:#6366f1;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">
      Verify Email
    </a>
    <p>This link expires in 24 hours.</p>
    """
    return await _send_email(to_email=email, subject="Verify your GEOCopilot account", html=body)


async def send_password_reset_email(email: str, token: str) -> bool:
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"
    body = f"""
    <h2>Reset your GEOCopilot password</h2>
    <p>Click the link below to reset your password. This link expires in 1 hour.</p>
    <a href="{reset_url}" style="background:#6366f1;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">
      Reset Password
    </a>
    <p>If you didn't request this, ignore this email.</p>
    """
    return await _send_email(to_email=email, subject="Reset your GEOCopilot password", html=body)


async def _send_email(to_email: str, subject: str, html: str) -> bool:
    if not settings.sendgrid_api_key:
        logger.warning(f"SendGrid not configured — skipping email to {to_email}: {subject}")
        return True

    try:
        message = Mail(
            from_email=(settings.email_from, settings.email_from_name),
            to_emails=to_email,
            subject=subject,
            html_content=html,
        )
        sg = SendGridAPIClient(settings.sendgrid_api_key)
        response = sg.send(message)
        return response.status_code in (200, 201, 202)
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
