"""Multi-agent PR review pipeline using pydantic-ai."""

import asyncio
import logging
import os

from deepagent.config import config

# Ensure OPENROUTER_API_KEY is in the process env so pydantic-ai's
# OpenRouterProvider can pick it up (our config reads .env only).
os.environ.setdefault("OPENROUTER_API_KEY", config.openrouter_api_key)

from pydantic_ai import Agent  # noqa: E402
from deepagent.models.agent_schemas import AgentFindings, Issue, ReviewResults
from deepagent.prompts import BUG_HUNTER_PROMPT, SECURITY_AUDITOR_PROMPT

logger = logging.getLogger(__name__)

MODEL = f"openrouter:{config.review_model}"

bug_hunter = Agent(
    MODEL,
    system_prompt=BUG_HUNTER_PROMPT,
    output_type=AgentFindings,
    name="bug-hunter",
)

security_auditor = Agent(
    MODEL,
    system_prompt=SECURITY_AUDITOR_PROMPT,
    output_type=AgentFindings,
    name="security-auditor",
)

# Logfire instrumentation
try:
    import logfire

    if config.enable_logfire and config.logfire_token:
        logfire.configure(token=config.logfire_token)
        logfire.instrument_pydantic_ai(bug_hunter)
        logfire.instrument_pydantic_ai(security_auditor)
except ImportError:
    pass


def _build_user_prompt(diff_text: str, graph_context_section: str, repo_id: str, pr_number: int) -> str:
    return (
        f"## PR #{pr_number} in {repo_id}\n\n"
        f"### Diff\n```diff\n{diff_text}\n```\n\n"
        f"### Dependency Graph Context\n{graph_context_section}"
    )


def _dedup_issues(issues: list[Issue]) -> list[Issue]:
    """Remove duplicate issues by (file, line_start, title)."""
    seen: set[tuple[str, int, str]] = set()
    deduped: list[Issue] = []
    for issue in issues:
        key = (issue.file, issue.line_start, issue.title)
        if key not in seen:
            seen.add(key)
            deduped.append(issue)
    return deduped


async def run_review(
    diff_text: str,
    graph_context_section: str,
    repo_id: str,
    pr_number: int,
) -> ReviewResults:
    """Run bug-hunter and security-auditor in parallel, merge results."""

    prompt = _build_user_prompt(diff_text, graph_context_section, repo_id, pr_number)

    logger.info(f"Starting multi-agent review for {repo_id}#{pr_number}")

    bug_result, sec_result = await asyncio.gather(
        bug_hunter.run(prompt),
        security_auditor.run(prompt),
    )

    bug_findings: AgentFindings = bug_result.output
    sec_findings: AgentFindings = sec_result.output

    logger.info(
        f"bug-hunter: {len(bug_findings.issues)} issues, "
        f"security-auditor: {len(sec_findings.issues)} issues"
    )

    all_issues = _dedup_issues(bug_findings.issues + sec_findings.issues)
    all_positives = list(dict.fromkeys(
        bug_findings.positive_findings + sec_findings.positive_findings
    ))

    issue_count = len(all_issues)
    critical = sum(1 for i in all_issues if i.severity == "critical")
    high = sum(1 for i in all_issues if i.severity == "high")

    if issue_count == 0:
        summary = "No significant issues found. The code looks good."
    else:
        summary = (
            f"Found {issue_count} issue(s) "
            f"({critical} critical, {high} high). "
            "Review the details below."
        )

    return ReviewResults(
        summary=summary,
        issues=all_issues,
        positive_findings=all_positives,
    )
