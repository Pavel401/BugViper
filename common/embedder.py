

import logging
import os

from openai import OpenAI

from db.client import Neo4jClient

logger = logging.getLogger(__name__)

# OpenRouter embedding model — same key as the LLM, no separate OpenAI key needed
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
EMBEDDING_MODEL     = "openai/text-embedding-3-small"
EMBEDDING_DIMS      = 1536   # fixed output size for text-embedding-3-small
BATCH_SIZE          = 2048   # max texts per API call

# Nodes we embed and the text we build from each one.
# Format: (node_label, text_expression_in_cypher)
_NODE_TYPES: list[tuple[str, str]] = [
    ("Function", "coalesce(n.name, '') + ' ' + coalesce(n.docstring, '') + ' ' + coalesce(n.source_code, n.source, '')"),
    ("Class",    "coalesce(n.name, '') + ' ' + coalesce(n.docstring, '') + ' ' + coalesce(n.source_code, n.source, '')"),
    ("Method",   "coalesce(n.name, '') + ' ' + coalesce(n.docstring, '') + ' ' + coalesce(n.source_code, n.source, '')"),
    ("File",     "coalesce(n.path, '') + ' ' + coalesce(n.source_code, '')"),
]


# ── Core helper ───────────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of strings via OpenRouter's embeddings endpoint.

    Uses the same OPENROUTER_API_KEY as the LLM — no separate OpenAI key needed.
    Sends texts in batches of 2048 so 700 nodes = 1 API call.

    Args:
        texts: List of strings to embed.

    Returns:
        List of embedding vectors in the same order as the input.
    """
    if not texts:
        return []

    # OpenAI client pointed at OpenRouter — API is fully compatible
    client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=OPENROUTER_BASE_URL,
    )
    all_embeddings: list[list[float]] = []

    for batch_start in range(0, len(texts), BATCH_SIZE):
        batch = texts[batch_start : batch_start + BATCH_SIZE]

        logger.info(
            "Embedding batch %d-%d of %d texts",
            batch_start, batch_start + len(batch), len(texts),
        )

        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)

        # The API returns embeddings in the same order as the input.
        # openai 2.x raises ValueError("No embedding data received") if data=[],
        # but guard against it here too to produce a clearer message.
        if not response.data:
            raise ValueError(
                f"OpenRouter returned empty data for batch of {len(batch)} texts "
                f"(batch_start={batch_start}). Likely the request was too large."
            )

        batch_vectors = [item.embedding for item in response.data]
        all_embeddings.extend(batch_vectors)

    return all_embeddings


# ── Neo4j helper ─────────────────────────────────────────────────────────────

def embed_nodes_in_neo4j(db: Neo4jClient) -> dict[str, int]:
    """
    Embed all Function, Class, and File nodes that don't have an embedding yet.

    All node types are fetched in ONE Neo4j query and sent to OpenAI in as few
    batches as possible (1 call per 2048 nodes). For a typical repo with 700
    nodes this is a single API call regardless of how many labels there are.

    Safe to re-run — skips nodes that already have n.embedding set.

    Returns:
        Dict with counts per label, e.g. {"Function": 400, "Class": 0, "File": 300}
    """
    # ── Step 1: fetch ALL nodes that need embeddings in one query ─────────────
    # Build a UNION query so Neo4j returns all labels in a single round-trip.
    union_parts = []
    for label, text_expr in _NODE_TYPES:
        union_parts.append(f"""
            MATCH (n:{label})
            WHERE n.embedding IS NULL
            RETURN elementId(n) AS eid, ({text_expr}) AS text, '{label}' AS label
        """)

    all_records, _, _ = db.run_query(" UNION ALL ".join(union_parts))

    if not all_records:
        logger.info("All nodes already have embeddings — nothing to do")
        return {label: 0 for label, _ in _NODE_TYPES}

    ids    = [r["eid"]   for r in all_records]
    texts  = [r["text"]  for r in all_records]
    labels = [r["label"] for r in all_records]

    total = len(ids)
    logger.info(
        "Embedding %d nodes total (%s) → %d OpenAI API call(s)",
        total,
        ", ".join(f"{labels.count(l)} {l}" for l, _ in _NODE_TYPES if labels.count(l) > 0),
        (total + BATCH_SIZE - 1) // BATCH_SIZE,   # ceiling division
    )

    # ── Step 2: embed everything in batches of 2048 (one call for < 2048) ────
    vectors = embed_texts(texts)

    # ── Step 3: write embeddings back to Neo4j in batches of 500 ─────────────
    # (keep Cypher param size reasonable)
    write_batch_size = 500
    for i in range(0, total, write_batch_size):
        batch = [
            {"eid": ids[j], "vec": vectors[j]}
            for j in range(i, min(i + write_batch_size, total))
        ]
        db.run_query("""
            UNWIND $batch AS row
            MATCH (n) WHERE elementId(n) = row.eid
            SET n.embedding = row.vec
        """, {"batch": batch})

    # ── Step 4: return per-label counts ──────────────────────────────────────
    stats = {label: labels.count(label) for label, _ in _NODE_TYPES}
    for label, count in stats.items():
        if count:
            logger.info("  ✓ %d %s nodes embedded", count, label)
    return stats
