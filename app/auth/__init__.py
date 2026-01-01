"""Authentication module for admin access via SSH key challenge/response."""

from auth.ssh_auth import (
    generate_challenge,
    verify_signature,
    create_admin_session,
    verify_admin_session,
    revoke_session,
)
from auth.decorators import require_admin

__all__ = [
    "generate_challenge",
    "verify_signature",
    "create_admin_session",
    "verify_admin_session",
    "revoke_session",
    "require_admin",
]
