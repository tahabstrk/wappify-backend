from flask import Blueprint, request, jsonify
import hmac, hashlib, os

bp_webhook = Blueprint("webhook_whatsapp", __name__, url_prefix="/webhook")

VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN", "dev-verify-token")

@bp_webhook.get("/wa")
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge", ""), 200
    return "bad verify token", 403

@bp_webhook.post("/wa")
def receive():
    data = request.get_json(force=True, silent=True) or {}
    # TODO: burada entry -> changes -> value içinden status, message_id, to, timestamp yakala
    # ve DB'ye kaydet (MessageLog tablosu gibi)
    return jsonify({"ok": True})