"""Embedding services: OpenAI-compatible API or a deterministic local fallback."""

import hashlib
import math
from collections.abc import Sequence

from litellm import aembedding

from app.config import get_settings
from app.rag.text import tokenize
from app.schemas.settings import LlmSettings


class EmbeddingError(RuntimeError):
    pass


def normalize_embedding_model(model: str) -> str:
    model = model.strip()
    if not model:
        return ""
    return model if "/" in model else f"openai/{model}"


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class EmbeddingService:
    name: str = "unknown"
    dimension: int = 0

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError


class HashingEmbeddingService(EmbeddingService):
    """Signed feature hashing over jieba words and character bigrams.

    It is not a semantic model, but it needs no key or model download and is
    good enough to exercise the ingestion/retrieval/citation pipeline.
    """

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension
        self.name = f"hash-{dimension}"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dimension
            sign = 1.0 if digest[0] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class ApiEmbeddingService(EmbeddingService):
    def __init__(self, model: str, api_base: str, api_key: str) -> None:
        self.model = normalize_embedding_model(model)
        self.name = self.model
        self.api_base = api_base.strip()
        self.api_key = api_key.strip()

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        batch_size = 32
        for start in range(0, len(texts), batch_size):
            batch = list(texts[start : start + batch_size])
            try:
                response = await aembedding(
                    model=self.model,
                    input=batch,
                    api_base=self.api_base or None,
                    api_key=self.api_key or None,
                )
            except Exception as exc:
                raise EmbeddingError(str(exc)) from exc

            data = getattr(response, "data", None)
            if data is None and isinstance(response, dict):
                data = response.get("data", [])
            if not data:
                raise EmbeddingError("Embedding 服务没有返回向量。")

            for item in data:
                embedding = (
                    item.get("embedding")
                    if isinstance(item, dict)
                    else getattr(item, "embedding", None)
                )
                if not embedding:
                    raise EmbeddingError("Embedding 返回格式不正确。")
                vectors.append([float(value) for value in embedding])

        if vectors:
            self.dimension = len(vectors[0])
        return vectors


def get_embedding_service(llm: LlmSettings | None = None) -> EmbeddingService:
    settings = get_settings()
    if settings.mock_llm:
        return HashingEmbeddingService(settings.hash_embedding_dim)

    model = (llm.embedding_model if llm else "").strip()
    if not model:
        return HashingEmbeddingService(settings.hash_embedding_dim)

    return ApiEmbeddingService(
        model=model,
        api_base=(llm.embedding_api_base or llm.api_base) if llm else "",
        api_key=(llm.embedding_api_key or llm.api_key) if llm else "",
    )
