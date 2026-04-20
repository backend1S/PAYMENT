import base64
import json

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


# ✅ Load ICICI CERTIFICATE → extract PUBLIC KEY
def load_public_key(path):
    with open(path, "rb") as f:
        cert_data = f.read()

    cert = x509.load_pem_x509_certificate(cert_data, default_backend())
    return cert.public_key()


# ✅ Load your PRIVATE KEY
def load_private_key(path):
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


# ✅ Encrypt request
def encrypt_payload(payload: dict, public_key):
    data = json.dumps(payload).encode()

    encrypted = public_key.encrypt(
        data,
        padding.PKCS1v15()
    )

    return base64.b64encode(encrypted).decode()


# ✅ Decrypt response
def decrypt_response(enc_response: str, private_key):
    decoded = base64.b64decode(enc_response)

    decrypted = private_key.decrypt(
        decoded,
        padding.PKCS1v15()
    )

    return json.loads(decrypted.decode())