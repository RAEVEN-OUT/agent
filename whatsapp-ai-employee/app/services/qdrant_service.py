import uuid
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.core.retry import external_retry

log = get_logger("qdrant")

try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        FilterSelector,
        HnswConfigDiff,
        MatchValue,
        PayloadSchemaType,
        PointStruct,
        VectorParams,
    )
except Exception:  # noqa: BLE001  pragma: no cover
    AsyncQdrantClient = None


@dataclass
class Chunk:
    id: str
    text: str
    score: float
    metadata: dict


class QdrantService:
    """Multi-tenant vector store: one collection, isolated by payload filter.

    NOTE: Qdrant and Postgres share no transaction. Any catalog/FAQ write must
    update both, and deletes must purge vectors here — otherwise searches
    return answers for products that no longer exist.
    """

    def __init__(self) -> None:
        self.client = None
        if AsyncQdrantClient:
            self.client = AsyncQdrantClient(
                host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=10.0
            )
        self.collection = settings.QDRANT_COLLECTION
        self.vector_size = settings.GEMINI_EMBEDDING_DIMENSIONS

    async def ping(self) -> bool:
        if not self.client:
            return False
        try:
            await self.client.get_collections()
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning({"event": "qdrant_unavailable", "error": str(exc)})
            return False

    async def ensure_collection(self) -> None:
        if not self.client:
            return
        existing = await self.client.get_collections()
        if any(c.name == self.collection for c in existing.collections):
            return

        await self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
        )
        for field in ("tenant_id", "source_type", "source_id"):
            await self.client.create_payload_index(
                collection_name=self.collection,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        await self.client.create_payload_index(
            collection_name=self.collection,
            field_name="is_active",
            field_schema=PayloadSchemaType.BOOL,
        )
        log.info({"event": "qdrant_collection_created", "collection": self.collection})

    @external_retry
    async def upsert(
        self,
        tenant_id: str,
        source_type: str,
        source_id: str,
        text: str,
        vector: list[float],
        metadata: dict | None = None,
    ) -> str:
        payload = {
            "tenant_id": tenant_id,
            "source_type": source_type,
            "source_id": source_id,
            "text": text,
            "is_active": True,
            **(metadata or {}),
        }
        point_id = str(uuid.uuid4())
        await self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        return point_id

    @external_retry
    async def delete_by_source(self, tenant_id: str, source_id: str) -> None:
        await self.client.delete(
            collection_name=self.collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
                        FieldCondition(key="source_id", match=MatchValue(value=source_id)),
                    ]
                )
            ),
        )

    async def search(
        self,
        tenant_id: str,
        vector: list[float],
        limit: int = 4,
        source_type: str | None = None,
    ) -> list[Chunk]:
        if not self.client:
            return []
        must = [
            FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
            FieldCondition(key="is_active", match=MatchValue(value=True)),
        ]
        if source_type:
            must.append(
                FieldCondition(key="source_type", match=MatchValue(value=source_type))
            )
        # qdrant-client renamed search() -> query_points() in recent versions.
        # Support both so a client upgrade cannot silently disable retrieval.
        try:
            if hasattr(self.client, "query_points"):
                response = await self.client.query_points(
                    collection_name=self.collection,
                    query=vector,
                    query_filter=Filter(must=must),
                    limit=limit,
                    with_payload=True,
                )
                hits = response.points
            else:  # pragma: no cover - older clients
                hits = await self.client.search(
                    collection_name=self.collection,
                    query_vector=vector,
                    query_filter=Filter(must=must),
                    limit=limit,
                )
        except Exception as exc:  # noqa: BLE001
            log.error({"event": "qdrant_search_failed", "error": str(exc)})
            return []

        return [
            Chunk(
                id=str(hit.id),
                text=hit.payload.get("text", ""),
                score=hit.score,
                metadata=hit.payload,
            )
            for hit in hits
        ]


qdrant_service = QdrantService()
