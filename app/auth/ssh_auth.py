"""SSH-key-based authentication for admin access using challenge/response.

This uses OpenSSH signatures:
- Client signs a challenge using: ssh-keygen -Y sign
- Server verifies signature using: ssh-keygen -Y verify

Why this is sane:
- No keyrings, no trust DB, no PGP clearsign parsing.
- Deterministic bytes-in/bytes-out verification.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from flask import Request, current_app
from models import AdminSession, db


def generate_challenge() -> str:
    """Generate a cryptographically secure challenge string."""
    token = secrets.token_hex(32)
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    return f"ADMIN_CHALLENGE_{token}_{timestamp}"


def _require_ssh_keygen() -> None:
    """Fail loudly if ssh-keygen is not available."""
    try:
        subprocess.run(["ssh-keygen", "-V"], capture_output=True, check=False)
    except FileNotFoundError as e:
        raise RuntimeError("ssh-keygen not found. Install openssh-client.") from e


def _read_admin_pubkey_line() -> str:
    key_path = current_app.config.get("ADMIN_SSH_PUBLIC_KEY_PATH", "keys/admin_ssh.pub")
    current_app.logger.info(f"Key path: {key_path}")
    p = Path(key_path)
    if not p.is_absolute():
        p = Path(current_app.root_path) / p

    if not p.exists():
        raise FileNotFoundError(f"Admin SSH public key not found: {p}")

    line = p.read_text(encoding="utf-8").strip()
    # Expect: "ssh-ed25519 AAAAC3... comment"
    parts = line.split()
    if len(parts) < 2:
        raise ValueError(f"Invalid SSH public key format in {p}")
    return line


def _ssh_pubkey_fingerprint(pubkey_path: str) -> str:
    """Return SHA256 fingerprint of the configured public key."""
    _require_ssh_keygen()
    proc = subprocess.run(
        ["ssh-keygen", "-lf", pubkey_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ssh-keygen -lf failed: {proc.stderr.strip()}")
    # Output: "<bits> SHA256:... comment (type)"
    out = (proc.stdout or "").strip()
    if not out:
        raise RuntimeError("ssh-keygen -lf returned empty output")
    # Extract "SHA256:...."
    for tok in out.split():
        if tok.startswith("SHA256:"):
            return tok
    # fallback: whole line
    return out


def verify_signature(
    challenge: str,
    signed_message: str,
) -> tuple[bool, Optional[str]]:
    """
    Verify an OpenSSH signature created by `ssh-keygen -Y sign`.

    The client pastes the signature block that looks like:

        -----BEGIN SSH SIGNATURE-----
        ...
        -----END SSH SIGNATURE-----

    Verification uses:
        ssh-keygen -Y verify -f allowed_signers -I <principal> -n <namespace> -s sigfile

    Returns:
        (ok, fingerprint)
    """
    _require_ssh_keygen()

    principal = (current_app.config.get("ADMIN_SSH_PRINCIPAL") or "admin").strip()
    namespace = (current_app.config.get("ADMIN_SSH_NAMESPACE") or "supasuge-admin").strip()

    msg = (signed_message or "").strip()
    if "-----BEGIN SSH SIGNATURE-----" not in msg:
        current_app.logger.warning("Signed message is not an OpenSSH signature block")
        return False, None

    try:
        # Create temp files for allowed_signers and signature
        with tempfile.TemporaryDirectory(prefix="ssh-auth-") as td:
            td_path = Path(td)

            # Write allowed_signers file
            pubkey_line = _read_admin_pubkey_line()
            allowed_signers_path = td_path / "allowed_signers"

            # allowed_signers format: <principal-patterns> <publickey>
            # We'll use an exact principal (no wildcards).
            allowed_signers_path.write_text(f"{principal} {pubkey_line}\n", encoding="utf-8")

            # Write signature file
            sig_path = td_path / "challenge.sig"
            sig_path.write_text(msg + "\n", encoding="utf-8")

            # We need the pubkey on disk for fingerprint extraction too
            pubkey_path = td_path / "admin.pub"
            pubkey_path.write_text(pubkey_line + "\n", encoding="utf-8")

            # Verify using stdin as the message
            # IMPORTANT: sign/verify must use identical bytes. We do NOT append newline.
            proc = subprocess.run(
                [
                    "ssh-keygen",
                    "-Y",
                    "verify",
                    "-f",
                    str(allowed_signers_path),
                    "-I",
                    principal,
                    "-n",
                    namespace,
                    "-s",
                    str(sig_path),
                    "-q",
                ],
                input=challenge.encode("utf-8"),
                capture_output=True,
                check=False,
            )

            if proc.returncode != 0:
                # stderr sometimes contains useful hints
                current_app.logger.warning(
                    f"SSH signature verification failed: {(proc.stderr or b'').decode(errors='ignore').strip()}"
                )
                return False, None

            fingerprint = _ssh_pubkey_fingerprint(str(pubkey_path))
            return True, fingerprint

    except Exception as e:
        current_app.logger.exception(f"SSH signature verification error: {e}")
        return False, None


def create_admin_session(key_fingerprint: str, request: Request) -> str:
    token = secrets.token_hex(64)
    timeout = int(current_app.config.get("ADMIN_SESSION_TIMEOUT", 28800))

    session = AdminSession(
        session_token=token,
        key_fingerprint=key_fingerprint,
        expires_at=datetime.utcnow() + timedelta(seconds=timeout),
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:512],
    )

    db.session.add(session)
    db.session.commit()
    return token


def verify_admin_session(session_token: str) -> Optional[AdminSession]:
    session = (
        db.session.query(AdminSession)
        .filter_by(session_token=session_token)
        .one_or_none()
    )
    if not session or session.revoked:
        return None

    if datetime.utcnow() > session.expires_at:
        return None

    session.last_activity = datetime.utcnow()

    renewal_threshold = int(current_app.config.get("ADMIN_SESSION_RENEWAL", 3600))
    if (session.expires_at - datetime.utcnow()).total_seconds() < renewal_threshold:
        timeout = int(current_app.config.get("ADMIN_SESSION_TIMEOUT", 28800))
        session.expires_at = datetime.utcnow() + timedelta(seconds=timeout)

    db.session.commit()
    return session


def revoke_session(session_token: str) -> bool:
    session = (
        db.session.query(AdminSession)
        .filter_by(session_token=session_token)
        .one_or_none()
    )
    if not session:
        return False

    session.revoked = True
    db.session.commit()
    return True
