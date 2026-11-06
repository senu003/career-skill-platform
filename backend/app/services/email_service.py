import os
import smtplib
import logging
from email.message import EmailMessage
from typing import Optional

logger = logging.getLogger(__name__)


def is_production() -> bool:
    """Return True if running in production environment."""
    env = (
        os.getenv("ENVIRONMENT")
        or os.getenv("APP_ENV")
        or os.getenv("NODE_ENV")
        or "development"
    ).strip().lower()
    return env in ("production", "prod")


def is_secure_email_available() -> bool:
    """
    Check if a secure email delivery provider is configured.
    Supports standard SMTP configuration with TLS/SSL, or explicit enablement flag.
    """
    if os.getenv("SECURE_EMAIL_DELIVERY_ENABLED", "").strip().lower() in ("1", "true", "yes"):
        return True

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    if not smtp_host:
        return False

    require_auth = os.getenv("SMTP_REQUIRE_AUTH", "1").strip().lower() in ("1", "true", "yes")
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()

    if require_auth and not (smtp_user and smtp_pass):
        return False

    return True


def is_password_reset_enabled() -> bool:
    """
    Password reset policy:
    In production: disabled unless secure email delivery is configured.
    In development/testing: enabled (tokens logged out-of-band for local dev).
    """
    if is_production():
        return is_secure_email_available()
    return True


def send_password_reset_email(to_email: str, raw_token: str, base_url: Optional[str] = None) -> bool:
    """
    Deliver password reset token via out-of-band secure email.
    Never exposes raw tokens in responses or non-audit error messages.
    """
    if not is_secure_email_available():
        logger.warning("Attempted to send password reset email, but secure email delivery is not available.")
        return False

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM_EMAIL", smtp_user or "noreply@career-intelligence.internal").strip()
    use_tls = os.getenv("SMTP_USE_TLS", "1").strip().lower() in ("1", "true", "yes")

    app_url = (base_url or os.getenv("FRONTEND_URL", "http://localhost:5173")).rstrip("/")
    reset_link = f"{app_url}/login?token={raw_token}"

    msg = EmailMessage()
    msg["Subject"] = "Password Reset Request - Career Skill Intelligence Platform"
    msg["From"] = smtp_from
    msg["To"] = to_email

    msg.set_content(
        f"Hello,\n\n"
        f"A password reset was requested for your account.\n"
        f"You can reset your password by opening the following link:\n\n"
        f"{reset_link}\n\n"
        f"This link will expire in 15 minutes.\n"
        f"If you did not request a password reset, please ignore this email.\n"
    )

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            if use_tls:
                server.starttls()

        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)

        server.send_message(msg)
        server.quit()
        logger.info("Password reset email successfully sent out-of-band.")
        return True
    except Exception as exc:
        logger.error("Failed to send password reset email: %s", exc)
        return False

