import asyncio
import httpx
import logging
import numpy as np

import config

log = logging.getLogger("stenabot.embeddings")

EMBEDDINGS_URL = config.EMBEDDINGS_URL
EMBEDDINGS_MODEL = config.EMBEDDINGS_MODEL
TIMEOUT = 10.0


async def embed(text: str) -> list[float]:
    """
    Gets an embedding from the llama.cpp embedding server.
    Network failures are retried with a growing delay.
    """
    payload = {
        "model": EMBEDDINGS_MODEL,
        "input": text
    }
    attempts = max(1, config.EMBEDDING_RETRIES)

    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.post(EMBEDDINGS_URL, json=payload)
                r.raise_for_status()

                data = r.json()
                embedding: list[float] = data["data"][0]["embedding"]
                return embedding

        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if attempt == attempts:
                log.exception("Embedding request failed after %s attempts", attempts)
                raise
            log.warning("Embedding attempt %s/%s failed: %s", attempt, attempts, exc)
            await asyncio.sleep(0.5 * attempt)

        except Exception:
            log.exception("Embedding request failed")
            raise

    raise AssertionError("unreachable: the loop above returns or raises")


def cosine_sim(v1: list[float], v2: list[float]) -> float:
    """
    Cosine similarity (without sklearn)
    """
    a = np.asarray(v1, dtype=np.float32)
    b = np.asarray(v2, dtype=np.float32)

    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0

    return float(np.dot(a, b) / denom)
