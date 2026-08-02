"""Shared input validation for the two file-upload endpoints
(routers/leads.py, routers/churn.py) -- rejected here, before an upload
ever reaches pandas, so a malformed or oversized file can't burn CPU/memory
parsing something that was never going to be usable anyway.
"""

from fastapi import HTTPException

from ..config import MAX_UPLOAD_ROWS, MAX_UPLOAD_SIZE_MB

ALLOWED_UPLOAD_EXTENSIONS = (".csv", ".xlsx", ".xls")


def validate_upload_file(filename: str | None, content: bytes) -> None:
    if not filename or not filename.lower().endswith(ALLOWED_UPLOAD_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type -- must be one of: {', '.join(ALLOWED_UPLOAD_EXTENSIONS)}.",
        )

    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large -- max {MAX_UPLOAD_SIZE_MB}MB per upload.",
        )


def enforce_row_cap(row_count: int) -> None:
    if row_count > MAX_UPLOAD_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"File has {row_count} rows -- max {MAX_UPLOAD_ROWS} per upload. Split it into smaller files.",
        )
