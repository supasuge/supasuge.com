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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

import re

from flask import Request, current_app
from models import AdminSession, db


def generate_challenge() -> str:
    """Generate a cryptographically secure challenge string."""
    token = secrets.token_hex(32)
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
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


_SIG_BLOCK_RE = re.compile(
    r"(-----BEGIN SSH SIGNATURE-----\s*\n.*?\n\s*-----END SSH SIGNATURE-----)",
    re.DOTALL,
)


def normalize_ssh_signature(raw: str) -> tuple[Optional[str], Optional[str]]:
    """Extract and normalize an SSH signature from pasted text.

    Handles common issues:
    - CRLF line endings from Windows/browser paste
    - Extra whitespace before/after the signature block
    - Surrounding text (e.g. terminal prompts, filenames)
    - Trailing whitespace per line

    Returns:
        (normalized_signature, error_message)
        On success: (signature, None)
        On failure: (None, human-readable error)
    """
    if not raw or not raw.strip():
        return None, "Empty signature input"

    # Normalize line endings: CRLF -> LF, CR -> LF
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Try regex extraction first (handles surrounding text)
    match = _SIG_BLOCK_RE.search(text)
    if match:
        block = match.group(1)
    elif "-----BEGIN SSH SIGNATURE-----" in text:
        # Fallback: extract between markers manually
        begin_idx = text.index("-----BEGIN SSH SIGNATURE-----")
        end_marker = "-----END SSH SIGNATURE-----"
        end_idx = text.find(end_marker)
        if end_idx == -1:
            return None, "Found BEGIN marker but missing END SSH SIGNATURE marker"
        block = text[begin_idx : end_idx + len(end_marker)]
    else:
        return None, (
            "No SSH signature found. The signature should contain "
            "'-----BEGIN SSH SIGNATURE-----' and '-----END SSH SIGNATURE-----' markers."
        )

    # Strip trailing whitespace per line, normalize internal whitespace
    lines = [line.rstrip() for line in block.split("\n")]
    # Remove empty lines at start/end but keep internal structure
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    if len(lines) < 3:
        return None, "Signature block appears truncated (too few lines)"

    normalized = "\n".join(lines)

    # Validate structure: first and last lines must be markers
    if not normalized.startswith("-----BEGIN SSH SIGNATURE-----"):
        return None, "Signature block does not start with BEGIN marker"
    if not normalized.endswith("-----END SSH SIGNATURE-----"):
        return None, "Signature block does not end with END marker"

    return normalized, None


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

    Handles common paste issues (CRLF, extra whitespace, surrounding text).

    Verification uses:
        ssh-keygen -Y verify -f allowed_signers -I <principal> -n <namespace> -s sigfile

    Returns:
        (ok, fingerprint)
    """
    _require_ssh_keygen()

    principal = (current_app.config.get("ADMIN_SSH_PRINCIPAL") or "admin").strip()
    namespace = (current_app.config.get("ADMIN_SSH_NAMESPACE") or "supasuge-admin").strip()

    # Normalize the signature with robust parsing
    normalized_sig, sig_error = normalize_ssh_signature(signed_message)
    if normalized_sig is None:
        current_app.logger.warning("SSH signature parse error: %s", sig_error)
        return False, None

    try:
        with tempfile.TemporaryDirectory(prefix="ssh-auth-") as td:
            td_path = Path(td)

            # Write allowed_signers file
            pubkey_line = _read_admin_pubkey_line()
            allowed_signers_path = td_path / "allowed_signers"
            allowed_signers_path.write_text(f"{principal} {pubkey_line}\n", encoding="utf-8")

            # Write normalized signature file
            sig_path = td_path / "challenge.sig"
            sig_path.write_text(normalized_sig + "\n", encoding="utf-8")

            # Pubkey on disk for fingerprint extraction
            pubkey_path = td_path / "admin.pub"
            pubkey_path.write_text(pubkey_line + "\n", encoding="utf-8")

            # Verify using stdin as the message
            # IMPORTANT: sign/verify must use identical bytes. We do NOT append newline.
            proc = subprocess.run(
                [
                    "ssh-keygen",
                    "-Y", "verify",
                    "-f", str(allowed_signers_path),
                    "-I", principal,
                    "-n", namespace,
                    "-s", str(sig_path),
                    "-q",
                ],
                input=challenge.encode("utf-8"),
                capture_output=True,
                check=False,
            )

            if proc.returncode != 0:
                stderr = (proc.stderr or b"").decode(errors="ignore").strip()
                current_app.logger.warning(
                    "SSH signature verification failed: %s", stderr
                )
                return False, None

            fingerprint = _ssh_pubkey_fingerprint(str(pubkey_path))
            return True, fingerprint

    except Exception as e:
        current_app.logger.exception("SSH signature verification error: %s", e)
        return False, None


def create_admin_session(key_fingerprint: str, request: Request) -> str:
    token = secrets.token_hex(64)
    timeout = int(current_app.config.get("ADMIN_SESSION_TIMEOUT", 28800))

    session = AdminSession(
        session_token=token,
        key_fingerprint=key_fingerprint,
        expires_at=datetime.now(UTC) + timedelta(seconds=timeout),
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

    # SQLite stores naive datetimes; make expires_at aware for comparison
    exp = session.expires_at.replace(tzinfo=UTC) if session.expires_at.tzinfo is None else session.expires_at
    now = datetime.now(UTC)

    if now > exp:
        return None

    session.last_activity = now

    renewal_threshold = int(current_app.config.get("ADMIN_SESSION_RENEWAL", 3600))
    if (exp - now).total_seconds() < renewal_threshold:
        timeout = int(current_app.config.get("ADMIN_SESSION_TIMEOUT", 28800))
        session.expires_at = now + timedelta(seconds=timeout)

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
