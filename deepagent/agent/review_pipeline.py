"""PR review pipeline using a single pydantic-ai reviewer agent."""

import logging
import os

from deepagent.config import config

# Ensure OPENROUTER_API_KEY is in the process env so pydantic-ai's
# OpenRouterProvider can pick it up (our config reads .env only).
os.environ.setdefault("OPENROUTER_API_KEY", config.openrouter_api_key)

from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.settings import ModelSettings  # noqa: E402
from deepagent.models.agent_schemas import AgentFindings, Issue, ReviewResults
from deepagent.prompts import REVIEWER_PROMPT

CONFIDENCE_THRESHOLD = 7

logger = logging.getLogger(__name__)

MODEL = f"openrouter:{config.review_model}"

# Generous output token budget + 3-minute timeout guard.
# GPT-4o-mini max output is 16,384 tokens; 15,000 leaves headroom for the
# structured JSON wrapper while still capturing all realistic findings.
_MODEL_SETTINGS = ModelSettings(max_tokens=15000, timeout=180)

reviewer = Agent(
    MODEL,
    system_prompt=REVIEWER_PROMPT,
    output_type=AgentFindings,
    model_settings=_MODEL_SETTINGS,
    name="reviewer",
)

# Logfire instrumentation
try:
    import logfire

    if config.enable_logfire and config.logfire_token:
        logfire.configure(token=config.logfire_token)
        logfire.instrument_pydantic_ai(reviewer)
except ImportError:
    pass


def _dedup_issues(issues: list[Issue]) -> list[Issue]:
    """Remove duplicate issues by (file, line_start, normalized title prefix)."""
    seen: set[tuple[str, int, str]] = set()
    deduped: list[Issue] = []
    for issue in issues:
        # Normalize: first 5 words of lowercase title to catch near-duplicate wording
        title_key = " ".join(issue.title.lower().split()[:5])
        key = (issue.file, issue.line_start, title_key)
        if key not in seen:
            seen.add(key)
            deduped.append(issue)
    return deduped


async def run_review(prompt: str, repo_id: str, pr_number: int) -> ReviewResults:
    """Run the reviewer agent on a pre-built prompt and return structured results."""

    logger.info(f"Starting review for {repo_id}#{pr_number}")

    try:
        result = await reviewer.run(prompt)
        findings: AgentFindings = result.output
    except Exception as exc:
        logger.error(f"Reviewer agent failed: {exc}", exc_info=exc)
        findings = AgentFindings(walk_through=[], issues=[], positive_findings=[])

    logger.info(f"Reviewer returned {len(findings.issues)} raw issues")

    # Filter low-confidence findings
    filtered = [i for i in findings.issues if i.confidence >= CONFIDENCE_THRESHOLD]
    logger.info(
        f"After confidence filter (≥{CONFIDENCE_THRESHOLD}): "
        f"{len(filtered)}/{len(findings.issues)} issues remain"
    )

    all_issues = _dedup_issues(filtered)

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
        positive_findings=findings.positive_findings,
        walk_through=findings.walk_through,
    )
