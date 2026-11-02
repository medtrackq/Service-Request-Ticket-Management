"""Plain-text e-mail delivery over SMTP (STARTTLS or implicit TLS)."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.config import get_settings


class EmailNotConfigured(Exception):
    pass


def smtp_configured() -> bool:
    return bool(get_settings().smtp_host)


def send_email(to: str, subject: str, body: str) -> None:
    s = get_settings()
    if not s.smtp_host:
        raise EmailNotConfigured("SMTP is not configured (BUC_SMTP_HOST)")
    msg = EmailMessage()
    msg["From"] = s.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=s.smtp_from.split("@")[-1].strip(">") or None)
    msg.set_content(body, charset="utf-8")

    context = ssl.create_default_context()
    if s.smtp_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds,
                                                context=context)
    else:
        server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds)
    try:
        server.ehlo()
        if s.smtp_starttls and not s.smtp_ssl:
            server.starttls(context=context)
            server.ehlo()
        if s.smtp_username:
            server.login(s.smtp_username, s.smtp_password)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            pass
