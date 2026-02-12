"""
PR Review Service
=================
Orchestrates the full review pipeline:
  1. Fetch PR diff from GitHub
  2. Parse diff → extract added source per file
  3. Use ingestion_service language parsers (tree-sitter) to extract imports & symbols
  4. Resolve those imports against the Neo4j graph (same repo)
  5. Find callers of changed functions (impact analysis)
  6. Build context → run LLM agents → post comment
"""

import importlib
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

from api.utils.comment_formatter import format_github_comment
from api.utils.graph_context import build_graph_context_section
from db.client import Neo4jClient
from db.queries import CodeQueryService
from deepagent.models.agent_schemas import ContextData
from deepagent.agent.review_pipeline import run_review
from common.github_client import GitHubClient
from common.diff_parser import parse_unified_diff

logger = logging.getLogger(__name__)


# ==========================================================================
# File extension → tree-sitter language name mapping (all 17 supported)
# ==========================================================================
_EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".c": "c",
    ".cpp": "cpp", ".h": "cpp", ".hpp": "cpp",
    ".cs": "c_sharp",
    ".kt": "kotlin",
    ".scala": "scala", ".sc": "scala",
    ".swift": "swift",
    ".php": "php",
    ".hs": "haskell",
}

# ==========================================================================
# Language parser registry
# Maps language name → (module path, class name) for lazy import.
# These are the SAME parsers used by the ingestion service to build the graph.
# ==========================================================================
_LANG_PARSER_REGISTRY = {
    "python":     ("ingestion_service.languages.python",     "PythonLangTreeSitterParser"),
    "javascript": ("ingestion_service.languages.javascript", "JavascriptLangTreeSitterParser"),
    "typescript": ("ingestion_service.languages.typescript", "TypescriptLangTreeSitterParser"),
    "go":         ("ingestion_service.languages.go",         "GoLangTreeSitterParser"),
    "java":       ("ingestion_service.languages.java",       "JavaLangTreeSitterParser"),
    "rust":       ("ingestion_service.languages.rust",       "RustLangTreeSitterParser"),
    "c":          ("ingestion_service.languages.c",          "CLangTreeSitterParser"),
    "cpp":        ("ingestion_service.languages.cpp",        "CppLangTreeSitterParser"),
    "ruby":       ("ingestion_service.languages.ruby",       "RubyLangTreeSitterParser"),
    "c_sharp":    ("ingestion_service.languages.csharp",     "CSharpLangTreeSitterParser"),
    "php":        ("ingestion_service.languages.php",        "PhpLangTreeSitterParser"),
    "kotlin":     ("ingestion_service.languages.kotlin",     "KotlinLangTreeSitterParser"),
    "scala":      ("ingestion_service.languages.scala",      "ScalaLangTreeSitterParser"),
    "swift":      ("ingestion_service.languages.swift",      "SwiftLangTreeSitterParser"),
    "haskell":    ("ingestion_service.languages.haskell",    "HaskellLangTreeSitterParser"),
}

# Cache so we only instantiate each language parser once
_parser_cache: Dict[str, object] = {}


# ==========================================================================
# Parser loading
# ==========================================================================

def _get_lang_parser(lang: str):
    """
    Get the tree-sitter language parser for `lang`.

    Each language parser (e.g. PythonLangTreeSitterParser) expects a wrapper
    with .language_name, .language, and .parser attributes.  We build a
    lightweight adapter instead of pulling in the full ingestion TreeSitterParser
    which depends on Neo4j/jobs.
    """
    # Return from cache if already loaded
    if lang in _parser_cache:
        return _parser_cache[lang]

    # Unknown language → skip
    if lang not in _LANG_PARSER_REGISTRY:
        return None

    module_path, class_name = _LANG_PARSER_REGISTRY[lang]
    try:
        from common.tree_sitter_manager import get_language_safe, create_parser

        # Build the adapter the language parser constructors expect
        class _Adapter:
            pass
        adapter = _Adapter()
        adapter.language_name = lang
        adapter.language = get_language_safe(lang)   # tree-sitter Language object
        adapter.parser = create_parser(lang)         # tree-sitter Parser object

        # Dynamically import the language-specific parser class
        module = importlib.import_module(module_path)
        parser_class = getattr(module, class_name)

        # Instantiate and configure
        parser_instance = parser_class(adapter)
        parser_instance.index_source = False  # we don't need source code stored on each node

        _parser_cache[lang] = parser_instance
        return parser_instance
    except Exception as e:
        logger.warning(f"Failed to load parser for {lang}: {e}")
        return None


