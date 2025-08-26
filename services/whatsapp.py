import base64, requests
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from config import APP_SECRET
from db.models import WaCredential

KEY = base64.urlsafe_b64encode(APP_SECRET.encode().ljust(32, b"0")[:32])
fernet = Fernet(KEY)

def enc(s: str) -> str: return fernet.encrypt((s or "").encode()).decode()
def dec(s: str) -> str: return fernet.decrypt((s or "").encode()).decode()

def get_creds(db: Session, account_id: int) -> tuple[str | None, str | None]:
    row = db.query(WaCredential).filter(WaCredential.account_id == account_id).first()
    if not row: return None, None
    return row.phone_number_id, dec(row.access_token_encrypted)

def upsert_creds(db: Session, account_id: int, phone_number_id: str, access_token: str, waba_id: str | None = None):
    row = db.query(WaCredential).filter(WaCredential.account_id == account_id).first()
    if row:
        row.phone_number_id = phone_number_id
        row.waba_id = waba_id
        row.access_token_encrypted = enc(access_token)
    else:
        row = WaCredential(account_id=account_id, phone_number_id=phone_number_id,
                           waba_id=waba_id, access_token_encrypted=enc(access_token))
        db.add(row)
    db.commit()

def send_whatsapp_text(account_id: int, phone_e164: str, text: str, timeout=15) -> bool:
    phone_number_id, token = get_creds(db=_db(), account_id=account_id)  # _db() aşağıda
    if not (phone_number_id and token): 
        print("[CloudAPI] credential yok"); return False
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": phone_e164.replace(" ", ""), "type": "text",
               "text": {"preview_url": False, "body": text or ""}}
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if r.status_code in (200, 201): return True
    print("[CloudAPI] Hata:", r.status_code, r.text); return False

def send_whatsapp_template(account_id: int, to_e164: str, name: str, language="tr", variables=None):
    with SessionLocal() as db:
        phone_number_id, token = get_creds(db, account_id)
    if not (phone_number_id and token): return False
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    components = []
    if variables:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": str(v)} for v in variables]
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": to_e164,
        "type": "template",
        "template": {"name": name, "language": {"code": language}, "components": components}
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    return r.ok


# basit session helper (thread-safe)
from db.session import SessionLocal
def _db():
    return SessionLocal()