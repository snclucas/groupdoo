"""Email delivery abstraction for Groupdoo."""
from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
import smtplib
from typing import Iterable, Optional, Sequence


class EmailSendError(RuntimeError):
    """Raised when an email cannot be sent."""


@dataclass
class EmailConfig:
    backend: str
    from_address: str
    smtp_host: str
    smtp_port: int
    smtp_username: Optional[str]
    smtp_password: Optional[str]
    smtp_use_tls: bool
    smtp_use_ssl: bool
    smtp_timeout: int
    fail_silently: bool
    subject_prefix: str


class EmailClient:
    """Send emails using configured backend (console or SMTP)."""

    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    def send_email(
        self,
        *,
        to_addrs: Sequence[str] | str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc_addrs: Sequence[str] | str | None = None,
        bcc_addrs: Sequence[str] | str | None = None,
        reply_to: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        """Send an email with optional HTML alternative."""
        to_list = _normalize_recipients(to_addrs)
        if not to_list:
            raise ValueError("to_addrs must include at least one recipient")

        cc_list = _normalize_recipients(cc_addrs)
        bcc_list = _normalize_recipients(bcc_addrs)
        message = self._build_message(
            to_list=to_list,
            cc_list=cc_list,
            bcc_list=bcc_list,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            reply_to=reply_to,
            headers=headers or {},
        )

        try:
            if self._config.backend == "console":
                _print_to_console(message)
                return
            if self._config.backend == "smtp":
                self._send_via_smtp(message, to_list + cc_list + bcc_list)
                return
            raise ValueError(f"Unsupported email backend: {self._config.backend}")
        except Exception as exc:  # pragma: no cover - transport errors are environment-specific
            if self._config.fail_silently:
                return
            raise EmailSendError(str(exc)) from exc

    def _build_message(
        self,
        *,
        to_list: Sequence[str],
        cc_list: Sequence[str],
        bcc_list: Sequence[str],
        subject: str,
        body_text: str,
        body_html: Optional[str],
        reply_to: Optional[str],
        headers: dict[str, str],
    ) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._config.from_address
        message["To"] = ", ".join(to_list)
        if cc_list:
            message["Cc"] = ", ".join(cc_list)
        if reply_to:
            message["Reply-To"] = reply_to
        message["Subject"] = f"{self._config.subject_prefix} {subject}"

        for key, value in headers.items():
            message[key] = value

        message.set_content(body_text)
        if body_html:
            message.add_alternative(body_html, subtype="html")
        return message

    def _send_via_smtp(self, message: EmailMessage, recipients: Sequence[str]) -> None:
        import ssl

        # Create SSL context
        context = ssl.create_default_context()

        if self._config.smtp_use_ssl:
            # SSL/TLS connection from the start (port 465)
            smtp_class = smtplib.SMTP_SSL
            kwargs = {"context": context}
        else:
            # STARTTLS connection (port 587 or 25)
            smtp_class = smtplib.SMTP
            kwargs = {}

        with smtp_class(
            self._config.smtp_host,
            self._config.smtp_port,
            timeout=self._config.smtp_timeout,
            **kwargs
        ) as server:
            if self._config.smtp_use_tls and not self._config.smtp_use_ssl:
                # STARTTLS: upgrade connection to TLS
                server.starttls(context=context)
            if self._config.smtp_username:
                server.login(self._config.smtp_username, self._config.smtp_password or "")
            server.send_message(message, to_addrs=list(recipients))


def build_email_config(config_obj) -> EmailConfig:
    """Create EmailConfig from an app config object."""
    return EmailConfig(
        backend=config_obj.EMAIL_BACKEND,
        from_address=config_obj.EMAIL_FROM,
        smtp_host=config_obj.EMAIL_SMTP_HOST,
        smtp_port=config_obj.EMAIL_SMTP_PORT,
        smtp_username=config_obj.EMAIL_SMTP_USERNAME,
        smtp_password=config_obj.EMAIL_SMTP_PASSWORD,
        smtp_use_tls=config_obj.EMAIL_SMTP_USE_TLS,
        smtp_use_ssl=config_obj.EMAIL_SMTP_USE_SSL,
        smtp_timeout=config_obj.EMAIL_SMTP_TIMEOUT,
        fail_silently=config_obj.EMAIL_FAIL_SILENTLY,
        subject_prefix=config_obj.EMAIL_SUBJECT_PREFIX,
    )


def _normalize_recipients(value: Sequence[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [addr.strip() for addr in value.split(",") if addr.strip()]
    return [addr.strip() for addr in value if addr.strip()]


def _print_to_console(message: EmailMessage) -> None:
    print("\n--- EMAIL (console backend) ---")
    print(message.as_string())
    print("--- END EMAIL ---\n")

