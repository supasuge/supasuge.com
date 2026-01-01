#!/usr/bin/env python3
"""
test.py

Strict SSH Ed25519 authentication verification using Paramiko.

Policy:
- Ed25519 ONLY
- Fixed local private key path: ~/.ssh/id_ed25519_admin
- Namespace must match expected value
- No verbose errors on failure
- No subprocess, no shell, no ssh-keygen
"""

from __future__ import annotations

import base64
from pathlib import Path

import paramiko
from paramiko.message import Message
from paramiko.ssh_exception import SSHException


# ---------------------------------------------------------------------------
# Policy configuration
# ---------------------------------------------------------------------------

EXPECTED_NAMESPACE = b"supasuge-admin"
EXPECTED_KEY_TYPE = "ssh-ed25519"

PRIVATE_KEY_PATH = Path("~/.ssh/id_ed25519_admin").expanduser()
print(PRIVATE_KEY_PATH)

# ---------------------------------------------------------------------------
# Key loading (private key used only to derive public parameters)
# ---------------------------------------------------------------------------

def _load_admin_key() -> paramiko.Ed25519Key | None:
    """
    Load the admin Ed25519 key from the fixed path.

    Returns None on any failure (fail-closed, no verbosity).
    """
    try:
        if not PRIVATE_KEY_PATH.is_file():
            print('not a file....?')
            return None

        key = paramiko.Ed25519Key(filename=str(PRIVATE_KEY_PATH))
        print(key)
        if key.get_name() != EXPECTED_KEY_TYPE:
            print('not expected')
            return None

        return key

    except Exception:
        return None


# ---------------------------------------------------------------------------
# SSHSIG decoding + validation
# ---------------------------------------------------------------------------

def _decode_signature(sig_b64: str) -> Message | None:
    """
    Decode base64 SSHSIG blob into a Paramiko Message.
    """
    try:
        raw = base64.b64decode(sig_b64)
        return Message(raw)
    except Exception:
        return None


def _validate_namespace(sig_msg: Message) -> bool:
    """
    Validate SSH signature namespace.

    SSHSIG structure (simplified):
        string  "SSHSIG"
        string  namespace
        string  reserved
        string  hash_alg
        string  signature
    """
    try:
        sig_msg.rewind()
        magic = sig_msg.get_string()
        if magic != b"SSHSIG":
            return False

        namespace = sig_msg.get_string()
        return namespace == EXPECTED_NAMESPACE

    except Exception:
        return False


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_admin_signature(
    challenge: bytes,
    signature_b64: str,
) -> bool:
    """
    Verify an SSH Ed25519 signature over a challenge.

    Returns:
        True  -> valid admin signature
        False -> anything else (quiet failure)
    """
    key = _load_admin_key()
    print(key)
    if key is None:
        return False

    sig_msg = _decode_signature(signature_b64)
    print(sig_msg)
    if sig_msg is None:
        return False

    # Namespace enforcement (before crypto)
    if not _validate_namespace(sig_msg):
        print(_validate_namespace(sig_msg))
        return False

    try:
        return key.verify_ssh_sig(challenge, sig_msg)
    except SSHException as e:
        print(e)
        return False


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

def main() -> None:
    # Must be byte-for-byte identical to what the client signed
    challenge = b"supasuge-admin-auth-2025-12-30"

    # Base64 SSHSIG blob (example)
    signature = (
        "U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgNAAShF6sHr5H+zc3eReqPeNV7/"
        "w/Nqfduh7khnvPvMkAAAAOc3VwYXN1Z2UtYWRtaW4AAAAAAAAABnNoYTUxMgAAAFMAAAAL"
        "c3NoLWVkMjU1MTkAAABAuw2upOYkyWOkpFl01f/GA+qt3QbAA4BNPskCGK/sRbu/5QYFd0"
        "iAif9KFAbkGri6iC9DZLLn7ERZDwnMTZRHAg=="
    )

    if verify_admin_signature(challenge, signature):
        print("✔ admin authenticated")
    else:
        print("✘ authentication failed")


if __name__ == "__main__":
    main()
