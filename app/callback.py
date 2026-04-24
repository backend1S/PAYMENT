from fastapi import APIRouter, Request
from fastapi.responses import Response
from datetime import datetime

from app.encryption import decrypt_response, load_private_key
from app.config import PRIVATE_KEY
from app.db import get_db_connection

router = APIRouter()
private_key = load_private_key(PRIVATE_KEY)


# 🔥 Convert ICICI date → SQL datetime
def format_icici_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d%H%M%S")
    except:
        return None


@router.post("/payments/icici/webhook")
async def icici_webhook(request: Request):
    try:
        raw_body = await request.body()

        print("\n==============================")
        print("🔥 ICICI CALLBACK RECEIVED")
        print("📦 RAW BYTES:", raw_body)

        body_str = raw_body.decode(errors="ignore").strip()
        print("📥 RAW STRING:", body_str)

        # ✅ Handle format
        if body_str.startswith("r="):
            encrypted = body_str.split("r=", 1)[-1]
            print("📦 FORMAT: r=ENC")
        else:
            encrypted = body_str
            print("📦 FORMAT: RAW BODY")

        print("🔐 ENCRYPTED DATA:\n", encrypted)

        decrypted_data = None
        payment_status_update = "NOT_UPDATED"
        callback_insert_status = "NOT_INSERTED"

        # 🔓 Decrypt
        try:
            if encrypted:
                decrypted_data = decrypt_response(encrypted, private_key)
                print("✅ DECRYPTED DATA:\n", decrypted_data)
        except Exception as e:
            print("❌ DECRYPT FAILED:", str(e))

        if decrypted_data:
            merchant_txn_id = decrypted_data.get("merchantTranId")
            txn_status = decrypted_data.get("TxnStatus")
            bank_rrn = decrypted_data.get("BankRRN")

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # =========================
                # 1️⃣ UPDATE PAYMENT TABLE
                # =========================
                if merchant_txn_id and txn_status:
                    cursor.execute("""
                        UPDATE PAYMENT
                        SET PAYMENT_STATUS = ?, UPDATED_AT = GETDATE()
                        WHERE merchantTranId = ?
                    """, txn_status, merchant_txn_id)

                    payment_status_update = "UPDATED"
                    print("✅ PAYMENT TABLE UPDATED")

                # =========================
                # 2️⃣ DUPLICATE CHECK
                # =========================
                cursor.execute("""
                    SELECT COUNT(1)
                    FROM PAYMENTS_ICICI_CALLBACK
                    WHERE MERCHANTTRANID = ? AND BANKRRN = ?
                """, merchant_txn_id, bank_rrn)

                exists = cursor.fetchone()[0]

                if exists == 0:
                    # =========================
                    # 3️⃣ INSERT CALLBACK TABLE
                    # =========================
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
                        decrypted_data.get("merchantId"),
                        merchant_txn_id,
                        bank_rrn,
                        decrypted_data.get("PayerName"),
                        decrypted_data.get("PayerMobile"),
                        decrypted_data.get("PayerVA"),
                        decrypted_data.get("PayerAmount"),
                        txn_status,
                        format_icici_date(decrypted_data.get("TxnInitDate")),
                        format_icici_date(decrypted_data.get("TxnCompletionDate")),
                        decrypted_data.get("ResponseCode"),
                        decrypted_data.get("RespCodeDescription"),
                        decrypted_data.get("PayeeVPA"),
                        decrypted_data.get("PayerAccountType")
                    )

                    callback_insert_status = "INSERTED"
                    print("✅ CALLBACK INSERTED")

                else:
                    callback_insert_status = "DUPLICATE_SKIPPED"
                    print("⚠️ DUPLICATE CALLBACK SKIPPED")

                conn.commit()
                conn.close()

            except Exception as e:
                print("❌ DB ERROR:", str(e))
                payment_status_update = "DB_ERROR"
                callback_insert_status = "DB_ERROR"

        # 📤 RESPONSE (ICICI ACK)
        response_xml = f"""<XML>
<Notification>
<Response>ACK</Response>
<PaymentUpdate>{payment_status_update}</PaymentUpdate>
<CallbackInsert>{callback_insert_status}</CallbackInsert>
</Notification>
</XML>"""

        print("📤 RESPONSE SENT")
        print("==============================\n")

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