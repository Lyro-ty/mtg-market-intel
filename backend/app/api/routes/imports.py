"""API routes for collection imports."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.import_job import ImportPlatform, ImportStatus
from app.models.user import User
from app.services.imports import ImportService


router = APIRouter(prefix="/imports", tags=["imports"])


class ImportJobResponse(BaseModel):
    """Response schema for import job."""
    id: int
    platform: str
    status: str
    filename: str
    file_size: int
    total_rows: int
    matched_cards: int
    unmatched_cards: int
    imported_count: int
    skipped_count: int
    error_count: int
    error_message: Optional[str] = None
    preview_data: Optional[dict[str, Any]] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class ImportListResponse(BaseModel):
    """Response for listing imports."""
    items: list[ImportJobResponse]
    total: int
    limit: int
    offset: int


class ConfirmImportRequest(BaseModel):
    """Request to confirm an import."""
    skip_unmatched: bool = True


def job_to_response(job) -> ImportJobResponse:
    """Convert ImportJob to response schema."""
    return ImportJobResponse(
        id=job.id,
        platform=job.platform.value if isinstance(job.platform, ImportPlatform) else job.platform,
        status=job.status.value if isinstance(job.status, ImportStatus) else job.status,
        filename=job.filename,
        file_size=job.file_size,
        total_rows=job.total_rows,
        matched_cards=job.matched_cards,
        unmatched_cards=job.unmatched_cards,
        imported_count=job.imported_count,
        skipped_count=job.skipped_count,
        error_count=job.error_count,
        error_message=job.error_message,
        preview_data=job.preview_data,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        created_at=job.created_at.isoformat(),
    )


@router.post("/upload", response_model=ImportJobResponse, status_code=status.HTTP_201_CREATED)
async def upload_import_file(
    file: UploadFile = File(...),
    platform: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    """
    Upload a collection CSV file for import.

    Supported platforms: moxfield, archidekt, deckbox, tcgplayer, generic_csv
    """
    # Validate platform
    try:
        import_platform = ImportPlatform(platform)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform. Supported: {[p.value for p in ImportPlatform]}",
        )

    # Validate file extension
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported",
        )

    # Validate content type (MIME type)
    allowed_content_types = [
        "text/csv",
        "text/plain",
        "application/csv",
        "application/vnd.ms-excel",
    ]

    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Expected CSV, got {file.content_type}",
        )

    # Read file content
    content = await file.read()

    # Check first 1KB for non-printable characters (UTF-8 validation)
    sample = content[:1024]
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File contains invalid characters. Must be UTF-8 text.",
        )

    # Decode full content
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded",
        )

    # Limit file size (10MB)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10MB",
        )

    service = ImportService(db)
    job = await service.create_import_job(
        user_id=current_user.id,
        filename=file.filename,
        content=content_str,
        platform=import_platform,
    )

    return job_to_response(job)


@router.post("/{job_id}/preview", response_model=ImportJobResponse)
async def generate_preview(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    """
    Parse the uploaded file and generate a preview of matched cards.
    """
    service = ImportService(db)
    try:
        job = await service.generate_preview(job_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return job_to_response(job)


@router.post("/{job_id}/confirm", response_model=ImportJobResponse)
async def confirm_import(
    job_id: int,
    request: ConfirmImportRequest = ConfirmImportRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    """
    Confirm and execute the import, creating inventory items.
    """
    service = ImportService(db)
    try:
        job = await service.confirm_import(
            job_id,
            current_user.id,
            skip_unmatched=request.skip_unmatched,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return job_to_response(job)


@router.post("/{job_id}/cancel", response_model=ImportJobResponse)
async def cancel_import(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    """
    Cancel a pending or preview-ready import.
    """
    service = ImportService(db)
    try:
        job = await service.cancel_import(job_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return job_to_response(job)


@router.get("/{job_id}", response_model=ImportJobResponse)
async def get_import_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    """
    Get details of an import job.
    """
    service = ImportService(db)
    job = await service._get_job(job_id, current_user.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found",
        )

    return job_to_response(job)


@router.get("", response_model=ImportListResponse)
async def list_imports(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportListResponse:
    """
    List user's import jobs with pagination.
    """
    service = ImportService(db)
    jobs, total = await service.get_user_imports(
        current_user.id,
        limit=min(limit, 100),
        offset=offset,
    )

    return ImportListResponse(
        items=[job_to_response(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )
