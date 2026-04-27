from fastapi import APIRouter, Request, Body
from fastapi.responses import Response
from datetime import datetime

from app.encryption import decrypt_response, load_private_key
from app.config import PRIVATE_KEY
from app.db import get_db_connection

router = APIRouter()
private_key = load_private_key(PRIVATE_KEY)


# =========================
# Convert ICICI date → SQL datetime
# =========================
def format_icici_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d%H%M%S")
    except:
        return None


# ==========================================================
# 🔹 OPTIONAL: Decrypt test (for Swagger debugging)
# ==========================================================
@router.post("/payments/icici/decrypt-test")
def decrypt_test(payload: str = Body(..., media_type="text/plain")):
    try:
        encrypted = payload.strip()

        if encrypted.startswith("r="):
            encrypted = encrypted.split("r=", 1)[-1]

        encrypted = encrypted.replace("\n", "")

        decrypted_data = decrypt_response(encrypted, private_key)

        return {
            "status": "success",
            "decrypted_data": decrypted_data
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# ==========================================================
# 🔥 ICICI WEBHOOK (MAIN - PRODUCTION)
# ==========================================================
@router.post("/payments/icici/webhook")
async def icici_webhook(request: Request):
    try:
        raw_body = await request.body()
        body_str = raw_body.decode("utf-8", errors="ignore").strip()

        # Handle ICICI format
        if body_str.startswith("r="):
            encrypted = body_str.split("r=", 1)[-1]
        else:
            encrypted = body_str

        encrypted = encrypted.strip().replace("\n", "")

        decrypted_data = None
        payment_status_update = "NOT_UPDATED"
        callback_insert_status = "NOT_INSERTED"

        # 🔓 Decrypt
        try:
            decrypted_data = decrypt_response(encrypted, private_key)
        except Exception:
            pass

        # =========================
        # DB OPERATIONS
        # =========================
        if decrypted_data:
            merchant_txn_id = decrypted_data.get("merchantTranId")
            txn_status = decrypted_data.get("TxnStatus")
            bank_rrn = decrypted_data.get("BankRRN")

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # UPDATE PAYMENT
                if merchant_txn_id and txn_status:
                    cursor.execute("""
                        UPDATE PAYMENT
                        SET PAYMENT_STATUS = ?, UPDATED_AT = GETDATE()
                        WHERE merchantTranId = ?
                    """, txn_status, merchant_txn_id)

                    payment_status_update = "UPDATED"

                # DUPLICATE CHECK
                cursor.execute("""
                    SELECT COUNT(1)
                    FROM PAYMENTS_ICICI_CALLBACK
                    WHERE MERCHANTTRANID = ? AND BANKRRN = ?
                """, merchant_txn_id, bank_rrn)

                exists = cursor.fetchone()[0]

                # INSERT CALLBACK
                if exists == 0:
                    cursor.execute("""
                        INSERT INTO PAYMENTS_ICICI_CALLBACK (
                            MERCHANTID, MERCHANTTRANID, BANKRRN,
                            PAYERNAME, PAYERMOBILE, PAYERVA,
                            PAYERAMOUNT, TXNSTATUS,
                            TXNINITDATE, TXNCOMPLETIONDATE,
                            RESPONSECODE, RESPCODEDESCRIPTION,
                            PAYEEVPA, PAYERACCOUNTTYPE,
                            CREATED_DATE, MODIFIED_DATE
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
                else:
                    callback_insert_status = "DUPLICATE_SKIPPED"

                conn.commit()
                conn.close()

            except Exception:
                payment_status_update = "DB_ERROR"
                callback_insert_status = "DB_ERROR"

        # =========================
        # ACK RESPONSE (MANDATORY)
        # =========================
        response_xml = f"""<XML>
<Notification>
<Response>ACK</Response>
<PaymentUpdate>{payment_status_update}</PaymentUpdate>
<CallbackInsert>{callback_insert_status}</CallbackInsert>
</Notification>
</XML>"""

        return Response(content=response_xml, media_type="application/xml")

    except Exception as e:
        return Response(
            content=f"""<XML>
<Notification>
<Response>ACK</Response>
<Error>{str(e)}</Error>
</Notification>
</XML>""",
            media_type="application/xml"
        )