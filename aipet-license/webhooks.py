def handle_payment_webhook(payload: dict) -> dict:
    return {"accepted": True, "event": payload.get("event", "unknown")}
