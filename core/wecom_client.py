from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx


TokenFetcher = Callable[[str, str], dict[str, Any]]
JsonPoster = Callable[[str, dict[str, Any]], dict[str, Any]]
JsonGetter = Callable[[str, dict[str, Any]], dict[str, Any]]


class WeComClient:
    token_url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    message_send_url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
    oauth_userinfo_url = "https://qyapi.weixin.qq.com/cgi-bin/auth/getuserinfo"
    user_detail_url = "https://qyapi.weixin.qq.com/cgi-bin/user/get"

    def __init__(
        self,
        corp_id: str,
        app_secret: str,
        agent_id: str = "",
        token_fetcher: TokenFetcher | None = None,
        post_json: JsonPoster | None = None,
        get_json: JsonGetter | None = None,
    ):
        self.corp_id = corp_id
        self.app_secret = app_secret
        self.agent_id = agent_id
        self.token_fetcher = token_fetcher or self._fetch_token
        self.post_json = post_json or self._post_json
        self.get_json = get_json or self._get_json
        self._cached_token: str | None = None
        self._token_expires_at = 0.0
        self.last_error: str | None = None

    def get_access_token(self) -> str | None:
        if not self.corp_id or not self.app_secret:
            self.last_error = "missing wecom credentials"
            return None

        now = time.time()
        if self._cached_token and now < self._token_expires_at:
            return self._cached_token

        try:
            payload = self.token_fetcher(self.corp_id, self.app_secret)
        except Exception as exc:  # pragma: no cover - defensive network boundary
            self.last_error = str(exc)
            return None

        token = payload.get("access_token")
        if not token:
            self.last_error = payload.get("errmsg") or "missing access_token"
            return None

        expires_in = int(payload.get("expires_in") or 7200)
        self._cached_token = str(token)
        self._token_expires_at = now + max(expires_in - 300, 60)
        self.last_error = None
        return self._cached_token

    def send_internal_text(self, to_user: str, content: str) -> dict[str, Any]:
        token = self.get_access_token()
        if not token:
            return {"errcode": -1, "errmsg": self.last_error or "missing access_token"}

        agent_id: int | str = int(self.agent_id) if self.agent_id.isdigit() else self.agent_id
        payload = {
            "touser": to_user,
            "msgtype": "text",
            "agentid": agent_id,
            "text": {"content": content},
            "safe": 0,
        }
        return self.post_json(f"{self.message_send_url}?access_token={token}", payload)

    def get_oauth_userid(self, code: str) -> str | None:
        token = self.get_access_token()
        if not token:
            return None

        payload = self.get_json(self.oauth_userinfo_url, {"access_token": token, "code": code})
        errcode = int(payload.get("errcode") or 0)
        if errcode != 0:
            self.last_error = payload.get("errmsg") or f"wecom oauth error {errcode}"
            return None

        userid = payload.get("UserId") or payload.get("userid")
        if not userid:
            self.last_error = "missing wecom oauth UserId"
            return None

        self.last_error = None
        return str(userid)

    def get_user_detail(self, userid: str) -> dict[str, Any]:
        token = self.get_access_token()
        if not token:
            return {}

        payload = self.get_json(self.user_detail_url, {"access_token": token, "userid": userid})
        errcode = int(payload.get("errcode") or 0)
        if errcode != 0:
            self.last_error = payload.get("errmsg") or f"wecom user detail error {errcode}"
            return {}

        self.last_error = None
        return payload

    def _fetch_token(self, corp_id: str, app_secret: str) -> dict[str, Any]:
        response = httpx.get(
            self.token_url,
            params={"corpid": corp_id, "corpsecret": app_secret},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        response = httpx.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