# ==========================================================================
# Diff parsing helpers
# ==========================================================================

def _extract_added_source_by_file(diff_text: str) -> Dict[str, str]:
    """
    Walk through a unified diff and collect added lines per file.

    Returns {"app/services/foo.py": "from x import y\\ndef bar(): ..."}

    Only lines starting with '+' (but not '+++ b/...') are collected,
    with the leading '+' stripped so tree-sitter can parse the source.
    """
    files: Dict[str, List[str]] = {}
    current_file = None

    for line in diff_text.splitlines():
        # "+++ b/path/to/file" marks the start of a new file in the diff
        if line.startswith("+++ b/"):
            current_file = line[6:]  # strip "+++ b/" prefix
            if current_file not in files:
                files[current_file] = []
        # Lines starting with "+" are added lines (skip the "+++ b/" header)
        elif line.startswith("+") and not line.startswith("+++") and current_file:
            files[current_file].append(line[1:])  # strip the leading "+"

    # Join lines into a single source string per file, skip empty files
    return {f: "\n".join(lines) for f, lines in files.items() if lines}


# ==========================================================================
# Import & symbol extraction from diff (tree-sitter powered)
# ==========================================================================

def extract_imports_from_diff(diff_text: str) -> List[Dict]:
    """
    Extract imports from the added lines of a diff using tree-sitter.

    Uses the same language parsers as the ingestion service, so the import
    format matches what the graph stores:
      Python:     {"name": "foo", "full_import_name": "bar.foo", ...}
      JavaScript: {"name": "useState", "source": "react", ...}
    """
    all_imports: List[Dict] = []

    # Group added source by file path
    added_source = _extract_added_source_by_file(diff_text)

    for file_path, source in added_source.items():
        # Determine language from file extension
        ext = Path(file_path).suffix.lower()
        lang = _EXT_TO_LANG.get(ext)
        if not lang:
            continue

        # Load the language-specific parser
        parser = _get_lang_parser(lang)
        if not parser or not hasattr(parser, "_find_imports"):
            continue

        try:
            # Parse the added source into a tree-sitter AST
            tree = parser.parser.parse(source.encode("utf-8"))
            # Use the parser's own _find_imports to extract structured import data
            file_imports = parser._find_imports(tree.root_node)
            all_imports.extend(file_imports)
        except Exception as e:
            logger.warning(f"Import extraction failed for {file_path}: {e}")

    return all_imports


def extract_symbols_from_diff(diff_text: str) -> Tuple[Set[str], Set[str]]:
    """
    Extract function and class names defined in the added lines of a diff.

    Returns (function_names, class_names) as sets of strings.
    """
    functions: Set[str] = set()
    classes: Set[str] = set()

    added_source = _extract_added_source_by_file(diff_text)

    print('----- The Added source for the diff -----')
    print(added_source)
    print('-----------------------------------------------------')

    for file_path, source in added_source.items():
        #get the file extension
        ext = Path(file_path).suffix.lower()

        #get the language from the file extension
        lang = _EXT_TO_LANG.get(ext)
        if not lang:
            continue

        #get the language-specific parser
        parser = _get_lang_parser(lang)
        if not parser:
            continue

        try:
            #parse the added source into a tree-sitter AST
            tree = parser.parser.parse(source.encode("utf-8"))
            root = tree.root_node

            # Extract function definitions
            if hasattr(parser, "_find_functions"):
                for func in parser._find_functions(root):
                    functions.add(func.get("name", ""))

            # Extract class definitions
            if hasattr(parser, "_find_classes"):
                for cls in parser._find_classes(root):
                    classes.add(cls.get("name", ""))
        except Exception as e:
            logger.warning(f"Symbol extraction failed for {file_path}: {e}")

    return functions, classes


# ==========================================================================
# Graph-based resolution
# ==========================================================================

