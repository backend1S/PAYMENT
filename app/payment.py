import uuid
import requests
import json
import qrcode
import base64
from io import BytesIO

from app.config import *
from app.db import get_db_connection
from app.encryption import load_public_key, load_private_key, encrypt_payload, decrypt_response


# 🔐 LOAD KEYS
public_key = load_public_key(ICICI_PUBLIC_KEY)
private_key = load_private_key(PRIVATE_KEY)


def create_payment_api(amount, booking_id, customer_name):

    # ✅ AUTO BOOKING ID
    if not booking_id:
        booking_id = "BK" + uuid.uuid4().hex[:8]

    txn_id = uuid.uuid4().hex[:20]

    payload = {
        "amount": f"{float(amount):.2f}",
        "merchantId": ICICI_MID,
        "terminalId": ICICI_TERMINAL_ID,
        "merchantTranId": txn_id,
        "billNumber": txn_id,
        "validatePayerAccFlag": "N",
        "payerAccount": "",
        "payerIFSC": ""
    }

    print("\n🔹 PLAIN REQUEST:")
    print(json.dumps(payload, indent=4))

    # 🔐 ENCRYPT
    encrypted = encrypt_payload(payload, public_key)

    print("\n🔹 ENCRYPTED REQUEST:")
    print(encrypted)

    headers = {
        "Content-Type": "text/plain",
        "apikey": ICICI_API_KEY
    }

    # 🔁 RETRY (ICICI sometimes fails)
    def call_icici():
        for _ in range(2):
            res = requests.post(ICICI_URL, data=encrypted, headers=headers, timeout=60)

            print("\n🔹 RAW RESPONSE:")
            print(res.text)

            if res.text and not res.text.startswith("Internal"):
                return res
        return res

    try:
        res = call_icici()
    except Exception as e:
        return {"status": "failed", "error": str(e)}

    # ❌ HANDLE ICICI ERROR
    if not res.text or res.text.startswith("Internal"):
        return {
            "status": "failed",
            "error": "ICICI Server Error",
            "raw": res.text
        }

    # 🔓 DECRYPT RESPONSE
    try:
        decrypted = decrypt_response(res.text, private_key)
    except Exception as e:
        return {
            "status": "failed",
            "error": f"Decryption failed: {str(e)}",
            "raw": res.text
        }

    print("\n🔹 DECRYPTED RESPONSE:")
    print(json.dumps(decrypted, indent=4))

    # ❌ ICICI BUSINESS ERROR
    if decrypted.get("success") == "false":
        return {
            "status": "failed",
            "icici_response": decrypted
        }

    ref_id = decrypted.get("refId")

    if not ref_id:
        return {
            "status": "failed",
            "icici_response": decrypted
        }

    # ✅ CORRECT UPI LINK (ICICI FORMAT)
    upi_link = (
        f"upi://pay?"
        f"pa={ICICI_VPA}&"
        f"pn={MERCHANT_NAME}&"
        f"tr={ref_id}&"
        f"am={float(amount):.2f}&"
        f"cu=INR&"
        f"mc=5411"
    )

    print("\n✅ FINAL UPI LINK:")
    print(upi_link)

    # 🔥 GENERATE QR
    qr = qrcode.make(upi_link)

    # Save image file
    file_name = f"{booking_id}.png"
    qr.save(file_name)

    print(f"✅ QR saved as {file_name}")

    # Convert to base64
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    # 💾 SAVE TO DB
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO PAYMENT (
                PAYMENT_ID,
                BOOKING_ID,
                AMOUNT,
                CURRENCY,
                CUSTOMER_NAME,
                PAYMENT_METHOD,
                PAYMENT_STATUS,
                TXN_REF,
                UPI_LINK,
                CREATED_AT,
                UPDATED_AT
            )
            VALUES (?, ?, ?, 'INR', ?, 'UPI', 'PENDING', ?, ?, GETDATE(), GETDATE())
        """,
            txn_id,
            booking_id,
            amount,
            customer_name,
            ref_id,
            upi_link
        )

        conn.commit()
        conn.close()

    except Exception as e:
        print("❌ DB ERROR:", e)

        return {
            "status": "partial_success",
            "booking_id": booking_id,
            "ref_id": ref_id,
            "payment_link": upi_link,
            "qr_code": qr_base64,
            "message": "Payment created but DB failed"
        }

    # ✅ FINAL RESPONSE
    return {
        "status": "success",
        "booking_id": booking_id,
        "payment_id": txn_id,
        "ref_id": ref_id,
        "amount": amount,
        "payment_link": upi_link,
        "qr_code": qr_base64,
        "qr_image_file": file_name,
        "message": "Scan QR or open link to pay"
    }