from fastapi import HTTPException, Request
import logging

import firebase_admin.auth
from db import Neo4jClient, get_neo4j_client as _build_neo4j_client

logger = logging.getLogger(__name__)


async def get_current_user(request: Request) -> dict:
    """Extract and verify Firebase ID token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.split("Bearer ", 1)[1]
    try:
        decoded = firebase_admin.auth.verify_id_token(token)
        return decoded
    except Exception as e:
        logger.warning("Firebase token verification failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_neo4j_client() -> Neo4jClient:
    """Get Neo4j database client from environment variables."""
    return _build_neo4j_client()
