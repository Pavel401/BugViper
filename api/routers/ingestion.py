import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_neo4j_client
from api.models.schemas import (
    GitHubIngestRequest,
    IngestionJobResponse,
    JobStatusResponse,
)
from api.services.cloud_tasks_service import CloudTasksService
from common.job_models import (
    IngestionTaskPayload,
    JobStatus,
)
from common.job_tracker import JobTrackerService
from db import Neo4jClient

logger = logging.getLogger(__name__)

router = APIRouter()
cloud_tasks = CloudTasksService()
job_tracker = JobTrackerService()


@router.post("/github", response_model=IngestionJobResponse)
async def ingest_github_repository(request: GitHubIngestRequest):
    # Prevent duplicate active jobs for the same repo
    existing = job_tracker.find_active_job(request.owner, request.repo_name)
    if existing:
        return IngestionJobResponse(
            job_id=existing.job_id,
            status=existing.status.value,
            message=f"Ingestion already in progress for {request.owner}/{request.repo_name}",
            poll_url=f"/api/v1/ingest/jobs/{existing.job_id}",
        )

    job_id = str(uuid.uuid4())
    payload = IngestionTaskPayload(
        job_id=job_id,
        owner=request.owner,
        repo_name=request.repo_name,
        branch=request.branch,
        clear_existing=request.clear_existing,
    )

    # Create Firestore job record
    job_tracker.create_job(payload)

    # Dispatch to Cloud Tasks → ingestion service
    task_name = cloud_tasks.dispatch_ingestion(payload)
    if task_name:
        job_tracker.update_status(
            job_id, JobStatus.DISPATCHED, cloud_task_name=task_name
        )
    else:
        job_tracker.update_status(
            job_id,
            JobStatus.FAILED,
            error_message="Failed to dispatch Cloud Task",
        )
        raise HTTPException(status_code=500, detail="Failed to dispatch ingestion task")

    return IngestionJobResponse(
        job_id=job_id,
        status=JobStatus.PENDING.value,
        message=f"Ingestion queued for {request.owner}/{request.repo_name}",
        poll_url=f"/api/v1/ingest/jobs/{job_id}",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    job = job_tracker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job.job_id,
        owner=job.owner,
        repo_name=job.repo_name,
        branch=job.branch,
        status=job.status.value,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        stats=job.stats.model_dump() if job.stats else None,
        error_message=job.error_message,
    )


@router.get("/jobs", response_model=list[JobStatusResponse])
async def list_jobs(limit: int = 20):
    jobs = job_tracker.list_jobs(limit=limit)
    return [
        JobStatusResponse(
            job_id=j.job_id,
            owner=j.owner,
            repo_name=j.repo_name,
            branch=j.branch,
            status=j.status.value,
            created_at=j.created_at,
            updated_at=j.updated_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
            stats=j.stats.model_dump() if j.stats else None,
            error_message=j.error_message,
        )
        for j in jobs
    ]
