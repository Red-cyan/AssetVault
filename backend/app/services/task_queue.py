from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Event, Lock, Thread
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.time import utc_now
from backend.app.db.session import SessionLocal
from backend.app.models import Task
from backend.app.services.asset_scanner import scan_folder
from backend.app.services.embedding_service import index_user_assets

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TaskClaim:
    id: str
    user_id: str
    type: str
    payload: dict


def claim_next_task(
    db: Session,
    *,
    worker_id: str,
    now: datetime | None = None,
) -> TaskClaim | None:
    claimed_at = now or utc_now()
    task = db.scalar(
        select(Task)
        .where(
            Task.status == "pending",
            Task.available_at <= claimed_at,
        )
        .order_by(Task.available_at, Task.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if task is None:
        db.rollback()
        return None

    task.status = "running"
    task.attempts += 1
    task.worker_id = worker_id
    task.started_at = claimed_at
    task.finished_at = None
    task.heartbeat_at = claimed_at
    task.error = None
    task.result = None
    task.message = f"Claimed by persistent worker, attempt {task.attempts}/{task.max_attempts}"
    db.commit()
    return TaskClaim(
        id=task.id,
        user_id=task.user_id,
        type=task.type,
        payload=dict(task.payload or {}),
    )


def recover_stale_tasks(
    db: Session,
    *,
    stale_before: datetime,
    now: datetime | None = None,
) -> int:
    recovered_at = now or utc_now()
    result = db.execute(
        update(Task)
        .where(
            Task.status == "running",
            or_(Task.heartbeat_at.is_(None), Task.heartbeat_at < stale_before),
        )
        .values(
            status="pending",
            worker_id=None,
            available_at=recovered_at,
            started_at=None,
            finished_at=None,
            heartbeat_at=None,
            message="Recovered after worker interruption",
        )
    )
    db.commit()
    return result.rowcount or 0


def _mark_unhandled_failure(db: Session, task_id: str, error: Exception) -> None:
    db.rollback()
    task = db.get(Task, task_id)
    if task is None or task.status == "canceled":
        return
    task.status = "failed"
    task.error = str(error)
    task.message = "Persistent task execution failed"
    task.finished_at = utc_now()
    db.commit()


def finalize_or_retry(db: Session, task_id: str) -> None:
    settings = get_settings()
    db.expire_all()
    task = db.get(Task, task_id)
    if task is None:
        return
    if task.status == "failed" and task.attempts < task.max_attempts:
        delay = settings.task_retry_delay_seconds * max(task.attempts, 1)
        task.status = "pending"
        task.available_at = utc_now() + timedelta(seconds=delay)
        task.progress = 0
        task.total = 0
        task.processed = 0
        task.started_at = None
        task.finished_at = None
        task.heartbeat_at = None
        task.worker_id = None
        task.result = None
        task.message = (
            f"Retry scheduled in {delay}s after attempt {task.attempts}/{task.max_attempts}"
        )
    else:
        task.worker_id = None
    db.commit()


def execute_claim(claim: TaskClaim) -> None:
    db = SessionLocal()
    try:
        if claim.type == "scan":
            folder_id = claim.payload.get("folder_id")
            if not isinstance(folder_id, str) or not folder_id:
                raise ValueError("Scan task is missing folder_id")
            scan_folder(
                db,
                task_id=claim.id,
                user_id=claim.user_id,
                folder_id=folder_id,
            )
        elif claim.type == "embedding":
            index_user_assets(
                db,
                task_id=claim.id,
                user_id=claim.user_id,
                force=bool(claim.payload.get("force", False)),
            )
        else:
            raise ValueError(f"Unsupported persistent task type: {claim.type}")
    except Exception as error:
        logger.exception("Task %s failed outside its service boundary", claim.id)
        _mark_unhandled_failure(db, claim.id, error)
    finally:
        finalize_or_retry(db, claim.id)
        db.close()


def process_next_task(worker_id: str) -> bool:
    db = SessionLocal()
    try:
        claim = claim_next_task(db, worker_id=worker_id)
    finally:
        db.close()
    if claim is None:
        return False
    execute_claim(claim)
    return True


class PersistentTaskWorker:
    def __init__(self) -> None:
        self.worker_id = f"assetvault-{uuid4()}"
        self._stop = Event()
        self._wake = Event()
        self._lock = Lock()
        self._thread: Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            self._stop.clear()
            self._wake.clear()
            settings = get_settings()
            with SessionLocal() as db:
                recovered = recover_stale_tasks(
                    db,
                    stale_before=utc_now()
                    - timedelta(seconds=settings.task_stale_after_seconds),
                )
            if recovered:
                logger.warning("Recovered %s stale task(s)", recovered)
            self._thread = Thread(
                target=self._run,
                name="assetvault-task-worker",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            if thread is None:
                return
            self._stop.set()
            self._wake.set()
        thread.join(timeout=5)
        with self._lock:
            self._thread = None

    def notify(self) -> None:
        self._wake.set()

    def _run(self) -> None:
        poll_seconds = max(get_settings().task_worker_poll_seconds, 0.1)
        while not self._stop.is_set():
            try:
                processed = process_next_task(self.worker_id)
            except Exception:
                logger.exception("Persistent task worker polling failed")
                processed = False
            if processed:
                continue
            self._wake.wait(timeout=poll_seconds)
            self._wake.clear()


task_worker = PersistentTaskWorker()
