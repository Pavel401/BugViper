"""
Code query endpoints - Advanced implementation with Neo4j integration.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Dict, Any, List

from db.client import Neo4jClient
from db.queries import CodeQueryService
from api.dependencies import get_neo4j_client
from api.services.code_search import CodeFinder

router = APIRouter()


def get_query_service(db: Neo4jClient = Depends(get_neo4j_client)) -> CodeQueryService:
    """Dependency to get query service."""
    return CodeQueryService(db)


def get_code_finder(db: Neo4jClient = Depends(get_neo4j_client)) -> CodeFinder:
    """Dependency to get code finder."""
    return CodeFinder(db)


@router.get("/search")
async def search_code(
    query: str = Query(..., description="Search term — any identifier, snippet, or keyword"),
    limit: int = Query(30, description="Maximum results to return"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Unified code search.

    Three-tier strategy:
    1. Fulltext index on symbols (name, docstring, source_code)
    2. Name CONTAINS fallback (uses primary extracted identifier)
    3. File content line search (file_content_search / source_code CONTAINS)

    Results include type ('function' | 'class' | 'variable' | 'line'),
    name, path, line_number, and score. Symbol results come first
    (higher score), file-content line matches follow.
    """
    if len(query) > 500:
        raise HTTPException(status_code=400, detail="Query too long (max 500 characters)")
    try:
        results = query_service.search_code(query)
        if limit:
            results = results[:limit]
        return {
            "results": results,
            "total": len(results),
            "query": query,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/method-usages")
async def find_method_usages(
    method_name: str = Query(..., description="Name of the method to find usages for"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Find all usages of a specific method.
    """
    try:
        usages = query_service.find_method_usages(method_name)
        return usages
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find method usages: {str(e)}")


@router.get("/find_usages")
async def find_usages(
    symbol_name: str = Query(..., description="Symbol name to find usages for"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Find all usages of a specific symbol (alias for method-usages).
    """
    try:
        usages = query_service.find_method_usages(symbol_name)
        return usages
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find usages: {str(e)}")


@router.get("/find_callers")
async def find_callers(
    symbol_name: str = Query(..., description="Symbol name to find callers for"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Find all methods/functions that call a specific symbol.
    """
    try:
        callers = query_service.find_callers(symbol_name)
        return {
            "callers": callers,
            "symbol": symbol_name,
            "total": len(callers)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find callers: {str(e)}")


@router.get("/class_hierarchy")
async def get_class_hierarchy(
    class_name: str = Query(..., description="Name of the class to analyze"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Get class hierarchy (inheritance tree).
    """
    try:
        hierarchy = query_service.get_class_hierarchy(class_name)
        return hierarchy
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get class hierarchy: {str(e)}")


@router.get("/class-hierarchy")
async def get_class_hierarchy_alt(
    class_name: str = Query(..., description="Name of the class to analyze"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Get class hierarchy (inheritance tree) - alternative endpoint.
    """
    try:
        hierarchy = query_service.get_class_hierarchy(class_name)
        return hierarchy
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get class hierarchy: {str(e)}")


@router.get("/file-structure")
async def analyze_file_structure(
    file_id: str = Query(..., description="File ID to analyze"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Analyze the structure of a specific file.
    """
    try:
        structure = query_service.get_file_structure(file_id)
        return structure
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze file structure: {str(e)}")


@router.get("/change_impact")
async def analyze_change_impact(
    symbol_name: str = Query(..., description="Symbol to analyze impact for"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Analyze the impact of changing a specific symbol.
    """
    try:
        # Get all usages of the symbol to understand impact
        usages = query_service.find_method_usages(symbol_name)
        callers = query_service.find_callers(symbol_name)
        
        return {
            "symbol": symbol_name,
            "usages": usages,
            "callers": callers,
            "impact_level": "high" if len(callers) > 5 else "medium" if len(callers) > 0 else "low"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze change impact: {str(e)}")


@router.get("/relationships")
async def get_code_relationships(
    symbol_name: str = Query(..., description="Symbol to find relationships for"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Get code relationship analysis for a symbol.
    """
    try:
        # Get comprehensive relationship data
        usages = query_service.find_method_usages(symbol_name)
        callers = query_service.find_callers(symbol_name)
        
        return {
            "symbol": symbol_name,
            "relationships": {
                "usages": usages,
                "callers": callers,
                "usage_count": len(usages.get('usages', [])),
                "caller_count": len(callers)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get code relationships: {str(e)}")


@router.get("/metrics")
async def get_code_metrics(
    repo_id: str = Query(None, description="Repository ID for repo-specific metrics"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Get code metrics and statistics.
    """
    try:
        if repo_id:
            # Get repository-specific stats
            stats = query_service.get_repository_stats(repo_id)
            return {
                "repository_id": repo_id,
                "metrics": stats
            }
        else:
            # Get global graph stats
            stats = query_service.get_graph_stats()
            return {
                "global_metrics": stats
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get code metrics: {str(e)}")


@router.get("/stats")
async def get_graph_stats(
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Get overall graph statistics.
    """
    try:
        stats = query_service.get_graph_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get graph stats: {str(e)}")


@router.get("/symbol/{qualified_name}")
async def get_symbol_by_qualified_name(
    qualified_name: str,
    repo_id: str = Query(..., description="Repository ID"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Get symbol information by its qualified name.
    """
    try:
        symbol = query_service.find_symbol_by_qualified_name(qualified_name, repo_id)
        if not symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
        return symbol
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find symbol: {str(e)}")


# =========================================================================
# CodeFinder Tool Integration Endpoints
# =========================================================================

@router.get("/code-finder/function")
async def find_function_by_name(
    name: str = Query(..., description="Function name to search for"),
    fuzzy: bool = Query(False, description="Enable fuzzy search"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Find functions by name using the CodeFinder tool.
    """
    try:
        results = code_finder.find_by_function_name(name, fuzzy)
        return {
            "function_name": name,
            "fuzzy_search": fuzzy,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Function search failed: {str(e)}")


@router.get("/code-finder/class")
async def find_class_by_name(
    name: str = Query(..., description="Class name to search for"),
    fuzzy: bool = Query(False, description="Enable fuzzy search"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Find classes by name using the CodeFinder tool.
    """
    try:
        results = code_finder.find_by_class_name(name, fuzzy)
        return {
            "class_name": name,
            "fuzzy_search": fuzzy,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Class search failed: {str(e)}")


@router.get("/code-finder/variable")
async def find_variable_by_name(
    name: str = Query(..., description="Variable name to search for"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Find variables by name using the CodeFinder tool.
    """
    try:
        results = code_finder.find_by_variable_name(name)
        return {
            "variable_name": name,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Variable search failed: {str(e)}")


@router.get("/code-finder/content")
async def find_by_content(
    query: str = Query(..., description="Content search term"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Find code by content matching using the CodeFinder tool.
    """
    try:
        results = code_finder.find_by_content(query)
        return {
            "search_query": query,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Content search failed: {str(e)}")


@router.get("/code-finder/module")
async def find_module_by_name(
    name: str = Query(..., description="Module name to search for"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Find modules by name using the CodeFinder tool.
    """
    try:
        results = code_finder.find_by_module_name(name)
        return {
            "module_name": name,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Module search failed: {str(e)}")


@router.get("/code-finder/imports")
async def find_imports(
    name: str = Query(..., description="Import name to search for"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Find import statements using the CodeFinder tool.
    """
    try:
        results = code_finder.find_imports(name)
        return {
            "import_name": name,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import search failed: {str(e)}")


@router.get("/code-finder/related")
async def find_related_code(
    query: str = Query(..., description="Search query for related code"),
    fuzzy: bool = Query(False, description="Enable fuzzy search"),
    edit_distance: int = Query(2, description="Edit distance for fuzzy search"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Find code related to a query using multiple search strategies.
    """
    try:
        results = code_finder.find_related_code(query, fuzzy, edit_distance)
        return {
            "search_query": query,
            "fuzzy_search": fuzzy,
            "edit_distance": edit_distance,
            **results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Related code search failed: {str(e)}")


@router.get("/code-finder/function/arguments")
async def find_functions_by_argument(
    argument_name: str = Query(..., description="Argument name to search for"),
    path: str = Query(None, description="Optional file path to filter by"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Find functions that take a specific argument.
    """
    try:
        results = code_finder.find_functions_by_argument(argument_name, path)
        return {
            "argument_name": argument_name,
            "path_filter": path,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Function argument search failed: {str(e)}")


@router.get("/code-finder/function/decorator")
async def find_functions_by_decorator(
    decorator_name: str = Query(..., description="Decorator name to search for"),
    path: str = Query(None, description="Optional file path to filter by"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Find functions that have a specific decorator.
    """
    try:
        results = code_finder.find_functions_by_decorator(decorator_name, path)
        return {
            "decorator_name": decorator_name,
            "path_filter": path,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Function decorator search failed: {str(e)}")


@router.get("/code-finder/complexity")
async def get_cyclomatic_complexity(
    function_name: str = Query(..., description="Function name to analyze"),
    path: str = Query(None, description="Optional file path to filter by"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Get cyclomatic complexity of a function.
    """
    try:
        result = code_finder.get_cyclomatic_complexity(function_name, path)
        if not result:
            raise HTTPException(status_code=404, detail="Function not found")
        return {
            "function_name": function_name,
            "path_filter": path,
            "complexity": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Complexity analysis failed: {str(e)}")


@router.get("/code-finder/complexity/top")
async def find_most_complex_functions(
    limit: int = Query(10, description="Number of results to return"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Find the most complex functions by cyclomatic complexity.
    """
    try:
        results = code_finder.find_most_complex_functions(limit)
        return {
            "limit": limit,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Complex function search failed: {str(e)}")


@router.get("/code-finder/line")
async def find_by_line(
    query: str = Query(..., description="Search term to find in file content"),
    limit: int = Query(50, description="Maximum number of line matches to return"),
    query_service: CodeQueryService = Depends(get_query_service),
) -> Dict[str, Any]:
    """
    Search raw file content line-by-line.
    Uses file_content_search fulltext index (falls back to CONTAINS).
    Returns path + line_number + match_line for each hit — no source dumps.
    Pair with /code-finder/peek to view context around a hit.
    """
    if len(query) > 500:
        raise HTTPException(status_code=400, detail="Query too long (max 500 characters)")
    limit = min(limit, 100)  # hard cap
    try:
        results = query_service.search_file_content(query, limit)
        return {
            "query": query,
            "results": results,
            "total": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Line search failed: {str(e)}")


@router.get("/code-finder/peek")
async def peek_file_lines(
    path: str = Query(..., description="Absolute file path (as stored in graph)"),
    line: int = Query(..., description="Anchor line number (1-indexed)"),
    above: int = Query(10, description="Lines to show above the anchor"),
    below: int = Query(10, description="Lines to show below the anchor"),
    query_service: CodeQueryService = Depends(get_query_service),
) -> Dict[str, Any]:
    """
    Return a window of lines around a given line in a file.
    The anchor line is flagged with is_anchor=true.
    Use above/below to control the context window size.
    """
    above = min(above, 200)   # hard cap — prevents fetching entire file as "context"
    below = min(below, 200)
    if line < 1:
        raise HTTPException(status_code=400, detail="line must be >= 1")
    try:
        result = query_service.peek_file_lines(path, line, above, below)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Peek failed: {str(e)}")


@router.get("/code-finder/relationships")
async def analyze_code_relationships(
    query_type: str = Query(..., description="Type of relationship query"),
    target: str = Query(..., description="Target symbol for analysis"),
    context: str = Query(None, description="Additional context for the query"),
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    Analyze code relationships using the CodeFinder's relationship query system.
    
    Supported query types:
    - find_callers: Find all functions that call the target function
    - find_callees: Find all functions called by the target function
    - find_importers: Find all files that import the target module
    - who_modifies: Find what functions modify a target variable
    - class_hierarchy: Find inheritance relationships for a class
    - call_chain: Find call paths between functions (format: 'start->end')
    - module_deps: Find module dependencies
    - variable_scope: Find variable usage across scopes
    """
    try:
        results = code_finder.execute_relationship_query(query_type, target, context)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Relationship analysis failed: {str(e)}")


@router.get("/repositories/indexed")
async def list_indexed_repositories(
    code_finder: CodeFinder = Depends(get_code_finder)
) -> Dict[str, Any]:
    """
    List all indexed repositories using the CodeFinder tool.
    """
    try:
        results = code_finder.list_indexed_repositories()
        return {
            "repositories": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list repositories: {str(e)}")



@router.get("/language/{language}/symbols")
async def get_language_symbols(
    language: str,
    symbol_type: str = Query(..., description="Symbol type: function, class, variable, etc."),
    limit: int = Query(50, description="Maximum number of results"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Get all symbols of a specific type for a given language.
    
    Supported symbol types:
    - function: All functions
    - class: All classes  
    - variable: All variables
    - module: All modules
    - file: All files
    """
    try:
        # Use Neo4j to query symbols by type and language
        if symbol_type.lower() == "function":
            query = f"""
                MATCH (n:Function)
                OPTIONAL MATCH (f:File)-[:CONTAINS]->(n)
                WHERE f.language = $language OR f.extension IN ['.{language.lower()}', '.{language[:2].lower()}']
                RETURN n.name as name, n.path as path, n.line_number as line_number,
                       n.docstring as docstring, n.is_dependency as is_dependency,
                       f.language as file_language
                ORDER BY n.is_dependency ASC, n.name
                LIMIT $limit
            """
        elif symbol_type.lower() == "class":
            query = f"""
                MATCH (n:Class)
                OPTIONAL MATCH (f:File)-[:CONTAINS]->(n)
                WHERE f.language = $language OR f.extension IN ['.{language.lower()}', '.{language[:2].lower()}']
                RETURN n.name as name, n.path as path, n.line_number as line_number,
                       n.docstring as docstring, n.is_dependency as is_dependency,
                       f.language as file_language
                ORDER BY n.is_dependency ASC, n.name
                LIMIT $limit
            """
        elif symbol_type.lower() == "variable":
            query = f"""
                MATCH (n:Variable)
                OPTIONAL MATCH (f:File)-[:CONTAINS*]->(n)
                WHERE f.language = $language OR f.extension IN ['.{language.lower()}', '.{language[:2].lower()}']
                RETURN n.name as name, n.path as path, n.line_number as line_number,
                       n.value as value, n.context as context, n.is_dependency as is_dependency,
                       f.language as file_language
                ORDER BY n.is_dependency ASC, n.name
                LIMIT $limit
            """
        elif symbol_type.lower() == "file":
            query = f"""
                MATCH (n:File)
                WHERE n.language = $language OR n.extension IN ['.{language.lower()}', '.{language[:2].lower()}']
                RETURN n.name as name, n.path as path, n.relative_path as relative_path,
                       n.language as language, n.extension as extension,
                       n.is_dependency as is_dependency
                ORDER BY n.is_dependency ASC, n.path
                LIMIT $limit
            """
        elif symbol_type.lower() == "module":
            query = f"""
                MATCH (n:Module)
                WHERE n.lang = $language
                RETURN n.name as name, n.lang as language,
                       n.full_import_name as full_import_name
                ORDER BY n.name
                LIMIT $limit
            """
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported symbol type: {symbol_type}")
        
        records, _, _ = query_service.db.run_query(query, {"language": language, "limit": limit})
        
        return {
            "language": language,
            "symbol_type": symbol_type,
            "results": [dict(record) for record in records],
            "total": len(records),
            "limit": limit
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Language symbol query failed: {str(e)}")


@router.get("/language/stats")
async def get_language_statistics(
    language: str = Query(None, description="Optional language filter"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Get statistics about programming languages in the codebase.
    """
    try:
        if language:
            # Get stats for specific language
            query = """
                MATCH (f:File)
                WHERE f.language = $language OR f.extension IN ['.{}'.format($language.lower()), '.{}'.format($language[:2].lower())]
                OPTIONAL MATCH (f)-[:CONTAINS]->(func:Function)
                OPTIONAL MATCH (f)-[:CONTAINS]->(cls:Class)
                OPTIONAL MATCH (f)-[:CONTAINS]->(var:Variable)
                RETURN 
                    count(DISTINCT f) as file_count,
                    count(DISTINCT func) as function_count,
                    count(DISTINCT cls) as class_count,
                    count(DISTINCT var) as variable_count
            """
            records, _, _ = query_service.db.run_query(query, {"language": language})
            result = dict(records[0]) if records else {}
            result["language"] = language
            return result
        else:
            # Get stats for all languages
            query = """
                MATCH (f:File)
                WHERE f.language IS NOT NULL
                OPTIONAL MATCH (f)-[:CONTAINS]->(func:Function)
                OPTIONAL MATCH (f)-[:CONTAINS]->(cls:Class)
                OPTIONAL MATCH (f)-[:CONTAINS]->(var:Variable)
                RETURN 
                    f.language as language,
                    count(DISTINCT f) as file_count,
                    count(DISTINCT func) as function_count,
                    count(DISTINCT cls) as class_count,
                    count(DISTINCT var) as variable_count
                ORDER BY file_count DESC
            """
            records, _, _ = query_service.db.run_query(query)
            return {
                "languages": [dict(record) for record in records],
                "total_languages": len(records)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Language statistics query failed: {str(e)}")


# --- Code Review / Diff Context Endpoints ---


@router.get("/symbols-at-lines")
async def get_symbols_at_lines(
    file_path: str = Query(..., description="Absolute file path"),
    start_line: int = Query(..., description="Start line number"),
    end_line: int = Query(..., description="End line number"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Find all symbols (functions, classes, variables) overlapping a line range.
    Useful for mapping diff hunks to affected code.
    """
    try:
        results = query_service.get_symbols_at_lines(file_path, start_line, end_line)
        return {
            "file_path": file_path,
            "start_line": start_line,
            "end_line": end_line,
            "symbols": results,
            "total": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Symbol lookup failed: {str(e)}")


@router.get("/symbols-at-lines-relative")
async def get_symbols_at_lines_relative(
    repo_id: str = Query(..., description="Repository ID (e.g. owner/repo)"),
    file_path: str = Query(..., description="Repo-relative file path (e.g. src/main.py)"),
    start_line: int = Query(..., description="Start line number"),
    end_line: int = Query(..., description="End line number"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Find all symbols overlapping a line range using repo-relative path.
    """
    try:
        results = query_service.get_symbols_at_lines_by_relative_path(
            repo_id, file_path, start_line, end_line
        )
        return {
            "repo_id": repo_id,
            "file_path": file_path,
            "start_line": start_line,
            "end_line": end_line,
            "symbols": results,
            "total": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Symbol lookup failed: {str(e)}")


class FileChange(BaseModel):
    file_path: str
    start_line: int = 1
    end_line: int = 999999


class DiffContextRequest(BaseModel):
    repo_id: str
    changes: List[FileChange]


@router.post("/diff-context")
async def get_diff_context(
    request: DiffContextRequest,
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Build full RAG context for a code diff.

    Given a repository and a list of file changes (path + line ranges),
    returns affected symbols with source code, their callers, class hierarchy,
    and full file sources. Designed for AI-powered code review.

    Example request:
    ```json
    {
        "repo_id": "owner/repo",
        "changes": [
            {"file_path": "src/main.py", "start_line": 10, "end_line": 30},
            {"file_path": "src/utils.py", "start_line": 1, "end_line": 50}
        ]
    }
    ```
    """
    try:
        changes_dicts = [c.model_dump() for c in request.changes]
        result = query_service.get_diff_context(request.repo_id, changes_dicts)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diff context failed: {str(e)}")


@router.get("/file-source")
async def get_file_source(
    repo_id: str = Query(..., description="Repository ID"),
    file_path: str = Query(..., description="Repo-relative file path"),
    query_service: CodeQueryService = Depends(get_query_service)
) -> Dict[str, Any]:
    """
    Get the full source code of a file from the graph.
    """
    try:
        query = """
        MATCH (f:File)
        WHERE f.relative_path = $relative_path AND f.path CONTAINS $repo_id
        RETURN f.source_code as source_code, f.relative_path as path,
               f.language as language, f.lines_count as lines_count
        LIMIT 1
        """
        records, _, _ = query_service.db.run_query(query, {
            "relative_path": file_path,
            "repo_id": repo_id,
        })
        if not records:
            raise HTTPException(status_code=404, detail="File not found")
        record = records[0]
        return {
            "file_path": record.get("path"),
            "language": record.get("language"),
            "lines_count": record.get("lines_count"),
            "source_code": record.get("source_code"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File source retrieval failed: {str(e)}")
