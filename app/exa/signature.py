from __future__ import annotations

import hashlib
import hmac
import time


def verify_webhook_signature(
    raw_body: bytes | str,
    signature_header: str | None,
    webhook_secret: str,
    *,
    max_age_seconds: int = 300,
    reject_stale: bool = True,
) -> bool:
    """
    Verify Exa `Exa-Signature` header (HMAC-SHA256 over `{timestamp}.{raw_body}`).

    Spec: https://docs.exa.ai/websets/api/webhooks/verifying-signatures
    """
    if not webhook_secret or not signature_header:
        return False

    payload = raw_body.decode("utf-8") if isinstance(raw_body, bytes) else raw_body

    try:
        pairs = [p.split("=", 1) for p in signature_header.split(",")]
        timestamp: str | None = None
        signatures: list[str] = []
        for key, value in pairs:
            key = key.strip()
            if key == "t":
                timestamp = value
            elif key == "v1":
                signatures.append(value)
        if not timestamp or not signatures:
            return False

        if reject_stale:
            ts = int(timestamp)
            if abs(int(time.time()) - ts) > max_age_seconds:
                return False

        signed_payload = f"{timestamp}.{payload}"
        expected = hmac.new(
            webhook_secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return any(hmac.compare_digest(expected, sig) for sig in signatures)
    except (ValueError, UnicodeDecodeError):
        return False
