from __future__ import annotations

import hashlib
import hmac
import time

from app.exa.signature import verify_webhook_signature


def _header(payload: str, secret: str, ts: int | None = None) -> str:
    t = str(ts if ts is not None else int(time.time()))
    sig = hmac.new(
        secret.encode("utf-8"),
        f"{t}.{payload}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"t={t},v1={sig}"


def test_verify_accepts_valid_signature():
    secret = "whsec_unit_test"
    payload = '{"hello":"world"}'
    assert verify_webhook_signature(
        payload.encode(),
        _header(payload, secret),
        secret,
        reject_stale=False,
    )


def test_verify_rejects_wrong_secret():
    payload = "{}"
    assert not verify_webhook_signature(
        payload.encode(),
        _header(payload, "good"),
        "bad",
        reject_stale=False,
    )


def test_verify_rejects_tampered_body():
    secret = "s"
    payload = '{"a":1}'
    header = _header(payload, secret)
    assert not verify_webhook_signature(
        b'{"a":2}',
        header,
        secret,
        reject_stale=False,
    )


def test_verify_rejects_stale_timestamp():
    secret = "s"
    payload = "{}"
    old = int(time.time()) - 99999
    assert not verify_webhook_signature(
        payload.encode(),
        _header(payload, secret, ts=old),
        secret,
        reject_stale=True,
    )
