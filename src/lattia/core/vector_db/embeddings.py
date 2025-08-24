import random
from enum import Enum
from typing import Protocol

from lattia.core.utils.openai_client import get_openai_like_client


class EmbeddingsProvider(Protocol):
    @property
    def dim(self) -> int: ...
    @property
    def model_name(self) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingModel(Enum):
    TEXT_EMBEDDING_3_SMALL = ("text-embedding-3-small", 1536)
    TEXT_EMBEDDING_3_LARGE = ("text-embedding-3-large", 3072)

    def __init__(self, model_name: str, dimension: int):
        self.model_name = model_name
        self.dimension = dimension


class OpenAIEmbeddings:
    """
    OpenAI embeddings provider using the specified model.
    """

    model: EmbeddingModel = EmbeddingModel.TEXT_EMBEDDING_3_SMALL

    def __init__(self):
        self._client = get_openai_like_client()

    @property
    def dim(self) -> int:
        return self.model.dimension

    @property
    def model_name(self) -> str:
        return self.model.model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self.model_name, input=texts)
        return [d.embedding for d in resp.data]


class MockEmbeddings:
    """
    A mock embeddings provider for testing.
    Always returns fixed or random vectors instead of calling an API.
    """

    def __init__(self, dim: int = 16, fill: float = 1.0, randomize: bool = False):
        self._dim = dim
        self._fill = fill
        self._randomize = randomize

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return "mock-embedding-model"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._randomize:
            return [[random.random() for _ in range(self._dim)] for _ in texts]
        return [[self._fill] * self._dim for _ in texts]
