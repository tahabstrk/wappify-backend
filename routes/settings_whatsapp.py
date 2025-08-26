from flask import Blueprint, request, jsonify, session
from db.session import SessionLocal
from services.whatsapp import upsert_creds, get_creds

bp_settings = Blueprint("settings_whatsapp", __name__, url_prefix="/api/settings/whatsapp")

def current_account_id():
    return session.get("account_id", 1)  # gerçek login varsa oradan al

@bp_settings.post("/upsert")
def upsert():
    data = request.get_json(force=True)
    phone_number_id = (data.get("phone_number_id") or "").strip()
    access_token    = (data.get("access_token") or "").strip()
    waba_id         = (data.get("waba_id") or "").strip() or None
    if not phone_number_id or not access_token:
        return jsonify({"ok": False, "error": "Eksik alanlar"}), 400
    with SessionLocal() as db:
        upsert_creds(db, current_account_id(), phone_number_id, access_token, waba_id)
    return jsonify({"ok": True})

@bp_settings.get("/status")
def status():
    with SessionLocal() as db:
        pnid, token = get_creds(db, current_account_id())
    if not pnid: return jsonify({"connected": False})
    masked = "****" + (token[-6:] if token else "")
    return jsonify({"connected": True, "phone_number_id": pnid, "access_token_masked": masked})