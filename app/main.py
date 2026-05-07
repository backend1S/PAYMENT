from fastapi import FastAPI
from app.payment import create_payment_api
from app.callback import router as callback_router
from app.icici_sender import router as icici_router
from app.icici_azure_sender import router as azure_sender_router

from app.icici_status import (
    check_icici_status,
    update_payment_from_status,
    get_pending_transactions
)

import threading
import time

app = FastAPI()


# =========================
# ROUTERS
# =========================
app.include_router(callback_router, tags=["ICICI CALLBACK"])
app.include_router(icici_router, tags=["ICICI MOCK"])
app.include_router(azure_sender_router, tags=["ICICI AZURE TEST"])


# =========================
# PAYMENT API
# =========================
@app.post("/create-payment")
def create_payment(amount: float, customer_name: str):
    return create_payment_api(amount, None, customer_name)


# =========================
# HEARTBEAT
# =========================
def heartbeat():
    while True:
        print("🟢 SERVER ALIVE")
        time.sleep(2)


# ==========================================================
# 🔥 SMART STATUS CHECKER
# ==========================================================
def icici_status_scheduler():
    print("🚀 STATUS CHECKER STARTED")

    while True:
        try:
            pending_txns = get_pending_transactions()

            if not pending_txns:
                print("✅ No pending transactions")
            else:
                print(f"\n🔍 Checking {len(pending_txns)} pending payments")

            for txn_id in pending_txns:
                try:
                    status_data = check_icici_status(txn_id)

                    if not status_data:
                        continue

                    status = status_data.get("status")

                    # 🔥 IMPORTANT LOGIC
                    if status == "SUCCESS":
                        update_payment_from_status(status_data)

                    elif status in ["FAIL", "FAILURE"]:
                        update_payment_from_status(status_data)

                    elif status == "PENDING":
                        print(f"⏳ Still pending → {txn_id}")

                except Exception as inner:
                    print(f"❌ Error in txn {txn_id}:", str(inner))

        except Exception as e:
            print("❌ Scheduler Error:", str(e))

        time.sleep(30)  # 🔥 faster check (30 sec)


# ==========================================================
# 🔥 WEBHOOK HEALTH MONITOR (OPTIONAL BUT POWERFUL)
# ==========================================================
def webhook_monitor():
    while True:
        print("📡 Webhook listener active...")
        time.sleep(10)


# ==========================================================
# 🔥 START THREADS
# ==========================================================
@app.on_event("startup")
def start_background_tasks():
    threading.Thread(target=heartbeat, daemon=True).start()
    threading.Thread(target=icici_status_scheduler, daemon=True).start()
    threading.Thread(target=webhook_monitor, daemon=True).start()