# -------------------- utils.py -------------------- #
import os
import json
import random
import base64
import rsa
import frappe

from cryptography.hazmat.primitives import serialization, hashes, padding as sym_padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding, rsa as crypto_rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEYS_DIR = os.path.join(frappe.get_site_path("private"), "bank_keys")
os.makedirs(KEYS_DIR, exist_ok=True)


def generate_bank_keypair(bank_name="HDFC"):
    """
    Generate RSA keypair for bank if not exists and save PEM files.
    """
    priv_path = os.path.join(KEYS_DIR, f"{bank_name}_private.pem")
    pub_path = os.path.join(KEYS_DIR, f"{bank_name}_public.pem")

    if os.path.exists(priv_path) and os.path.exists(pub_path):
        with open(priv_path, "rb") as f:
            privkey = rsa.PrivateKey.load_pkcs1(f.read())
        with open(pub_path, "rb") as f:
            pubkey = rsa.PublicKey.load_pkcs1(f.read())
    else:
        pubkey, privkey = rsa.newkeys(2048)
        with open(priv_path, "wb") as f:
            f.write(privkey.save_pkcs1("PEM"))
        with open(pub_path, "wb") as f:
            f.write(pubkey.save_pkcs1("PEM"))

    return pubkey, privkey


def load_bank_keys(bank_name="HDFC"):
    """
    Load bank keys from PEM files.
    """
    priv_path = os.path.join(KEYS_DIR, f"{bank_name}_private.pem")
    pub_path = os.path.join(KEYS_DIR, f"{bank_name}_public.pem")

    if not os.path.exists(priv_path) or not os.path.exists(pub_path):
        raise FileNotFoundError(f"Bank keys not found for {bank_name}")

    with open(priv_path, "rb") as f:
        privkey = rsa.PrivateKey.load_pkcs1(f.read())
    with open(pub_path, "rb") as f:
        pubkey = rsa.PublicKey.load_pkcs1(f.read())

    return pubkey, privkey


def encrypt_with_client_key(client_pubkey_pem, message: dict) -> str:
    """
    Hybrid encryption: AES for message + RSA for AES key.
    Returns base64 JSON string containing both.
    """
    pubkey = serialization.load_pem_public_key(
        client_pubkey_pem.encode(),
        backend=default_backend()
    )

    # Generate random AES key (32 bytes for AES-256)
    aes_key = os.urandom(32)
    iv = os.urandom(16)

    # AES encrypt the message
    data_bytes = json.dumps(message).encode()
    padder = sym_padding.PKCS7(128).padder()
    padded_data = padder.update(data_bytes) + padder.finalize()

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    # Encrypt AES key using RSA
    encrypted_aes_key = pubkey.encrypt(
        aes_key,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    # Prepare base64 JSON payload
    payload = {
        "key": base64.b64encode(encrypted_aes_key).decode(),
        "iv": base64.b64encode(iv).decode(),
        "data": base64.b64encode(ciphertext).decode()
    }

    return base64.b64encode(json.dumps(payload).encode()).decode()


def decrypt_with_bank_key(encrypted_message: str, bank_name="HDFC") -> dict:
    """
    Decrypt message encrypted with hybrid AES-RSA.
    """
    _, privkey = load_bank_keys(bank_name)

    # Decode base64 JSON
    payload_json = base64.b64decode(encrypted_message)
    payload = json.loads(payload_json)

    # Extract components
    encrypted_aes_key = base64.b64decode(payload["key"])
    iv = base64.b64decode(payload["iv"])
    ciphertext = base64.b64decode(payload["data"])

    # Decrypt AES key using bank private RSA key
    aes_key = rsa.decrypt(encrypted_aes_key, privkey)

    # Decrypt AES ciphertext
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = sym_padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    return json.loads(data.decode())


# ------------------- Account Utilities ------------------- #
def generate_account_number() -> str:
    """Generate random 11 or 12 digit account number."""
    length = random.choice([11, 12])
    return str(random.randint(10**(length-1), 10**length-1))


def validate_phone(phone: str):
    """Ensure phone is exactly 10 digits numeric."""
    import re
    if not phone:
        frappe.throw("Phone number is required")
    if not re.fullmatch(r"\d{10}", phone):
        frappe.throw("Invalid phone number. Must be exactly 10 digits")


def get_public_key_pem_pkcs8(pubkey):
    """
    Convert rsa.PublicKey to PKCS#8 PEM (for compatibility with cryptography library).
    """
    pub_numbers = crypto_rsa.RSAPublicNumbers(pubkey.e, pubkey.n)
    crypto_pubkey = pub_numbers.public_key(default_backend())

    pem = crypto_pubkey.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem.decode()