def _resolve_imports_from_graph(
    neo4j_client: Neo4jClient, imports: List[Dict], repo_id: str,
) -> List[Dict]:
    """
    For each imported name, search the Neo4j graph for its definition.

    Queries directly with repo filtering (WHERE n.repo = $repo) so results
    are scoped to the PR's repository. Searches Function, Class, and Variable
    nodes by exact name match.

    Returns a list of resolved import dicts with source code from the graph.
    """
    resolved = []
    seen = set()  # avoid looking up the same name twice

    with neo4j_client.driver.session() as session:
        for imp in imports:
            name = imp.get("name", "")

            # Skip empty, already-seen, or wildcard imports
            if not name or name in seen or name == "*":
                continue
            seen.add(name)

            # full_import_name for Python ("app.services.foo.bar"),
            # source for JS/TS ("react", "./utils")
            module = imp.get("full_import_name", imp.get("source", ""))

            try:
                # Search for the symbol in the graph, scoped to this repo
                result = session.run("""
                    MATCH (n)
                    WHERE (n:Function OR n:Class OR n:Variable)
                      AND n.name = $name
                      AND n.repo = $repo
                    RETURN n.name AS name, n.path AS path,
                           n.line_number AS line_number,
                           n.source AS source, n.docstring AS docstring,
                           labels(n) AS labels
                    LIMIT 1
                """, name=name, repo=repo_id)

                records = result.data()
                if not records:
                    continue  # symbol not in graph (external dep or not ingested)

                r = records[0]
                labels = r.get("labels", [])
                node_type = "class" if "Class" in labels else "function"

                resolved.append({
                    "name": name,
                    "module": module,
                    "type": node_type,
                    "source": r.get("source", ""),
                    "path": r.get("path", ""),
                    "line": r.get("line_number"),
                    "docstring": r.get("docstring", ""),
                })
            except Exception as e:
                logger.warning(f"Failed to resolve import {name}: {e}")

    return resolved


def _find_callers(code_finder, symbol_names: Set[str]) -> List[Dict]:
    """
    For each changed symbol, find functions that call it (impact analysis).

    Uses CodeFinder.who_calls_function which queries CALLS relationships
    in the graph.  Returns at most 10 callers per symbol.
    """
    callers = []

    for name in symbol_names:
        try:
            results = code_finder.who_calls_function(name)
            if not results:
                continue

            # Extract caller info, limit to 10 per symbol
            caller_list = [
                {
                    "name": c.get("caller_function"),
                    "path": c.get("caller_file_path"),
                    "line": c.get("caller_line_number"),
                }
                for c in results
                if c.get("caller_function")
            ][:10]

            if caller_list:
                callers.append({"symbol": name, "callers": caller_list})
        except Exception as e:
            logger.warning(f"Failed to find callers for {name}: {e}")

    return callers


# ==========================================================================
# Context formatting (for LLM agents)
# ==========================================================================

def _build_agent_context(
    import_context: List[Dict],
    caller_context: List[Dict],
    graph_section: str,
) -> str:
    """
    Build the markdown context string that gets sent to the LLM review agents.

    Combines:
      - Resolved import source code from the graph
      - Impact analysis (who calls the changed code)
      - Graph context (symbols in changed line ranges)
    """
    parts = []

    # Section 1: Source code of imported dependencies
    if import_context:
        parts.append("## Imported Dependencies (source from graph)")
        for imp in import_context:
            source = imp.get("source", "")
            if source:
                parts.append(f"### `{imp['name']}` from `{imp['module']}` ({imp.get('path', '')})")
                parts.append(f"```python\n{source}\n```")
            else:
                parts.append(f"- `{imp['name']}` from `{imp['module']}` (source not in graph)")
        parts.append("")

    # Section 2: Callers of changed functions
    if caller_context:
        parts.append("## Impact Analysis (who calls the changed code)")
        for entry in caller_context:
            caller_names = ", ".join(
                f"`{c['name']}` in `{c.get('path', '?')}`" for c in entry["callers"]
            )
            parts.append(f"- `{entry['symbol']}` is called by: {caller_names}")
        parts.append("")

    # Section 3: Graph context (symbols overlapping changed lines)
    if graph_section and graph_section != "No graph context available.":
        parts.append("## Graph Context")
        parts.append(graph_section)
        parts.append("")

    return "\n".join(parts) if parts else "No additional context available."


