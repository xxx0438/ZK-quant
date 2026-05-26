"""Echo API client. Used by `echo-cli submit` and `echo-cli verify`."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

import httpx

from echo_quant.exceptions import ApiError

DEFAULT_BASE = os.getenv("ECHO_API_URL", "https://api.echo.ai")

class EchoClient:
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE, timeout: float = 30.0):
        if not api_key.startswith(("echo_sk_live_", "echo_sk_test_")):
            raise ValueError("Invalid api_key format (must start with echo_sk_live_ or echo_sk_test_)")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._client.close()

    # ─── Quant Marketplace ───

    def me(self) -> dict:
        """Get the current quant profile (or raise 403 if not registered)."""
        return self._request("GET", "/v1/quant/models")

    def get_upload_url(self, proposed_model_id: str, artifact_type: str) -> dict:
        return self._request(
            "POST",
            "/v1/quant/models/upload-url",
            json={"proposed_model_id": proposed_model_id, "artifact_type": artifact_type},
        )

    def upload_file(self, upload_url: str, file_path: Path) -> None:
        with file_path.open("rb") as f:
            r = httpx.put(upload_url, content=f.read(),
                          headers={"content-type": "application/octet-stream"},
                          timeout=300.0)
        if r.status_code not in (200, 201):
            raise ApiError(r.status_code, "upload_failed", f"S3 PUT failed: {r.text[:200]}")

    def submit_model(self, **kwargs) -> dict:
        return self._request("POST", "/v1/quant/models/submit", json=kwargs)

    def get_cert(self, cert_id: str) -> dict:
        return self._request("GET", f"/v1/certs/{cert_id}")

    def list_my_models(self) -> dict:
        return self._request("GET", "/v1/quant/models")

    def earnings(self) -> dict:
        return self._request("GET", "/v1/quant/earnings")

    # ─── Internal ───

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            r = self._client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.HTTPError as e:
            raise ApiError(0, "network_error", str(e)) from e

        if r.status_code >= 400:
            try:
                body = r.json()
                err = body.get("error", {})
                raise ApiError(
                    r.status_code,
                    err.get("code", "unknown"),
                    err.get("message", r.text[:200]),
                    err.get("hint"),
                )
            except ValueError:
                raise ApiError(r.status_code, "unknown", r.text[:200])

        try:
            return r.json()
        except ValueError:
            return {"raw": r.text}
