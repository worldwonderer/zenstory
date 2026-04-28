"""
Material upload API endpoints.

Handles file upload and job retry operations for the material library:
- Upload novels and start decomposition
- Retry failed decomposition jobs
- Internal file download for Prefect workers
"""
import contextlib
import json
import os
import re
import secrets

import chardet
from fastapi import APIRouter, Depends, Header, Query, UploadFile
from fastapi import File as FastAPIFile
from fastapi.responses import FileResponse
from services.auth import get_current_active_user
from sqlmodel import Session, select

from config.datetime_utils import utcnow
from core.error_codes import ErrorCode
from core.error_handler import APIException
from core.permissions import (
    FeatureNotIncludedException,
    QuotaExceededException,
    check_quota,
    consume_quota,
    require_quota,
)
from database import get_session
from models import User
from models.material_models import IngestionJob, Novel
from services.quota_service import quota_service
from utils.logger import get_logger

from .constants import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, MAX_TEXT_CHARACTERS
from .helpers import _get_novel_or_404, _start_flow_deployment
from .schemas import MaterialUploadResponse

logger = get_logger(__name__)

# Router without prefix/tags - will be set by parent router
router = APIRouter()

SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
ENCODING_DETECTION_SAMPLE_SIZE = 10_000
ENCODING_CONFIDENCE_THRESHOLD = 0.7
UTF8_BOM = b"\xef\xbb\xbf"
UTF16_LE_BOM = b"\xff\xfe"
UTF16_BE_BOM = b"\xfe\xff"


def _sanitize_original_filename(filename: str) -> str:
    """
    Sanitize client-provided filename to prevent path traversal and unsafe chars.
    """
    base_name = os.path.basename(filename).replace("\x00", "").strip()
    if not base_name:
        raise APIException(error_code=ErrorCode.VALIDATION_ERROR, status_code=400)

    stem, ext = os.path.splitext(base_name)
    safe_ext = ext.lower()
    if safe_ext not in ALLOWED_EXTENSIONS:
        raise APIException(error_code=ErrorCode.FILE_TYPE_INVALID, status_code=400)

    safe_stem = SAFE_FILENAME_RE.sub("_", stem).strip("._")
    if not safe_stem:
        safe_stem = "material"

    return f"{safe_stem}{safe_ext}"


def _build_safe_upload_path(upload_dir: str, filename: str) -> str:
    """
    Build a canonical path under upload_dir and reject path escape.
    """
    if not filename or filename != os.path.basename(filename) or "\x00" in filename:
        raise APIException(error_code=ErrorCode.VALIDATION_ERROR, status_code=400)

    upload_dir_real = os.path.realpath(upload_dir)
    file_path = os.path.realpath(os.path.join(upload_dir_real, filename))
    if os.path.commonpath([upload_dir_real, file_path]) != upload_dir_real:
        raise APIException(error_code=ErrorCode.VALIDATION_ERROR, status_code=400)
    return file_path


def _decode_upload_text(content_bytes: bytes) -> str:
    """Decode uploaded text content for character-limit validation."""
    if not content_bytes:
        return ""

    if content_bytes.startswith(UTF8_BOM):
        return content_bytes.decode("utf-8-sig")
    if content_bytes.startswith(UTF16_LE_BOM) or content_bytes.startswith(UTF16_BE_BOM):
        return content_bytes.decode("utf-16")

    detected = chardet.detect(content_bytes[:ENCODING_DETECTION_SAMPLE_SIZE])
    detected_encoding = detected.get("encoding")
    detected_confidence = float(detected.get("confidence") or 0.0)

    encodings_to_try: list[str] = []
    if (
        isinstance(detected_encoding, str)
        and detected_encoding
        and detected_confidence >= ENCODING_CONFIDENCE_THRESHOLD
    ):
        normalized_detected_encoding = detected_encoding.lower().replace("_", "-")
        encoding_aliases = {
            "utf8": "utf-8",
            "gbk": "gb18030",
            "gb2312": "gb18030",
            "gb-2312": "gb18030",
        }
        encodings_to_try.append(
            encoding_aliases.get(normalized_detected_encoding, normalized_detected_encoding)
        )
    encodings_to_try.extend(["utf-8", "gb18030"])

    seen_encodings: set[str] = set()
    for encoding in encodings_to_try:
        normalized = encoding.lower()
        if normalized in seen_encodings:
            continue
        seen_encodings.add(normalized)

        with contextlib.suppress(UnicodeDecodeError, LookupError):
            return content_bytes.decode(encoding)

    return content_bytes.decode("utf-8", errors="ignore")


