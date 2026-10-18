"""Vector computations for clustering and fuzzy dedup."""

import numpy as np
from rapidfuzz import fuzz, process


def best_cluster_match(embedding, clusters):
    """Return (cluster_id, cosine similarity) of the best cluster, or (None, 0.0).

    clusters: [(cluster_id, centroid, member_count), ...]
    """
    vector = np.asarray(embedding, dtype=np.float32)
    valid = [
        (cluster_id, centroid)
        for cluster_id, centroid, *_ in clusters
        if centroid is not None and len(centroid) == vector.shape[0]
    ]
    if not valid:
        return None, 0.0

    matrix = np.asarray([centroid for _, centroid in valid], dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(vector)
    safe = np.where(norms == 0.0, 1.0, norms)
    scores = np.where(norms == 0.0, 0.0, (matrix @ vector) / safe)
    index = int(np.argmax(scores))
    if scores[index] <= 0.0:
        return None, 0.0
    return valid[index][0], float(scores[index])


def merge_centroid(centroid, count, embedding, max_weight):
    """Average of the old centroid (weighted by count) and the new embedding."""
    weight = max(1, min(int(count), int(max_weight)))
    merged = (np.asarray(centroid, dtype=np.float64) * weight
              + np.asarray(embedding, dtype=np.float64)) / (weight + 1)
    return merged.tolist()


MIN_LENGTH_RATIO = 0.5   # shorter than half the candidate: compare more strictly


def best_fuzzy_score(text: str, candidates) -> float:
    """Maximum similarity of text to the candidates (0..100).

    token_set_ratio gives 100 when the words of one text are a subset of the other's, so a short post
    would "drown" in any long one with the same words. Candidates more than twice as long as the text
    are compared with token_sort_ratio, which accounts for the whole content."""
    if not candidates:
        return 0.0
    best = 0.0
    short = [c for c in candidates if min(len(text), len(c)) < MIN_LENGTH_RATIO * max(len(text), len(c))]
    comparable = [c for c in candidates if c not in short]
    for group, scorer in ((comparable, fuzz.token_set_ratio), (short, fuzz.token_sort_ratio)):
        if group:
            match = process.extractOne(text, group, scorer=scorer, processor=None)
            if match:
                best = max(best, float(match[1]))
    return best
