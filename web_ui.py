import os
import json
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from functools import wraps
import requests
from routes.settings_whatsapp import bp_settings
app.register_blueprint(bp_settings)
from services.whatsapp import send_whatsapp_text

def send_whatsapp_text_cloudapi(phone_e164: str, text: str) -> bool:
    """WhatsApp Business Cloud API ile metin mesajı gönderir (UI açmadan)."""
    settings = load_json(SETTINGS_FILE, {})
    token = settings.get("meta_access_token", "")
    phone_number_id = settings.get("wa_phone_number_id", "")

    if not token or not phone_number_id:
        print("[CloudAPI] Eksik ayar: meta_access_token / wa_phone_number_id")
        return False

    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": (phone_e164 or "").replace(" ", ""),
        "type": "text",
        "text": {"preview_url": False, "body": text or ""}
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code in (200, 201):
            return True
        print("[CloudAPI] Hata:", r.status_code, r.text)
        return False
    except Exception as e:
        print("[CloudAPI] İstisna:", e)
        return False

# -------------------------------------------------
# Flask app
# -------------------------------------------------
app = Flask(__name__, static_folder="wp", static_url_path="/wp")
app.secret_key = "supersecret"  # değiştir

# -------------------------------------------------
# Basit kullanıcı doğrulama (hardcoded)
# -------------------------------------------------
USERNAME = "admin"
PASSWORD = "1234"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        if u == USERNAME and p == PASSWORD:
            session["logged_in"] = True
            return redirect("/1.anasayfa.html")
        return "Hatalı giriş", 401
    return send_from_directory("wp", "login-paneli.html")

@app.route("/logout")
def logout_page():
    session.clear()
    return redirect("/login")

