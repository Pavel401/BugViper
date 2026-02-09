"""Direct HTTP dispatch to the ingestion service (local dev fallback)."""

import logging
import os

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

INGESTION_SERVICE_URL = os.environ.get("INGESTION_SERVICE_URL", "http://localhost:8080")


async def call_ingestion_service(path: str, payload: BaseModel) -> None:
    """POST *payload* to the ingestion service at *path*.

    Used as a local-dev fallback when Cloud Tasks is not configured.
    The 30-minute timeout matches Cloud Tasks' dispatch_deadline.
    """
    url = f"{INGESTION_SERVICE_URL.rstrip('/')}{path}"
    logger.info("Dispatching to ingestion service: %s", url)

    async with httpx.AsyncClient(timeout=1800.0) as client:
        resp = await client.post(url, json=payload.model_dump())
        logger.info("Ingestion service responded: %d", resp.status_code)
