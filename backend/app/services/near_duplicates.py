"""Small-set SimHash clustering for retrieved and newly ingested signals."""
from __future__ import annotations

import hashlib
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOPWORDS = {"about", "after", "amid", "and", "for", "from", "into", "over", "said", "says", "the", "their", "this", "with"}
SIMHASH_BITS = 64
DEFAULT_HAMMING_DISTANCE = 3


def _value(item, key: str, default=""):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _tokens(item) -> set[str]:
    text = " ".join(str(_value(item, key, "") or "") for key in ("title", "snippet", "content")).lower()
    return {token for token in _TOKEN_RE.findall(text) if len(token) > 1 and token not in _STOPWORDS}


def simhash(item) -> int:
    """Create a deterministic 64-bit SimHash from signal title and content."""
    text = " ".join(str(_value(item, key, "") or "") for key in ("title", "snippet", "content")).lower()
    tokens = [token for token in _TOKEN_RE.findall(text) if len(token) > 1 and token not in _STOPWORDS]
    if not tokens:
        return 0
    shingles = set(tokens)
    shingles.update(f"{left} {right}" for left, right in zip(tokens, tokens[1:]))
    weights = [0] * SIMHASH_BITS
    for shingle in shingles:
        fingerprint = int.from_bytes(hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(SIMHASH_BITS):
            weights[bit] += 1 if fingerprint & (1 << bit) else -1
    return sum(1 << bit for bit, weight in enumerate(weights) if weight >= 0)


def cluster_indices(items: list, max_distance: int = DEFAULT_HAMMING_DISTANCE) -> list[list[int]]:
    """Return transitive SimHash clusters; each index occurs exactly once."""
    fingerprints = [simhash(item) for item in items]
    token_sets = [_tokens(item) for item in items]
    parents = list(range(len(items)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for left in range(len(items)):
        if not fingerprints[left]:
            continue
        for right in range(left + 1, len(items)):
            distance = bin(fingerprints[left] ^ fingerprints[right]).count("1")
            shared = token_sets[left] & token_sets[right]
            union = token_sets[left] | token_sets[right]
            jaccard = len(shared) / len(union) if union else 0.0
            if fingerprints[right] and (distance <= max_distance or jaccard >= 0.8):
                parent_left, parent_right = find(left), find(right)
                if parent_left != parent_right:
                    parents[parent_right] = parent_left

    groups: dict[int, list[int]] = {}
    for index in range(len(items)):
        groups.setdefault(find(index), []).append(index)
    return list(groups.values())


def annotate_clusters(items: list, max_distance: int = DEFAULT_HAMMING_DISTANCE) -> list[list[int]]:
    """Attach stable cluster ID and size metadata, preserving all cluster members."""
    groups = cluster_indices(items, max_distance)
    fingerprints = [simhash(item) for item in items]
    for group in groups:
        representative = min(fingerprints[index] for index in group)
        cluster_id = f"simhash:{representative:016x}"
        if representative == 0:
            cluster_id = f"simhash:empty:{group[0]}"
        for index in group:
            item = items[index]
            if isinstance(item, dict):
                item["cluster_id"] = cluster_id
                item["cluster_size"] = len(group)
            else:
                item.cluster_id = cluster_id
                item.cluster_size = len(group)
    return groups
