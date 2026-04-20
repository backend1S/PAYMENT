from fastapi import FastAPI
from app.payment import create_payment_api
from app.callback import router as callback_router

app = FastAPI()

app.include_router(callback_router)

@app.post("/create-payment")
def create_payment(amount: float, customer_name: str):
    return create_payment_api(amount, None, customer_name)