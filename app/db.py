import pyodbc
from app.config import *

def get_db_connection():
    drivers = pyodbc.drivers()

    if "ODBC Driver 18 for SQL Server" in drivers:
        driver = "ODBC Driver 18 for SQL Server"
    elif "ODBC Driver 17 for SQL Server" in drivers:
        driver = "ODBC Driver 17 for SQL Server"
    else:
        raise Exception("❌ No SQL Server ODBC Driver found")

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER=tcp:{DB_SERVER},1433;"   # 🔥 IMPORTANT
        f"DATABASE={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    return pyodbc.connect(conn_str)