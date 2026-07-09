from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.db.session import SessionLocal, get_db
from backend.app.models import Asset, Folder, Task, User
from backend.app.schemas.folder import FolderCreate, FolderRead
from backend.app.schemas.task import TaskRead
from backend.app.services.asset_scanner import scan_folder

router = APIRouter(prefix="/folders", tags=["folders"])


def run_scan_task(task_id: str, user_id: str, folder_id: str) -> None:
    db = SessionLocal()
    try:
        scan_folder(db, task_id=task_id, user_id=user_id, folder_id=folder_id)
    finally:
        db.close()


@router.get("", response_model=list[FolderRead])
def list_folders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[Folder]:
    return list(db.scalars(select(Folder).where(Folder.user_id == current_user.id)))


@router.post("", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: FolderCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Folder:
    path = Path(payload.path).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Folder does not exist")
    folder = Folder(user_id=current_user.id, name=payload.name or path.name, path=str(path))
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


@router.post("/{folder_id}/scan", response_model=TaskRead, status_code=status.HTTP_202_ACCEPTED)
def scan(
    folder_id: str,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Task:
    folder = db.get(Folder, folder_id)
    if folder is None or folder.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Folder not found")
    task = Task(
        user_id=current_user.id,
        type="scan",
        status="pending",
        payload={"folder_id": folder.id, "path": folder.path},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    background_tasks.add_task(run_scan_task, task.id, current_user.id, folder.id)
    return task


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    folder = db.get(Folder, folder_id)
    if folder is None or folder.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Folder not found")
    db.execute(update(Asset).where(Asset.folder_id == folder_id).values(folder_id=None))
    db.delete(folder)
    db.commit()
