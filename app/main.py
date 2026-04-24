from fastapi import FastAPI
from app.payment import create_payment_api
from app.callback import router as callback_router
from app.icici_sender import router as icici_router  # mock sender

import threading
import time

app = FastAPI()

# =========================
# ROUTERS
# =========================
app.include_router(callback_router, tags=["ICICI CALLBACK"])
app.include_router(icici_router, tags=["ICICI MOCK"])


# =========================
# PAYMENT API
# =========================
@app.post("/create-payment")
def create_payment(amount: float, customer_name: str):
    return create_payment_api(amount, None, customer_name)


# =========================
# HEARTBEAT (server alive)
# =========================
def heartbeat():
    while True:
        print("🟢 SWITRUS SERVER RUNNING & LISTENING...")
        time.sleep(1)


@app.on_event("startup")
def start_background_tasks():
    threading.Thread(target=heartbeat, daemon=True).start()