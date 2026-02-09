
import logging
import os

from fastapi import APIRouter

from common.job_models import IncrementalPRPayload, IncrementalPushPayload, IngestionTaskPayload, JobStatus
from common.job_tracker import JobTrackerService
from db.client import Neo4jClient
from ingestion_service.core.incremental_updater import handleCodePush, handleDirectPush

logger = logging.getLogger(__name__)

router = APIRouter()
job_tracker = JobTrackerService()


def _get_neo4j_client() -> Neo4jClient:
    """Build a Neo4jClient from environment variables."""
    return Neo4jClient(
        uri=os.environ.get("NEO4J_URI", ""),
        user=os.environ.get("NEO4J_USERNAME", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", ""),
        database=os.environ.get("NEO4J_DATABASE", "neo4j"),
    )


@router.post("/tasks/incremental-pr")
async def handle_incremental_pr(payload: IncrementalPRPayload):
    """Execute incremental graph update for a merged PR.

    Always returns 200 to prevent Cloud Tasks from retrying on permanent failures.
    The job status in Firestore reflects the real outcome.
    """
    job_id = payload.job_id
    logger.info(
        "Starting incremental PR job %s for %s/%s#%d",
        job_id, payload.owner, payload.repo_name, payload.pr_number,
    )

    if not job_tracker.get_job(job_id):
        pp=IngestionTaskPayload(
            job_id=payload.job_id,
            owner=payload.owner,
            repo_name=payload.repo_name,
            branch=None,
            clear_existing=False,
            pr_number=payload.pr_number,
        )
        job_tracker.create_job(pp)

    try:
        job_tracker.update_status(job_id, JobStatus.RUNNING)

        client = _get_neo4j_client()
        stats = await handleCodePush(
            owner=payload.owner,
            repo=payload.repo_name,
            pr_number=payload.pr_number,
            neo4j_client=client,
        )

        job_tracker.update_status(job_id, JobStatus.COMPLETED)
        logger.info(
            "Incremental PR job %s completed: added=%d, modified=%d, deleted=%d, errors=%d",
            job_id, stats.files_added, stats.files_modified,
            stats.files_deleted, len(stats.errors),
        )

    except Exception as exc:
        logger.exception("Incremental PR job %s failed", job_id)
        job_tracker.update_status(
            job_id,
            JobStatus.FAILED,
            error_message=f"{type(exc).__name__}: {exc}",
        )

    # Always 200 — Cloud Tasks should not retry permanent failures
    return {"status": "processed", "job_id": job_id}


@router.post("/tasks/incremental-push")
async def handle_incremental_push(payload: IncrementalPushPayload):
    """Execute incremental graph update for a direct push.

    Always returns 200 to prevent Cloud Tasks from retrying on permanent failures.
    The job status in Firestore reflects the real outcome.
    """
    job_id = payload.job_id
    logger.info(
        "Starting incremental push job %s for %s/%s (%s..%s)",
        job_id, payload.owner, payload.repo_name,
        payload.before_sha[:7], payload.after_sha[:7],
    )

    try:
        job_tracker.update_status(job_id, JobStatus.RUNNING)

        client = _get_neo4j_client()
        stats = await handleDirectPush(
            owner=payload.owner,
            repo=payload.repo_name,
            before_sha=payload.before_sha,
            after_sha=payload.after_sha,
            neo4j_client=client,
        )

        job_tracker.update_status(job_id, JobStatus.COMPLETED)
        logger.info(
            "Incremental push job %s completed: added=%d, modified=%d, deleted=%d, errors=%d",
            job_id, stats.files_added, stats.files_modified,
            stats.files_deleted, len(stats.errors),
        )

    except Exception as exc:
        logger.exception("Incremental push job %s failed", job_id)
        job_tracker.update_status(
            job_id,
            JobStatus.FAILED,
            error_message=f"{type(exc).__name__}: {exc}",
        )

    # Always 200 — Cloud Tasks should not retry permanent failures
    return {"status": "processed", "job_id": job_id}
