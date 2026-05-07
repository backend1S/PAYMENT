import requests
from datetime import datetime

from app.config import *
from app.encryption import (
    encrypt_payload,
    decrypt_response,
    load_public_key,
    load_private_key
)
from app.db import get_db_connection


# 🔐 Keys
public_key = load_public_key(ICICI_PUBLIC_KEY)
private_key = load_private_key(PRIVATE_KEY)


# ==========================================================
# 🔹 SAFE CONVERSIONS
# ==========================================================
def safe_float(val):
    if val in (None, "", "null"):
        return 0.0
    try:
        return float(val)
    except:
        return 0.0


def safe_int(val):
    if val in (None, "", "null"):
        return 0
    try:
        return int(val)
    except:
        return 0


def safe_str(val):
    return str(val) if val not in (None, "") else ""


def format_icici_date(date_str):
    try:
        if date_str:
            return datetime.strptime(date_str, "%Y%m%d%H%M%S")
    except:
        pass
    return None


# ==========================================================
# 🔹 STATUS API
# ==========================================================
def check_icici_status(merchant_txn_id: str):
    try:
        payload = {
            "merchantId": ICICI_MID,
            "subMerchantId": ICICI_MID,
            "terminalId": ICICI_TERMINAL_ID,
            "merchantTranId": merchant_txn_id
        }

        encrypted = encrypt_payload(payload, public_key)

        headers = {
            "Content-Type": "text/plain",
            "apikey": ICICI_API_KEY
        }

        url = f"https://apibankingonesandbox.icici.bank.in/api/MerchantAPI/UPI/v0/TransactionStatus3/{ICICI_MID}"

        res = requests.post(url, data=encrypted, headers=headers, timeout=30)

        if not res.text:
            return None

        return decrypt_response(res.text, private_key)

    except Exception as e:
        print("❌ STATUS API ERROR:", str(e))
        return None


# ==========================================================
# 🔹 UPDATE + UPSERT CALLBACK
# ==========================================================
def update_payment_from_status(data: dict):
    try:
        txn_id = safe_str(data.get("merchantTranId"))
        status = safe_str(data.get("status"))

        if not txn_id:
            return

        # =========================
        # SAFE FIELD MAPPING
        # =========================
        merchant_id = safe_str(data.get("merchantId"))
        bank_rrn = safe_int(data.get("OriginalBankRRN"))  # numeric safe
        payer_name = safe_str(data.get("PayerName"))
        payer_mobile = safe_int(data.get("PayerMobile"))
        payer_va = safe_str(data.get("PayerVA"))
        amount = safe_float(data.get("Amount"))
        response_code = safe_int(data.get("response"))
        resp_desc = safe_str(data.get("message"))
        payee_vpa = safe_str(data.get("PayeeVPA"))
        payer_acc_type = safe_str(data.get("payerAccountType"))

        txn_init = format_icici_date(data.get("TxnInitDate"))

        # 🔥 CRITICAL FIX (NO NULL ALLOWED)
        txn_complete = format_icici_date(data.get("TxnCompletionDate"))
        if txn_complete is None:
            txn_complete = datetime.now()  # fallback

        conn = get_db_connection()
        cursor = conn.cursor()

        # =========================
        # UPDATE PAYMENT
        # =========================
        cursor.execute("""
            UPDATE PAYMENT
            SET PAYMENT_STATUS = ?, UPDATED_AT = GETDATE()
            WHERE merchantTranId = ?
        """, status, txn_id)

        # =========================
        # CHECK EXISTING
        # =========================
        cursor.execute("""
            SELECT COUNT(1)
            FROM PAYMENTS_ICICI_CALLBACK
            WHERE MERCHANTTRANID = ?
            AND ISNULL(BANKRRN, 0) = ISNULL(?, 0)
        """, txn_id, bank_rrn)

        exists = cursor.fetchone()[0]

        # =========================
        # UPSERT
        # =========================
        if exists == 0:
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
                merchant_id,
                txn_id,
                bank_rrn,
                payer_name,
                payer_mobile,
                payer_va,
                amount,
                status,
                txn_init,
                txn_complete,
                response_code,
                resp_desc,
                payee_vpa,
                payer_acc_type
            )
        else:
            cursor.execute("""
                UPDATE PAYMENTS_ICICI_CALLBACK
                SET
                    TXNSTATUS = ?,
                    PAYERAMOUNT = ?,
                    RESPONSECODE = ?,
                    RESPCODEDESCRIPTION = ?,
                    TXNCOMPLETIONDATE = ?,
                    MODIFIED_DATE = GETDATE()
                WHERE MERCHANTTRANID = ?
                AND ISNULL(BANKRRN, 0) = ISNULL(?, 0)
            """,
                status,
                amount,
                response_code,
                resp_desc,
                txn_complete,
                txn_id,
                bank_rrn
            )

        conn.commit()
        conn.close()

        print(f"✅ UPSERT OK → {txn_id} → {status}")

    except Exception as e:
        print("❌ STATUS SAVE ERROR:", str(e))


# ==========================================================
# 🔹 FETCH PENDING
# ==========================================================
def get_pending_transactions():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT merchantTranId
            FROM PAYMENT
            WHERE PAYMENT_STATUS = 'PENDING'
            AND CREATED_AT < DATEADD(SECOND, -30, GETDATE())
        """)

        rows = cursor.fetchall()
        conn.close()

        return [r[0] for r in rows]

    except Exception as e:
        print("❌ FETCH ERROR:", str(e))
        return []