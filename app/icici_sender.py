from fastapi import APIRouter
import requests
import threading
import time

router = APIRouter()

# 🔥 Your SWITRUS webhook URL (LIVE or LOCAL)
WEBHOOK_URL = "http://135.13.36.155:8100/payments/icici/webhook"

# 🔐 Sample encrypted payload (use real one if you have)
ENCRYPTED_DATA = """aN40xrQG07Yfm7TG8MnlR0UzJQD/Hxf9H8ifATZmk/xE2oAolP1KUTCr9QMKj3c4krF5VKWiyXV56cnvw4XQ8VCGKNhYWv3FvcfWkGWwtxmKb3NVdV1tTniyeL8mjV6n3uz3ekLyIanSzi0jTnqR+Qhhg59XsUVaqBtJw0zJ2rCxnuseorlXid5GHJ6Pavcr/So0fClFbxR+QjK42qyQKEm9jL/KWMiCg3InWbO1tqVgMRVLhxOAelbOgGMSVcmZsLP6jLNAcGRtJhIZ8VtebBxMpRaDxBeKJ5WHG6TOowEyunPzY8i+14aR1/tLsaKn/t8TjVXgbZLm+06WsI2i4WuHAvOcSKycsblAeyEvvpscRUhsgKfpim6fHYDm1Qpuh1gkCXTR8n3vwhUW2vTqIwK6xjiuhLGuCbfDSWJMWban2yLilT7otKJOMFiQLwkUMb6QZNd3x8H+7zrDHGIlu6yihRQzFEZz358bAzZ+Zyd12rGU0o+K4IDnmPU/+WG+Y1e8SmYic7aVRgObq/83hJd+s2pMbDIEz9ByxeKrZwj6wY+q4EFojX+rk1w4l7dcaqW28SN0MKVvpcytteV6Cuv27eyyR2Qhjcd+Z/SQwp+rpCEuFC8dBrU1gHVEplVjhYJjW/XplyHHnCoXsh5MavLgxLe7Cgmzsgs+v1B7/Xo="""


def send_continuous():
    print("🚀 ICICI MOCK STARTED (sending continuously)")

    while True:
        try:
            print("\n📡 ICICI → Sending encrypted data...")

            response = requests.post(
                WEBHOOK_URL,
                data=ENCRYPTED_DATA,
                headers={"Content-Type": "text/plain"},
                timeout=10
            )

            print("📥 SWITRUS RESPONSE:", response.status_code)
            print("📥 RESPONSE BODY:", response.text)

        except Exception as e:
            print("❌ ERROR:", str(e))

        time.sleep(5)  # every 5 seconds


@router.get("/icici/start")
def start_icici_mock():
    thread = threading.Thread(target=send_continuous, daemon=True)
    thread.start()

    return {
        "status": "ICICI mock started",
        "message": "Sending webhook every 5 seconds"
    }