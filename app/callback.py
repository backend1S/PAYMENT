from fastapi import APIRouter, Request
from app.db import get_db_connection
from app.encryption import load_private_key, decrypt_response
import os
import json

router = APIRouter()

# 🔐 Load private key once
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PRIVATE_KEY_PATH = os.path.join(BASE_DIR, "keys", "private_key.pem")
private_key = load_private_key(PRIVATE_KEY_PATH)


@router.post("/api/iciciwebhook")
async def icici_webhook(request: Request):

    print("\n🔥 ===== ICICI CALLBACK HIT =====")

    try:
        # =========================
        # STEP 1: Read raw body
        # =========================
        raw_body = await request.body()

        print("🔹 HEADERS:", dict(request.headers))
        print("🔹 RAW BODY LENGTH:", len(raw_body))

        # ❌ Ignore empty (Swagger/manual test)
        if not raw_body:
            print("⚠️ Empty callback (ignored)")
            return {"status": "ignored"}

        # =========================
        # STEP 2: Decode payload
        # =========================
        try:
            encrypted_data = raw_body.decode("utf-8").strip()
        except Exception as e:
            print("❌ Decode error:", str(e))
            return {"status": "error", "message": "Invalid encoding"}

        print("🔐 ENCRYPTED PAYLOAD (first 100 chars):", encrypted_data[:100])

        # =========================
        # STEP 3: Decrypt
        # =========================
        try:
            decrypted = decrypt_response(encrypted_data, private_key)

            if isinstance(decrypted, str):
                decrypted = json.loads(decrypted)

        except Exception as e:
            print("❌ Decryption failed:", str(e))
            return {"status": "error", "message": "Decryption failed"}

        print("\n🔓 DECRYPTED CALLBACK:")
        print(json.dumps(decrypted, indent=4))

        # =========================
        # STEP 4: Extract fields
        # =========================
        txn_id = decrypted.get("merchantTranId")   # maps to PAYMENT_ID
        status = decrypted.get("TxnStatus")        # SUCCESS / FAILURE
        rrn = decrypted.get("BankRRN")             # bank reference

        print("\n✅ PARSED VALUES:")
        print("TXN ID:", txn_id)
        print("STATUS:", status)
        print("RRN:", rrn)

        if not txn_id:
            print("❌ Missing merchantTranId")
            return {"status": "error", "message": "Invalid callback data"}

        # =========================
        # STEP 5: Update DB
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
            return {"status": "error", "message": "DB update failed"}

        # =========================
        # STEP 6: Response to ICICI
        # =========================
        return {
            "status": "success",
            "message": "Callback processed"
        }

    except Exception as e:
        print("❌ UNEXPECTED ERROR:", str(e))
        return {"status": "error", "message": "Internal server error"}