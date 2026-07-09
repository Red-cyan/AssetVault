from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.api.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.models import Asset, Project, ProjectAsset, User
from backend.app.schemas.asset import AssetRead
from backend.app.schemas.project import (
    ProjectAssetAdd,
    ProjectAssetRead,
    ProjectCreate,
    ProjectDetail,
    ProjectRead,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def ensure_cover_asset(db: Session, *, user_id: str, asset_id: str | None) -> None:
    if asset_id is None:
        return
    asset = db.get(Asset, asset_id)
    if asset is None or asset.user_id != user_id:
        raise HTTPException(status_code=400, detail="Cover asset not found")


def serialize_project(project: Project, asset_count: int = 0) -> ProjectRead:
    data = ProjectRead.model_validate(project).model_dump()
    data["asset_count"] = asset_count
    return ProjectRead(**data)


def serialize_project_detail(project: Project) -> ProjectDetail:
    data = ProjectRead.model_validate(project).model_dump()
    data["asset_count"] = len(project.assets)
    data["assets"] = [
        ProjectAssetRead(
            role=link.role,
            created_at=link.created_at,
            asset=AssetRead.model_validate(link.asset),
        )
        for link in project.assets
    ]
    return ProjectDetail(**data)


@router.get("", response_model=list[ProjectRead])
def list_projects(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ProjectRead]:
    rows = db.execute(
        select(Project, func.count(ProjectAsset.asset_id))
        .outerjoin(ProjectAsset, ProjectAsset.project_id == Project.id)
        .where(Project.user_id == current_user.id)
        .group_by(Project.id)
        .order_by(Project.updated_at.desc())
    )
    return [serialize_project(project, asset_count) for project, asset_count in rows]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectRead:
    ensure_cover_asset(db, user_id=current_user.id, asset_id=payload.cover_asset_id)
    project = Project(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        cover_asset_id=payload.cover_asset_id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return serialize_project(project)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectDetail:
    project = db.scalar(
        select(Project)
        .options(selectinload(Project.assets).selectinload(ProjectAsset.asset))
        .where(Project.id == project_id, Project.user_id == current_user.id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return serialize_project_detail(project)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectRead:
    project = db.get(Project, project_id)
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    data = payload.model_dump(exclude_unset=True)
    ensure_cover_asset(db, user_id=current_user.id, asset_id=data.get("cover_asset_id"))
    for field, value in data.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return serialize_project(project, len(project.assets))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    project = db.get(Project, project_id)
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()


@router.post("/{project_id}/assets", response_model=ProjectDetail)
def add_project_asset(
    project_id: str,
    payload: ProjectAssetAdd,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectDetail:
    project = db.scalar(
        select(Project)
        .options(selectinload(Project.assets).selectinload(ProjectAsset.asset))
        .where(Project.id == project_id, Project.user_id == current_user.id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    asset = db.get(Asset, payload.asset_id)
    if asset is None or asset.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Asset not found")
    existing = db.get(ProjectAsset, {"project_id": project_id, "asset_id": payload.asset_id})
    if existing is None:
        db.add(ProjectAsset(project_id=project_id, asset_id=payload.asset_id, role=payload.role))
    else:
        existing.role = payload.role
    db.commit()
    return get_project(project_id, db, current_user)


@router.delete("/{project_id}/assets/{asset_id}", response_model=ProjectDetail)
def remove_project_asset(
    project_id: str,
    asset_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectDetail:
    project = db.get(Project, project_id)
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    link = db.get(ProjectAsset, {"project_id": project_id, "asset_id": asset_id})
    if link is not None:
        db.delete(link)
        db.commit()
    return get_project(project_id, db, current_user)
