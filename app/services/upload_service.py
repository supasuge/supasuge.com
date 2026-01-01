"""File upload validation and handling for markdown content."""

from __future__ import annotations

import os
import re
from typing import Optional, Tuple
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from flask import current_app


def validate_markdown_upload(file: FileStorage) -> Tuple[bool, Optional[str]]:
    """
    Validate an uploaded markdown file for security and content.

    Args:
        file: The uploaded file from request.files

    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])

    Validation checks:
        - File is not None/empty
        - Filename has allowed extension (.md, .markdown)
        - File size within MAX_UPLOAD_SIZE
        - Content is valid UTF-8
        - No malicious content (scripts, javascript:)

    Example:
        >>> file = request.files['markdown']
        >>> valid, error = validate_markdown_upload(file)
        >>> if not valid:
        ...     flash(error, 'error')
    """
    # Check file exists
    if not file or not file.filename:
        return False, "No file uploaded"

    # Check filename
    filename = secure_filename(file.filename)
    if not filename:
        return False, "Invalid filename"

    # Check extension
    allowed_extensions = current_app.config.get("ALLOWED_EXTENSIONS", {".md", ".markdown"})
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        return False, f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"

    # Read file content
    try:
        file.seek(0)
        content = file.read()
        file.seek(0)  # Reset for later reading
    except Exception as e:
        return False, f"Failed to read file: {str(e)}"

    # Check size
    max_size = current_app.config.get("MAX_UPLOAD_SIZE", 2097152)  # 2MB default
    if len(content) > max_size:
        size_mb = max_size / 1024 / 1024
        return False, f"File too large. Maximum size: {size_mb}MB"

    # Validate UTF-8
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        return False, "File must be UTF-8 encoded"

    # Check for malicious content
    dangerous_patterns = [
        r'<script[^>]*>',  # Script tags
        r'javascript:',     # Javascript protocol
        r'on\w+\s*=',      # Event handlers (onclick, onload, etc.)
        r'<iframe[^>]*>',  # Iframes
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, content_str, re.IGNORECASE):
            return False, "File contains potentially malicious content"

    return True, None


def save_uploaded_markdown(
    file: FileStorage,
    category: str,
    frontmatter: Optional[dict] = None,
) -> Tuple[bool, str]:
    """
    Save an uploaded markdown file to the content directory.

    Args:
        file: The uploaded file from request.files
        category: Category slug for the post
        frontmatter: Optional frontmatter metadata to prepend

    Returns:
        Tuple of (success: bool, file_path_or_error: str)

    File naming:
        - Uses secure_filename() for safety
        - Removes special characters
        - Falls back to timestamp if filename invalid

    Storage location:
        - Saved to: content/articles/<category>/<filename>.md
        - Creates category directory if needed

    Example:
        >>> file = request.files['markdown']
        >>> success, path = save_uploaded_markdown(file, "linux")
        >>> if success:
        ...     print(f"Saved to: {path}")
    """
    from datetime import datetime

    # Validate first
    valid, error = validate_markdown_upload(file)
    if not valid:
        return False, error

    # Secure filename
    filename = secure_filename(file.filename)
    if not filename:
        # Fallback to timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"post_{timestamp}.md"

    # Ensure .md extension
    if not filename.endswith(('.md', '.markdown')):
        filename += '.md'

    # Build target path
    content_dir = current_app.config.get("CONTENT_DIR", "content/articles")
    category_dir = os.path.join(content_dir, category)

    # Create category directory if needed
    os.makedirs(category_dir, exist_ok=True)

    target_path = os.path.join(category_dir, filename)

    # SECURITY: Validate path containment (prevent traversal attacks)
    abs_content_dir = os.path.abspath(content_dir)
    abs_target_path = os.path.abspath(target_path)

    # Ensure directory separator to prevent prefix matching bypass
    if not abs_content_dir.endswith(os.sep):
        abs_content_dir += os.sep

    if not abs_target_path.startswith(abs_content_dir):
        return False, "Invalid file path (security violation - path traversal attempt)"

    # Check if file exists
    if os.path.exists(target_path):
        return False, f"File already exists: {filename}"

    try:
        # Read content
        content = file.read().decode("utf-8")

        # Prepend frontmatter if provided
        if frontmatter:
            fm_lines = ["---"]
            for key, value in frontmatter.items():
                if isinstance(value, list):
                    fm_lines.append(f"{key}:")
                    for item in value:
                        fm_lines.append(f"  - {item}")
                else:
                    fm_lines.append(f"{key}: {value}")
            fm_lines.append("---\n")
            content = "\n".join(fm_lines) + content

        # Write file
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        current_app.logger.info(f"Saved markdown file: {target_path}")
        return True, target_path

    except Exception as e:
        current_app.logger.error(f"Failed to save markdown file: {e}")
        return False, f"Failed to save file: {str(e)}"


def delete_markdown_file(file_path: str) -> Tuple[bool, str]:
    """
    Delete a markdown file from the content directory.

    Args:
        file_path: Path to the file to delete

    Returns:
        Tuple of (success: bool, message: str)

    Security:
        - Validates file is within content directory (no path traversal)
        - Only deletes .md/.markdown files
        - Logs all deletions

    Example:
        >>> success, msg = delete_markdown_file("content/articles/linux/test.md")
        >>> if success:
        ...     print("File deleted")
    """
    # Security: ensure file is in content directory
    content_dir = current_app.config.get("CONTENT_DIR", "content/articles")
    abs_content_dir = os.path.abspath(content_dir)
    abs_file_path = os.path.abspath(file_path)

    # Ensure directory separator to prevent prefix matching bypass
    if not abs_content_dir.endswith(os.sep):
        abs_content_dir += os.sep

    if not abs_file_path.startswith(abs_content_dir):
        return False, "Invalid file path (security violation)"

    # Ensure it's a markdown file
    if not abs_file_path.endswith(('.md', '.markdown')):
        return False, "Can only delete markdown files"

    # Check if file exists
    if not os.path.exists(abs_file_path):
        return False, "File not found"

    try:
        os.remove(abs_file_path)
        current_app.logger.info(f"Deleted markdown file: {abs_file_path}")
        return True, "File deleted successfully"
    except Exception as e:
        current_app.logger.error(f"Failed to delete file: {e}")
        return False, f"Failed to delete file: {str(e)}"
