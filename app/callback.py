from fastapi import APIRouter, Request, Response
from app.db import get_db_connection
from app.encryption import load_private_key, decrypt_response
import os, json, time

router = APIRouter()

# 🔐 Load private key once
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PRIVATE_KEY_PATH = os.path.join(BASE_DIR, "keys", "private_key.pem")
private_key = load_private_key(PRIVATE_KEY_PATH)


def safe_get(data, *keys):
    """Try multiple possible keys"""
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def normalize_status(status):
    if not status:
        return "UNKNOWN"

    status = str(status).upper()

    if status in ["SUCCESS", "S", "00"]:
        return "SUCCESS"
    if status in ["FAILURE", "FAILED", "F"]:
        return "FAILED"
    if status in ["PENDING", "INITIATED"]:
        return "PENDING"

    return status


@router.post("/api/iciciwebhook")
async def icici_webhook(request: Request):

    print("\n🔥 ===== ICICI CALLBACK RECEIVED =====")
    start_time = time.time()

    try:
        # =========================
        # 1️⃣ READ RAW BODY
        # =========================
        raw_body = await request.body()
        headers = dict(request.headers)

        print("🔹 HEADERS:", headers)
        print("🔹 RAW LENGTH:", len(raw_body))

        if not raw_body:
            print("⚠️ Empty callback (manual hit)")
            return {"status": "ignored"}

        # =========================
        # 2️⃣ DECODE SAFELY
        # =========================
        try:
            encrypted_payload = raw_body.decode("utf-8").strip()
        except Exception as e:
            print("❌ Decode error:", str(e))
            return {"status": "error", "message": "decode_failed"}

        print("🔐 ENCRYPTED PREVIEW:", encrypted_payload[:100])

        # =========================
        # 3️⃣ DECRYPT SAFELY
        # =========================
        try:
            decrypted = decrypt_response(encrypted_payload, private_key)

            if isinstance(decrypted, str):
                decrypted = json.loads(decrypted)

        except Exception as e:
            print("❌ Decryption failed:", str(e))
            return {"status": "error", "message": "decrypt_failed"}

        print("\n🔓 DECRYPTED CALLBACK:")
        print(json.dumps(decrypted, indent=4))

        # =========================
        # 4️⃣ EXTRACT ALL POSSIBLE FIELDS
        # =========================
        txn_id = safe_get(decrypted, "merchantTranId", "merchantTranID", "txnId")
        status = safe_get(decrypted, "TxnStatus", "status", "txnStatus")
        rrn = safe_get(decrypted, "BankRRN", "rrn", "bankRrn")

        payer_name = safe_get(decrypted, "PayerName", "payerName")
        payer_mobile = safe_get(decrypted, "PayerMobile", "payerMobile")
        payer_vpa = safe_get(decrypted, "PayerVA", "payerVpa")
        amount = safe_get(decrypted, "PayerAmount", "amount")

        response_code = safe_get(decrypted, "ResponseCode", "responseCode")
        response_desc = safe_get(decrypted, "RespCodeDescription", "message")

        status = normalize_status(status)

        print("\n✅ FINAL PARSED:")
        print("TXN ID:", txn_id)
        print("STATUS:", status)
        print("RRN:", rrn)
        print("AMOUNT:", amount)

        if not txn_id:
            print("❌ Missing transaction ID → ignoring")
            return {"status": "error", "message": "invalid_payload"}

        # =========================
        # 5️⃣ UPDATE DATABASE
        # =========================
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE PAYMENT
                SET 
                    PAYMENT_STATUS = ?,
                    GATEWAY_PAYMENT_ID = ?,
                    UPDATED_AT = GETDATE()
                WHERE PAYMENT_ID = ?
            """,
                status,
                rrn,
                txn_id
            )

            conn.commit()
            conn.close()

            print("✅ DB UPDATED SUCCESS")

        except Exception as e:
            print("❌ DB ERROR:", str(e))
            return {"status": "error", "message": "db_failed"}

        # =========================
        # 6️⃣ RESPONSE TO ICICI
        # =========================
        duration = round(time.time() - start_time, 3)
        print(f"⏱️ Processed in {duration}s")

        return Response(
            content=json.dumps({
                "status": "success"
            }),
            media_type="application/json",
            status_code=200
        )

    except Exception as e:
        print("❌ UNEXPECTED ERROR:", str(e))

        return Response(
            content=json.dumps({
                "status": "error"
            }),
            media_type="application/json",
            status_code=200
        )