# -------------------------------------------------
# Veri dosyaları
# -------------------------------------------------
DATA_DIR = "data"
LEADS_FILE = os.path.join(DATA_DIR, "leads.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
TEMPLATES_FILE = os.path.join(DATA_DIR, "templates.json")
SCHEDULES_FILE = os.path.join(DATA_DIR, "schedules.json")

os.makedirs(DATA_DIR, exist_ok=True)

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# -------------------------------------------------
# Dummy driver (manuel Chrome kullanacağın için)
# -------------------------------------------------
driver = None   # WhatsApp Web’i sen açacaksın
driver_lock = threading.Lock()

# -------------------------------------------------
# Kuyruk ve işçi thread
# -------------------------------------------------
send_queue = []
stop_flags = {"sender": False, "autoreply": True}

def sender_worker():
    global send_queue
    while not stop_flags["sender"]:
        job = None
        with driver_lock:
            if send_queue:
                job = send_queue.pop(0)
        if not job:
            time.sleep(2); continue

        account_id = job.get("account_id") or 1
        phone = (job.get("phone") or "").strip()
        msg   = job.get("msg") or ""

        if phone.startswith("0") and len(phone) >= 10:
            phone = "+90" + phone[1:]
        phone = phone.replace(" ", "")

        ok = send_whatsapp_text(account_id, phone, msg)
        print(f"[Kuyruk][acc={account_id}] {'OK' if ok else 'FAIL'} {phone} -> {msg[:60]}")
        time.sleep(0.35)


def _start_sending_if_needed():
    if not getattr(_start_sending_if_needed, "started", False):
        stop_flags["sender"] = False
        t = threading.Thread(target=sender_worker, daemon=True)
        t.start()
        _start_sending_if_needed.started = True

# -------------------------------------------------
# API: Kişiler / Gruplar
# -------------------------------------------------
@app.route("/api/leads")
@login_required
def api_leads():
    return jsonify(load_json(LEADS_FILE, []))

@app.route("/api/categories")
@login_required
def api_categories():
    leads = load_json(LEADS_FILE, [])
    cats = sorted(set(l.get("category") or "" for l in leads if l.get("category")))
    return jsonify(cats)

# -------------------------------------------------
# API: Mesaj gönderme (hemen)
# -------------------------------------------------
@app.route("/api/send_category", methods=["POST"])
@login_required
def api_send_category():
    data = request.json
    cat = data.get("category")
    msg = data.get("customMessage")
    if not cat or not msg:
        return jsonify(ok=False, error="Eksik veri")
    leads = load_json(LEADS_FILE, [])
    targets = [l for l in leads if l.get("category") == cat]
    for l in targets:
        send_queue.append({"phone": l.get("phone"), "msg": msg})
    _start_sending_if_needed()
    return jsonify(ok=True, count=len(targets))

@app.route("/api/send_bulk", methods=["POST"])
@login_required
def api_send_bulk():
    data = request.json
    ids = data.get("ids", [])
    msg = data.get("customMessage")
    if not ids or not msg:
        return jsonify(ok=False, error="Eksik veri")
    leads = load_json(LEADS_FILE, [])
    targets = [l for l in leads if l.get("id") in ids]
    for l in targets:
        send_queue.append({"phone": l.get("phone"), "msg": msg})
    _start_sending_if_needed()
    return jsonify(ok=True, count=len(targets))

# -------------------------------------------------
# API: Zamanlayıcı
# -------------------------------------------------
@app.route("/api/schedules", methods=["GET"])
@login_required
def api_sched_list():
    return jsonify(load_json(SCHEDULES_FILE, []))

@app.route("/api/schedules", methods=["POST"])
@login_required
def api_sched_add():
    rows = load_json(SCHEDULES_FILE, [])
    body = request.json
    new_id = str(int(time.time()))
    body["id"] = new_id
    body["done"] = False
    dt = datetime.strptime(body["when"], "%Y-%m-%dT%H:%M")
    body["due_ts"] = int(dt.timestamp())
    rows.append(body)
    save_json(SCHEDULES_FILE, rows)
    return jsonify(ok=True, id=new_id)

@app.route("/api/schedules", methods=["DELETE"])
@login_required
def api_sched_del():
    rows = load_json(SCHEDULES_FILE, [])
    task_id = request.json.get("id")
    rows = [r for r in rows if r.get("id") != task_id]
    save_json(SCHEDULES_FILE, rows)
    return jsonify(ok=True)

@app.route("/api/schedules/run_now", methods=["POST"])
@login_required
def api_sched_run_now():
    task_id = request.json.get("id")
    rows = load_json(SCHEDULES_FILE, [])
    for r in rows:
        if r.get("id") == task_id:
            # kuyruğa at
            if r.get("target") == "category":
                cat = r.get("category")
                leads = load_json(LEADS_FILE, [])
                for l in leads:
                    if l.get("category") == cat:
                        send_queue.append({"phone": l.get("phone"), "msg": r.get("message")})
            elif r.get("target") == "ids":
                leads = load_json(LEADS_FILE, [])
                for l in leads:
                    if l.get("id") in r.get("ids", []):
                        send_queue.append({"phone": l.get("phone"), "msg": r.get("message")})
            _start_sending_if_needed()
            return jsonify(ok=True)
    return jsonify(ok=False, error="Bulunamadı")

# -------------------------------------------------
# Worker: Zamanlı görevleri kontrol et
# -------------------------------------------------
def schedule_worker():
    while True:
        now = int(time.time())
        rows = load_json(SCHEDULES_FILE, [])
        changed = False
        for r in rows:
            if not r.get("done") and now >= r.get("due_ts"):
                # Kuyruğa at
                if r.get("target") == "category":
                    cat = r.get("category")
                    leads = load_json(LEADS_FILE, [])
                    for l in leads:
                        if l.get("category") == cat:
                            send_queue.append({"phone": l.get("phone"), "msg": r.get("message")})
                elif r.get("target") == "ids":
                    leads = load_json(LEADS_FILE, [])
                    for l in leads:
                        if l.get("id") in r.get("ids", []):
                            send_queue.append({"phone": l.get("phone"), "msg": r.get("message")})
                r["done"] = True
                changed = True
        if changed:
            save_json(SCHEDULES_FILE, rows)
            _start_sending_if_needed()
        time.sleep(15)

# -------------------------------------------------
# Statik dosyalar (tema)
# -------------------------------------------------
@app.route("/")
def root():
    return redirect("/login")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory("wp", path)

# -------------------------------------------------
# Main
# -------------------------------------------------
if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    stop_flags["sender"] = False
    threading.Thread(target=sender_worker, daemon=True).start()
    threading.Thread(target=schedule_worker, daemon=True).start()
    app.run(host="0.0.0.0", port=8080, debug=True)
