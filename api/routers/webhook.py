
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from api.dependencies import get_neo4j_client
from api.services.review_service import execute_pr_review
from api.services.push_service import handleCodePush, handleDirectPush
from db import Neo4jClient

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/github")
async def github_webhook(request: Request):
    """Legacy GitHub webhook endpoint (kept for backwards compatibility)."""
    await request.json()  # Consume body but don't store
    event_type = request.headers.get("X-GitHub-Event")
    logger.info(f"Received GitHub webhook: {event_type}")
    return {
        "status": "received",
        "message": "Use /api/v1/webhook/onComment for PR events (review + merge) or /api/v1/webhook/onPush for push events",
        "event": event_type,
    }


@router.post("/onPush")
async def on_push(
    request: Request,
    background_tasks: BackgroundTasks,
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Receive GitHub push webhook and incrementally update the code graph.

    Handles:
    - Direct pushes to branches
    - PR merges (which trigger push events)

    The graph is updated incrementally - only changed files are processed,
    avoiding a full rebuild.
    """
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "")

    if event_type != "push":
        return {"status": "ignored", "reason": f"event is '{event_type}', not 'push'"}

    # Extract push information
    repo_info = payload.get("repository", {})
    owner = repo_info.get("owner", {}).get("login") or repo_info.get("owner", {}).get("name", "")
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

    logger.info(f"Push event received: {owner}/{repo_name} {ref} ({before_sha[:7]}..{after_sha[:7]})")

    # Run incremental update in background
    async def _run_incremental_update():
        try:
            stats = await handleDirectPush(
                owner=owner,
                repo=repo_name,
                before_sha=before_sha,
                after_sha=after_sha,
                neo4j_client=neo4j_client
            )
            logger.info(f"Incremental update completed for {owner}/{repo_name}: "
                       f"added={stats.files_added}, modified={stats.files_modified}, "
                       f"deleted={stats.files_deleted}, errors={len(stats.errors)}")
        except Exception as e:
            logger.error(f"Incremental update failed for {owner}/{repo_name}: {e}")

    background_tasks.add_task(_run_incremental_update)

    return {
        "status": "processing",
        "repo": f"{owner}/{repo_name}",
        "ref": ref,
        "commits": f"{before_sha[:7]}..{after_sha[:7]}"
    }


@router.post("/onComment")
async def on_comment(
    request: Request,
    background_tasks: BackgroundTasks,
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
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

    # Handle PR merge events - incrementally update graph
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

        # Run incremental update in background
        async def _run_pr_incremental_update():
            try:
                stats = await handleCodePush(
                    owner=owner,
                    repo=repo_name,
                    pr_number=pr_number,
                    neo4j_client=neo4j_client
                )
                logger.info(f"PR merge update completed for {owner}/{repo_name}#{pr_number}: "
                           f"added={stats.files_added}, modified={stats.files_modified}, "
                           f"deleted={stats.files_deleted}, errors={len(stats.errors)}")
            except Exception as e:
                logger.error(f"PR merge update failed for {owner}/{repo_name}#{pr_number}: {e}")

        background_tasks.add_task(_run_pr_incremental_update)

        return {"status": "processing", "pr": f"{owner}/{repo_name}#{pr_number}", "action": "graph_update"}

    # Handle comment events - trigger AI review
    if event_type != "issue_comment":
        return {"status": "ignored", "reason": f"event is '{event_type}', not 'issue_comment' or 'pull_request'"}

    if payload.get("action") != "created":
        return {"status": "ignored", "reason": f"action is '{payload.get('action')}', not 'created'"}

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
