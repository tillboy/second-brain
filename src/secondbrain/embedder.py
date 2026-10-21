"""Pluggable embedders. API-first (Voyage) with local fallback (sentence-transformers)."""

from __future__ import annotations

import json
import logging
import math
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from tenacity import retry, stop_after_attempt, wait_exponential

from .budget import check_budget, record_usage
from .config import Config

log = logging.getLogger(__name__)

# Voyage caps a single embed request at 1000 inputs. Stay well under that to
# avoid the limit flaring on edge cases, and to keep individual batches small
# enough that a transient TPM rate-limit doesn't lose a huge file's worth of
# work on a single retry. 128 is well-tested and gives smooth throttling.
_VOYAGE_BATCH_SIZE = 128


@runtime_checkable
class Embedder(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


_VOYAGE_DIMS: dict[str, int] = {
    "voyage-3": 1024,
    "voyage-3-lite": 512,
    "voyage-3-large": 1024,
    "voyage-code-3": 1024,
}


class VoyageEmbedder:
    def __init__(self, api_key: str, model: str = "voyage-3", cfg: Config | None = None):
        import voyageai

        if model not in _VOYAGE_DIMS:
            raise ValueError(f"Unknown Voyage model: {model}. Known: {list(_VOYAGE_DIMS)}")
        self._client = voyageai.Client(api_key=api_key)
        self.name = model
        self.dim = _VOYAGE_DIMS[model]
        self._cfg = cfg

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(min=2, max=120),
    )
    def _embed_batch(self, texts: list[str], input_type: str) -> tuple[list[list[float]], int]:
        """Embed a single Voyage-sized batch (<= _VOYAGE_BATCH_SIZE)."""
        result = self._client.embed(texts, model=self.name, input_type=input_type)
        return [list(e) for e in result.embeddings], int(getattr(result, "total_tokens", 0))

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        if not texts:
            return []

        out: list[list[float]] = []
        total_tokens = 0
        # Round 15 (audit-found gap A3) — gate AND record per batch
        # so a 50k-chunk bulk index that crosses the cap mid-stream
        # actually halts (instead of running to completion silently
        # past the cap). Also keeps the dashboard spend graph
        # accurate during long-running indexes instead of showing
        # $0 until the very last batch lands. A2: explicit
        # feature='embed' so the per-feature bucket fires.
        for start in range(0, len(texts), _VOYAGE_BATCH_SIZE):
            if self._cfg is not None:
                check_budget(self._cfg, "voyage", feature="embed")
            chunk = texts[start:start + _VOYAGE_BATCH_SIZE]
            embeddings, tokens = self._embed_batch(chunk, input_type)
            out.extend(embeddings)
            total_tokens += tokens
            if self._cfg is not None:
                record_usage(
                    self._cfg, "voyage", self.name,
                    input_tokens=tokens,
                    note=f"embed/{input_type}/batch",
                    feature="embed",
                )
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, input_type="document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], input_type="query")[0]


class LocalEmbedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "Local embedder requires sentence-transformers. "
                "Install with: pip install second-brain[local]"
            ) from e
        self._model = SentenceTransformer(model_name)
        self.name = model_name
        self.dim = self._model.get_sentence_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        arr = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return arr.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class ODSEmbedder:
    """Use the embedding service already managed by the ODS stack.

    The endpoint is OpenAI-compatible (`/v1/embeddings`) inside the ODS
    Docker network. A TEI-compatible `/embed` endpoint is also accepted for
    host-side development. No model is downloaded by this adapter.
    """

    def __init__(self, url: str, model: str, dimension: int):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("ODS embedding URL must be an absolute HTTP(S) URL")
        self.url = url.rstrip("/")
        self.model = model
        self.name = model
        self.dim = dimension

    def _request(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.url.endswith("/v1"):
            endpoint = self.url + "/embeddings"
            payload = {"input": texts, "model": self.model}
        else:
            endpoint = self.url + "/embed"
            payload = {"inputs": texts, "truncate": True}
        request = Request(
            endpoint,
            json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=120) as response:
            body = json.load(response)
        if self.url.endswith("/v1"):
            rows = [row["embedding"] for row in sorted(body["data"], key=lambda r: r["index"])]
        else:
            rows = body
        if len(rows) != len(texts) or any(
            len(row) != self.dim or not all(math.isfinite(value) for value in row)
            for row in rows
        ):
            raise ValueError("ODS embedding response has invalid count, dimension, or values")
        return rows

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        output = []
        for start in range(0, len(texts), 16):
            output.extend(self._request(texts[start:start + 16]))
        return output

    def embed_query(self, text: str) -> list[float]:
        return self._request([text])[0]


def make_embedder(cfg: Config) -> Embedder:
    """Pick an embedder based on config and available credentials."""
    provider = cfg.embedder_provider
    if provider == "auto":
        provider = "voyage" if cfg.voyage_api_key else "local"

    if provider == "voyage":
        if not cfg.voyage_api_key:
            raise RuntimeError(
                "embedder_provider='voyage' but VOYAGE_API_KEY is not set. "
                "Export it or set embedder_provider='local'."
            )
        return VoyageEmbedder(cfg.voyage_api_key, model=cfg.voyage_model, cfg=cfg)

    if provider == "local":
        return LocalEmbedder(cfg.local_model)

    if provider == "ods":
        return ODSEmbedder(
            cfg.ods_embedding_url,
            cfg.ods_embedding_model,
            cfg.ods_embedding_dimension,
        )

    raise ValueError(f"Unknown embedder_provider: {provider}")
