"""Markdown ingestion helpers for vault assets and metadata fallbacks."""

from __future__ import annotations

import hashlib
import logging
import shutil
import urllib.parse
from pathlib import Path
import re

from flask import current_app
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

MARKDOWN_EXTENSIONS = {".md", ".markdown"}
WIKI_IMAGE_RE = re.compile(r"!\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")
MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
HTML_IMG_RE = re.compile(r'(<img[^>]+src=["\'])([^"\']+)(["\'])', re.IGNORECASE)


class VaultAssetResolver:
    """Resolve vault asset references and materialize them into the app asset dir."""

    def __init__(self, vault_root: Path, output_dir: Path, url_prefix: str):
        self.vault_root = vault_root
        self.output_dir = output_dir
        self.url_prefix = url_prefix.rstrip("/")
        self._relative_index: dict[str, Path] = {}
        self._basename_index: dict[str, list[Path]] = {}
        self._stem_index: dict[str, list[Path]] = {}
        self._materialized: dict[Path, str] = {}

    def build_index(self) -> None:
        if not self.vault_root.exists() or not self.vault_root.is_dir():
            return

        for path in self.vault_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in MARKDOWN_EXTENSIONS:
                continue

            rel = path.relative_to(self.vault_root).as_posix().lower()
            self._relative_index[rel] = path
            self._basename_index.setdefault(path.name.lower(), []).append(path)
            self._stem_index.setdefault(path.stem.lower(), []).append(path)

    def resolve(self, reference: str) -> str | None:
        source = self._resolve_source_path(reference)
        if source is None:
            return None
        return self._materialize(source)

    def _resolve_source_path(self, reference: str) -> Path | None:
        cleaned = _clean_reference(reference)
        if not cleaned:
            return None

        exact = self._relative_index.get(cleaned.lower())
        if exact:
            return exact

        basename = Path(cleaned).name.lower()
        if basename:
            candidates = self._basename_index.get(basename, [])
            if candidates:
                return _pick_best_candidate(cleaned, candidates)

        stem = Path(cleaned).stem.lower()
        if stem and stem.startswith("pasted image "):
            candidates = self._stem_index.get(stem, [])
            if candidates:
                return _pick_best_candidate(cleaned, candidates)

        return None

    def _materialize(self, source: Path) -> str:
        cached = self._materialized.get(source)
        if cached:
            return cached

        self.output_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
        base = secure_filename(source.stem) or "asset"
        suffix = source.suffix.lower()
        filename = f"{base}-{digest}{suffix}"
        target = self.output_dir / filename

        if not target.exists():
            shutil.copy2(source, target)
            logger.info("Imported vault asset %s -> %s", source, target)

        url = f"{self.url_prefix}/{filename}"
        self._materialized[source] = url
        return url


def prepare_markdown_for_storage(raw_markdown: str) -> str:
    """Rewrite vault asset references to stable site asset URLs."""
    resolver = _build_resolver()
    if resolver is None:
        return raw_markdown

    resolver.build_index()

    def replace_wiki(match: re.Match[str]) -> str:
        reference = match.group(1).strip()
        resolved = resolver.resolve(reference)
        if not resolved:
            return match.group(0)
        alt = Path(reference).name
        return f"![{alt}]({resolved})"

    def replace_markdown(match: re.Match[str]) -> str:
        alt, reference = match.groups()
        local_ref = _extract_markdown_target(reference)
        if not _is_local_reference(local_ref):
            return match.group(0)
        resolved = resolver.resolve(local_ref)
        if not resolved:
            return match.group(0)
        return f"![{alt}]({resolved})"

    def replace_html(match: re.Match[str]) -> str:
        prefix, reference, suffix = match.groups()
        if not _is_local_reference(reference):
            return match.group(0)
        resolved = resolver.resolve(reference)
        if not resolved:
            return match.group(0)
        return f"{prefix}{resolved}{suffix}"

    updated = WIKI_IMAGE_RE.sub(replace_wiki, raw_markdown)
    updated = MARKDOWN_IMAGE_RE.sub(replace_markdown, updated)
    updated = HTML_IMG_RE.sub(replace_html, updated)
    return updated


def source_name_to_title(source_name: str | None) -> str:
    """Derive a human-readable title from a filename."""
    if not source_name:
        return "Untitled"
    stem = Path(source_name).stem.strip()
    if not stem:
        return "Untitled"
    return re.sub(r"[_\-]+", " ", stem).strip() or "Untitled"


def _build_resolver() -> VaultAssetResolver | None:
    vault_root_raw = current_app.config.get("OBSIDIAN_VAULT_ROOT", "~/Main-Notes-Sync")
    vault_root = Path(vault_root_raw).expanduser()
    if not vault_root.exists() or not vault_root.is_dir():
        logger.info("Obsidian vault root not found: %s", vault_root)
        return None

    output_dir_raw = current_app.config.get("MARKDOWN_ASSET_OUTPUT_DIR")
    if output_dir_raw:
        output_dir = Path(output_dir_raw).expanduser()
    else:
        output_dir = Path(current_app.root_path) / "static" / "img" / "vault"

    url_prefix = current_app.config.get("MARKDOWN_ASSET_URL_PREFIX", "/static/img/vault")
    return VaultAssetResolver(vault_root=vault_root, output_dir=output_dir, url_prefix=url_prefix)


def _clean_reference(reference: str) -> str:
    candidate = urllib.parse.unquote(reference.strip().strip("<>"))
    candidate = candidate.split("?", 1)[0].split("#", 1)[0]
    candidate = candidate.replace("\\", "/")

    while candidate.startswith("./"):
        candidate = candidate[2:]
    while candidate.startswith("/"):
        candidate = candidate[1:]

    return candidate.strip()


def _extract_markdown_target(reference: str) -> str:
    target = reference.strip()
    if target.startswith("<") and ">" in target:
        return target[1:target.index(">")]
    if ' "' in target:
        target = target.split(' "', 1)[0]
    if " '" in target:
        target = target.split(" '", 1)[0]
    return target


def _is_local_reference(reference: str) -> bool:
    lowered = reference.strip().lower()
    if not lowered:
        return False
    return not lowered.startswith((
        "http://",
        "https://",
        "data:",
        "mailto:",
        "/static/",
        "/media/",
    ))


def _pick_best_candidate(reference: str, candidates: list[Path]) -> Path:
    wanted_parts = [part.lower() for part in Path(reference).parts[:-1] if part not in (".", "..")]
    if wanted_parts:
        for candidate in candidates:
            rel_parts = [part.lower() for part in candidate.parts]
            if all(part in rel_parts for part in wanted_parts):
                return candidate

    return sorted(
        candidates,
        key=lambda path: (len(path.parts), len(path.as_posix()), path.as_posix().lower()),
    )[0]
