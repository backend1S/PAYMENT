from fastapi import APIRouter
from pydantic import BaseModel
import requests

router = APIRouter()

# 🔥 ONLY AZURE WEBHOOK
AZURE_WEBHOOK = "https://crmengine.azurewebsites.net/api/iciciwebhook"


# 🔹 Request model
class ICICIRequest(BaseModel):
    encrypted_data: str


@router.post("/icici/send-azure")
def send_to_azure(data: ICICIRequest):
    try:
        print("\n📡 SENDING TO AZURE WEBHOOK")
        print("🔐 DATA:", data.encrypted_data[:100] + "...")

        response = requests.post(
            AZURE_WEBHOOK,
            data=data.encrypted_data,   # 🔥 RAW BODY
            headers={"Content-Type": "text/plain"},
            timeout=20
        )

        print("📥 STATUS:", response.status_code)
        print("📥 RESPONSE:", response.text)

        return {
            "status": "sent",
            "url": AZURE_WEBHOOK,
            "response_status": response.status_code,
            "response_body": response.text
        }

    except Exception as e:
        print("❌ ERROR:", str(e))
        return {
            "status": "error",
            "message": str(e)
        }