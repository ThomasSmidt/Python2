"""Security module.

Encrypts the transformed data at rest (ETL-Load) with symmetric AES, and
decrypts it again when it is read back for the charts.
"""

import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_SIZE = 32  # AES-256; all three methods share this key material

KEY_FILE = "secret.key"


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

def load_or_create_key(key_file: str = KEY_FILE) -> bytes:
    """Load the AES key, generating it on the first run.

    Never hardcoded, and secret.key is in .gitignore.
    """
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            key = base64.urlsafe_b64decode(f.read().strip())
        if len(key) != KEY_SIZE:
            raise ValueError(f"{key_file} does not contain a valid {KEY_SIZE}-byte key")
        return key

    key = os.urandom(KEY_SIZE)  # cryptographically secure randomness
    with open(key_file, "wb") as f:
        f.write(base64.urlsafe_b64encode(key))
    return key


# ---------------------------------------------------------------------------
# Method 1: AES-GCM
# ---------------------------------------------------------------------------

def encrypt_aes_gcm(plaintext: str, key: bytes) -> str:
    """AES in GCM mode - authenticated encryption.

    Fresh 12-byte nonce per call (must be unique, need not be secret),
    stored in front. GCM appends a 16-byte tag, so tampering is detected
    at decryption instead of yielding a plausible wrong number. No
    padding needed - GCM is a stream mode.

    Layout: base64( nonce[12] || ciphertext || tag[16] )
    """
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_aes_gcm(token: str, key: bytes) -> str:
    """Decrypt an AES-GCM token. Raises InvalidTag if tampered with."""
    raw = base64.urlsafe_b64decode(token)
    nonce, ciphertext = raw[:12], raw[12:]
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")


# ---------------------------------------------------------------------------
# Method 2: AES-CBC (raw block cipher)
# ---------------------------------------------------------------------------

def encrypt_aes_cbc(plaintext: str, key: bytes) -> str:
    """AES in CBC mode.

    Random 16-byte IV (must be unpredictable), stored in front. CBC needs
    whole blocks, hence PKCS7 padding.

    Confidentiality ONLY - no authentication tag, so tampering goes
    unnoticed, and CBC is the mode behind padding oracle attacks. It
    needs a separate HMAC to be safe, which is what method 3 adds.

    Layout: base64( iv[16] || ciphertext )
    """
    iv = os.urandom(16)
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()

    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.urlsafe_b64encode(iv + ciphertext).decode("ascii")


def decrypt_aes_cbc(token: str, key: bytes) -> str:
    """Decrypt an AES-CBC token and strip the PKCS7 padding."""
    raw = base64.urlsafe_b64decode(token)
    iv, ciphertext = raw[:16], raw[16:]

    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8")


# ---------------------------------------------------------------------------
# Method 3: AES-CBC using Fernet technology
# ---------------------------------------------------------------------------

def _fernet_key(key: bytes) -> bytes:
    """Fernet wants 32 bytes in url-safe Base64: 16 for HMAC-SHA256,
    16 for AES-128-CBC."""
    return base64.urlsafe_b64encode(key)


def encrypt_fernet(plaintext: str, key: bytes) -> str:
    """Fernet - internally AES-128-CBC + HMAC-SHA256 (encrypt-then-MAC).

    Handles IV, padding and HMAC itself, so it fixes CBC's integrity gap.
    Costs 57 bytes of overhead per value (version + timestamp + IV +
    HMAC) and locks the key size to AES-128. The timestamp enables a ttl,
    which suits sessions and API tokens.
    """
    return Fernet(_fernet_key(key)).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_fernet(token: str, key: bytes) -> str:
    """Decrypt a Fernet token. Raises InvalidToken if the HMAC fails."""
    return Fernet(_fernet_key(key)).decrypt(token.encode("ascii")).decode("utf-8")


# ---------------------------------------------------------------------------
# CHOICE OF METHOD - we encrypt with AES-GCM (method 1)
# ---------------------------------------------------------------------------
# Integrity: research data must be tamper-evident - a silently altered
#   measurement would flow straight into the graphs. GCM is AEAD and
#   detects it. Raw CBC (method 2) protects confidentiality only, and
#   adds padding oracle risk. Rejected.
# Size: values are 3-4 chars and encrypted per cell, so overhead
#   dominates. GCM costs 28 bytes, Fernet 57, and CBC wastes a whole
#   16-byte block on padding.
# Fernet (method 3) is sound, but built for time-limited tokens: it
#   locks us to AES-128 and adds a ttl we cannot use. Rejected.
#
# GCM is also the mode recommended for new systems.
# ---------------------------------------------------------------------------

CHOSEN_METHOD = "AES-GCM"


def encrypt_value(value, key: bytes) -> str:
    """Encrypt one cell with the chosen method (AES-GCM)."""
    return encrypt_aes_gcm(str(value), key)


def decrypt_value(token: str, key: bytes) -> str:
    """Decrypt one cell with the chosen method (AES-GCM)."""
    return decrypt_aes_gcm(token, key)


# ---------------------------------------------------------------------------
# DataFrame helpers used by Load and by the chart stage
# ---------------------------------------------------------------------------

def encrypt_dataframe(df, key: bytes):
    """Encrypt every cell.

    Column names stay in clear text - they are schema, not measurements,
    and SQL queries need them.
    """
    return df.map(lambda value: encrypt_value(value, key))


def decrypt_dataframe(df, key: bytes, numeric_columns=()):
    """Decrypt every cell; cast numeric_columns back to float so the
    result can go straight to the visualisation module."""
    import pandas as pd

    decrypted = df.map(lambda token: decrypt_value(token, key))
    for column in numeric_columns:
        if column in decrypted.columns:
            decrypted[column] = pd.to_numeric(decrypted[column])
    return decrypted
