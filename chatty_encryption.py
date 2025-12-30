# Chatty Encryption
# Finley 2025
# 
# Fernet-based encryption for secrets before uploading to Supabase

import json
import base64
import hashlib
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    InvalidToken = Exception  # Fallback for type hints


# Salt for key derivation - fixed so same passphrase always produces same key
CHATTY_SALT = b'chatty_friend_salt_2025'


def is_crypto_available() -> bool:
    """Check if cryptography library is available"""
    return CRYPTO_AVAILABLE


def derive_key(passphrase: str) -> bytes:
    """
    Derive a Fernet-compatible key from a user passphrase.
    Uses PBKDF2 with SHA256 for secure key derivation.
    
    Args:
        passphrase: User-provided passphrase string
        
    Returns:
        Base64-encoded 32-byte key suitable for Fernet
    """
    if not passphrase:
        raise ValueError("Passphrase cannot be empty")
    
    # PBKDF2 with 100,000 iterations for security
    key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        CHATTY_SALT,
        100000,
        dklen=32  # Fernet requires exactly 32 bytes
    )
    return base64.urlsafe_b64encode(key)


def encrypt_secrets(secrets_dict: dict, passphrase: str) -> str:
    """
    Encrypt a secrets dictionary using Fernet symmetric encryption.
    
    Args:
        secrets_dict: Dictionary of secrets to encrypt
        passphrase: User-provided passphrase for encryption
        
    Returns:
        Base64-encoded encrypted string
        
    Raises:
        ValueError: If passphrase is empty or cryptography not available
    """
    if not CRYPTO_AVAILABLE:
        raise ValueError("cryptography library is not installed")
    
    if not passphrase:
        raise ValueError("Passphrase cannot be empty")
    
    # Convert dict to JSON string
    secrets_json = json.dumps(secrets_dict, indent=None, separators=(',', ':'))
    
    # Derive key and encrypt
    key = derive_key(passphrase)
    fernet = Fernet(key)
    encrypted_bytes = fernet.encrypt(secrets_json.encode('utf-8'))
    
    # Return as string for storage
    return encrypted_bytes.decode('utf-8')


def decrypt_secrets(encrypted_str: str, passphrase: str) -> Optional[dict]:
    """
    Decrypt an encrypted secrets string back to a dictionary.
    
    Args:
        encrypted_str: Base64-encoded encrypted string from encrypt_secrets()
        passphrase: User-provided passphrase for decryption
        
    Returns:
        Decrypted secrets dictionary, or None if decryption fails
        
    Raises:
        ValueError: If passphrase is empty or cryptography not available
    """
    if not CRYPTO_AVAILABLE:
        raise ValueError("cryptography library is not installed")
    
    if not passphrase:
        raise ValueError("Passphrase cannot be empty")
    
    if not encrypted_str:
        return None
    
    try:
        # Derive key and decrypt
        key = derive_key(passphrase)
        fernet = Fernet(key)
        decrypted_bytes = fernet.decrypt(encrypted_str.encode('utf-8'))
        
        # Parse JSON back to dict
        secrets_dict = json.loads(decrypted_bytes.decode('utf-8'))
        return secrets_dict
        
    except InvalidToken:
        # Wrong passphrase or corrupted data
        print("Decryption failed: invalid passphrase or corrupted data")
        return None
    except json.JSONDecodeError as e:
        print(f"Decryption failed: invalid JSON after decryption: {e}")
        return None
    except Exception as e:
        print(f"Decryption failed: {e}")
        return None


def verify_passphrase(encrypted_str: str, passphrase: str) -> bool:
    """
    Verify that a passphrase can successfully decrypt the encrypted string.
    
    Args:
        encrypted_str: Encrypted string to test
        passphrase: Passphrase to verify
        
    Returns:
        True if passphrase is correct, False otherwise
    """
    result = decrypt_secrets(encrypted_str, passphrase)
    return result is not None


def generate_passphrase_hint(passphrase: str) -> str:
    """
    Generate a hint for the passphrase (first and last characters).
    
    Args:
        passphrase: The passphrase to generate a hint for
        
    Returns:
        A hint string like "p****d" for "password"
    """
    if not passphrase:
        return ""
    
    if len(passphrase) <= 2:
        return "*" * len(passphrase)
    
    return passphrase[0] + "*" * (len(passphrase) - 2) + passphrase[-1]

