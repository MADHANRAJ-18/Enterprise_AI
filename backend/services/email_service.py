from __future__ import annotations

import os
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class BaseEmailProvider(ABC):
    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        pass


class ConsoleEmailProvider(BaseEmailProvider):
    def __init__(self, from_email: str = "notifications@enterprise-ai.internal"):
        self.from_email = from_email

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        logger.info(
            "\n" + "=" * 60 + "\n"
            "[EMAIL SERVICE - CONSOLE DISPATCH]\n"
            f"From:    {self.from_email}\n"
            f"To:      {to_email}\n"
            f"Subject: {subject}\n"
            "-" * 60 + "\n"
            f"{body_text}\n"
            + "=" * 60
        )
        return True


class ResendEmailProvider(BaseEmailProvider):
    def __init__(self, api_key: str, from_email: str):
        self.api_key = api_key
        self.from_email = from_email

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        import urllib.request
        import json

        payload = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "text": body_text,
        }
        if body_html:
            payload["html"] = body_html

        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        def _do_request():
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read()

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _do_request)
            logger.info("Email dispatched successfully to %s via Resend", to_email)
            return True
        except Exception as exc:
            logger.error("Failed to send email to %s via Resend: %s", to_email, exc)
            return False


class SMTPEmailProvider(BaseEmailProvider):
    def __init__(
        self,
        host: str,
        port: int,
        user: Optional[str],
        password: Optional[str],
        from_email: str,
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to_email

        part1 = MIMEText(body_text, "plain", "utf-8")
        msg.attach(part1)
        if body_html:
            part2 = MIMEText(body_html, "html", "utf-8")
            msg.attach(part2)

        def _send_sync():
            clean_pwd = self.password.replace(" ", "") if self.password else self.password
            
            # Primary attempt
            if self.port == 465:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=12)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=12)
                if self.use_tls:
                    server.starttls()
            
            try:
                if self.user and clean_pwd:
                    server.login(self.user, clean_pwd)
                server.sendmail(self.from_email, [to_email], msg.as_string())
            finally:
                try:
                    server.quit()
                except Exception:
                    pass

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _send_sync)
            logger.info("Email dispatched successfully to %s via SMTP (%s:%d)", to_email, self.host, self.port)
            return True
        except Exception as exc:
            logger.error("Failed to send email to %s via SMTP: %s", to_email, exc)
            return False


class BrevoEmailProvider(BaseEmailProvider):
    def __init__(self, api_key: str, from_email: str):
        self.api_key = api_key
        self.from_email = from_email

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        import urllib.request
        import json
        import re

        sender_name = "Enterprise AI"
        sender_email = self.from_email
        match = re.match(r"(.*?)\s*<(.+@.+)>", self.from_email)
        if match:
            sender_name = match.group(1).strip()
            sender_email = match.group(2).strip()

        payload = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "textContent": body_text,
        }
        if body_html:
            payload["htmlContent"] = body_html

        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        def _do_request():
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read()

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _do_request)
            logger.info("Email dispatched successfully to %s via Brevo API", to_email)
            return True
        except Exception as exc:
            logger.error("Failed to send email to %s via Brevo API: %s", to_email, exc)
            return False


class SendGridEmailProvider(BaseEmailProvider):
    def __init__(self, api_key: str, from_email: str):
        self.api_key = api_key
        self.from_email = from_email

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        import urllib.request
        import json
        import re

        sender_name = "Enterprise AI"
        sender_email = self.from_email
        match = re.match(r"(.*?)\s*<(.+@.+)>", self.from_email)
        if match:
            sender_name = match.group(1).strip()
            sender_email = match.group(2).strip()

        content_list = [{"type": "text/plain", "value": body_text}]
        if body_html:
            content_list.append({"type": "text/html", "value": body_html})

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": sender_email, "name": sender_name},
            "subject": subject,
            "content": content_list,
        }

        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        def _do_request():
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read()

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _do_request)
            logger.info("Email dispatched successfully to %s via SendGrid API", to_email)
            return True
        except Exception as exc:
            logger.error("Failed to send email to %s via SendGrid API: %s", to_email, exc)
            return False


_email_service_instance: Optional[BaseEmailProvider] = None


def get_email_service() -> BaseEmailProvider:
    global _email_service_instance
    if _email_service_instance is not None:
        return _email_service_instance

    provider_type = os.getenv("EMAIL_PROVIDER", "").lower().strip()
    api_key = os.getenv("EMAIL_API_KEY", "").strip()
    from_email = os.getenv("EMAIL_FROM", "Enterprise AI <notifications@enterprise-ai.internal>").strip()
    smtp_host = os.getenv("SMTP_HOST", "").strip()

    if provider_type == "sendgrid" or api_key.startswith("SG."):
        logger.info("Configuring SendGrid email provider (from: %s)", from_email)
        _email_service_instance = SendGridEmailProvider(api_key=api_key, from_email=from_email)
    elif provider_type == "brevo" or api_key.startswith("xkeysib-"):
        logger.info("Configuring Brevo (Sendinblue) email provider (from: %s)", from_email)
        _email_service_instance = BrevoEmailProvider(api_key=api_key, from_email=from_email)
    elif provider_type == "resend" or api_key.startswith("re_"):
        logger.info("Configuring Resend email provider (from: %s)", from_email)
        _email_service_instance = ResendEmailProvider(api_key=api_key, from_email=from_email)
    elif provider_type == "smtp" or (smtp_host and not provider_type):
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", None)
        smtp_pass = os.getenv("SMTP_PASSWORD", None)
        use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        logger.info("Configuring SMTP email provider (%s:%d)", smtp_host, smtp_port)
        _email_service_instance = SMTPEmailProvider(
            host=smtp_host,
            port=smtp_port,
            user=smtp_user,
            password=smtp_pass,
            from_email=from_email,
            use_tls=use_tls,
        )
    else:
        logger.info("Configuring Console/Mock email provider (logs to console)")
        _email_service_instance = ConsoleEmailProvider(from_email=from_email)

    return _email_service_instance
