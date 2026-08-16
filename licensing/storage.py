from __future__ import annotations

import json
import os
import secrets
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


PLAN_GRACE_DAYS = {
    "starter": 7,
    "professional": 15,
    "growth": 30,
    "managed": 30,
}


class LicenseStorage:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.getenv("AIPET_LICENSE_FILE") or "data/license.json")

    def save_token(
        self,
        token: str,
        plan_code: str,
        expires_at: str,
        *,
        remaining_ai_calls: int | None = None,
        last_heartbeat_at: str | None = None,
        is_trial: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "token": token,
            "plan_code": plan_code,
            "expires_at": expires_at,
            "remaining_ai_calls": remaining_ai_calls,
            "last_heartbeat_at": last_heartbeat_at or datetime.utcnow().isoformat(),
            "is_trial": is_trial,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to temp file then replace to prevent corruption on crash
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".json", prefix=".license_", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        return payload

    def get_token(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def create_trial_token(self, now: datetime | None = None) -> dict[str, Any] | None:
        """Create a 14-day growth trial token. Returns None if a paid non-trial license already exists."""
        existing = self.get_token()
        if existing and not existing.get("is_trial") and not str(existing.get("token", "")).startswith("TRIAL-"):
            return None  # Guard: don't overwrite a paid license
        current = now or datetime.utcnow()
        token = f"TRIAL-{int(current.timestamp())}-{secrets.token_hex(4)}"
        return self.save_token(
            token=token,
            plan_code="growth",
            expires_at=(current + timedelta(days=14)).isoformat(),
            remaining_ai_calls=None,
            last_heartbeat_at=current.isoformat(),
            is_trial=True,
        )

    def is_trial_token(self, token: str | None = None) -> bool:
        payload = self.get_token()
        if payload is None:
            return False
        if token is not None and payload.get("token") != token:
            return False
        return bool(payload.get("is_trial")) or str(payload.get("token", "")).startswith("TRIAL-")

    def offline_grace_days(self, plan_code: str | None = None) -> int:
        payload = self.get_token() or {}
        plan = plan_code or payload.get("plan_code") or "starter"
        return PLAN_GRACE_DAYS.get(str(plan), PLAN_GRACE_DAYS["starter"])

    def offline_remaining_days(self, now: datetime | None = None) -> int:
        payload = self.get_token()
        if payload is None:
            return 0
        last_heartbeat_at = _parse_datetime(payload.get("last_heartbeat_at"))
        if last_heartbeat_at is None:
            return self.offline_grace_days(payload.get("plan_code"))
        current = now or datetime.utcnow()
        used_days = max((current - last_heartbeat_at).days, 0)
        return max(self.offline_grace_days(payload.get("plan_code")) - used_days, 0)

    def is_grace_period_ok(self, now: datetime | None = None) -> bool:
        payload = self.get_token()
        if payload is None:
            return False
        if self.is_trial_token():
            return self._not_expired(payload, now)
        return self.offline_remaining_days(now) > 0 and self._not_expired(payload, now)

    def get_status(self, now: datetime | None = None) -> dict[str, Any]:
        payload = self.get_token()
        if payload is None:
            return {
                "mode": "inactive",
                "plan_code": "none",
                "allowed_features": downgraded_features(),
                "offline_remaining_days": 0,
            }
        active = self._not_expired(payload, now) and (self.is_trial_token() or self.is_grace_period_ok(now))
        return {
            **payload,
            "mode": "active" if active else "downgraded",
            "offline_remaining_days": self.offline_remaining_days(now),
            "allowed_features": full_features() if active else downgraded_features(),
        }

    def _not_expired(self, payload: dict[str, Any], now: datetime | None = None) -> bool:
        expires_at = _parse_datetime(payload.get("expires_at"))
        if expires_at is None:
            return False
        return expires_at >= (now or datetime.utcnow())


def full_features() -> dict[str, bool]:
    return {
        "customer_files": True,
        "manual_script_generation": True,
        "auto_send": True,
        "dashboard_refresh": True,
        "content_generation": True,
    }


def downgraded_features() -> dict[str, bool]:
    return {
        "customer_files": True,
        "manual_script_generation": True,
        "auto_send": False,
        "dashboard_refresh": False,
        "content_generation": False,
    }


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
