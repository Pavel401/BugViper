
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from api.services.cloud_tasks_service import CloudTasksService
from api.services.ingestion_dispatch import call_ingestion_service
from api.services.review_service import execute_pr_review

logger = logging.getLogger(__name__)

router = APIRouter()
cloud_tasks = CloudTasksService()


@router.post("/github")
async def github_webhook(request: Request):
    """Legacy GitHub webhook endpoint (kept for backwards compatibility)."""
    await request.json()  # Consume body but don't store
    await request.json()  # Consume body but don't store
    event_type = request.headers.get("X-GitHub-Event")
    logger.info(f"Received GitHub webhook: {event_type}")
    return {
        "status": "received",
        "message": (
            "Use /api/v1/webhook/onComment for PR events (review + merge) "
            "or /api/v1/webhook/onPush for push events"
        ),
        "event": event_type,
    }


@router.post("/onPush")
async def on_push(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Receive GitHub push webhook and dispatch incremental graph update
    to the ingestion service.

    Handles:
    - Direct pushes to branches
    - PR merges (which trigger push events)
    """
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "")

    if event_type != "push":
        return {"status": "ignored", "reason": f"event is '{event_type}', not 'push'"}

    # Extract push information
    repo_info = payload.get("repository", {})
    owner = (
        repo_info.get("owner", {}).get("login")
        or repo_info.get("owner", {}).get("name", "")
    )
    repo_name = repo_info.get("name", "")
    ref = payload.get("ref", "")  # e.g., "refs/heads/main"
    before_sha = payload.get("before", "")
    after_sha = payload.get("after", "")

    # Skip if this is a branch deletion (after_sha is all zeros)
    if after_sha == "0000000000000000000000000000000000000000":
        return {"status": "ignored", "reason": "branch deletion"}

    # Skip if this is a new branch creation (before_sha is all zeros)
    if before_sha == "0000000000000000000000000000000000000000":
        logger.info(f"New branch created: {ref} - consider full ingestion")
        return {"status": "ignored", "reason": "new branch creation - use full ingestion"}

    logger.info(
        f"Push event received: {owner}/{repo_name} {ref} ({before_sha[:7]}..{after_sha[:7]})"
    )

    job_id = f"inc-push-{uuid.uuid4().hex[:12]}"
    task_payload = IncrementalPushPayload(
        job_id=job_id,
        owner=owner,
        repo_name=repo_name,
        before_sha=before_sha,
        after_sha=after_sha,
    )

    # Dispatch via Cloud Tasks or direct HTTP fallback
    if cloud_tasks.is_enabled:
        cloud_tasks.dispatch_incremental_push(task_payload)
    else:
        background_tasks.add_task(
            call_ingestion_service, "/tasks/incremental-push", task_payload
        )

    return {
        "status": "processing",
        "job_id": job_id,
        "repo": f"{owner}/{repo_name}",
        "ref": ref,
        "commits": f"{before_sha[:7]}..{after_sha[:7]}",
    }


@router.post("/onComment")
async def on_comment(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Receive GitHub webhooks for:
    - issue_comment: Trigger AI code review if @bugviper is mentioned
    - pull_request (closed+merged): Incrementally update the code graph
    """
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "")

    logger.info(f"Received GitHub webhook: {event_type}")

    # Handle push events - redirect to onPush
    if event_type == "push":
        return {"status": "ignored", "reason": "Use /api/v1/webhook/onPush for push events"}

    # Handle PR merge events - dispatch incremental graph update
    if event_type == "pull_request":
        action = payload.get("action", "")
        if action != "closed":
            return {"status": "ignored", "reason": f"action is '{action}', not 'closed'"}

        pr = payload.get("pull_request", {})
        if not pr.get("merged"):
            return {"status": "ignored", "reason": "PR was closed but not merged"}

        repo_info = payload.get("repository", {})
        owner = repo_info.get("owner", {}).get("login", "")
        repo_name = repo_info.get("name", "")
        pr_number = pr.get("number")

        logger.info(f"PR merged: {owner}/{repo_name}#{pr_number}")

        job_id = f"inc-pr-{uuid.uuid4().hex[:12]}"
        task_payload = IncrementalPRPayload(
            job_id=job_id,
            owner=owner,
            repo_name=repo_name,
            pr_number=pr_number,
        )

        # Dispatch via Cloud Tasks or direct HTTP fallback
        if cloud_tasks.is_enabled:
            cloud_tasks.dispatch_incremental_pr(task_payload)
        else:
            background_tasks.add_task(
                call_ingestion_service, "/tasks/incremental-pr", task_payload
            )

        return {
            "status": "processing",
            "job_id": job_id,
            "pr": f"{owner}/{repo_name}#{pr_number}",
            "action": "graph_update",
        }

    # Handle comment events - trigger AI review
    if event_type != "issue_comment":
        return {
            "status": "ignored",
            "reason": f"event is '{event_type}', not 'issue_comment' or 'pull_request'",
        }

    if payload.get("action") != "created":
        return {
            "status": "ignored",
            "reason": f"action is '{payload.get('action')}', not 'created'",
        }

    issue = payload.get("issue", {})
    if not issue.get("pull_request"):
        return {"status": "ignored", "reason": "comment is not on a pull request"}

    comment_body = payload.get("comment", {}).get("body", "")
    if "@bugviper" not in comment_body.lower():
        return {"status": "ignored", "reason": "no @bugviper mention"}

    repo_info = payload.get("repository", {})
    owner = repo_info.get("owner", {}).get("login", "")
    repo_name = repo_info.get("name", "")
    pr_number = issue.get("number")

    logger.info(f"PR review triggered: {owner}/{repo_name}#{pr_number}")

    background_tasks.add_task(execute_pr_review, owner, repo_name, pr_number)

    return {"status": "processing", "pr": f"{owner}/{repo_name}#{pr_number}", "action": "review"}
