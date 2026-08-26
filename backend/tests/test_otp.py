"""OTP delivery — ConsoleOTPSender/ResendOTPSender/get_otp_sender. Pure, no
DB. Never hits the real Resend API — httpx.post is monkeypatched."""

import httpx
import pytest

from cohab.services import otp as otp_module
from cohab.services.otp import ConsoleOTPSender, OTPDeliveryFailed, ResendOTPSender, SMTPOTPSender, get_otp_sender


def test_console_sender_logs_the_code(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="cohab.otp"):
        ConsoleOTPSender().send("student@christuniversity.in", "123456")
    assert "123456" in caplog.text
    assert "student@christuniversity.in" in caplog.text


def test_resend_sender_posts_to_resend_api(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_post(url: str, headers: dict, json: dict, timeout: float) -> httpx.Response:
        calls.append({"url": url, "headers": headers, "json": json})
        return httpx.Response(200, json={"id": "email_123"})

    monkeypatch.setattr(otp_module.httpx, "post", fake_post)

    sender = ResendOTPSender(api_key="re_test_key", from_email="onboarding@resend.dev")
    sender.send("student@christuniversity.in", "654321")

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == otp_module.RESEND_API_URL
    assert call["headers"]["Authorization"] == "Bearer re_test_key"
    assert call["json"]["to"] == ["student@christuniversity.in"]
    assert call["json"]["from"] == "onboarding@resend.dev"
    assert "654321" in call["json"]["html"]


def test_resend_sender_raises_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, headers: dict, json: dict, timeout: float) -> httpx.Response:
        return httpx.Response(422, text="invalid recipient")

    monkeypatch.setattr(otp_module.httpx, "post", fake_post)

    sender = ResendOTPSender(api_key="re_test_key", from_email="onboarding@resend.dev")
    with pytest.raises(OTPDeliveryFailed):
        sender.send("student@christuniversity.in", "111111")


def test_resend_sender_raises_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, headers: dict, json: dict, timeout: float) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(otp_module.httpx, "post", fake_post)

    sender = ResendOTPSender(api_key="re_test_key", from_email="onboarding@resend.dev")
    with pytest.raises(OTPDeliveryFailed):
        sender.send("student@christuniversity.in", "222222")


def test_smtp_sender_sends_via_smtplib(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = {}

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            sent["host"], sent["port"] = host, port

        def __enter__(self) -> "FakeSMTP":
            return self

        def __exit__(self, *exc: object) -> None:
            pass

        def starttls(self) -> None:
            sent["starttls"] = True

        def login(self, user: str, password: str) -> None:
            sent["user"], sent["password"] = user, password

        def sendmail(self, from_addr: str, to_addrs: list, msg: str) -> None:
            sent["from"], sent["to"], sent["msg"] = from_addr, to_addrs, msg

    monkeypatch.setattr(otp_module.smtplib, "SMTP", FakeSMTP)

    sender = SMTPOTPSender(host="smtp.gmail.com", port=587, user="bot@gmail.com", password="app-pw", from_email="bot@gmail.com")
    sender.send("student@christuniversity.in", "999999")

    assert sent["host"] == "smtp.gmail.com"
    assert sent["to"] == ["student@christuniversity.in"]
    assert "999999" in sent["msg"]


def test_smtp_sender_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            pass

        def __enter__(self) -> "FakeSMTP":
            raise OSError("connection refused")

        def __exit__(self, *exc: object) -> None:
            pass

    monkeypatch.setattr(otp_module.smtplib, "SMTP", FakeSMTP)

    sender = SMTPOTPSender(host="smtp.gmail.com", port=587, user="bot@gmail.com", password="app-pw", from_email="bot@gmail.com")
    with pytest.raises(OTPDeliveryFailed):
        sender.send("student@christuniversity.in", "888888")


def test_get_otp_sender_defaults_to_console_when_nothing_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(otp_module, "RESEND_API_KEY", None)
    monkeypatch.setattr(otp_module, "SMTP_HOST", None)
    assert isinstance(get_otp_sender(), ConsoleOTPSender)


def test_get_otp_sender_uses_resend_when_api_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(otp_module, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(otp_module, "SMTP_HOST", None)
    monkeypatch.setattr(otp_module, "OTP_SENDER_EMAIL", "onboarding@resend.dev")
    sender = get_otp_sender()
    assert isinstance(sender, ResendOTPSender)
    assert sender._from_email == "onboarding@resend.dev"


def test_get_otp_sender_prefers_smtp_over_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(otp_module, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(otp_module, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(otp_module, "SMTP_USER", "bot@gmail.com")
    monkeypatch.setattr(otp_module, "SMTP_PASSWORD", "app-pw")
    assert isinstance(get_otp_sender(), SMTPOTPSender)
