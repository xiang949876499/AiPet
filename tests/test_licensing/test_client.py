def test_license_client_activate_posts_payload():
    from licensing.client import LicenseClient

    calls = []

    def post_json(url: str, payload: dict):
        calls.append((url, payload))
        return {"token": "LICENSE-1", "plan_code": "starter", "expires_at": "2027-06-22T00:00:00"}

    client = LicenseClient(base_url="https://license.example", post_json=post_json)
    result = client.activate("CODE-1", "Store", "13800000000", "machine-1")

    assert result["token"] == "LICENSE-1"
    assert calls == [
        (
            "https://license.example/activate",
            {
                "activation_code": "CODE-1",
                "store_name": "Store",
                "phone": "13800000000",
                "machine_id": "machine-1",
            },
        )
    ]
