"""Orchestrates the full PR review pipeline: fetch diff, graph context, agents, format, post."""

import logging
import os
import traceback

from api.utils.comment_formatter import format_github_comment
from api.utils.graph_context import build_graph_context_section
from db.client import Neo4jClient
from db.queries import CodeQueryService
from deepagent.models.agent_schemas import ContextData
from deepagent.agent.review_pipeline import run_review
from ingestion.github_client import GitHubClient
from common.diff_parser import parse_unified_diff

logger = logging.getLogger(__name__)


async def execute_pr_review(owner: str, repo: str, pr_number: int) -> None:
    """Fetch diff, gather context, run agents, format comment, post to GitHub."""
    try:
        logger.info(f"Starting review pipeline for {owner}/{repo}#{pr_number}")

        # 1. Fetch diff
        gh = GitHubClient()
        diff_text = await gh.get_pr_diff(owner, repo, pr_number)
        if not diff_text:
            logger.warning("Empty diff, skipping review")
            return

        logger.info(f"Fetched diff ({len(diff_text)} chars)")

        # 2. Parse diff
        changes = parse_unified_diff(diff_text)
        logger.info(f"Parsed {len(changes)} hunks across files")

        # 3. Build graph context
        repo_id = f"{owner}/{repo}"
        neo4j = Neo4jClient(
            uri=os.environ.get("NEO4J_URI", ""),
            user=os.environ.get("NEO4J_USERNAME", "neo4j"),
            password=os.environ.get("NEO4J_PASSWORD", ""),
            database=os.environ.get("NEO4J_DATABASE", "neo4j"),
        )
        query_service = CodeQueryService(neo4j)
        graph_context = query_service.get_diff_context_enhanced(repo_id, changes)

        affected_symbols = graph_context.get("affected_symbols", [])
        callers = graph_context.get("callers", [])
        total_callers = sum(len(c.get("callers", [])) for c in callers)
        files_changed = list({c["file_path"] for c in changes})
        modified_symbol_names = [s.get("name", "") for s in affected_symbols]

        if total_callers > 10 or len(affected_symbols) > 5:
            risk_level = "high"
        elif total_callers > 3 or len(affected_symbols) > 2:
            risk_level = "medium"
        else:
            risk_level = "low"

        graph_section = build_graph_context_section(graph_context)
        logger.info(f"Graph context section ({len(graph_section)} chars)")

        # 4. Run multi-agent review
        review_results = await run_review(diff_text, graph_section, repo_id, pr_number)
        logger.info(f"Review complete: {len(review_results.issues)} issues found")

        # 5. Format comment
        context_data = ContextData(
            files_changed=files_changed,
            modified_symbols=modified_symbol_names,
            total_callers=total_callers,
            risk_level=risk_level,
        )

        final_comment = format_github_comment(review_results, context_data, pr_number)

        # 6. Post comment
        await gh.post_comment(owner, repo, pr_number, final_comment)
        logger.info(f"Posted review comment on {owner}/{repo}#{pr_number}")

    except Exception:
        logger.error(f"Review pipeline failed: {traceback.format_exc()}")
