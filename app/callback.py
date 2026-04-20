from fastapi import APIRouter, Request
from app.db import get_db_connection
from app.encryption import load_private_key, decrypt_response
import os
import json

router = APIRouter()

# ✅ Load private key
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PRIVATE_KEY_PATH = os.path.join(BASE_DIR, "keys", "private_key.pem")
private_key = load_private_key(PRIVATE_KEY_PATH)


@router.post("/api/iciciwebhook")
async def icici_webhook(request: Request):

    print("\n🔥 ===== ICICI CALLBACK HIT =====")

    try:
        # ✅ Read raw body (ICICI sends encrypted TEXT, not JSON)
        raw_body = await request.body()

        print("🔹 HEADERS:", dict(request.headers))
        print("🔹 RAW BODY:", raw_body)

        # ❌ If empty → ignore (Swagger/manual test)
        if not raw_body:
            print("⚠️ Empty callback received (manual test)")
            return {"status": "ignored", "message": "Empty callback"}

        # ✅ Convert bytes → string
        try:
            encrypted_data = raw_body.decode("utf-8").strip()
        except Exception as e:
            print("❌ Decode error:", str(e))
            return {"status": "error", "message": "Invalid encoding"}

        # 🔐 Decrypt ICICI payload
        try:
            decrypted = decrypt_response(encrypted_data, private_key)

            # If string → convert to dict
            if isinstance(decrypted, str):
                decrypted = json.loads(decrypted)

            print("\n🔓 DECRYPTED CALLBACK:")
            print(json.dumps(decrypted, indent=4))

        except Exception as e:
            print("❌ Decryption failed:", str(e))
            return {"status": "error", "message": "Decryption failed"}

        # ==============================
        # ✅ Extract all ICICI fields
        # ==============================

        txn_id = decrypted.get("merchantTranId")
        status = decrypted.get("TxnStatus")
        rrn = decrypted.get("BankRRN")

        payer_name = decrypted.get("PayerName")
        payer_mobile = decrypted.get("PayerMobile")
        payer_va = decrypted.get("PayerVA")
        amount = decrypted.get("PayerAmount")

        response_code = decrypted.get("ResponseCode")
        response_desc = decrypted.get("RespCodeDescription")

        print("\n✅ PARSED VALUES:")
        print("TXN ID:", txn_id)
        print("STATUS:", status)
        print("RRN:", rrn)

        # ==============================
        # ❌ Validate required fields
        # ==============================

        if not txn_id:
            print("❌ Missing merchantTranId")
            return {"status": "error", "message": "Invalid callback data"}

        # ==============================
        # 💾 Update Database
        # ==============================

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE PAYMENT
                SET 
                    PAYMENT_STATUS = ?,
                    GATEWAY_PAYMENT_ID = ?,
                    PAYER_NAME = ?,
                    PAYER_MOBILE = ?,
                    PAYER_VPA = ?,
                    UPDATED_AT = GETDATE()
                WHERE PAYMENT_ID = ?
            """,
                status,
                rrn,
                payer_name,
                payer_mobile,
                payer_va,
                txn_id
            )

            conn.commit()
            conn.close()

            print("✅ DB UPDATED SUCCESS")

        except Exception as e:
            print("❌ DB ERROR:", str(e))
            return {"status": "error", "message": "DB update failed"}

        # ==============================
        # ✅ Final Response to ICICI
        # ==============================

        return {
            "status": "success",
            "message": "Callback processed successfully"
        }

    except Exception as e:
        print("❌ UNEXPECTED ERROR:", str(e))
        return {"status": "error", "message": "Internal server error"}