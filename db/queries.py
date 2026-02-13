

from typing import Dict, List, Any, Optional
import re
import logging

from .client import Neo4jClient
from .schema import CYPHER_QUERIES

logger = logging.getLogger(__name__)

class CodeQueryService:
    """
    Service for querying code elements from the Neo4j graph.
    
    Provides methods for:
    - Finding method/function usages and callers
    - Analyzing class hierarchies
    - Searching code by name or content
    - Reconstructing files from the graph
    """
    
    def __init__(self, client: Neo4jClient):
        self.db = client
    
    # =========================================================================
    # Graph Statistics
    # =========================================================================
    
    def get_graph_stats(self) -> Dict[str, int]:
        """Get statistics about the code graph."""
        query = CYPHER_QUERIES["get_graph_stats"]
        records, _, _ = self.db.run_query(query)
        
        if records:
            return dict(records[0])
        return {}

    def list_repositories(self) -> List[Dict[str, Any]]:
        """List all repositories in the database."""
        query = """
        MATCH (r:Repository)
        OPTIONAL MATCH (r)-[:CONTAINS*]->(f:File)
        RETURN r.id as id, r.name as name, r.owner as owner, 
               r.url as url, r.path as local_path,
               r.last_commit_hash as last_commit,
               r.created_at as created_at,
               r.updated_at as updated_at,
               count(DISTINCT f) as file_count
        ORDER BY r.updated_at DESC, r.name
        """
        records, _, _ = self.db.run_query(query)
        
        def convert_datetime(value):
            """Convert Neo4j DateTime to ISO string format."""
            if value is None:
                return None
            # Check if it's a Neo4j DateTime object
            if hasattr(value, 'iso_format'):
                return value.iso_format()
            # If it's already a string or other type, return as is
            return str(value) if value is not None else None
        
        return [
            {
                "id": record.get("id"),
                "name": record.get("name"),
                "owner": record.get("owner"),
                "url": record.get("url"),
                "local_path": record.get("local_path"),
                "last_commit": record.get("last_commit"),
                "created_at": convert_datetime(record.get("created_at")),
                "updated_at": convert_datetime(record.get("updated_at")),
                "file_count": record.get("file_count") or 0
            }
            for record in records
        ]

    def delete_repository(self, repo_id: str) -> bool:
        """Delete a repository and all its associated data."""
        try:
            query = """
            MATCH (r:Repository {id: $repo_id})
            OPTIONAL MATCH (r)-[:CONTAINS*]->(n)
            DETACH DELETE r, n
            RETURN count(r) as deleted_count
            """
            records, _, _ = self.db.run_query(query, {"repo_id": repo_id})
            return records and records[0]["deleted_count"] > 0
        except Exception as e:
            print(f"Error deleting repository {repo_id}: {str(e)}")
            return False
    
    def get_repository_stats(self, repo_id: str) -> Dict[str, Any]:
        """Get statistics for a specific repository."""
        if not self.db.connected:
            # Return mock stats
            return {
                "files": 25,
                "classes": 12,
                "functions": 89,
                "methods": 156,
                "lines": 3420,
                "imports": 67,
                "languages": ["Python", "TypeScript", "JavaScript"]
            }
            
        query = CYPHER_QUERIES["get_repo_stats"]
        records, _, _ = self.db.run_query(query, {"repo_id": repo_id})
        
        if records:
            record = records[0]
            return {
                "files": record["file_count"],
                "classes": record["class_count"],
                "functions": record["function_count"],
                "methods": record["method_count"],
                "lines": record["line_count"],
                "imports": record["import_count"],
                "languages": record["languages"]
            }
        return {}
    
    # =========================================================================
    # Method and Function Queries
    # =========================================================================
    
    def find_method_usages(self, method_name: str) -> Dict[str, Any]:
        """Find all usages of a method by name."""
        query = CYPHER_QUERIES["find_method_usages"]
        records, _, _ = self.db.run_query(query, {"method_name": method_name})

        results = []
        for record in records:
            # Convert Neo4j Node objects to dictionaries for JSON serialization
            callers = []
            for caller_dict in record["callers"]:
                if caller_dict and caller_dict.get("caller"):
                    callers.append({
                        "caller": dict(caller_dict["caller"]) if hasattr(caller_dict["caller"], "__iter__") and not isinstance(caller_dict["caller"], str) else {"name": str(caller_dict["caller"])},
                        "line": caller_dict.get("line")
                    })

            references = []
            for ref_dict in record["references"]:
                if ref_dict and ref_dict.get("line"):
                    references.append({
                        "line": dict(ref_dict["line"]) if hasattr(ref_dict["line"], "__iter__") and not isinstance(ref_dict["line"], str) else {"line": str(ref_dict["line"])},
                        "col_start": ref_dict.get("col_start")
                    })

            results.append({
                "method": dict(record["m"]) if record["m"] else None,
                "callers": callers,
                "references": references
            })
        return {"usages": results}
    
    def find_method_context(self, method_id: str) -> Dict[str, Any]:
        """Find the full context of a method (class, file, repo, user)."""
        query = CYPHER_QUERIES["find_method_context"]
        records, _, _ = self.db.run_query(query, {"method_id": method_id})
        
        if records:
            record = records[0]
            return {
                "user": record["user"],
                "repo": record["repo"],
                "file": record["file"],
                "class": record["class_name"],
                "method": record["method"],
                "lines": f"{record['start_line']}-{record['end_line']}"
            }
        return {}
    
    def find_callers(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Find all methods/functions that call a specific symbol."""
        query = CYPHER_QUERIES["find_callers"]
        records, _, _ = self.db.run_query(query, {"name": symbol_name})
        
        return [
            {
                "caller": record["caller_name"],
                "type": record["caller_type"],
                "file": record["file_path"],
                "line": record["call_line"]
            }
            for record in records
        ]
    
    # =========================================================================
    # Class Queries
    # =========================================================================
    
    def get_class_hierarchy(self, class_name: str) -> Dict[str, Any]:
        """Get the inheritance hierarchy of a class."""
        query = CYPHER_QUERIES["get_class_hierarchy"]
        records, _, _ = self.db.run_query(query, {"class_name": class_name})
        
        if records:
            record = records[0]
            return {
                "class": dict(record["c"]) if record["c"] else None,
                "ancestors": [dict(n) for n in record["ancestors"]] if record["ancestors"] else [],
                "descendants": [dict(n) for n in record["descendants"]] if record["descendants"] else []
            }
        return {}
    
    # =========================================================================
    # File Queries
    # =========================================================================
    
    def get_file_structure(self, file_id: str) -> Dict[str, Any]:
        """Get the structure of a file (classes, functions, imports)."""
        query = CYPHER_QUERIES["get_file_structure"]
        records, _, _ = self.db.run_query(query, {"file_id": file_id})
        
        if records:
            record = records[0]
            return {
                "file": dict(record["f"]) if record["f"] else None,
                "classes": record["classes"],
                "functions": [dict(f) for f in record["functions"]] if record["functions"] else [],
                "imports": [dict(i) for i in record["imports"]] if record["imports"] else []
            }
        return {}
    
    def get_repo_overview(self, repo_id: str) -> Dict[str, Any]:
        """Get an overview of a repository."""
        if not self.db.connected:
            # Return mock overview
            return {
                "repo": {
                    "id": repo_id,
                    "name": repo_id.split("/")[-1] if "/" in repo_id else repo_id,
                    "owner": repo_id.split("/")[0] if "/" in repo_id else "unknown"
                },
                "files": 25,
                "classes": 12,
                "functions": 89,
                "languages": ["Python", "TypeScript", "JavaScript"]
            }
            
        query = CYPHER_QUERIES["get_repo_overview"]
        records, _, _ = self.db.run_query(query, {"repo_id": repo_id})
        
        if records:
            record = records[0]
            return {
                "repo": record["repo"],
                "files": record["file_count"],
                "classes": record["class_count"],
                "functions": record["function_count"],
                "languages": record["languages"]
            }
        return {}
    
    def get_repo_files(self, repo_id: str) -> List[Dict[str, Any]]:
        """Get all files in a repository."""
        query = CYPHER_QUERIES["get_repo_files"]
        records, _, _ = self.db.run_query(query, {"repo_id": repo_id})
        
        return [
            {
                "file": dict(record["f"]) if record["f"] else None,
                "language": record["language"],
                "lines_count": record["lines_count"]
                
            }
            for record in records
        ]
    
    # =========================================================================
    # Search Operations
    # =========================================================================
    
    def _escape_lucene_query(self, query: str) -> str:
        """
        Escape Lucene special characters in search query.

        Strategy: Wrap the entire query in quotes to treat it as a literal phrase search.
        This prevents Lucene from interpreting special characters.

        For complex queries, users can use wildcards: *
        """
        query = query.strip()

        # If query is empty, return a wildcard
        if not query:
            return '*'

        # If the query already has quotes, escape internal quotes
        if '"' in query:
            # Escape any existing quotes and wrap in quotes
            query = query.replace('"', '\\"')

        # Wrap in quotes to make it a literal phrase search
        # This treats special characters as literals
        return f'"{query}"'

    def search_code(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for code by name or docstring."""
        # Escape Lucene special characters to prevent query parsing errors
        escaped_term = self._escape_lucene_query(search_term)

        query = CYPHER_QUERIES["search_code"]
        records, _, _ = self.db.run_query(query, {"search_term": escaped_term})

        return [
            {
                "node": dict(record["node"]) if record["node"] else None,
                "type": record["type"],
                "file": record["file"],
                "score": record["score"]
            }
            for record in records
        ]

    def search_symbols(
        self,
        search_term: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search symbols using fulltext index.

        Args:
            search_term: Search query (supports fuzzy matching)
            limit: Maximum results to return

        Returns:
            List of matching symbols with scores
        """
        query = CYPHER_QUERIES["search_symbols"]
        records, _, _ = self.db.run_query(query, {
            "search_term": search_term,
            "limit": limit
        })

        return [
            {
                "name": record["name"],
                "qualified_name": record["qualified_name"],
                "type": record["type"],
                "file_id": record["file_id"],
                "line": record["line"],
                "visibility": record["visibility"],
                "score": record["score"]
            }
            for record in records
        ]

    def find_symbol_by_qualified_name(
        self,
        qualified_name: str,
        repo_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a symbol by its exact qualified name.

        Args:
            qualified_name: Full qualified name (e.g., module.Class.method)
            repo_id: Repository ID to search in

        Returns:
            Symbol information if found
        """
        query = CYPHER_QUERIES["search_symbols_by_qualified_name"]
        records, _, _ = self.db.run_query(query, {
            "qualified_name": qualified_name,
            "repo_id": repo_id
        })

        if records:
            record = records[0]
            return {
                "id": record["id"],
                "name": record["name"],
                "qualified_name": record["qualified_name"],
                "type": record["type"],
                "file_id": record["file_id"],
                "line_start": record["line_start"],
                "line_end": record["line_end"],
                "scope": record["scope"],
                "visibility": record["visibility"],
                "docstring": record["docstring"]
            }
        return None

    def autocomplete_symbols(
        self,
        prefix: str,
        repo_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get symbol autocomplete suggestions.

        Args:
            prefix: Prefix to match (e.g., "module.Clas")
            repo_id: Repository ID
            limit: Maximum results

        Returns:
            List of matching symbol qualified names
        """
        query = CYPHER_QUERIES["autocomplete_symbols"]
        records, _, _ = self.db.run_query(query, {
            "prefix": prefix,
            "repo_id": repo_id,
            "limit": limit
        })

        return [
            {
                "qualified_name": record["qualified_name"],
                "type": record["type"],
                "visibility": record["visibility"],
                "file_id": record["file_id"]
            }
            for record in records
        ]

    def find_symbols_in_scope(
        self,
        file_id: str,
        scope: str = "module"
    ) -> List[Dict[str, Any]]:
        """
        Find all symbols in a specific scope.

        Args:
            file_id: File ID to search in
            scope: Scope type (module, class, function)

        Returns:
            List of symbols in the scope
        """
        query = CYPHER_QUERIES["find_symbols_in_scope"]
        records, _, _ = self.db.run_query(query, {
            "file_id": file_id,
            "scope": scope
        })

        return [
            {
                "name": record["name"],
                "qualified_name": record["qualified_name"],
                "type": record["type"],
                "line_start": record["line_start"],
                "visibility": record["visibility"]
            }
            for record in records
        ]
    
    def find_symbol_definition(self, symbol_name: str, repo_id: str) -> List[Dict[str, Any]]:
        """Find where a symbol (class, function, method, variable) is defined."""
        query = """
        MATCH (symbol)
        WHERE symbol.name = $symbol_name
          AND (symbol.file_id STARTS WITH $repo_id OR symbol.class_id STARTS WITH $repo_id)
        MATCH (f:File)-[:DEFINES*1..2]->(symbol)
        RETURN symbol.name as name, labels(symbol)[0] as type,
               f.path as file, symbol.line_start as line,
               symbol.docstring as docstring, symbol.source_code as source_code
        """
        records, _, _ = self.db.run_query(query, {
            "symbol_name": symbol_name,
            "repo_id": repo_id
        })

        return [
            {
                "name": record["name"],
                "type": record["type"],
                "file": record["file"],
                "line": record["line"],
                "docstring": record["docstring"],
                "source_code": record.get("source_code")
            }
            for record in records
        ]
    
    # =========================================================================
    # Impact Analysis
    # =========================================================================
    
    def analyze_change_impact(self, target_id: str) -> List[Dict[str, Any]]:
        """Analyze the impact of changing a specific code element."""
        query = CYPHER_QUERIES["analyze_change_impact"]
        records, _, _ = self.db.run_query(query, {"target_id": target_id})

        return [
            {
                "affected": record["affected"],
                "type": record["type"],
                "file": record["file"],
                "distance": record["distance"]
            }
            for record in records
        ]

    def analyze_change_impact_enhanced(
        self,
        qualified_name: str,
        repo_id: str
    ) -> Dict[str, Any]:
        """
        Enhanced impact analysis with multi-dimensional impact tracking.

        Analyzes:
        - Direct callers
        - Transitive callers (up to 3 levels)
        - Inheritance impact (for classes/methods)
        - Import impact (files that import changed file)

        Args:
            qualified_name: Fully qualified name of the symbol
            repo_id: Repository ID

        Returns:
            Dict with categorized impact analysis
        """
        query = CYPHER_QUERIES["analyze_change_impact_enhanced"]
        records, _, _ = self.db.run_query(query, {
            "qualified_name": qualified_name,
            "repo_id": repo_id
        })

        if records:
            record = records[0]
            return {
                "target": record["target"],
                "direct_calls": [call for call in record["direct_calls"] if call.get("name")],
                "transitive_calls": [call for call in record["transitive_calls"] if call.get("name")],
                "inheritance_impact": [imp for imp in record["inheritance_impact"] if imp.get("name")],
                "import_impact": [imp for imp in record["import_impact"] if imp.get("name")],
                "total_impact": record["total_impact"]
            }
        return {
            "target": qualified_name,
            "direct_calls": [],
            "transitive_calls": [],
            "inheritance_impact": [],
            "import_impact": [],
            "total_impact": 0
        }

    def get_call_graph(
        self,
        qualified_name: str,
        repo_id: str,
        max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get the call graph starting from a symbol.

        Args:
            qualified_name: Starting symbol
            repo_id: Repository ID
            max_depth: Maximum depth to traverse

        Returns:
            List of caller-callee relationships
        """
        query = CYPHER_QUERIES["get_call_graph"]
        records, _, _ = self.db.run_query(query, {
            "qualified_name": qualified_name,
            "repo_id": repo_id,
            "max_depth": max_depth
        })

        return [
            {
                "caller": record["caller"],
                "callee": record["callee"],
                "caller_type": record["caller_type"],
                "callee_type": record["callee_type"],
                "line": record["line"],
                "depth": record["depth"]
            }
            for record in records
        ]
    
    # =========================================================================
    # Code Retrieval Operations
    # =========================================================================

    def get_code_at_line(self, file_id: str, line_number: int) -> Optional[str]:
        """
        Get the code content at a specific line.

        Note: Uses file source_code and extracts the specific line.
        """
        source_code = self.reconstruct_file(file_id)
        if not source_code:
            return None

        lines = source_code.split('\n')
        if 0 < line_number <= len(lines):
            return lines[line_number - 1]
        return None

    def get_code_range(
        self,
        file_id: str,
        start_line: int,
        end_line: int
    ) -> List[Dict[str, Any]]:
        """
        Get code content for a range of lines.

        Note: Uses file source_code and extracts the range.
        """
        source_code = self.reconstruct_file(file_id)
        if not source_code:
            return []

        lines = source_code.split('\n')
        result = []

        for i in range(start_line - 1, min(end_line, len(lines))):
            if i >= 0:
                line_content = lines[i]
                result.append({
                    "line": i + 1,
                    "content": line_content,
                    "is_comment": line_content.strip().startswith(('#', '//', '/*')),
                    "is_blank": len(line_content.strip()) == 0
                })

        return result
    
    # =========================================================================
    # File Reconstruction
    # =========================================================================
    
    def get_repository_files(self, repo_id: str) -> List[Dict[str, Any]]:
        """Get all files in a repository."""
        query = """
        MATCH (r:Repository {id: $repo_id})-[:CONTAINS*]->(f:File)
        RETURN f.id as id, f.path as path, f.language as language, 
               f.lines_count as lines_count
        ORDER BY f.path
        """
        records, _, _ = self.db.run_query(query, {"repo_id": repo_id})
        return [
            {
                "id": record["id"],
                "path": record["path"],
                "language": record["language"],
                "lines_count": record["lines_count"]
            }
            for record in records
        ]
    
    def reconstruct_file(self, file_id: str) -> Optional[str]:
        """
        Reconstruct a file's complete content from source_code property.

        Returns:
            Complete file source code or None if not found
        """
        query = """
        MATCH (f:File {id: $file_id})
        RETURN f.source_code as source_code, f.path as path
        """
        records, _, _ = self.db.run_query(query, {"file_id": file_id})

        if not records:
            return None

        source_code = records[0].get("source_code")
        if not source_code:
            # Fallback: try to reconstruct from individual code elements
            # This shouldn't be needed but provides a safety net
            print(f"⚠️  Warning: File {records[0].get('path')} has no source_code stored")
            return None

        return source_code

    def verify_reconstruction(self, file_id: str) -> Dict[str, Any]:
        """
        Verify that file reconstruction is possible and show stats.

        Args:
            file_id: File ID to verify

        Returns:
            Dict with verification results
        """
        query = """
        MATCH (f:File {id: $file_id})
        OPTIONAL MATCH (f)-[:DEFINES]->(c:Class)
        OPTIONAL MATCH (f)-[:DEFINES]->(fn:Function)
        OPTIONAL MATCH (c)-[:HAS_METHOD]->(m:Method)
        RETURN f.path as path,
               f.language as language,
               f.lines_count as lines_count,
               f.source_code IS NOT NULL as has_source_code,
               size(f.source_code) as source_code_size,
               count(DISTINCT c) as class_count,
               count(DISTINCT fn) as function_count,
               count(DISTINCT m) as method_count
        """
        records, _, _ = self.db.run_query(query, {"file_id": file_id})

        if not records:
            return {"error": "File not found", "file_id": file_id}

        record = records[0]
        can_reconstruct = record["has_source_code"]

        return {
            "file_id": file_id,
            "path": record["path"],
            "language": record["language"],
            "lines_count": record["lines_count"],
            "can_reconstruct": can_reconstruct,
            "source_code_size": record["source_code_size"] or 0,
            "classes": record["class_count"],
            "functions": record["function_count"],
            "methods": record["method_count"],
            "status": "✅ Ready" if can_reconstruct else "❌ No source_code"
        }
    
    def get_symbol_source(self, qualified_name: str, repo_id: str) -> Optional[str]:
        """
        Get source code for a specific symbol.

        Args:
            qualified_name: Fully qualified name of the symbol
            repo_id: Repository ID

        Returns:
            Source code of the symbol or None
        """
        query = """
        MATCH (s:Symbol {qualified_name: $qualified_name})
        WHERE s.file_id STARTS WITH $repo_id
        RETURN s.source_code as source_code
        LIMIT 1
        """
        records, _, _ = self.db.run_query(query, {
            "qualified_name": qualified_name,
            "repo_id": repo_id
        })

        if records and records[0]["source_code"]:
            return records[0]["source_code"]

        # Fallback: try to get from definition node
        symbol = self.find_symbol_by_qualified_name(qualified_name, repo_id)
        if symbol and symbol.get("type"):
            if symbol["type"] == "class":
                return self.get_class_source(f"{symbol['file_id']}:class:{symbol['name']}:{symbol['line_start']}")
            elif symbol["type"] == "function":
                return self.get_function_source(f"{symbol['file_id']}:func:{symbol['name']}:{symbol['line_start']}")
            elif symbol["type"] == "method":
                # More complex - need to find class first
                pass

        return None

    def verify_repository_reconstruction(self, repo_id: str) -> Dict[str, Any]:
        """
        Verify that all files in a repository can be reconstructed.

        Args:
            repo_id: Repository ID

        Returns:
            Dict with verification stats
        """
        query = """
        MATCH (r:Repository {id: $repo_id})-[:CONTAINS*]->(f:File)
        RETURN count(f) as total_files,
               sum(CASE WHEN f.source_code IS NOT NULL THEN 1 ELSE 0 END) as files_with_source,
               sum(f.lines_count) as total_lines,
               sum(size(f.source_code)) as total_source_size
        """
        records, _, _ = self.db.run_query(query, {"repo_id": repo_id})

        if not records:
            return {"error": "Repository not found", "repo_id": repo_id}

        record = records[0]
        total_files = record["total_files"] or 0
        files_with_source = record["files_with_source"] or 0
        success_rate = (files_with_source / total_files * 100) if total_files > 0 else 0

        # Get list of files without source code
        problem_files_query = """
        MATCH (r:Repository {id: $repo_id})-[:CONTAINS*]->(f:File)
        WHERE f.source_code IS NULL
        RETURN f.path as path, f.id as file_id
        LIMIT 10
        """
        problem_records, _, _ = self.db.run_query(problem_files_query, {"repo_id": repo_id})

        return {
            "repo_id": repo_id,
            "total_files": total_files,
            "files_with_source": files_with_source,
            "files_without_source": total_files - files_with_source,
            "success_rate": f"{success_rate:.1f}%",
            "total_lines": record["total_lines"] or 0,
            "total_source_size_mb": (record["total_source_size"] or 0) / 1024 / 1024,
            "status": "✅ All files ready" if success_rate == 100 else f"⚠️  {total_files - files_with_source} files missing source",
            "problem_files": [r["path"] for r in problem_records] if problem_records else []
        }

    def reconstruct_repository(self, repo_id: str) -> Dict[str, str]:
        """
        Reconstruct all files in a repository.
        
        Returns:
            Dict mapping file paths to their reconstructed content
        """
        files = self.get_repository_files(repo_id)
        reconstructed = {}
        
        for file_info in files:
            content = self.reconstruct_file(file_info["id"])
            if content is not None:
                reconstructed[file_info["path"]] = content
        
        return reconstructed
    
    def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get complete metadata for a file including all code elements."""
        query = """
        MATCH (f:File {id: $file_id})
        OPTIONAL MATCH (f)-[:DEFINES]->(c:Class)
        OPTIONAL MATCH (f)-[:DEFINES]->(fn:Function)
        OPTIONAL MATCH (f)-[:HAS_IMPORT]->(i:Import)
        RETURN f.path as path,
               f.language as language,
               f.lines_count as lines_count,
               collect(DISTINCT {name: c.name, line: c.line_start, bases: c.base_classes}) as classes,
               collect(DISTINCT {name: fn.name, line: fn.line_start, params: fn.params}) as functions,
               collect(DISTINCT {module: i.module, names: i.imported_names}) as imports
        """
        records, _, _ = self.db.run_query(query, {"file_id": file_id})

        if records:
            record = records[0]
            return {
                "path": record["path"],
                "language": record["language"],
                "lines_count": record["lines_count"],
                "classes": [c for c in record["classes"] if c["name"]],
                "functions": [f for f in record["functions"] if f["name"]],
                "imports": [i for i in record["imports"] if i["module"]]
            }
        return {}

    def get_method_source(self, method_id: str) -> Optional[str]:
        """Get the source code of a specific method."""
        query = """
        MATCH (m:Method {id: $method_id})
        RETURN m.source_code as source_code
        """
        records, _, _ = self.db.run_query(query, {"method_id": method_id})
        return records[0]["source_code"] if records and records[0]["source_code"] else None

    def get_function_source(self, function_id: str) -> Optional[str]:
        """Get the source code of a specific function."""
        query = """
        MATCH (f:Function {id: $function_id})
        RETURN f.source_code as source_code
        """
        records, _, _ = self.db.run_query(query, {"function_id": function_id})
        return records[0]["source_code"] if records and records[0]["source_code"] else None

    def get_class_source(self, class_id: str) -> Optional[str]:
        """Get the source code of a specific class."""
        query = """
        MATCH (c:Class {id: $class_id})
        RETURN c.source_code as source_code
        """
        records, _, _ = self.db.run_query(query, {"class_id": class_id})
        return records[0]["source_code"] if records and records[0]["source_code"] else None
    
    # =========================================================================
    # Config File Queries
    # =========================================================================
    
    def get_repo_config_files(self, repo_id: str) -> List[Dict[str, Any]]:
        """Get all config files in a repository."""
        query = """
        MATCH (r:Repository {id: $repo_id})-[:HAS_CONFIG]->(cf:ConfigFile)
        RETURN cf.id as id, cf.path as path, cf.file_type as file_type,
               cf.project_name as project_name, cf.version as version,
               cf.lines_count as lines_count
        ORDER BY cf.path
        """
        records, _, _ = self.db.run_query(query, {"repo_id": repo_id})
        return [
            {
                "id": record["id"],
                "path": record["path"],
                "file_type": record["file_type"],
                "project_name": record["project_name"],
                "version": record["version"],
                "lines_count": record["lines_count"]
            }
            for record in records
        ]
    
    def get_repo_dependencies(self, repo_id: str) -> List[Dict[str, Any]]:
        """Get all dependencies in a repository."""
        query = """
        MATCH (r:Repository {id: $repo_id})-[:HAS_CONFIG]->(cf:ConfigFile)-[:HAS_DEPENDENCY]->(d:Dependency)
        RETURN d.name as name, d.version_spec as version, d.is_dev as is_dev,
               d.source as source, cf.path as config_file
        ORDER BY d.is_dev, d.name
        """
        records, _, _ = self.db.run_query(query, {"repo_id": repo_id})
        return [
            {
                "name": record["name"],
                "version": record["version"],
                "is_dev": record["is_dev"],
                "source": record["source"],
                "config_file": record["config_file"]
            }
            for record in records
        ]
    
    def delete_repository(self, repo_id: str) -> bool:
        """Delete a repository and all its data."""
        if not self.db.connected:
            # Mock success for testing
            return True
            
        query = """
        MATCH (r:Repository {id: $repo_id})
        DETACH DELETE r
        RETURN count(r) as deleted_count
        """
        records, _, _ = self.db.run_query(query, {"repo_id": repo_id})
        
        return len(records) > 0 and records[0].get("deleted_count", 0) > 0
    
    def get_repo_overview_extended(self, repo_id: str) -> Dict[str, Any]:
        """Get extended repository overview including config files and dependencies."""
        # Get basic stats
        basic = self.get_repo_overview(repo_id)
        
        # Get config file count
        config_query = """
        MATCH (r:Repository {id: $repo_id})-[:HAS_CONFIG]->(cf:ConfigFile)
        OPTIONAL MATCH (cf)-[:HAS_DEPENDENCY]->(d:Dependency)
        RETURN count(DISTINCT cf) as config_count, count(DISTINCT d) as dep_count
        """
        records, _, _ = self.db.run_query(config_query, {"repo_id": repo_id})
        
        if records:
            basic["config_files"] = records[0]["config_count"]
            basic["dependencies"] = records[0]["dep_count"]
        else:
            basic["config_files"] = 0
            basic["dependencies"] = 0
        
        return basic

    def get_all_ingested_repositories(self, owner: str) -> List[Dict[str, Any]]:
        """Get all ingested repositories."""
        query = """
        MATCH (r:Repository {owner: $owner})
        RETURN r.id as repo_id, r.owner as owner, r.name as name, r.url as url
        ORDER BY r.owner, r.name
        """
        records, _, _ = self.db.run_query(query, {"owner": owner})
        return [
            {
                "repo_id": record["repo_id"],
                "owner": record["owner"],
                "name": record["name"],
                "url": record["url"]
            }
            for record in records
        ]

    # =========================================================================
    # Hierarchy Navigation
    # =========================================================================

    def get_module_tree(self, repo_id: str) -> List[Dict[str, Any]]:
        """
        Get the complete module/directory tree for a repository.

        Args:
            repo_id: Repository ID

        Returns:
            List of modules with hierarchy information
        """
        query = CYPHER_QUERIES["get_module_tree"]
        records, _, _ = self.db.run_query(query, {"repo_id": repo_id})

        return [
            {
                "path": record["path"],
                "name": record["name"],
                "parent_path": record["parent_path"],
                "is_package": record["is_package"],
                "depth": record["depth"]
            }
            for record in records
        ]

    def get_file_hierarchy(self, file_id: str) -> List[Dict[str, Any]]:
        """
        Get the breadcrumb hierarchy for a file.

        Args:
            file_id: File ID

        Returns:
            Ordered list from repository to file
        """
        query = CYPHER_QUERIES["get_file_hierarchy"]
        records, _, _ = self.db.run_query(query, {"file_id": file_id})

        return [
            {
                "type": record["type"],
                "name": record["name"],
                "path": record["path"],
                "depth": record["depth"]
            }
            for record in records
        ]

    def get_directory_contents(
        self,
        repo_id: str,
        dir_path: str
    ) -> List[Dict[str, Any]]:
        """
        Get contents of a specific directory.

        Args:
            repo_id: Repository ID
            dir_path: Directory path

        Returns:
            List of files and subdirectories
        """
        query = CYPHER_QUERIES["get_directory_contents"]
        records, _, _ = self.db.run_query(query, {
            "repo_id": repo_id,
            "dir_path": dir_path
        })

        return [
            {
                "type": record["type"],
                "name": record["name"],
                "path": record["path"],
                "is_package": record["is_package"]
            }
            for record in records
        ]

    def get_symbols_at_lines(self, file_path: str, start_line: int, end_line: int) -> List[Dict[str, Any]]:
        """
        Find all symbols (functions, classes, variables) that overlap a line range in a file.
        Used to map diff hunks to affected code symbols.
        """
        query = """
        MATCH (f:File {path: $file_path})-[:CONTAINS]->(n)
        WHERE (n:Function OR n:Class OR n:Variable)
          AND n.line_number IS NOT NULL
          AND n.line_number <= $end_line
          AND coalesce(n.end_line, n.line_number) >= $start_line
        RETURN
            CASE
                WHEN n:Function THEN 'function'
                WHEN n:Class THEN 'class'
                ELSE 'variable'
            END as type,
            n.name as name,
            n.line_number as start_line,
            coalesce(n.end_line, n.line_number) as end_line,
            n.source as source,
            n.docstring as docstring,
            n.path as path
        ORDER BY n.line_number
        """
        records, _, _ = self.db.run_query(query, {
            "file_path": file_path,
            "start_line": start_line,
            "end_line": end_line,
        })
        return [dict(r) for r in records]

    def get_symbols_at_lines_by_relative_path(self, repo_id: str, relative_path: str, start_line: int, end_line: int) -> List[Dict[str, Any]]:
        """
        Find all symbols overlapping a line range using repo-relative file path.
        """
        query = """
        MATCH (f:File)
        WHERE f.relative_path = $relative_path
          AND f.path CONTAINS $repo_id
        WITH f
        MATCH (f)-[:CONTAINS]->(n)
        WHERE (n:Function OR n:Class OR n:Variable)
          AND n.line_number IS NOT NULL
          AND n.line_number <= $end_line
          AND coalesce(n.end_line, n.line_number) >= $start_line
        RETURN
            CASE
                WHEN n:Function THEN 'function'
                WHEN n:Class THEN 'class'
                ELSE 'variable'
            END as type,
            n.name as name,
            n.line_number as start_line,
            coalesce(n.end_line, n.line_number) as end_line,
            n.source as source,
            n.docstring as docstring,
            f.relative_path as file_path
        ORDER BY n.line_number
        """
        records, _, _ = self.db.run_query(query, {
            "repo_id": repo_id,
            "relative_path": relative_path,
            "start_line": start_line,
            "end_line": end_line,
        })
        return [dict(r) for r in records]

    def get_diff_context(self, repo_id: str, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build full RAG context for a set of file changes (diff).

        Args:
            repo_id: Repository ID (e.g. "owner/repo")
            changes: List of {"file_path": "relative/path.py", "start_line": 10, "end_line": 30}

        Returns:
            Dict with affected_symbols, callers, hierarchy, and file_sources.
        """
        all_affected = []
        all_callers = []
        all_hierarchy = []
        file_sources = {}

        for change in changes:
            file_path = change["file_path"]
            start_line = change.get("start_line", 1)
            end_line = change.get("end_line", 999999)

            # 1. Find affected symbols
            symbols = self.get_symbols_at_lines_by_relative_path(
                repo_id, file_path, start_line, end_line
            )
            for s in symbols:
                s["change_file"] = file_path
            all_affected.extend(symbols)

            # 2. For each affected symbol, find callers
            for sym in symbols:
                caller_query = """
                MATCH (caller)-[:CALLS]->(target)
                WHERE target.name = $name AND target.path CONTAINS $repo_id
                RETURN
                    CASE
                        WHEN caller:Function THEN 'function'
                        WHEN caller:Class THEN 'class'
                        ELSE 'other'
                    END as type,
                    caller.name as name,
                    caller.path as path,
                    caller.line_number as line_number,
                    caller.source as source
                LIMIT 20
                """
                records, _, _ = self.db.run_query(caller_query, {
                    "name": sym["name"],
                    "repo_id": repo_id,
                })
                callers = [dict(r) for r in records]
                if callers:
                    all_callers.append({
                        "symbol": sym["name"],
                        "symbol_type": sym["type"],
                        "callers": callers,
                    })

            # 3. For affected classes, get hierarchy
            class_symbols = [s for s in symbols if s["type"] == "class"]
            for cls in class_symbols:
                hier_query = """
                MATCH (c:Class {name: $name})-[:INHERITS*0..5]->(parent:Class)
                WHERE c.path CONTAINS $repo_id
                RETURN parent.name as name, parent.path as path,
                       parent.source as source, parent.docstring as docstring
                """
                records, _, _ = self.db.run_query(hier_query, {
                    "name": cls["name"],
                    "repo_id": repo_id,
                })
                if records:
                    all_hierarchy.append({
                        "class": cls["name"],
                        "hierarchy": [dict(r) for r in records],
                    })

            # 4. Get file source
            file_src_query = """
            MATCH (f:File)
            WHERE f.relative_path = $relative_path AND f.path CONTAINS $repo_id
            RETURN f.source_code as source_code, f.relative_path as path
            LIMIT 1
            """
            records, _, _ = self.db.run_query(file_src_query, {
                "relative_path": file_path,
                "repo_id": repo_id,
            })
            if records and records[0].get("source_code"):
                file_sources[file_path] = records[0]["source_code"]

        return {
            "affected_symbols": all_affected,
            "callers": all_callers,
            "class_hierarchy": all_hierarchy,
            "file_sources": file_sources,
            "total_affected": len(all_affected),
            "total_files": len(changes),
        }

    def get_diff_context_condensed(
        self, repo_id: str, changes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build lean context for a set of file changes — optimized for LLM prompts.

        Compared to get_diff_context:
        - Only returns functions/classes/methods (skips variables)
        - Returns symbol source snippets (the changed code chunk, not the whole file)
        - Returns caller names + file paths only (no caller source code)
        - Returns hierarchy as name chains only (no parent source)
        - No full file sources at all

        Args:
            repo_id: Repository ID (e.g. "owner/repo")
            changes: List of {"file_path": "relative/path.py", "start_line": 10, "end_line": 30}

        Returns:
            Dict with affected_symbols, callers, hierarchy.
        """
        all_affected: List[Dict[str, Any]] = []
        all_callers: List[Dict[str, Any]] = []
        all_hierarchy: List[Dict[str, Any]] = []
        seen_symbols: set = set()

        for change in changes:
            file_path = change["file_path"]
            start_line = change.get("start_line", 1)
            end_line = change.get("end_line", 999999)

            # 1. Find affected symbols — functions and classes only
            query = """
            MATCH (f:File)
            WHERE f.relative_path = $relative_path
              AND f.path CONTAINS $repo_id
            WITH f
            MATCH (f)-[:CONTAINS]->(n)
            WHERE (n:Function OR n:Class OR n:Method)
              AND n.line_number IS NOT NULL
              AND n.line_number <= $end_line
              AND coalesce(n.end_line, n.line_number) >= $start_line
            RETURN
                CASE
                    WHEN n:Function THEN 'function'
                    WHEN n:Method THEN 'method'
                    WHEN n:Class THEN 'class'
                END as type,
                n.name as name,
                n.line_number as start_line,
                coalesce(n.end_line, n.line_number) as end_line,
                n.source as source,
                n.docstring as docstring,
                f.relative_path as file_path
            ORDER BY n.line_number
            """
            records, _, _ = self.db.run_query(query, {
                "repo_id": repo_id,
                "relative_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
            })

            symbols = [dict(r) for r in records]
            for s in symbols:
                s["change_file"] = file_path
                # Truncate source to keep prompts lean
                if s.get("source") and len(s["source"]) > 500:
                    s["source"] = s["source"][:500] + "\n... (truncated)"
            all_affected.extend(symbols)

            # 2. For each symbol, find caller names only (no source)
            for sym in symbols:
                sym_key = f"{file_path}:{sym['name']}"
                if sym_key in seen_symbols:
                    continue
                seen_symbols.add(sym_key)

                caller_query = """
                MATCH (caller)-[:CALLS]->(target)
                WHERE target.name = $name AND target.path CONTAINS $repo_id
                RETURN DISTINCT
                    caller.name as name,
                    CASE
                        WHEN caller:Function THEN 'function'
                        WHEN caller:Method THEN 'method'
                        WHEN caller:Class THEN 'class'
                        ELSE 'other'
                    END as type,
                    caller.path as path
                LIMIT 10
                """
                records, _, _ = self.db.run_query(caller_query, {
                    "name": sym["name"],
                    "repo_id": repo_id,
                })
                callers = [dict(r) for r in records]
                if callers:
                    all_callers.append({
                        "symbol": sym["name"],
                        "symbol_type": sym["type"],
                        "callers": callers,
                    })

            # 3. For affected classes, get hierarchy names only
            class_symbols = [s for s in symbols if s["type"] == "class"]
            for cls in class_symbols:
                hier_query = """
                MATCH (c:Class {name: $name})-[:INHERITS*0..3]->(parent:Class)
                WHERE c.path CONTAINS $repo_id
                RETURN parent.name as name, parent.path as path
                """
                records, _, _ = self.db.run_query(hier_query, {
                    "name": cls["name"],
                    "repo_id": repo_id,
                })
                if records:
                    all_hierarchy.append({
                        "class": cls["name"],
                        "hierarchy": [{"name": r["name"], "path": r["path"]} for r in records],
                    })

        return {
            "affected_symbols": all_affected,
            "callers": all_callers,
            "class_hierarchy": all_hierarchy,
            "total_affected": len(all_affected),
            "total_files": len(set(c["file_path"] for c in changes)),
        }

    def get_diff_context_enhanced(
        self, repo_id: str, changes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Enhanced context gathering using CodeFinder for comprehensive dependency analysis.
        
        This version:
        - Gets full source code (not truncated)
        - Follows import statements to retrieve imported function sources
        - Uses CodeFinder for robust searching
        - Falls back gracefully when CALLS relationships don't exist
        - Includes upstream dependencies (what the function calls)
        
        Args:
            repo_id: Repository ID (e.g. "owner/repo")
            changes: List of {"file_path": "relative/path.py", "start_line": 10, "end_line": 30}
            
        Returns:
            Dict with affected_symbols, callers, imports, dependencies, hierarchy
        """
        from api.services.code_search import CodeFinder
        
        code_finder = CodeFinder(self.db)
        
        all_affected: List[Dict[str, Any]] = []
        all_callers: List[Dict[str, Any]] = []
        all_imports: List[Dict[str, Any]] = []
        all_dependencies: List[Dict[str, Any]] = []
        all_hierarchy: List[Dict[str, Any]] = []
        seen_symbols: set = set()
        seen_imports: set = set()

        for change in changes:
            file_path = change["file_path"]
            start_line = change.get("start_line", 1)
            end_line = change.get("end_line", 999999)

            # 1. Find affected symbols with FULL source code
            query = """
            MATCH (f:File {repo: $repo_id, path: $file_path})
            WITH f
            MATCH (f)-[:CONTAINS]->(n)
            WHERE (n:Function OR n:Class)
              AND n.line_number IS NOT NULL
              AND n.line_number <= $end_line
              AND coalesce(n.end_line, n.line_number) >= $start_line
            RETURN
                CASE
                    WHEN n:Function THEN 'function'
                    WHEN n:Class THEN 'class'
                END as type,
                n.name as name,
                n.line_number as start_line,
                coalesce(n.end_line, n.line_number) as end_line,
                n.source as source,
                n.docstring as docstring,
                f.path as file_path
            ORDER BY n.line_number
            """
            records, _, _ = self.db.run_query(query, {
                "repo_id": repo_id,
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
            })

            symbols = [dict(r) for r in records]
            for s in symbols:
                s["change_file"] = file_path
                # Keep full source - don't truncate for better context
            all_affected.extend(symbols)

            # 2. For each affected symbol, find callers using CodeFinder
            for sym in symbols:
                sym_key = f"{file_path}:{sym['name']}"
                if sym_key in seen_symbols:
                    continue
                seen_symbols.add(sym_key)

                # Use CodeFinder to find who calls this function
                try:
                    caller_results = code_finder.who_calls_function(
                        sym["name"],
                        sym.get("file_path")
                    )
                    
                    if caller_results:
                        callers = [
                            {
                                "name": c.get("caller_function"),
                                "type": "function",
                                "path": c.get("caller_file_path"),
                                "line": c.get("caller_line_number"),
                                "call_line": c.get("call_line_number"),
                            }
                            for c in caller_results
                            if c.get("caller_function")
                        ]
                        
                        if callers:
                            all_callers.append({
                                "symbol": sym["name"],
                                "symbol_type": sym["type"],
                                "callers": callers[:10],  # Limit to 10 callers
                            })
                except Exception as e:
                    logger.warning(f"Error finding callers for {sym['name']}: {e}")

                # 3. Find what this function calls (dependencies)
                try:
                    dep_results = code_finder.what_does_function_call(
                        sym["name"],
                        sym.get("file_path")
                    )
                    
                    if dep_results:
                        dependencies = [
                            {
                                "name": d.get("called_function"),
                                "path": d.get("called_file_path"),
                                "line": d.get("called_line_number"),
                            }
                            for d in dep_results
                            if d.get("called_function")
                        ]
                        
                        if dependencies:
                            all_dependencies.append({
                                "symbol": sym["name"],
                                "dependencies": dependencies[:10],
                            })
                except Exception as e:
                    logger.warning(f"Error finding dependencies for {sym['name']}: {e}")

            # 4. Find imports in the changed file and retrieve imported function sources
            import_query = """
            MATCH (f:File {repo: $repo_id, path: $file_path})
            MATCH (f)-[r:IMPORTS]->(m)
            RETURN
                r.alias as alias,
                r.imported_name as imported_name,
                m.name as module_name,
                r.line_number as line_number
            ORDER BY r.line_number
            LIMIT 20
            """
            import_records, _, _ = self.db.run_query(import_query, {
                "repo_id": repo_id,
                "file_path": file_path,
            })
            
            for imp in import_records:
                imported_name = imp.get("imported_name") or imp.get("alias")
                if not imported_name or imported_name in seen_imports:
                    continue
                seen_imports.add(imported_name)
                
                # Use CodeFinder to find the actual function/class source
                try:
                    # Try to find as function first
                    func_results = code_finder.find_by_function_name(imported_name, fuzzy_search=False)
                    
                    if func_results:
                        for func in func_results[:1]:  # Take the best match
                            # Filter to same repo only
                            if func.get("path") and repo_id in func.get("path", ""):
                                all_imports.append({
                                    "name": imported_name,
                                    "type": "function",
                                    "source": func.get("source", ""),
                                    "path": func.get("path"),
                                    "line": func.get("line_number"),
                                    "docstring": func.get("docstring"),
                                    "from_file": file_path,
                                })
                    else:
                        # Try as class
                        class_results = code_finder.find_by_class_name(imported_name, fuzzy_search=False)
                        if class_results:
                            for cls in class_results[:1]:
                                if cls.get("path") and repo_id in cls.get("path", ""):
                                    all_imports.append({
                                        "name": imported_name,
                                        "type": "class",
                                        "source": cls.get("source", ""),
                                        "path": cls.get("path"),
                                        "line": cls.get("line_number"),
                                        "docstring": cls.get("docstring"),
                                        "from_file": file_path,
                                    })
                except Exception as e:
                    logger.warning(f"Error finding import {imported_name}: {e}")

            # 5. For affected classes, get hierarchy using CodeFinder
            class_symbols = [s for s in symbols if s["type"] == "class"]
            for cls in class_symbols:
                try:
                    hierarchy_info = code_finder.find_class_hierarchy(
                        cls["name"],
                        cls.get("file_path")
                    )
                    
                    if hierarchy_info:
                        all_hierarchy.append({
                            "class": cls["name"],
                            "parents": hierarchy_info.get("parents", []),
                            "children": hierarchy_info.get("children", []),
                        })
                except Exception as e:
                    logger.warning(f"Error finding hierarchy for {cls['name']}: {e}")

        return {
            "affected_symbols": all_affected,
            "callers": all_callers,
            "imports": all_imports,
            "dependencies": all_dependencies,
            "class_hierarchy": all_hierarchy,
            "total_affected": len(all_affected),
            "total_imports": len(all_imports),
            "total_files": len(set(c["file_path"] for c in changes)),
        }