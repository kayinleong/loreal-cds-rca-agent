"""
retrieval_tool.py — Semantic-similarity retrieval for ticket assignment routing.
=================================================================================
Pure functions — no LLM calls. Loads sentence-transformers `all-MiniLM-L6-v2`
on first use, embeds the local incident corpus once, and answers nearest-neighbour
queries from a cached NPZ index.

Two public functions:
  build_index(incidents_json_path, index_path)
      Loads `_all_incidents.json`, embeds each ticket's text, saves a `.npz` file
      containing parallel arrays of numbers / current_groups / embeddings.

  find_similar(query_text, top_k, index_path)
      Embeds `query_text`, computes cosine similarity vs the cached index,
      returns top_k `(number, group, score)` entries.

Both functions lazy-import sentence-transformers + numpy so this module imports
cleanly even when the heavy deps are not installed. ImportError is converted to
RuntimeError with the install instruction.

Index is built off the SAME text concatenation the keyword scorer uses
(short_description + description + category + subcategory + comments + work_notes)
so retrieval and keyword scoring see the same view of each ticket.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default model — small (80 MB), fast on CPU, multilingual-OK
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Module-level caches (populated on first call)
_model = None
_index_cache: dict[str, Any] | None = None


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "")


def _ticket_text(rec: dict) -> str:
    """Same text view that the keyword scorer sees."""
    inc = rec.get("incident", {}) or {}
    parts = [
        inc.get("short_description") or "",
        inc.get("description") or "",
        inc.get("category") or "",
        inc.get("subcategory") or "",
        " ".join((c.get("text") or "") for c in (rec.get("comments") or [])),
        " ".join((n.get("text") or "") for n in (rec.get("work_notes") or [])),
    ]
    return _strip_html(" ".join(parts))


def _load_model():
    """Lazy-load sentence-transformers. Raises RuntimeError if not installed."""
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers not installed. Run: "
            "pip install 'sentence-transformers>=2.5.0'"
        ) from exc
    logger.info(f"[RETRIEVAL] Loading model {_MODEL_NAME}")
    _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _import_numpy():
    try:
        import numpy as np  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "numpy not installed (should ship with sentence-transformers)."
        ) from exc
    return np


def build_index(incidents_json_path: str, index_path: str) -> dict:
    """
    Load `_all_incidents.json`, embed each ticket's text, save to `index_path` as .npz.

    Returns a summary dict with counts. Idempotent — overwrites any existing index.
    """
    np = _import_numpy()
    model = _load_model()

    incidents_path = Path(incidents_json_path)
    if not incidents_path.exists():
        raise FileNotFoundError(f"Incidents file not found: {incidents_path}")

    with incidents_path.open(encoding="utf-8") as fh:
        incidents = json.load(fh)

    numbers: list[str] = []
    groups: list[str] = []
    texts: list[str] = []
    for rec in incidents:
        inc = rec.get("incident", {}) or {}
        numbers.append(inc.get("number") or "?")
        groups.append((inc.get("assignment_group") or "").strip())
        texts.append(_ticket_text(rec))

    if not texts:
        raise ValueError("No incidents found in source file")

    logger.info(f"[RETRIEVAL] Embedding {len(texts)} tickets...")
    embeddings = model.encode(
        texts,
        batch_size=16,
        show_progress_bar=False,
        normalize_embeddings=True,  # so cosine == dot product
        convert_to_numpy=True,
    )

    out_path = Path(index_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        out_path,
        numbers=np.array(numbers, dtype=object),
        groups=np.array(groups, dtype=object),
        embeddings=embeddings.astype("float32"),
    )

    # Reset cache so subsequent reads re-load
    global _index_cache
    _index_cache = None

    return {
        "indexed_count": len(texts),
        "index_path": str(out_path),
        "model": _MODEL_NAME,
        "dimensions": int(embeddings.shape[1]),
    }


def _load_index(index_path: str) -> dict:
    """Load NPZ index into memory; cache for subsequent calls."""
    global _index_cache
    if _index_cache is not None and _index_cache.get("path") == index_path:
        return _index_cache
    np = _import_numpy()
    path = Path(index_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Retrieval index not found at {path}. "
            f"Run build_index() first."
        )
    data = np.load(path, allow_pickle=True)
    _index_cache = {
        "path": index_path,
        "numbers": data["numbers"].tolist(),
        "groups": data["groups"].tolist(),
        "embeddings": data["embeddings"],  # keep as np array
    }
    return _index_cache


def find_similar(
    query_text: str,
    top_k: int = 5,
    index_path: str = "",
    exclude_number: str = "",
) -> list[dict]:
    """
    Embed `query_text`, find top_k most-similar tickets in the cached index by
    cosine similarity (dot product on pre-normalized vectors).

    Args:
        query_text:      Incident text to query with (caller assembles it however).
        top_k:           How many neighbours to return.
        index_path:      Path to the .npz built by build_index.
        exclude_number:  Optional — if the query is itself a known incident in the index,
                         pass its number here so it is excluded from neighbours.

    Returns:
        list of dicts: [{"number": str, "group": str, "score": float}, ...]
        Sorted by descending score (highest similarity first).
    """
    np = _import_numpy()
    model = _load_model()
    idx = _load_index(index_path)

    if not query_text or not query_text.strip():
        return []

    query_emb = model.encode(
        [_strip_html(query_text)],
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    # (1, D) @ (N, D).T → (1, N)
    scores = (query_emb @ idx["embeddings"].T)[0]

    # Build sortable list, optionally excluding self
    candidates = []
    for i, (num, grp, score) in enumerate(zip(idx["numbers"], idx["groups"], scores)):
        if exclude_number and num == exclude_number:
            continue
        candidates.append({"number": num, "group": grp, "score": float(score)})

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[: max(1, top_k)]


def vote_group(
    similar: list[dict],
    min_score: float = 0.0,
    mode: str = "weighted",
) -> tuple[str, float, dict]:
    """
    Pick the top group among the neighbours.

    Args:
        similar:    Output of `find_similar` — list of {number, group, score}.
        min_score:  Drop neighbours below this similarity threshold.
        mode:       "weighted" (default) — each neighbour contributes its score to its
                    group; the group with the highest accumulated score wins. This avoids
                    bias toward groups that happen to be over-represented in the corpus.
                    "count" — simple majority count of group occurrences.

    Returns:
        (top_group, top_value, {group: value_per_group})
        - top_value is sum-of-scores when mode="weighted", else integer vote count.
        - Empty input or all-filtered → ("", 0.0, {}).
    """
    eligible = [s for s in similar if s.get("score", 0.0) >= min_score and s.get("group")]
    if not eligible:
        return "", 0.0, {}

    tally: dict[str, float] = {}
    for s in eligible:
        g = s["group"]
        if mode == "count":
            tally[g] = tally.get(g, 0.0) + 1.0
        else:
            tally[g] = tally.get(g, 0.0) + float(s.get("score", 0.0))

    top_group = max(tally.items(), key=lambda x: x[1])[0]
    return top_group, tally[top_group], dict(tally)
