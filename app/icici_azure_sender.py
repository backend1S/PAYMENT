from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests

router = APIRouter()

AZURE_WEBHOOK = "https://crmengine.azurewebsites.net/api/iciciwebhook"


# 🔹 Request model
class ICICIRequest(BaseModel):
    encrypted_data: str


@router.post("/icici/send-azure")
def send_to_azure(data: ICICIRequest):
    try:
        print("\n==============================")
        print("📡 SENDING TO AZURE WEBHOOK")
        print("🌐 URL:", AZURE_WEBHOOK)

        # =========================
        # 1️⃣ VALIDATE INPUT
        # =========================
        if not data.encrypted_data or len(data.encrypted_data.strip()) == 0:
            raise HTTPException(status_code=400, detail="Encrypted data is empty")

        encrypted_data = data.encrypted_data.strip().replace("\n", "")

        print("🔐 DATA LENGTH:", len(encrypted_data))
        print("🔐 PREVIEW:", encrypted_data[:100] + "...")

        # =========================
        # 2️⃣ SEND REQUEST (RAW)
        # =========================
        response = requests.post(
            AZURE_WEBHOOK,
            data=encrypted_data,  # 🔥 RAW BODY (VERY IMPORTANT)
            headers={
                "Content-Type": "text/plain",
                "Accept": "*/*"
            },
            timeout=20
        )

        # =========================
        # 3️⃣ LOG RESPONSE
        # =========================
        print("\n📥 AZURE RESPONSE")
        print("STATUS:", response.status_code)
        print("BODY:", response.text)
        print("==============================\n")

        # =========================
        # 4️⃣ HANDLE ERROR
        # =========================
        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Azure returned {response.status_code}"
            )

        return {
            "status": "success",
            "flow": "ICICI → Azure → SWITRUS",
            "azure_status": response.status_code,
            "azure_response": response.text
        }

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Azure timeout")

    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail="Azure not reachable")

    except Exception as e:
        print("❌ ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))