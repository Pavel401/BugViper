from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv

from src.embeddings.embedding_handler import EmbeddingHandler
from src.graph.neo4j_handler import Neo4jHandler

load_dotenv()


class CodeRAGSystem:
    """RAG system for code review and query."""

    def __init__(self, neo4j_handler: Neo4jHandler = None,
                 embedding_handler: EmbeddingHandler = None):
        self.neo4j = neo4j_handler or Neo4jHandler()
        self.embeddings = embedding_handler or EmbeddingHandler()

    def semantic_search(self, query: str, top_k: int = 5,
                       filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Perform semantic search over code chunks."""
        results = self.embeddings.search_similar_code(query, top_k=top_k, filters=filters)
        return results

    def graph_search(self, entity_name: str, entity_type: str = 'function') -> List[Dict[str, Any]]:
        """Search for code entities in the graph database."""
        if entity_type.lower() == 'function':
            return self.neo4j.find_functions_by_name(entity_name)
        elif entity_type.lower() == 'class':
            return self.neo4j.find_classes_by_name(entity_name)
        return []

    def hybrid_search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Combine semantic and graph search for comprehensive results."""
        semantic_results = self.semantic_search(query, top_k=top_k)

        enriched_results = []
        for result in semantic_results:
            enriched = result.copy()

            if result['code_type'] in ['function', 'class']:
                node_id = result['id']
                related = self.neo4j.query_related_code(node_id, depth=1)
                enriched['related_code'] = related

            enriched_results.append(enriched)

        return {
            'semantic_results': semantic_results,
            'enriched_results': enriched_results
        }

    def find_related_code(self, file_path: str, start_line: int, depth: int = 2) -> List[Dict[str, Any]]:
        """Find code related to a specific location."""
        node_id = f"{file_path}:function:{start_line}"
        related = self.neo4j.query_related_code(node_id, depth=depth)
        return related

    def get_file_context(self, file_path: str) -> Dict[str, Any]:
        """Get complete context for a file including all functions and classes."""
        structure = self.neo4j.get_file_structure(file_path)
        return structure

    def review_code_snippet(self, code: str, language: str = None,
                          context_files: List[str] = None) -> Dict[str, Any]:
        """Review a code snippet by finding similar code and related patterns."""
        filters = {}
        if language:
            filters['language'] = language

        similar_code = self.semantic_search(code, top_k=5, filters=filters)

        patterns = []
        for similar in similar_code:
            if similar['similarity'] > 0.7:
                patterns.append({
                    'file': similar['file_path'],
                    'name': similar['name'],
                    'similarity': similar['similarity'],
                    'content': similar['content']
                })

        related_context = []
        if context_files:
            for file_path in context_files:
                structure = self.get_file_context(file_path)
                if structure:
                    related_context.append(structure)

        return {
            'similar_patterns': patterns,
            'related_context': related_context,
            'suggestions': self._generate_suggestions(code, patterns)
        }

    def _generate_suggestions(self, code: str, similar_patterns: List[Dict]) -> List[str]:
        """Generate code review suggestions based on similar patterns."""
        suggestions = []

        if len(similar_patterns) >= 3:
            suggestions.append("Similar code patterns found in the codebase. Consider extracting common functionality.")

        high_similarity = [p for p in similar_patterns if p['similarity'] > 0.85]
        if high_similarity:
            suggestions.append(f"Very similar code found in {high_similarity[0]['file']}. Check for potential duplication.")

        if not similar_patterns:
            suggestions.append("No similar patterns found. This might be new functionality or could benefit from alignment with existing code style.")

        return suggestions

    def find_code_by_functionality(self, description: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Find code that matches a functional description."""
        results = self.semantic_search(description, top_k=top_k)

        grouped_by_file = {}
        for result in results:
            file_path = result['file_path']
            if file_path not in grouped_by_file:
                grouped_by_file[file_path] = []
            grouped_by_file[file_path].append(result)

        return {
            'results': results,
            'by_file': grouped_by_file
        }

    def analyze_function_usage(self, function_name: str) -> Dict[str, Any]:
        """Analyze where and how a function is used."""
        functions = self.neo4j.find_functions_by_name(function_name)

        if not functions:
            return {'found': False, 'message': 'Function not found'}

        function_data = functions[0]
        function_id = function_data.get('id')

        related = self.neo4j.query_related_code(function_id, depth=2)

        callers = [r for r in related if any(
            rel.type == 'CALLS' for rel in r.get('rels', [])
        )]

        return {
            'found': True,
            'function': function_data,
            'usage_count': len(callers),
            'callers': callers,
            'related_code': related
        }

    def compare_implementations(self, description: str, top_k: int = 5) -> Dict[str, Any]:
        """Compare different implementations of similar functionality."""
        results = self.semantic_search(description, top_k=top_k)

        implementations = []
        for result in results:
            impl = {
                'name': result['name'],
                'file': result['file_path'],
                'language': result['language'],
                'content': result['content'],
                'similarity': result['similarity'],
                'loc': result['end_line'] - result['start_line'] + 1
            }
            implementations.append(impl)

        if len(implementations) >= 2:
            avg_loc = sum(i['loc'] for i in implementations) / len(implementations)
            insights = {
                'avg_lines': avg_loc,
                'shortest': min(implementations, key=lambda x: x['loc']),
                'longest': max(implementations, key=lambda x: x['loc'])
            }
        else:
            insights = {}

        return {
            'implementations': implementations,
            'insights': insights
        }

    def close(self):
        """Close all connections."""
        self.neo4j.close()
        self.embeddings.close()
