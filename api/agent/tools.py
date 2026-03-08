import asyncio
import json
from typing import Optional

from langchain_core.tools import tool

from api.models.semantic import SemanticHit, SemanticSearchResponse
from common.embedder import embed_texts
from db.code_serarch_layer import CodeSearchService


def get_tools(query_service: CodeSearchService, repo_id: str | None = None) -> list:
    """Return all agent tools bound to a CodeSearchService.

    If repo_id is provided every tool that supports it is scoped to that repository.
    """

    # ── helpers ───────────────────────────────────────────────────────────────

    def _fmt_results(results: list[dict], *, key_fields: list[str]) -> str:
        if not results:
            return "No results found."
        lines = []
        for r in results:
            parts = [str(r.get(f, "")) for f in key_fields if r.get(f) is not None]
            lines.append("• " + "  |  ".join(parts))
        return "\n".join(lines)

    # ── 1. Unified fulltext search ────────────────────────────────────────────

    @tool
    def search_code(query: str) -> str:
        """Search the codebase for functions, classes, variables and file content by name or keyword.
        Use this first when you need to locate any symbol or code snippet.
        Returns: type, name, file path, line number.
        """
        results = query_service.search_code(query, repo_id=repo_id)
        if not results:
            return f"No results for: '{query}'"
        return "\n".join(
            f"[{r.get('type')}] {r.get('name')}  →  {r.get('path')}:{r.get('line_number')}"
            for r in results
        )

    # ── 2. Peek file lines ────────────────────────────────────────────────────

    @tool
    def peek_code(path: str, line: int, above: int = 10, below: int = 10) -> str:
        """Read source code around a specific line in a file.
        Use after search_code or find_by_line to see the actual implementation.
        Args:
            path:  File path as returned by any search tool.
            line:  Anchor line number (1-indexed).
            above: Lines to show above the anchor (default 10, max 200).
            below: Lines to show below the anchor (default 10, max 200).
        Returns: annotated code snippet with line numbers.
        """
        result = query_service.peek_file_lines(path, line, min(above, 200), min(below, 200))
        if "error" in result:
            return f"Error: {result['error']}"
        header = f"File: {result['path']}  (anchor: line {result['anchor_line']}, total: {result['total_lines']} lines)"
        sep = "-" * 60
        body = ""
        for entry in result["window"]:
            prefix = "→" if entry["is_anchor"] else " "
            body += f"{prefix} {entry['line_number']:>4} │ {entry['content'].replace(chr(9), '    ')}\n"
        return f"{header}\n{sep}\n{body}"

    # ── 3. Semantic vector search ─────────────────────────────────────────────

    @tool
    async def semantic_search(question: str) -> str:
        """Find semantically similar code using vector embeddings.
        Use when you need to find code by meaning rather than exact keywords.
        Args:
            question: A natural language description of what you're looking for.
        Returns: ranked code snippets with name, path, score, and docstring.
        """
        vectors: list[list[float]] = await asyncio.to_thread(embed_texts, [question])
        results = query_service.semantic_search(vectors[0], repo_id=repo_id)
        if not results:
            return "No semantic matches found."
        lines = []
        for r in results[:10]:
            score = f"{float(r.get('score') or 0):.3f}"
            lines.append(
                f"[{r.get('type')}] {r.get('name')}  score={score}  →  {r.get('path')}:{r.get('line_number')}"
            )
            if r.get("docstring"):
                lines.append(f"    {r['docstring'][:120]}")
        return "\n".join(lines)

    # ── 4. Find function by name ──────────────────────────────────────────────

    @tool
    def find_function(name: str, fuzzy: bool = False) -> str:
        """Find a function by its exact name (or fuzzy match).
        Use when you know the function name and want its definition and location.
        Args:
            name:  Function name.
            fuzzy: Set True for partial / fuzzy matching.
        Returns: function name, file path, line number, docstring, source snippet.
        """
        results = query_service.find_by_function_name(name, fuzzy, repo_id=repo_id)
        if not results:
            return f"Function '{name}' not found."
        lines = []
        for r in results:
            lines.append(f"[function] {r.get('name')}  →  {r.get('path')}:{r.get('line_number')}")
            if r.get("docstring"):
                lines.append(f"  docstring: {r['docstring'][:200]}")
            if r.get("source") or r.get("source_code"):
                src = (r.get("source_code") or r.get("source") or "")[:300]
                lines.append(f"  source:\n    {src}")
        return "\n".join(lines)

    # ── 5. Find class by name ─────────────────────────────────────────────────

    @tool
    def find_class(name: str, fuzzy: bool = False) -> str:
        """Find a class by its exact name (or fuzzy match).
        Use when you need the definition, methods, or inheritance of a class.
        Args:
            name:  Class name.
            fuzzy: Set True for partial / fuzzy matching.
        Returns: class name, file path, line number, docstring, source snippet.
        """
        results = query_service.find_by_class_name(name, fuzzy, repo_id=repo_id)
        if not results:
            return f"Class '{name}' not found."
        lines = []
        for r in results:
            lines.append(f"[class] {r.get('name')}  →  {r.get('path')}:{r.get('line_number')}")
            if r.get("docstring"):
                lines.append(f"  docstring: {r['docstring'][:200]}")
            if r.get("source") or r.get("source_code"):
                src = (r.get("source_code") or r.get("source") or "")[:300]
                lines.append(f"  source:\n    {src}")
        return "\n".join(lines)

    # ── 6. Find variable by name ──────────────────────────────────────────────

    @tool
    def find_variable(name: str) -> str:
        """Find a variable or constant by name (substring match).
        Use when you need to locate a specific variable definition.
        Returns: variable name, file path, line number.
        """
        results = query_service.find_by_variable_name(name, repo_id=repo_id)
        if not results:
            return f"Variable '{name}' not found."
        return _fmt_results(results, key_fields=["name", "path", "line_number"])

    # ── 7. Find by content ────────────────────────────────────────────────────

    @tool
    def find_by_content(query: str) -> str:
        """Search function/class/variable bodies for a specific code pattern or string.
        Use when you're looking for a particular implementation detail or usage pattern.
        Returns: symbol name, type, file path, line number.
        """
        results = query_service.find_by_content(query, repo_id=repo_id)
        if not results:
            return f"No content matches for: '{query}'"
        return _fmt_results(results, key_fields=["type", "name", "path", "line_number"])

    # ── 8. Find by file line ──────────────────────────────────────────────────

    @tool
    def find_by_line(query: str, limit: int = 20) -> str:
        """Search raw file content line-by-line for a specific string or pattern.
        Use when you need to find where a literal string appears across all files.
        Pair with peek_code to read context around a hit.
        Returns: file path, line number, and the matching line.
        """
        results = query_service.search_file_content(query, min(limit, 100), repo_id=repo_id)
        if not results:
            return f"No line matches for: '{query}'"
        return _fmt_results(results, key_fields=["path", "line_number", "match_line"])

    # ── 9. Find module ────────────────────────────────────────────────────────

    @tool
    def find_module(name: str) -> str:
        """Find a module (package, directory, or external dependency) by name.
        Use to understand what files import a given package/module.
        Returns: module name, language, files that import it.
        """
        results = query_service.find_by_module_name(name)
        if not results:
            return f"Module '{name}' not found."
        lines = []
        for r in results:
            lines.append(f"[module] {r.get('module_name')}  lang={r.get('lang')}")
            importers = r.get("files") or []
            for f in importers[:10]:
                lines.append(f"  imported by: {f}")
        return "\n".join(lines)

    # ── 10. Find imports ──────────────────────────────────────────────────────

    @tool
    def find_imports(name: str) -> str:
        """Find all import statements that reference a module, symbol, or alias by name.
        Use to understand where a dependency is used across the codebase.
        Returns: module name, imported name, alias, file path, line number.
        """
        results = query_service.find_imports(name, repo_id=repo_id)
        if not results:
            return f"No imports found for: '{name}'"
        return _fmt_results(
            results, key_fields=["module_name", "imported_name", "alias", "path", "line_number"]
        )

    # ── 11. Find method usages ────────────────────────────────────────────────

    @tool
    def find_method_usages(method_name: str) -> str:
        """Find all places where a specific method or function is called.
        Use to understand how widely a function is used before modifying it.
        Returns: method definition, callers, and call sites.
        """
        result = query_service.find_method_usages(method_name, repo_id=repo_id)
        if not result:
            return f"No usages found for method: '{method_name}'"
        lines = []
        if result.get("method"):
            m = result["method"]
            lines.append(f"Definition: {m.get('name')}  →  {m.get('path')}:{m.get('line_number')}")
        callers = result.get("callers") or []
        if callers:
            lines.append(f"\nCallers ({len(callers)}):")
            for c in callers:
                lines.append(f"  • {c.get('caller_name')}  →  {c.get('path')}:{c.get('call_line')}")
        else:
            lines.append("No callers found.")
        return "\n".join(lines)

    # ── 12. Find callers ──────────────────────────────────────────────────────

    @tool
    def find_callers(symbol_name: str) -> str:
        """Find all functions/methods that call a given symbol.
        Use to trace call chains and understand dependencies.
        Returns: symbol definitions and all callers with their file locations.
        """
        result = query_service.find_callers(symbol_name, repo_id=repo_id)
        if not result:
            return f"No callers found for: '{symbol_name}'"
        lines = []
        for defn in result.get("definitions") or []:
            lines.append(f"Definition: [{defn.get('type')}] {defn.get('name')}  →  {defn.get('path')}:{defn.get('line_number')}")
        callers = result.get("callers") or []
        if callers:
            lines.append(f"\nCallers ({len(callers)}):")
            for c in callers:
                lines.append(f"  • {c.get('name')}  →  {c.get('path')}:{c.get('line_number')}")
        else:
            lines.append("No callers found.")
        return "\n".join(lines)

    # ── 13. Class hierarchy ───────────────────────────────────────────────────

    @tool
    def get_class_hierarchy(class_name: str) -> str:
        """Get the inheritance tree for a class — both parent and child classes.
        Use when you need to understand OOP structure or polymorphism.
        Returns: the class, its parents, its children, and their file locations.
        """
        result = query_service.get_class_hierarchy(class_name, repo_id=repo_id)
        if not result:
            return f"Class '{class_name}' not found."
        lines = []
        if result.get("class"):
            c = result["class"]
            lines.append(f"[class] {c.get('name')}  →  {c.get('path')}:{c.get('line_number')}")
        for parent in result.get("parents") or []:
            lines.append(f"  ↑ inherits from: {parent.get('name')}  ({parent.get('path')})")
        for child in result.get("children") or []:
            lines.append(f"  ↓ subclassed by: {child.get('name')}  ({child.get('path')})")
        return "\n".join(lines) if lines else f"No hierarchy data for '{class_name}'."

    # ── 14. Change impact analysis ────────────────────────────────────────────

    @tool
    def get_change_impact(symbol_name: str) -> str:
        """Analyze the blast radius of changing a function, class, or variable.
        Use before modifying a symbol to understand what would break or be affected.
        Returns: impact level (low/medium/high), callers, and usages.
        """
        usages = query_service.find_method_usages(symbol_name, repo_id=repo_id)
        callers_result = query_service.find_callers(symbol_name, repo_id=repo_id)
        callers = callers_result.get("callers") or []
        impact = "high" if len(callers) > 5 else "medium" if callers else "low"
        lines = [f"Symbol: {symbol_name}", f"Impact level: {impact.upper()}  ({len(callers)} callers)"]
        if callers:
            lines.append("\nCallers:")
            for c in callers[:10]:
                lines.append(f"  • {c.get('name')}  →  {c.get('path')}")
        return "\n".join(lines)

    # ── 15. Cyclomatic complexity ─────────────────────────────────────────────

    @tool
    def get_complexity(function_name: str, path: str | None = None) -> str:
        """Get the cyclomatic complexity score for a specific function.
        Use to identify how risky or hard to test a function is.
        Score guide: 1-5 simple, 6-10 moderate, 11-20 complex, 20+ high risk.
        Args:
            function_name: Exact function name.
            path:          Optional file path to disambiguate if the name is not unique.
        Returns: function name, file, complexity score, and risk level.
        """
        result = query_service.get_cyclomatic_complexity(function_name, path, repo_id=repo_id)
        if not result:
            return f"Function '{function_name}' not found."
        score = result.get("cyclomatic_complexity", 1)
        risk = "simple" if score <= 5 else "moderate" if score <= 10 else "complex" if score <= 20 else "high risk"
        return (
            f"Function: {result.get('name')}\n"
            f"File:     {result.get('path')}:{result.get('line_number')}\n"
            f"Score:    {score}  ({risk})"
        )

    # ── 16. Top complex functions ─────────────────────────────────────────────

    @tool
    def get_top_complex_functions(limit: int = 10) -> str:
        """List the most complex functions in the codebase by cyclomatic complexity.
        Use to identify the riskiest, hardest-to-maintain code.
        Args:
            limit: Number of results to return (default 10).
        Returns: ranked list of function name, score, file path.
        """
        results = query_service.find_most_complex_functions(limit, repo_id=repo_id)
        if not results:
            return "No complexity data found."
        lines = []
        for i, r in enumerate(results, 1):
            score = r.get("cyclomatic_complexity", 1)
            lines.append(f"{i:>2}. [{score:>3}] {r.get('name')}  →  {r.get('path')}:{r.get('line_number')}")
        return "\n".join(lines)

    # ── 17. Get full file source ──────────────────────────────────────────────

    @tool
    def get_file_source(file_path: str) -> str:
        """Get the complete source code of a file stored in the graph.
        Use when peek_code is not enough and you need the full file.
        Args:
            file_path: Repo-relative path (e.g. 'api/app.py').
        Returns: full file source with line count.
        """
        scoped_repo_id = repo_id or ""
        result = query_service.get_file_source(scoped_repo_id, file_path)
        if not result:
            return f"File not found: '{file_path}'"
        source = result.get("source_code") or result.get("source") or ""
        lines = source.splitlines()
        header = f"File: {file_path}  ({len(lines)} lines)\n" + "-" * 60
        numbered = "\n".join(f"{i+1:>4} │ {l}" for i, l in enumerate(lines))
        return f"{header}\n{numbered}"

    # ── 18. Language statistics ───────────────────────────────────────────────

    @tool
    def get_language_stats(language: str | None = None) -> str:
        """Get the breakdown of programming languages in the codebase.
        Use to understand what languages are used and how much of each.
        Args:
            language: Optional — filter to a single language (e.g. 'Python').
        Returns: per-language file count, function count, class count.
        """
        result = query_service.get_language_stats(language, repo_id=repo_id)
        if not result:
            return "No language stats available."
        if isinstance(result, dict) and "languages" in result:
            rows = result["languages"]
        elif isinstance(result, list):
            rows = result
        else:
            return json.dumps(result, indent=2)
        lines = []
        for row in rows:
            lines.append(
                f"  {row.get('language', '?'):<15} "
                f"files={row.get('file_count', 0):>4}  "
                f"functions={row.get('function_count', 0):>5}  "
                f"classes={row.get('class_count', 0):>4}"
            )
        return "Language breakdown:\n" + "\n".join(lines)

    # ── 19. Graph / repo stats ────────────────────────────────────────────────

    @tool
    def get_repo_stats() -> str:
        """Get overall statistics for the selected repository (or entire graph if no repo selected).
        Use to understand the size and composition of the codebase.
        Returns: counts of files, functions, classes, variables, imports.
        """
        if repo_id:
            stats = query_service.get_repository_stats(repo_id)
        else:
            stats = query_service.get_graph_stats()
        if not stats:
            return "No stats available."
        return json.dumps(stats, indent=2)

    return [
        search_code,
        peek_code,
        semantic_search,
        find_function,
        find_class,
        find_variable,
        find_by_content,
        find_by_line,
        find_module,
        find_imports,
        find_method_usages,
        find_callers,
        get_class_hierarchy,
        get_change_impact,
        get_complexity,
        get_top_complex_functions,
        get_file_source,
        get_language_stats,
        get_repo_stats,
    ]
