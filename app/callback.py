from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.encryption import decrypt_response, load_private_key
from app.config import PRIVATE_KEY
from app.db import get_db_connection

router = APIRouter()

private_key = load_private_key(PRIVATE_KEY)


@router.post("/payments/icici/webhook")
async def icici_webhook(request: Request):
    try:
        raw_body = await request.body()
        body_str = raw_body.decode(errors="ignore").strip()

        print("\n🔥 ICICI CALLBACK HIT")

        # ✅ Handle both formats
        if body_str.startswith("r="):
            encrypted = body_str.split("r=", 1)[-1]
            print("📦 FORMAT: r=ENC")
        else:
            encrypted = body_str
            print("📦 FORMAT: RAW BODY")

        print("🔐 ENCRYPTED DATA:\n", encrypted)

        decrypted_data = None
        db_status = "NOT_UPDATED"

        # 🔓 Decrypt
        try:
            decrypted_data = decrypt_response(encrypted, private_key)
            print("✅ DECRYPTED DATA:\n", decrypted_data)
        except Exception as e:
            print("❌ DECRYPTION FAILED:", str(e))

        # 💾 Update DB
        if decrypted_data:
            merchant_txn_id = decrypted_data.get("merchantTranId")
            txn_status = decrypted_data.get("TxnStatus")

            if merchant_txn_id and txn_status:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    cursor.execute("""
                        UPDATE PAYMENT
                        SET PAYMENT_STATUS = ?, UPDATED_AT = GETDATE()
                        WHERE merchantTranId = ?
                    """,
                        txn_status,
                        merchant_txn_id
                    )

                    conn.commit()
                    conn.close()

                    db_status = "UPDATED"
                    print("✅ DB UPDATED")

                except Exception as e:
                    db_status = f"DB_ERROR: {str(e)}"
                    print("❌ DB ERROR:", str(e))
            else:
                db_status = "MISSING_FIELDS"

        # 📤 Response with debug (for testing)
        response_xml = f"""<XML>
<Notification>
<Response>ACK</Response>
<Encrypted>{encrypted}</Encrypted>
<Decrypted>{str(decrypted_data)}</Decrypted>
<DBStatus>{db_status}</DBStatus>
</Notification>
</XML>"""

        print("📤 RESPONSE:\n", response_xml)

        return Response(content=response_xml, media_type="application/xml")

    except Exception as e:
        print("❌ WEBHOOK ERROR:", str(e))

        return Response(
            content=f"""<XML>
<Notification>
<Response>ACK</Response>
<Error>{str(e)}</Error>
</Notification>
</XML>""",
            media_type="application/xml"
        )