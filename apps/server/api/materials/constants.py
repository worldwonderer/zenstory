"""Constants for materials API."""

# Allowed file extensions for material upload
ALLOWED_EXTENSIONS = {".txt"}

# Maximum file size for uploads (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024

# Maximum total characters for a single materials decomposition upload
MAX_TEXT_CHARACTERS = 300_000

__all__ = ["ALLOWED_EXTENSIONS", "MAX_FILE_SIZE", "MAX_TEXT_CHARACTERS"]
