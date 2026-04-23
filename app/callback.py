from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from app.encryption import load_private_key, decrypt_response
from app.db import get_db_connection
import os, json, base64, re
from urllib.parse import parse_qs
import xml.etree.ElementTree as ET

router = APIRouter()

# 🔐 Load private key
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PRIVATE_KEY_PATH = os.path.join(BASE_DIR, "keys", "private_key.pem")
private_key = load_private_key(PRIVATE_KEY_PATH)

# 🔁 Toggle this
DEBUG_MODE = False   # 👉 change to False in production


def ack_xml():
    return """<XML>
<Notification>
<Response>ACK</Response>
</Notification>
</XML>"""


def clean(s):
    return re.sub(r"\s+", "", s.strip()) if s else s


def is_base64(s):
    try:
        base64.b64decode(s, validate=True)
        return True
    except:
        return False


def try_json(s):
    try:
        return json.loads(s)
    except:
        return None


def try_form(s):
    try:
        return {k: v[0] for k, v in parse_qs(s).items()}
    except:
        return None


def try_xml(s):
    try:
        root = ET.fromstring(s)
        return {child.tag: child.text for child in root.iter() if child.text}
    except:
        return None


@router.post("/payments/api/iciciwebhook")
async def icici_webhook(request: Request):

    print("\n🔥 ===== ICICI CALLBACK HIT =====")

    debug = {}

    try:
        raw_body = await request.body()
        headers = dict(request.headers)

        debug["headers"] = headers
        debug["raw_body"] = raw_body.decode(errors="ignore")

        print("📥 HEADERS:", headers)
        print("📥 RAW:", raw_body)

        # =========================
        # 🔍 EXTRACT PAYLOAD
        # =========================
        body = raw_body.decode(errors="ignore").strip()
        payload = body

        if not payload:
            payload = list(request.query_params.values())[0] if request.query_params else None

        debug["payload"] = payload

        if not payload:
            return JSONResponse({"status": "no_payload", "debug": debug})

        payload = clean(payload)

        print("🔐 PAYLOAD:", payload[:100])

        # =========================
        # 🔓 DECRYPT / PARSE
        # =========================
        parsed = None

        if is_base64(payload):
            try:
                parsed = decrypt_response(payload, private_key)
                debug["decrypt_mode"] = "base64_decrypted"
            except Exception as e:
                debug["decrypt_error"] = str(e)

        if not parsed:
            parsed = try_json(payload) or try_form(payload) or try_xml(payload) or {"raw": payload}
            debug["fallback_mode"] = "non_encrypted"

        debug["parsed"] = parsed

        print("🔓 PARSED:")
        print(json.dumps(parsed, indent=4))

        # =========================
        # 💾 SAVE CALLBACK
        # =========================
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
            INSERT INTO PAYMENTS_ICICI_CALLBACK (
                MERCHANTID,
                MERCHANTTRANID,
                BANKRRN,
                PAYERNAME,
                PAYERMOBILE,
                PAYERVA,
                PAYERAMOUNT,
                TXNSTATUS,
                TXNINITDATE,
                TXNCOMPLETIONDATE,
                RESPONSECODE,
                RESPCODEDESCRIPTION,
                PAYEEVPA,
                PAYERACCOUNTTYPE,
                CREATED_DATE,
                MODIFIED_DATE
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())
            """,
                parsed.get("merchantId"),
                parsed.get("merchantTranId"),
                parsed.get("BankRRN"),
                parsed.get("PayerName"),
                parsed.get("PayerMobile"),
                parsed.get("PayerVA"),
                parsed.get("PayerAmount"),
                parsed.get("TxnStatus"),
                parsed.get("TxnInitDate"),
                parsed.get("TxnCompletionDate"),
                parsed.get("ResponseCode"),
                parsed.get("RespCodeDescription"),
                parsed.get("PayeeVPA"),
                parsed.get("PayerAccountType")
            )

            conn.commit()
            conn.close()

            debug["callback_saved"] = True

        except Exception as e:
            debug["callback_db_error"] = str(e)

        # =========================
        # 🔁 UPDATE PAYMENT
        # =========================
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            txn_id = parsed.get("merchantTranId")
            status = parsed.get("TxnStatus")
            rrn = parsed.get("BankRRN")

            debug["txn_id"] = txn_id
            debug["status"] = status

            if txn_id:
                cursor.execute("""
                    SELECT PAYMENT_ID, CUSTOMER_NAME, PAYMENT_STATUS
                    FROM PAYMENT WHERE PAYMENT_ID=?
                """, txn_id)

                row = cursor.fetchone()

                if row:
                    debug["customer"] = row[1]

                    if row[2] != "SUCCESS":
                        cursor.execute("""
                        UPDATE PAYMENT
                        SET PAYMENT_STATUS=?, GATEWAY_PAYMENT_ID=?, UPDATED_AT=GETDATE()
                        WHERE PAYMENT_ID=?
                        """,
                            status,
                            rrn,
                            txn_id
                        )

                        debug["payment_updated"] = True
                    else:
                        debug["already_success"] = True
                else:
                    debug["no_payment_found"] = True

            conn.commit()
            conn.close()

        except Exception as e:
            debug["payment_update_error"] = str(e)

        # =========================
        # 🎯 RESPONSE
        # =========================
        if DEBUG_MODE:
            return JSONResponse({
                "status": "debug",
                "debug": debug
            })

        return Response(content=ack_xml(), media_type="application/xml")

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e)
        })