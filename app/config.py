import os
from dotenv import load_dotenv

load_dotenv()

DB_SERVER = os.getenv("DB_SERVER")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

ICICI_MID = os.getenv("ICICI_MID")
ICICI_TERMINAL_ID = os.getenv("ICICI_TERMINAL_ID")
ICICI_VPA = os.getenv("ICICI_VPA")
ICICI_API_KEY = os.getenv("ICICI_API_KEY")
ICICI_URL = os.getenv("ICICI_URL")

MERCHANT_NAME = os.getenv("MERCHANT_NAME")

ICICI_PUBLIC_KEY = os.getenv("ICICI_PUBLIC_KEY")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")