# ==========================================================================
# Debug dump (writes context to output/<pr_number>/context_<timestamp>.md)
# ==========================================================================

def _dump_context_to_file(
    owner: str, repo: str, pr_number: int, diff_text: str,
    agent_context: str, raw_imports: List[Dict], resolved_imports: List[Dict],
    caller_context: List[Dict], graph_symbols: list,
    files_changed: list, changed_symbol_names: list, risk_level: str,
) -> None:
    """Save all gathered context to a markdown file for debugging/inspection."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = Path("output") / str(pr_number)
        output_dir.mkdir(parents=True, exist_ok=True)
        context_file = output_dir / f"context_{timestamp}.md"

        total_callers = sum(len(c["callers"]) for c in caller_context)

        lines = [
            f"# PR Review Context — {owner}/{repo}#{pr_number}",
            f"**Generated at:** {datetime.now().isoformat()}",
            f"**Risk level:** {risk_level}",
            "",
            # What files were touched
            "## Files Changed",
            *[f"- `{f}`" for f in files_changed],
            "",
            # Functions/classes defined in the added lines
            "## Changed Symbols (from diff)",
            *[f"- `{s}`" for s in changed_symbol_names],
            "",
            # All imports found in the added lines (tree-sitter extraction)
            f"## Extracted Imports from Diff ({len(raw_imports)})",
            *[f"- `{imp.get('name', '?')}` (full: `{imp.get('full_import_name', imp.get('source', '?'))}`)"
              for imp in raw_imports],
            "",
            # Which of those imports we found in the graph (with source code)
            f"## Resolved Imports ({len(resolved_imports)}/{len(raw_imports)} resolved from graph)",
            *[f"- `{imp['name']}` from `{imp['module']}` → `{imp.get('path', 'not found')}`"
              for imp in resolved_imports],
            "",
            # Functions that call the changed symbols
            f"## Caller Impact ({total_callers} callers)",
            *[f"- `{c['symbol']}` called by: "
              + ", ".join(f"`{caller['name']}`" for caller in c["callers"])
              for c in caller_context],
            "",
            # Symbols from the graph that overlap with changed line ranges
            f"## Graph Symbols ({len(graph_symbols)})",
            *[f"- `{s.get('name', '')}` ({s.get('type', 'unknown')}) in `{s.get('file_path', '')}`"
              for s in graph_symbols],
            "",
            # The full context string that gets sent to the LLM agents
            "## Context Sent to Agents",
            agent_context,
            "",
            # Raw diff for reference
            "## Diff",
            "```diff",
            diff_text,
            "```",
        ]

        context_file.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Review context saved to {context_file}")
    except Exception as e:
        logger.warning(f"Failed to dump review context: {e}")


# ==========================================================================
# Main pipeline
# ==========================================================================

async def execute_pr_review(owner: str, repo: str, pr_number: int) -> None:
    """
    Full PR review pipeline.

    Steps:
      1. Fetch the PR diff from GitHub
      2. Parse the diff into changed file paths and line ranges
      3. Extract imports and symbol definitions from added lines (tree-sitter)
      4. Connect to Neo4j and resolve context:
         a. Find graph symbols overlapping changed line ranges
         b. Look up imported symbols in the graph (get source code)
         c. Find callers of changed functions (impact analysis)
      5. Build risk level based on scope of changes
      6. Format everything into context for the LLM agents
      7. Dump context to file for debugging
      8. Run multi-agent review (bug-hunter + security-auditor)
      9. Format and post the review comment on the PR
    """
    try:
        logger.info(f"Starting review pipeline for {owner}/{repo}#{pr_number}")
        repo_id = f"{owner}/{repo}"  # matches the repo identifier stored in the graph

        # ── Step 1: Fetch diff from GitHub ──────────────────────────────
        gh = GitHubClient()
        diff_text = await gh.get_pr_diff(owner, repo, pr_number)
        if not diff_text:
            logger.warning("Empty diff, skipping review")
            return
        logger.info(f"Fetched diff ({len(diff_text)} chars)")

        # ── Step 2: Parse diff structure ────────────────────────────────
        # Returns list of {"file_path", "start_line", "end_line"} hunks
        changes = parse_unified_diff(diff_text)
        files_changed = list({c["file_path"] for c in changes})
        logger.info(f"Parsed {len(changes)} hunks across {len(files_changed)} files")

        # ── Step 3: Extract imports & symbols from added lines ──────────
        # Uses the same tree-sitter language parsers as the ingestion service
        diff_imports = extract_imports_from_diff(diff_text)

        print('-----------------------------------------------------')
        print(diff_imports)
        print('-----------------------------------------------------')

        diff_functions, diff_classes = extract_symbols_from_diff(diff_text)

        print('-----------------------------------------------------')
        print(diff_functions)
        print(diff_classes)
        print('-----------------------------------------------------')

    
        all_diff_symbols = diff_functions | diff_classes
        logger.info(
            f"Diff extraction: {len(diff_imports)} imports, "
            f"{len(diff_functions)} functions, {len(diff_classes)} classes"
        )

        # ── Step 4: Connect to Neo4j and resolve context ────────────────
        neo4j = Neo4jClient(
            uri=os.environ.get("NEO4J_URI", ""),
            user=os.environ.get("NEO4J_USERNAME", "neo4j"),
            password=os.environ.get("NEO4J_PASSWORD", ""),
            database=os.environ.get("NEO4J_DATABASE", "neo4j"),
        )
        query_service = CodeQueryService(neo4j)
        from api.services.code_search import CodeFinder
        code_finder = CodeFinder(neo4j)

        # 4a. Graph symbols overlapping the changed line ranges
        graph_context = query_service.get_diff_context_enhanced(repo_id, changes)
        graph_symbols = graph_context.get("affected_symbols", [])
        graph_section = build_graph_context_section(graph_context)

        # 4b. Look up each imported name in the graph (scoped to this repo)
        resolved_imports = _resolve_imports_from_graph(neo4j, diff_imports, repo_id)
        logger.info(f"Resolved {len(resolved_imports)}/{len(diff_imports)} imports from graph")

        # 4c. Find callers of changed functions (impact analysis)
        # Merge symbols from diff extraction + graph overlap
        all_symbol_names = all_diff_symbols | {s.get("name", "") for s in graph_symbols}
        caller_context = _find_callers(code_finder, all_symbol_names)
        total_callers = sum(len(c["callers"]) for c in caller_context)
        logger.info(f"Found {total_callers} callers across {len(caller_context)} symbols")

        # ── Step 5: Determine risk level ────────────────────────────────
        changed_symbol_names = list(all_symbol_names)
        if total_callers > 10 or len(all_symbol_names) > 5:
            risk_level = "high"
        elif total_callers > 3 or len(all_symbol_names) > 2:
            risk_level = "medium"
        else:
            risk_level = "low"

        # ── Step 6: Build context for LLM agents ───────────────────────
        agent_context = _build_agent_context(
            resolved_imports, caller_context, graph_section
        )

        # ── Step 7: Dump context to file for debugging ──────────────────
        _dump_context_to_file(
            owner, repo, pr_number, diff_text,
            agent_context, diff_imports, resolved_imports, caller_context,
            graph_symbols, files_changed, changed_symbol_names, risk_level,
        )

        # ── Step 8: Run multi-agent review ──────────────────────────────
        review_results = await run_review(diff_text, agent_context, repo_id, pr_number)
        logger.info(f"Review complete: {len(review_results.issues)} issues found")

        # ── Step 9: Format and post comment ─────────────────────────────
        context_data = ContextData(
            files_changed=files_changed,
            modified_symbols=changed_symbol_names,
            total_callers=total_callers,
            risk_level=risk_level,
        )
        final_comment = format_github_comment(review_results, context_data, pr_number)
        await gh.post_comment(owner, repo, pr_number, final_comment)
        logger.info(f"Posted review comment on {owner}/{repo}#{pr_number}")

    except Exception:
        logger.error(f"Review pipeline failed: {traceback.format_exc()}")
