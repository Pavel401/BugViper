import logging
from typing import Any, Dict, List, Literal, Optional

from db import Neo4jClient

logger = logging.getLogger(__name__)

class CodeFinder:
    """Module for finding relevant code snippets and analyzing relationships."""

    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j_client = neo4j_client
        self.driver = self.neo4j_client.driver

    def format_query(self, find_by: Literal["Class", "Function"], fuzzy_search: bool) -> str:
        """Format the fulltext search query for class/function name lookup."""
        return f"""
            CALL db.index.fulltext.queryNodes("code_search_index", $search_term) YIELD node, score
                WITH node, score
                WHERE node:{find_by} {'AND node.name CONTAINS $search_term' if not fuzzy_search else ''}
                RETURN node.name as name, node.path as path, node.line_number as line_number,
                    node.source as source, node.docstring as docstring, node.is_dependency as is_dependency
                ORDER BY score DESC
                LIMIT 20
            """

    def find_by_function_name(self, search_term: str, fuzzy_search: bool) -> List[Dict]:
        """Find functions by name matching."""
        with self.driver.session() as session:
            if not fuzzy_search:
                result = session.run("""
                    MATCH (node:Function {name: $name})
                    RETURN node.name as name, node.path as path, node.line_number as line_number,
                           node.source as source, node.docstring as docstring, node.is_dependency as is_dependency
                    LIMIT 20
                """, name=search_term)
                return result.data()

            formatted_search_term = f"name:{search_term}"
            result = session.run(self.format_query("Function", fuzzy_search), search_term=formatted_search_term)
            return result.data()

    def find_by_class_name(self, search_term: str, fuzzy_search: bool) -> List[Dict]:
        """Find classes by name matching."""
        with self.driver.session() as session:
            if not fuzzy_search:
                result = session.run("""
                    MATCH (node:Class {name: $name})
                    RETURN node.name as name, node.path as path, node.line_number as line_number,
                           node.source as source, node.docstring as docstring, node.is_dependency as is_dependency
                    LIMIT 20
                """, name=search_term)
                return result.data()

            formatted_search_term = f"name:{search_term}"
            result = session.run(self.format_query("Class", fuzzy_search), search_term=formatted_search_term)
            return result.data()

    def find_by_variable_name(self, search_term: str) -> List[Dict]:
        """Find variables by name matching."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (v:Variable)
                WHERE v.name CONTAINS $search_term
                RETURN v.name as name, v.path as path, v.line_number as line_number,
                       v.value as value, v.context as context, v.is_dependency as is_dependency
                ORDER BY v.is_dependency ASC, v.name
                LIMIT 20
            """, search_term=search_term)
            return result.data()

    def find_by_content(self, search_term: str) -> List[Dict]:
        """Find code by content matching in source or docstrings."""
        with self.driver.session() as session:
            try:
                result = session.run("""
                    CALL db.index.fulltext.queryNodes("code_search_index", $search_term) YIELD node, score
                    WITH node, score
                    WHERE node:Function OR node:Class OR node:Variable
                    RETURN
                        CASE
                            WHEN node:Function THEN 'function'
                            WHEN node:Class THEN 'class'
                            ELSE 'variable'
                        END as type,
                        node.name as name, node.path as path,
                        node.line_number as line_number, node.source as source,
                        node.docstring as docstring, node.is_dependency as is_dependency
                    ORDER BY score DESC
                    LIMIT 20
                """, search_term=search_term)
                return result.data()
            except Exception:
                result = session.run("""
                    MATCH (node)
                    WHERE (node:Function OR node:Class OR node:Variable)
                      AND (node.name CONTAINS $search_term
                           OR node.source CONTAINS $search_term
                           OR node.docstring CONTAINS $search_term)
                    RETURN
                        CASE
                            WHEN node:Function THEN 'function'
                            WHEN node:Class THEN 'class'
                            ELSE 'variable'
                        END as type,
                        node.name as name, node.path as path,
                        node.line_number as line_number, node.source as source,
                        node.docstring as docstring, node.is_dependency as is_dependency
                    LIMIT 20
                """, search_term=search_term)
                return result.data()

    def find_by_module_name(self, search_term: str) -> List[Dict]:
        """Find modules by name matching."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (m:Module)
                WHERE m.name CONTAINS $search_term
                RETURN m.name as name, m.lang as lang
                ORDER BY m.name
                LIMIT 20
            """, search_term=search_term)
            return result.data()

    def find_imports(self, search_term: str) -> List[Dict]:
        """Find imported symbols (aliases or original names)."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (f:File)-[r:IMPORTS]->(m:Module)
                WHERE r.alias = $search_term OR r.imported_name = $search_term
                RETURN
                    r.alias as alias,
                    r.imported_name as imported_name,
                    m.name as module_name,
                    f.path as path,
                    r.line_number as line_number
                ORDER BY f.path
                LIMIT 20
            """, search_term=search_term)
            return result.data()

    def find_class_hierarchy(self, class_name: str, path: str = None) -> Dict[str, Any]:
        """Find class inheritance relationships using INHERITS relationships."""
        with self.driver.session() as session:
            if path:
                match_clause = "MATCH (child:Class {name: $class_name, path: $path})"
            else:
                match_clause = "MATCH (child:Class {name: $class_name})"

            parents_result = session.run(f"""
                {match_clause}
                MATCH (child)-[:INHERITS]->(parent:Class)
                OPTIONAL MATCH (parent_file:File)-[:CONTAINS]->(parent)
                RETURN DISTINCT
                    parent.name as parent_class,
                    parent.path as parent_file_path,
                    parent.line_number as parent_line_number,
                    parent.docstring as parent_docstring,
                    parent.is_dependency as parent_is_dependency
                ORDER BY parent.is_dependency ASC, parent.name
            """, class_name=class_name, path=path)

            children_result = session.run(f"""
                {match_clause}
                MATCH (grandchild:Class)-[:INHERITS]->(child)
                OPTIONAL MATCH (child_file:File)-[:CONTAINS]->(grandchild)
                RETURN DISTINCT
                    grandchild.name as child_class,
                    grandchild.path as child_file_path,
                    grandchild.line_number as child_line_number,
                    grandchild.docstring as child_docstring,
                    grandchild.is_dependency as child_is_dependency
                ORDER BY grandchild.is_dependency ASC, grandchild.name
            """, class_name=class_name, path=path)

            methods_result = session.run(f"""
                {match_clause}
                MATCH (child)-[:CONTAINS]->(method:Function)
                RETURN DISTINCT
                    method.name as method_name,
                    method.path as method_file_path,
                    method.line_number as method_line_number,
                    method.args as method_args,
                    method.docstring as method_docstring,
                    method.is_dependency as method_is_dependency
                ORDER BY method.is_dependency ASC, method.line_number
            """, class_name=class_name, path=path)

            return {
                "class_name": class_name,
                "parent_classes": [dict(record) for record in parents_result],
                "child_classes": [dict(record) for record in children_result],
                "methods": [dict(record) for record in methods_result],
            }

    def get_cyclomatic_complexity(self, function_name: str, path: str = None) -> Optional[Dict]:
        """Get the cyclomatic complexity of a function."""
        with self.driver.session() as session:
            if path:
                query = """
                    MATCH (f:Function {name: $function_name})
                    WHERE f.path ENDS WITH $path OR f.path = $path
                    RETURN f.name as function_name, f.cyclomatic_complexity as complexity,
                           f.path as path, f.line_number as line_number
                """
                result = session.run(query, function_name=function_name, path=path)
            else:
                query = """
                    MATCH (f:Function {name: $function_name})
                    RETURN f.name as function_name, f.cyclomatic_complexity as complexity,
                           f.path as path, f.line_number as line_number
                """
                result = session.run(query, function_name=function_name)

            result_data = result.data()
            return result_data[0] if result_data else None

    def find_most_complex_functions(self, limit: int = 10) -> List[Dict]:
        """Find the most complex functions based on cyclomatic complexity."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (f:Function)
                WHERE f.cyclomatic_complexity IS NOT NULL AND f.is_dependency = false
                RETURN f.name as function_name, f.path as path,
                       f.cyclomatic_complexity as complexity, f.line_number as line_number
                ORDER BY f.cyclomatic_complexity DESC
                LIMIT $limit
            """, limit=limit)
            return result.data()

    def list_indexed_repositories(self) -> List[Dict]:
        """List all indexed repositories."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (r:Repository)
                RETURN r.name as name, r.path as path, r.is_dependency as is_dependency
                ORDER BY r.name
            """)
            return result.data()
