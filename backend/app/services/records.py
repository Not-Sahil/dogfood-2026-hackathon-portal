import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

KEY_PATH = Path(__file__).resolve().parents[2] / "data" / "judge_record_private.key"


def _load_private_key() -> Ed25519PrivateKey:
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if KEY_PATH.exists():
        return serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    KEY_PATH.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return key


def signing_public_key_b64() -> str:
    key = _load_private_key().public_key()
    return base64.urlsafe_b64encode(key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def sign_record(payload: dict) -> str:
    key = _load_private_key()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(key.sign(canonical)).decode()


def verify_record(payload: dict, signature: str) -> bool:
    try:
        raw_key = base64.urlsafe_b64decode(signing_public_key_b64())
        raw_sig = base64.urlsafe_b64decode(signature)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(raw_key).verify(raw_sig, json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        return True
    except Exception:
        return False
