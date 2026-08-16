from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx


JsonPoster = Callable[[str, dict[str, Any]], dict[str, Any]]


class LicenseClient:
    def __init__(self, base_url: str = "https://license.aipet.local", post_json: JsonPoster | None = None):
        self.base_url = base_url.rstrip("/")
        self.post_json = post_json or self._post_json
        self.last_error: str | None = None

    def activate(self, activation_code: str, store_name: str, phone: str, machine_id: str) -> dict[str, Any] | None:
        payload = {
            "activation_code": activation_code,
            "store_name": store_name,
            "phone": phone,
            "machine_id": machine_id,
        }
        try:
            result = self.post_json(f"{self.base_url}/activate", payload)
        except Exception as exc:  # pragma: no cover - network boundary
            self.last_error = str(exc)
            return None
        if result.get("error"):
            self.last_error = str(result["error"])
            return None
        self.last_error = None
        return result

    def heartbeat(self, token: str, machine_id: str) -> dict[str, Any] | None:
        try:
            return self.post_json(f"{self.base_url}/heartbeat", {"token": token, "machine_id": machine_id})
        except Exception as exc:  # pragma: no cover - network boundary
            self.last_error = str(exc)
            return None

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
