from collections.abc import Sequence
from functools import lru_cache
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import get_settings
from backend.app.core.time import utc_now
from backend.app.models import Asset, AssetEmbedding, AssetTag, Task


class EmbeddingModelError(RuntimeError):
    pass


def build_asset_embedding_text(asset: Asset) -> str | None:
    tags = "、".join(link.tag.name for link in asset.tags if link.tag)
    has_trusted_semantics = bool(
        asset.description
        or asset.author
        or tags
        or (asset.semantic_eligible and asset.extracted_text)
    )
    if not has_trusted_semantics:
        return None
    return "\n".join(
        part
        for part in [
            f"名称：{asset.name}",
            f"类型：{asset.asset_type}",
            f"格式：{asset.extension}",
            f"格式解析内容：{asset.extracted_text}"
            if asset.semantic_eligible and asset.extracted_text
            else "",
            f"描述：{asset.description}" if asset.description else "",
            f"标签：{tags}" if tags else "",
            f"作者：{asset.author}" if asset.author else "",
        ]
        if part
    )


def embedding_content_hash(text: str, model: str) -> str:
    return sha256(f"{model}\0{text}".encode()).hexdigest()


@lru_cache(maxsize=1)
def get_embedding_model():
    settings = get_settings()
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            settings.embedding_model,
            device=settings.embedding_device,
            cache_folder=str(settings.model_cache_dir),
        )
    except Exception as error:
        raise EmbeddingModelError(f"Unable to load {settings.embedding_model}: {error}") from error


def encode_texts(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    try:
        vectors = get_embedding_model().encode(
            list(texts),
            batch_size=settings.embedding_batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
    except EmbeddingModelError:
        raise
    except Exception as error:
        raise EmbeddingModelError(f"Embedding generation failed: {error}") from error

    result = [vector.tolist() for vector in vectors]
    if any(len(vector) != settings.embedding_dimensions for vector in result):
        raise EmbeddingModelError(
            f"{settings.embedding_model} returned an unexpected embedding dimension"
        )
    return result


def _task_was_canceled(db: Session, task: Task) -> bool:
    db.expire(task, ["status"])
    return task.status == "canceled"


def index_user_assets(
    db: Session,
    *,
    task_id: str,
    user_id: str,
    force: bool = False,
) -> None:
    settings = get_settings()
    task = db.get(Task, task_id)
    if task is None or task.status == "canceled":
        return

    task.status = "running"
    task.started_at = utc_now()
    task.heartbeat_at = task.started_at
    task.message = f"Loading {settings.embedding_model}"
    db.commit()

    try:
        assets = list(
            db.scalars(
                select(Asset)
                .options(selectinload(Asset.tags).selectinload(AssetTag.tag))
                .where(
                    Asset.user_id == user_id,
                    Asset.is_deleted.is_(False),
                )
                .order_by(Asset.id)
            )
        )
        task.total = len(assets)
        task.message = "Generating semantic index"
        task.heartbeat_at = utc_now()
        db.commit()

        existing = {
            row.asset_id: row
            for row in db.scalars(
                select(AssetEmbedding).where(AssetEmbedding.user_id == user_id)
            )
        }
        indexed = 0
        skipped = 0
        ineligible = 0
        removed = 0
        batch_size = max(settings.embedding_batch_size, 1)

        for offset in range(0, len(assets), batch_size):
            if _task_was_canceled(db, task):
                task.message = "Embedding indexing canceled"
                task.finished_at = utc_now()
                task.result = {"indexed": indexed, "skipped": skipped, "total": len(assets)}
                db.commit()
                return

            batch_assets = assets[offset : offset + batch_size]
            pending: list[tuple[Asset, str, str]] = []
            for asset in batch_assets:
                source_text = build_asset_embedding_text(asset)
                if source_text is None:
                    ineligible += 1
                    row = existing.pop(asset.id, None)
                    if row is not None:
                        db.delete(row)
                        removed += 1
                    continue
                content_hash = embedding_content_hash(source_text, settings.embedding_model)
                row = existing.get(asset.id)
                if (
                    not force
                    and row is not None
                    and row.model == settings.embedding_model
                    and row.content_hash == content_hash
                ):
                    skipped += 1
                    continue
                pending.append((asset, source_text, content_hash))

            vectors = encode_texts([item[1] for item in pending])
            for (asset, source_text, content_hash), vector in zip(pending, vectors, strict=True):
                row = existing.get(asset.id)
                if row is None:
                    row = AssetEmbedding(asset_id=asset.id, user_id=user_id)
                    db.add(row)
                    existing[asset.id] = row
                row.model = settings.embedding_model
                row.content_hash = content_hash
                row.source_text = source_text
                row.embedding = vector
                indexed += 1

            task.processed = min(offset + len(batch_assets), len(assets))
            task.progress = int(task.processed / max(task.total, 1) * 100)
            task.heartbeat_at = utc_now()
            db.commit()

        task.status = "success"
        task.progress = 100
        task.message = (
            f"Semantic index ready: indexed {indexed}, unchanged {skipped}, "
            f"metadata-only {ineligible}, removed {removed}"
        )
        task.result = {
            "indexed": indexed,
            "skipped": skipped,
            "ineligible": ineligible,
            "removed": removed,
            "total": len(assets),
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
        }
        task.heartbeat_at = utc_now()
        task.finished_at = utc_now()
        db.commit()
    except Exception as error:
        db.rollback()
        task = db.get(Task, task_id)
        if task is not None and task.status != "canceled":
            task.status = "failed"
            task.error = str(error)
            task.message = "Semantic indexing failed"
            task.heartbeat_at = utc_now()
            task.finished_at = utc_now()
            db.commit()
