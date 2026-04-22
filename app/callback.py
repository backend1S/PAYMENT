from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from app.encryption import load_private_key, decrypt_response
from app.db import get_db_connection
import os, json, base64, re
from urllib.parse import parse_qs
import xml.etree.ElementTree as ET

router = APIRouter()

# =========================
# 🔐 LOAD PRIVATE KEY
# =========================
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PRIVATE_KEY_PATH = os.path.join(BASE_DIR, "keys", "private_key.pem")
private_key = load_private_key(PRIVATE_KEY_PATH)


# =========================
# ✅ ACK XML (ICICI REQUIRED)
# =========================
def ack_xml():
    return """<XML>
<Notification>
<Response>ACK</Response>
</Notification>
</XML>"""


# =========================
# 🔧 CLEAN STRING
# =========================
def clean_string(s: str):
    if not s:
        return s
    return re.sub(r"\s+", "", s.strip())


# =========================
# 🔧 PARSERS
# =========================
def try_json(s):
    try:
        return json.loads(s)
    except:
        return None


def try_xml(s):
    try:
        root = ET.fromstring(s)
        data = {}
        for child in root.iter():
            if child.text:
                data[child.tag] = child.text.strip()
        return data
    except:
        return None


def try_form(s):
    try:
        parsed = parse_qs(s)
        return {k: v[0] for k, v in parsed.items()}
    except:
        return None


def is_base64(s):
    try:
        base64.b64decode(s, validate=True)
        return True
    except:
        return False


# =========================
# 🔍 EXTRACT PAYLOAD (ALL SOURCES)
# =========================
def extract_payload(request, raw_body, headers):

    debug = {}

    # 🔹 BODY
    if raw_body:
        body = raw_body.decode(errors="ignore").strip()
        debug["body"] = body

        # JSON
        j = try_json(body)
        if isinstance(j, dict):
            return j.get("data") or j.get("payload") or body, debug

        # FORM
        f = try_form(body)
        if f:
            return f.get("data") or f.get("payload") or body, debug

        return body, debug

    # 🔹 QUERY PARAM
    if request.query_params:
        qp = dict(request.query_params)
        debug["query"] = qp
        return list(qp.values())[0], debug

    # 🔹 HEADERS
    debug["headers_payload"] = headers.get("payload")
    return headers.get("payload"), debug


# =========================
# 🔓 DECRYPT OR PARSE
# =========================
def parse_icici_payload(enc):

    enc = clean_string(enc)

    # Try decrypt
    if is_base64(enc):
        try:
            return decrypt_response(enc, private_key), "decrypted"
        except Exception as e:
            return {"decrypt_error": str(e)}, "decrypt_failed"

    # Try JSON
    j = try_json(enc)
    if j:
        return j, "json"

    # Try XML
    x = try_xml(enc)
    if x:
        return x, "xml"

    # Try FORM
    f = try_form(enc)
    if f:
        return f, "form"

    return {"raw": enc}, "raw"


# =========================
# 🔁 NORMALIZE
# =========================
def normalize(d):
    return {
        "txn_id": d.get("merchantTranId"),
        "status": d.get("TxnStatus"),
        "rrn": d.get("BankRRN"),
        "amount": d.get("PayerAmount"),
        "payer_name": d.get("PayerName"),
        "payer_vpa": d.get("PayerVA"),
        "payer_mobile": d.get("PayerMobile"),
    }


# =========================
# 🔥 MAIN WEBHOOK
# =========================
@router.post("/api/iciciwebhook")
async def icici_webhook(request: Request):

    print("\n🔥 ===== ICICI CALLBACK HIT =====")

    debug = {}

    try:
        raw_body = await request.body()
        headers = dict(request.headers)

        print("📥 HEADERS:", headers)
        print("📥 RAW BODY:", raw_body)

        debug["headers"] = headers
        debug["raw_body"] = raw_body.decode(errors="ignore")

        # 🔍 Extract payload
        enc, extract_debug = extract_payload(request, raw_body, headers)
        debug["extract_debug"] = extract_debug
        debug["extracted_payload"] = enc

        if not enc:
            print("❌ NO PAYLOAD FOUND")
            return JSONResponse({
                "status": "no_payload",
                "debug": debug,
                "ack": ack_xml()
            })

        print("🔐 EXTRACTED:", enc[:100])

        # 🔓 Decrypt / parse
        parsed, mode = parse_icici_payload(enc)
        debug["parse_mode"] = mode
        debug["parsed"] = parsed

        print("🔓 PARSED:", parsed)

        # Normalize
        normalized = normalize(parsed)
        debug["normalized"] = normalized

        print("✅ NORMALIZED:", normalized)

        # =========================
        # 💾 DB UPDATE
        # =========================
        if normalized["txn_id"]:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE PAYMENT
                    SET PAYMENT_STATUS=?, GATEWAY_PAYMENT_ID=?, UPDATED_AT=GETDATE()
                    WHERE PAYMENT_ID=?
                """,
                normalized["status"],
                normalized["rrn"],
                normalized["txn_id"]
                )

                conn.commit()
                conn.close()

                debug["db"] = "updated"
                print("✅ DB UPDATED")

            except Exception as e:
                debug["db_error"] = str(e)
                print("❌ DB ERROR:", e)

        # =========================
        # RESPONSE
        # =========================
        return JSONResponse({
            "status": "success",
            "ack_xml": ack_xml(),
            "debug": debug
        })

    except Exception as e:
        print("❌ UNEXPECTED ERROR:", e)

        return JSONResponse({
            "status": "error",
            "error": str(e),
            "ack_xml": ack_xml()
        })


# =========================
# 🔓 SWAGGER DECRYPT API
# =========================
class DecryptRequest(BaseModel):
    encrypted_data: str


@router.post("/api/icici/decrypt")
async def decrypt_api(req: DecryptRequest):

    try:
        enc = clean_string(req.encrypted_data)

        decrypted = decrypt_response(enc, private_key)

        return {
            "encrypted": enc,
            "decrypted": decrypted
        }

    except Exception as e:
        return {
            "error": str(e)
        }


# =========================
# 🔓 RAW DECRYPT API
# =========================
@router.post("/api/icici/decrypt-raw")
async def decrypt_raw(request: Request):

    raw = await request.body()

    if not raw:
        return {"error": "no data"}

    try:
        enc = clean_string(raw.decode())
        decrypted = decrypt_response(enc, private_key)

        return decrypted

    except Exception as e:
        return {"error": str(e)}