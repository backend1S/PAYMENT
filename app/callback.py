from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter()

@router.post("/payments/icici/webhook")
async def icici_webhook(request: Request):
    try:
        # 📥 Receive RAW encrypted payload
        raw_body = await request.body()
        encrypted = raw_body.decode(errors="ignore").strip()

        # 🖥 Print in terminal
        print("\n🔥 ICICI CALLBACK HIT")
        print("🔐 RAW ENCRYPTED DATA:\n", encrypted)

        # 📤 Response (XML + debug data)
        response_xml = f"""<XML>
<Notification>
<Response>ACK</Response>
<Debug>{encrypted}</Debug>
</Notification>
</XML>"""

        return Response(content=response_xml, media_type="application/xml")

    except Exception as e:
        print("❌ ERROR:", str(e))

        response_xml = """<XML>
<Notification>
<Response>ACK</Response>
</Notification>
</XML>"""

        return Response(content=response_xml, media_type="application/xml")