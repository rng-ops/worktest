import hmac
import hashlib
from typing import Optional


def derive_psk(epoch_secret: bytes, node_id: str, length: int = 32) -> bytes:
    """
    Derive a per-node PSK using HMAC-SHA256.
    
    For PoC, we use a simple HMAC-based KDF. In production, use HKDF-SHA256 with proper salt.
    
    Args:
        epoch_secret: Shared epoch secret (32 bytes)
        node_id: Node identifier (string, e.g., "node-a")
        length: Output length (32 bytes = 256 bits)
    
    Returns:
        Derived PSK as bytes
    """
    # Simple HMAC-based derivation: HMAC_SHA256(epoch_secret, node_id)
    h = hmac.new(epoch_secret, node_id.encode(), hashlib.sha256)
    return h.digest()[:length]


def epoch_secret_hash(secret: bytes) -> str:
    """Hash epoch secret for logging/display (do not expose full secret)."""
    return "sha256:" + hashlib.sha256(secret).hexdigest()[:16]


def verify_signature(message: str, signature: str, public_key: Optional[str] = None) -> bool:
    """
    Placeholder for signature verification.
    
    In PoC: always return True (signatures are optional).
    In production: implement ECDSA/Ed25519 verification against public key.
    """
    if not signature or not public_key:
        return True  # Optional for PoC
    # TODO: implement real verification
    return True