def _is_compensatory_retry(job: IngestionJob) -> bool:
    """
    Return True when a retry should be treated as compensatory and not re-billed.

    For now this is intentionally conservative: only deployment-start failures
    are considered infrastructure failures eligible for a no-charge retry.
    """
    if not job.error_details:
        return False

    with contextlib.suppress(Exception):
        parsed = json.loads(job.error_details)
        if isinstance(parsed, dict) and parsed.get("stage") == "deployment_start":
            return True

    return False


# ==================== Internal Endpoints ====================

@router.get("/internal/files/{filename}")
async def download_upload_file(
    filename: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Internal endpoint for Prefect worker to download uploaded files.

    Verifies file ownership based on filename format: {user_id}_{timestamp}_{original_filename}
    """
    from config.material_settings import material_settings

    # Verify file ownership (filename format: {user_id}_{timestamp}_{original_filename})
    if not filename.startswith(f"{current_user.id}_"):
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=403,
            detail="Not authorized to access this file",
        )

    file_path = _build_safe_upload_path(material_settings.UPLOAD_FOLDER, filename)
    if not os.path.isfile(file_path):
        raise APIException(error_code=ErrorCode.VALIDATION_ERROR, status_code=404)
    return FileResponse(file_path)


@router.get("/internal/system/files/{filename}")
async def download_upload_file_for_worker(
    filename: str,
    user_id: str = Query(..., description="Owner user id"),
    internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
):
    """
    Internal endpoint for worker-to-server file download.

    Uses a shared secret (`MATERIAL_INTERNAL_TOKEN`) and explicit user_id ownership check.
    """
    from config.material_settings import material_settings

    expected_token = os.getenv("MATERIAL_INTERNAL_TOKEN", "")
    if not expected_token or not internal_token or not secrets.compare_digest(internal_token, expected_token):
        raise APIException(
            error_code=ErrorCode.AUTH_UNAUTHORIZED,
            status_code=401,
            message="Invalid internal token",
        )

    if not filename.startswith(f"{user_id}_"):
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=403,
            message="Not authorized to access this file",
        )

    file_path = _build_safe_upload_path(material_settings.UPLOAD_FOLDER, filename)
    if not os.path.isfile(file_path):
        raise APIException(error_code=ErrorCode.VALIDATION_ERROR, status_code=404)
    return FileResponse(file_path)


# ==================== Upload Endpoints ====================

@router.post("/upload", response_model=MaterialUploadResponse)
@require_quota("material_decompose")
async def upload_material(
    file: UploadFile = FastAPIFile(...),
    title: str | None = Query(None, description="Novel title (optional, auto-detect from file)"),
    author: str | None = Query(None, description="Author name (optional)"),
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """
    Upload a novel file and start decomposition.

    Constraints:
    - Only .txt files allowed
    - Maximum 100MB file size
    - Maximum 300,000 characters per novel
    - File will be saved to uploads/ directory
    - Returns success only after the decomposition flow dispatch is accepted
    """
    # 1. Validate file extension
    if not file.filename:
        raise APIException(error_code=ErrorCode.VALIDATION_ERROR, status_code=400)

    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise APIException(
            error_code=ErrorCode.FILE_TYPE_INVALID,
            status_code=400,
        )

    # 2. Read and validate file size
    content_bytes = await file.read()
    if len(content_bytes) > MAX_FILE_SIZE:
        raise APIException(
            error_code=ErrorCode.FILE_TOO_LARGE,
            status_code=400,
        )

    content = _decode_upload_text(content_bytes)
    char_count = len(content)
    if char_count > MAX_TEXT_CHARACTERS:
        raise APIException(
            error_code=ErrorCode.FILE_CONTENT_TOO_LONG,
            status_code=400,
        )

    # 3. Save file to uploads directory
    from config.material_settings import material_settings

    upload_dir = material_settings.UPLOAD_FOLDER
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename with timestamp and sanitized original filename
    timestamp = utcnow().strftime("%Y%m%d_%H%M%S")
    original_filename = file.filename
    sanitized_original_filename = _sanitize_original_filename(original_filename)
    safe_filename = f"{current_user.id}_{timestamp}_{sanitized_original_filename}"
    file_path = _build_safe_upload_path(upload_dir, safe_filename)

    with open(file_path, "wb") as f:
        f.write(content_bytes)

    logger.info(f"File saved: {file_path} ({len(content_bytes)} bytes)")

    # 4. Use provided title or extract from filename
    novel_title = title or os.path.splitext(file.filename)[0]

    # 5. Create Novel record (will be populated by flow)
    source_meta = {
        "file_path": file_path,
        "file_size": len(content_bytes),
        "char_count": char_count,
        "original_filename": original_filename,
    }

    novel = Novel(
        user_id=current_user.id,
        title=novel_title,
        author=author,
        source_meta=json.dumps(source_meta),
    )
    session.add(novel)
    session.commit()
    session.refresh(novel)

    # 6. Create IngestionJob record
    job = IngestionJob(
        novel_id=novel.id,
        source_path=file_path,
        status="pending",
        total_chapters=0,
        processed_chapters=0,
    )
    job.update_stage_progress("queue", "pending", message="等待调度")
    session.add(job)
    session.commit()
    session.refresh(job)

    # 7. Start flow via Prefect deployment and only return success after dispatch is accepted.
    flow_run_id = await _start_flow_deployment(
        file_path=file_path,
        novel_title=novel_title,
        author=author,
        user_id=str(current_user.id),
        novel_id=novel.id,
    )

    if flow_run_id is None:
        raise APIException(
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=503,
            detail="Failed to dispatch ingestion flow",
        )

    logger.info(
        "Novel ingestion dispatched: novel_id=%s, job_id=%s, flow_run_id=%s",
        novel.id,
        job.id,
        flow_run_id,
    )

    return MaterialUploadResponse(
        novel_id=novel.id,
        title=novel.title,
        job_id=job.id,
        status="pending",
        message="Novel upload successful, decomposition started",
    )


# ==================== Retry Endpoints ====================

@router.post("/{novel_id}/retry")
async def retry_material_job(
    novel_id: int,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """
    Retry failed decomposition task.

    Creates a new ingestion job and restarts the flow from the beginning.
    """
    # Verify novel ownership and soft delete check
    novel = _get_novel_or_404(session, novel_id, current_user.id)

    # Get latest job
    latest_job = session.exec(
        select(IngestionJob)
        .where(IngestionJob.novel_id == novel_id)
        .order_by(IngestionJob.created_at.desc())
    ).first()

    if not latest_job:
        raise APIException(error_code=ErrorCode.FILE_NOT_FOUND, status_code=404)

    if latest_job.status in {"pending", "processing"}:
        raise APIException(
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=409,
            detail="Decomposition job is already running",
        )

    # Only allow retry for failed jobs
    if latest_job.status != "failed":
        raise APIException(
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=400,
        )

    if not quota_service.has_feature_access(
        session, current_user.id, "materials_library_access"
    ):
        raise FeatureNotIncludedException(feature_type="material_decompose")

    compensatory_retry = _is_compensatory_retry(latest_job)
    if not compensatory_retry:
        check_quota("material_decompose", session, current_user.id)

    # Create new job
    new_job = IngestionJob(
        novel_id=novel_id,
        source_path=latest_job.source_path,
        status="pending",
        total_chapters=0,
        processed_chapters=0,
    )
    new_job.update_stage_progress("queue", "pending", message="等待重试调度")
    session.add(new_job)
    session.commit()
    session.refresh(new_job)

    if not compensatory_retry and not consume_quota(
        "material_decompose", session, current_user.id
    ):
        session.delete(new_job)
        session.commit()
        allowed, used, limit = quota_service.check_feature_quota(
            session, current_user.id, "material_decompose"
        )
        if not allowed:
            raise QuotaExceededException(
                feature_type="material_decompose",
                used=used,
                limit=limit,
            )

    # Parse source_meta to get file path
    source_meta = {}
    if novel.source_meta:
        with contextlib.suppress(Exception):
            parsed = json.loads(novel.source_meta)
            if isinstance(parsed, dict):
                source_meta = parsed
    file_path = source_meta.get("file_path", latest_job.source_path)

    flow_run_id = await _start_flow_deployment(
        file_path=file_path,
        novel_title=novel.title,
        author=novel.author,
        user_id=str(current_user.id),
        novel_id=novel_id,
    )

    if flow_run_id is None:
        raise APIException(
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=503,
            detail="Failed to dispatch ingestion flow",
        )

    logger.info(
        "Material job retry dispatched: novel_id=%s, new_job_id=%s, flow_run_id=%s",
        novel_id,
        new_job.id,
        flow_run_id,
    )

    return {
        "message": "Retry started successfully",
        "job_id": new_job.id,
        "status": "pending",
    }


__all__ = ["router"]
