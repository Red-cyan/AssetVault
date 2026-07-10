from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.api.v1.folders import create_scan_task, run_scan_task
from backend.app.api.v1.search import create_embedding_task, run_embedding_task
from backend.app.db.session import get_db
from backend.app.models import Folder, Task, User
from backend.app.schemas.task import TaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
def list_tasks(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[Task]:
    return list(
        db.scalars(
            select(Task)
            .where(Task.user_id == current_user.id)
            .order_by(Task.created_at.desc())
            .limit(50)
        )
    )


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/cancel", response_model=TaskRead)
def cancel_task(
    task_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in {"pending", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending or running tasks can be canceled",
        )
    task.status = "canceled"
    task.message = "Cancellation requested"
    task.finished_at = datetime.now()
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/retry", response_model=TaskRead, status_code=status.HTTP_202_ACCEPTED)
def retry_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Task:
    previous = db.get(Task, task_id)
    if previous is None or previous.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    if previous.type not in {"scan", "embedding"} or previous.status in {"pending", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed scan tasks can be retried",
        )
    if previous.type == "embedding":
        force = bool(previous.payload.get("force")) if previous.payload else False
        task = create_embedding_task(db, user_id=current_user.id, force=force)
        task.payload = {**(task.payload or {}), "retry_of": previous.id}
        db.commit()
        db.refresh(task)
        background_tasks.add_task(run_embedding_task, task.id, current_user.id, force)
        return task

    folder_id = previous.payload.get("folder_id") if previous.payload else None
    folder = db.get(Folder, folder_id) if folder_id else None
    if folder is None or folder.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Source folder not found")

    task = create_scan_task(db, user_id=current_user.id, folder=folder)
    task.payload = {**(task.payload or {}), "retry_of": previous.id}
    db.commit()
    db.refresh(task)
    background_tasks.add_task(run_scan_task, task.id, current_user.id, folder.id)
    return task
