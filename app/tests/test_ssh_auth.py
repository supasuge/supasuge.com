"""Tests for SSH authentication and signature normalization."""

import pytest


class TestNormalizeSshSignature:
    """Test the SSH signature normalization/extraction function."""

    def setup_method(self):
        from auth.ssh_auth import normalize_ssh_signature
        self.normalize = normalize_ssh_signature

    VALID_SIG = (
        "-----BEGIN SSH SIGNATURE-----\n"
        "U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg\n"
        "dGVzdGtleQ==\n"
        "-----END SSH SIGNATURE-----"
    )

    def test_valid_signature_passthrough(self):
        """Clean signature passes through unchanged."""
        result, err = self.normalize(self.VALID_SIG)
        assert err is None
        assert result == self.VALID_SIG

    def test_crlf_normalization(self):
        """Windows-style CRLF line endings are normalized to LF."""
        crlf_sig = self.VALID_SIG.replace("\n", "\r\n")
        result, err = self.normalize(crlf_sig)
        assert err is None
        assert "\r" not in result
        assert result.startswith("-----BEGIN SSH SIGNATURE-----")
        assert result.endswith("-----END SSH SIGNATURE-----")

    def test_cr_only_normalization(self):
        """Old Mac-style CR line endings are normalized."""
        cr_sig = self.VALID_SIG.replace("\n", "\r")
        result, err = self.normalize(cr_sig)
        assert err is None
        assert "\r" not in result

    def test_trailing_whitespace_stripped(self):
        """Trailing spaces/tabs per line are removed."""
        messy = (
            "-----BEGIN SSH SIGNATURE-----   \n"
            "U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg\t\n"
            "dGVzdGtleQ==  \n"
            "-----END SSH SIGNATURE-----  "
        )
        result, err = self.normalize(messy)
        assert err is None
        for line in result.split("\n"):
            assert line == line.rstrip(), f"Line has trailing whitespace: {line!r}"

    def test_surrounding_text_extracted(self):
        """Signature is extracted from surrounding terminal output."""
        pasted = (
            "$ cat challenge.txt.sig\n"
            "-----BEGIN SSH SIGNATURE-----\n"
            "U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg\n"
            "dGVzdGtleQ==\n"
            "-----END SSH SIGNATURE-----\n"
            "$ \n"
        )
        result, err = self.normalize(pasted)
        assert err is None
        assert result.startswith("-----BEGIN SSH SIGNATURE-----")
        assert result.endswith("-----END SSH SIGNATURE-----")
        assert "$ cat" not in result

    def test_empty_input(self):
        """Empty string returns error."""
        result, err = self.normalize("")
        assert result is None
        assert err == "Empty signature input"

    def test_whitespace_only_input(self):
        """Whitespace-only string returns error."""
        result, err = self.normalize("   \n\t  ")
        assert result is None
        assert err == "Empty signature input"

    def test_no_signature_markers(self):
        """Text without signature markers returns error."""
        result, err = self.normalize("just some random text\nnothing to see here")
        assert result is None
        assert "No SSH signature found" in err

    def test_missing_end_marker(self):
        """BEGIN without END returns error."""
        partial = "-----BEGIN SSH SIGNATURE-----\nU1NIU0lH\n"
        result, err = self.normalize(partial)
        assert result is None
        assert "END SSH SIGNATURE" in err

    def test_truncated_block(self):
        """Block with only markers (no content) returns error."""
        minimal = "-----BEGIN SSH SIGNATURE-----\n-----END SSH SIGNATURE-----"
        result, err = self.normalize(minimal)
        # Only 2 lines - should report truncated
        assert result is None
        assert "truncated" in err

    def test_multiline_base64_preserved(self):
        """Multi-line base64 content within markers is preserved."""
        multi = (
            "-----BEGIN SSH SIGNATURE-----\n"
            "U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg\n"
            "AAAAI0AAAAbFNzaC1lZDI1NTE5AAAAI3B1AAAAAQ==\n"
            "YWJjZGVmZw==\n"
            "-----END SSH SIGNATURE-----"
        )
        result, err = self.normalize(multi)
        assert err is None
        lines = result.split("\n")
        assert len(lines) == 5  # begin + 3 base64 + end


class TestVerifySignature:
    """Test the full verify_signature flow (requires ssh-keygen)."""

    def test_verify_rejects_empty_signature(self, app):
        """Empty signature is rejected before hitting ssh-keygen."""
        with app.app_context():
            from auth.ssh_auth import verify_signature

            ok, fp = verify_signature("some-challenge", "")
            assert ok is False
            assert fp is None

    def test_verify_rejects_garbage_signature(self, app):
        """Random text without markers is rejected."""
        with app.app_context():
            from auth.ssh_auth import verify_signature

            ok, fp = verify_signature("some-challenge", "not a signature at all")
            assert ok is False
            assert fp is None

    def test_verify_rejects_invalid_signature_block(self, app):
        """Structurally valid but cryptographically invalid signature is rejected."""
        fake_sig = (
            "-----BEGIN SSH SIGNATURE-----\n"
            "U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg\n"
            "ZmFrZWtleQ==\n"
            "-----END SSH SIGNATURE-----"
        )
        with app.app_context():
            from auth.ssh_auth import verify_signature

            ok, fp = verify_signature("test-challenge", fake_sig)
            assert ok is False
