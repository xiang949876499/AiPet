def test_wecom_client_returns_token_from_cache():
    from core.wecom_client import WeComClient

    calls = []

    def fetch_token(corp_id: str, app_secret: str):
        calls.append((corp_id, app_secret))
        return {"access_token": "abc", "expires_in": 7200}

    client = WeComClient(corp_id="cid", app_secret="sec", agent_id="1000001", token_fetcher=fetch_token)

    assert client.get_access_token() == "abc"
    assert client.get_access_token() == "abc"
    assert calls == [("cid", "sec")]


def test_wecom_client_refuses_without_credentials():
    from core.wecom_client import WeComClient

    client = WeComClient(corp_id="", app_secret="", agent_id="1000001")

    assert client.get_access_token() is None


def test_wecom_client_sends_internal_text_with_injected_http():
    from core.wecom_client import WeComClient

    posts = []

    def fetch_token(corp_id: str, app_secret: str):
        return {"access_token": "abc", "expires_in": 7200}

    def post_json(url: str, payload: dict):
        posts.append((url, payload))
        return {"errcode": 0, "errmsg": "ok"}

    client = WeComClient(
        corp_id="cid",
        app_secret="sec",
        agent_id="1000001",
        token_fetcher=fetch_token,
        post_json=post_json,
    )

    result = client.send_internal_text("wang", "请跟进豆豆的洗护提醒")

    assert result == {"errcode": 0, "errmsg": "ok"}
    assert "access_token=abc" in posts[0][0]
    assert posts[0][1]["touser"] == "wang"
    assert posts[0][1]["agentid"] == 1000001
    assert posts[0][1]["text"]["content"] == "请跟进豆豆的洗护提醒"
