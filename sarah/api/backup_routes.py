"""
Backup and recovery API routes.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from sarah.api.dependencies import get_current_user
from sarah.services.backup import backup_service
from sarah.sanctuary.permissions import require_permission

router = APIRouter(prefix="/api/backup", tags=["backup"])


class BackupResponse(BaseModel):
    """Response model for backup operations."""

    path: str
    name: str
    type: str
    timestamp: str
    size: int


class RestoreRequest(BaseModel):
    """Request model for restore operations."""

    backup_path: str
    components: Optional[List[str]] = None


class BackupListResponse(BaseModel):
    """Response model for listing backups."""

    backups: List[BackupResponse]
    total: int


@router.post("/create")
@require_permission("backup.create")
async def create_backup(
    background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)
):
    """Create a manual backup of the system."""
    try:
        # Run backup in background
        background_tasks.add_task(backup_service.create_backup, "manual")

        return {"message": "Backup initiated", "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-sync")
@require_permission("backup.create")
async def create_backup_sync(current_user: dict = Depends(get_current_user)):
    """Create a manual backup of the system (synchronous)."""
    try:
        backup_path = await backup_service.create_backup("manual")

        # Get backup info
        backups = await backup_service.list_backups()
        backup_info = next((b for b in backups if b["path"] == backup_path), None)

        if not backup_info:
            raise HTTPException(status_code=500, detail="Backup created but not found")

        return BackupResponse(**backup_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=BackupListResponse)
@require_permission("backup.read")
async def list_backups(
    backup_type: Optional[str] = None, current_user: dict = Depends(get_current_user)
):
    """List all available backups."""
    try:
        backups = await backup_service.list_backups()

        # Filter by type if specified
        if backup_type:
            backups = [b for b in backups if b["type"] == backup_type]

        return BackupListResponse(
            backups=[BackupResponse(**b) for b in backups], total=len(backups)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restore")
@require_permission("backup.restore")
async def restore_backup(
    request: RestoreRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Restore system from a backup."""
    try:
        # Verify backup exists
        backups = await backup_service.list_backups()
        if not any(b["path"] == request.backup_path for b in backups):
            raise HTTPException(status_code=404, detail="Backup not found")

        # Run restore in background
        background_tasks.add_task(
            backup_service.restore_backup, request.backup_path, request.components
        )

        return {
            "message": "Restore initiated",
            "status": "processing",
            "backup_path": request.backup_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{backup_name}")
@require_permission("backup.delete")
async def delete_backup(
    backup_name: str, current_user: dict = Depends(get_current_user)
):
    """Delete a specific backup."""
    try:
        # Find backup
        backups = await backup_service.list_backups()
        backup = next((b for b in backups if b["name"] == backup_name), None)

        if not backup:
            raise HTTPException(status_code=404, detail="Backup not found")

        # Delete backup file
        import os

        os.remove(backup["path"])

        return {"message": "Backup deleted successfully", "backup_name": backup_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedule")
@require_permission("backup.read")
async def get_backup_schedule(current_user: dict = Depends(get_current_user)):
    """Get the current backup schedule."""
    try:
        jobs = backup_service.scheduler.get_jobs()

        schedule = []
        for job in jobs:
            schedule.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                    "trigger": str(job.trigger),
                }
            )

        return {
            "schedule": schedule,
            "timezone": str(backup_service.scheduler.timezone),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
