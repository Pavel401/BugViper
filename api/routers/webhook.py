
import logging

from fastapi import APIRouter, BackgroundTasks, Request

from api.services.review_service import execute_pr_review

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/github")
async def github_webhook(request: Request):
    """Legacy GitHub webhook endpoint (kept for backwards compatibility)."""
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event")
    logger.info(f"Received GitHub webhook: {event_type}")
    return {
        "status": "received",
        "message": "Use /api/v1/webhook/onComment for PR review",
        "event": event_type,
    }


@router.post("/onComment")
async def on_comment(request: Request, background_tasks: BackgroundTasks):
    """Receive GitHub issue_comment webhook, trigger AI code review if @bugviper is mentioned."""
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "")

    if event_type != "issue_comment":
        return {"status": "ignored", "reason": f"event is '{event_type}', not 'issue_comment'"}

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

    return {"status": "processing", "pr": f"{owner}/{repo_name}#{pr_number}"}
