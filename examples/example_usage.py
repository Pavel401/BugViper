#!/usr/bin/env python3
"""
Example usage of the Code Review Tool
Demonstrates various features and capabilities
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ingestion_pipeline import CodeIngestionPipeline
from rag.rag_system import CodeRAGSystem
from graph.neo4j_handler import Neo4jHandler
from embeddings.embedding_handler import EmbeddingHandler


def example_1_ingest_repository():
    """Example 1: Ingest a code repository"""
    print("="*60)
    print("Example 1: Ingesting a Repository")
    print("="*60)

    # Replace with your repository path
    repo_path = "/path/to/your/repository"

    pipeline = CodeIngestionPipeline()

    try:
        # Clear existing data and ingest repository
        stats = pipeline.ingest_repository(repo_path, clear_existing=True)

        print(f"\n✓ Successfully ingested {stats['files']} files")
        print(f"  - Functions: {stats['functions']}")
        print(f"  - Classes: {stats['classes']}")
        print(f"  - Embeddings: {stats['embeddings']}")

    finally:
        pipeline.close()


def example_2_semantic_search():
    """Example 2: Semantic search for code"""
    print("\n" + "="*60)
    print("Example 2: Semantic Code Search")
    print("="*60)

    rag = CodeRAGSystem()

    try:
        # Search for authentication-related code
        query = "user authentication and login"
        results = rag.semantic_search(query, top_k=3)

        print(f"\nSearching for: '{query}'")
        print(f"Found {len(results)} results:\n")

        for i, result in enumerate(results, 1):
            print(f"{i}. {result['name']} ({result['code_type']})")
            print(f"   File: {result['file_path']}:{result['start_line']}")
            print(f"   Similarity: {result['similarity']:.3f}")
            print(f"   Preview: {result['content'][:100]}...\n")

    finally:
        rag.close()


def example_3_code_review():
    """Example 3: Review a code snippet"""
    print("\n" + "="*60)
    print("Example 3: Code Review")
    print("="*60)

    code_snippet = """
def authenticate_user(username, password):
    user = database.get_user(username)
    if user and user.password == password:
        return create_session(user)
    return None
"""

    rag = CodeRAGSystem()

    try:
        review = rag.review_code_snippet(code_snippet, language='python')

        print("\nReviewing code snippet...")
        print("\nSimilar patterns found:")
        for pattern in review['similar_patterns']:
            print(f"  - {pattern['name']} in {pattern['file']}")
            print(f"    Similarity: {pattern['similarity']:.3f}")

        print("\nSuggestions:")
        for suggestion in review['suggestions']:
            print(f"  - {suggestion}")

    finally:
        rag.close()


def example_4_function_analysis():
    """Example 4: Analyze function usage"""
    print("\n" + "="*60)
    print("Example 4: Function Usage Analysis")
    print("="*60)

    rag = CodeRAGSystem()

    try:
        # Analyze a specific function
        function_name = "authenticate"
        analysis = rag.analyze_function_usage(function_name)

        if analysis['found']:
            print(f"\nFunction: {analysis['function'].get('name')}")
            print(f"Location: {analysis['function'].get('id')}")
            print(f"Usage count: {analysis['usage_count']}")

            if analysis['callers']:
                print("\nCalled by:")
                for caller in analysis['callers'][:5]:
                    print(f"  - {caller}")
        else:
            print(f"\nFunction '{function_name}' not found")

    finally:
        rag.close()


def example_5_compare_implementations():
    """Example 5: Compare different implementations"""
    print("\n" + "="*60)
    print("Example 5: Compare Implementations")
    print("="*60)

    rag = CodeRAGSystem()

    try:
        # Find and compare different implementations
        description = "sorting algorithm"
        comparison = rag.compare_implementations(description, top_k=3)

        print(f"\nComparing implementations of: '{description}'")
        print(f"Found {len(comparison['implementations'])} implementations:\n")

        for impl in comparison['implementations']:
            print(f"- {impl['name']} ({impl['language']})")
            print(f"  File: {impl['file']}")
            print(f"  Lines: {impl['loc']}")
            print(f"  Similarity: {impl['similarity']:.3f}\n")

        if comparison['insights']:
            insights = comparison['insights']
            print("Insights:")
            print(f"  Average LOC: {insights['avg_lines']:.1f}")
            print(f"  Shortest: {insights['shortest']['name']} ({insights['shortest']['loc']} lines)")
            print(f"  Longest: {insights['longest']['name']} ({insights['longest']['loc']} lines)")

    finally:
        rag.close()


def example_6_hybrid_search():
    """Example 6: Hybrid search combining semantic and graph"""
    print("\n" + "="*60)
    print("Example 6: Hybrid Search")
    print("="*60)

    rag = CodeRAGSystem()

    try:
        query = "database connection"
        results = rag.hybrid_search(query, top_k=3)

        print(f"\nHybrid search for: '{query}'")
        print("\nEnriched results with graph context:")

        for result in results['enriched_results']:
            print(f"\n- {result['name']} ({result['code_type']})")
            print(f"  File: {result['file_path']}:{result['start_line']}")
            print(f"  Similarity: {result['similarity']:.3f}")

            if 'related_code' in result:
                print(f"  Related: {len(result['related_code'])} connected nodes")

    finally:
        rag.close()


def example_7_graph_queries():
    """Example 7: Direct graph queries"""
    print("\n" + "="*60)
    print("Example 7: Graph Database Queries")
    print("="*60)

    neo4j = Neo4jHandler()

    try:
        # Find all Python functions
        functions = neo4j.find_functions_by_name("parse")
        print(f"\nFunctions containing 'parse': {len(functions)}")

        for func in functions[:5]:
            print(f"  - {func.get('name')} in {func.get('id')}")

        # Get file structure
        file_path = "example.py"
        structure = neo4j.get_file_structure(file_path)

        if structure:
            print(f"\nStructure of {file_path}:")
            print(f"  Elements: {len(structure['elements'])}")

    finally:
        neo4j.close()


def example_8_filter_by_language():
    """Example 8: Search with language filter"""
    print("\n" + "="*60)
    print("Example 8: Language-Filtered Search")
    print("="*60)

    rag = CodeRAGSystem()

    try:
        query = "HTTP request handler"

        # Search only in Python files
        filters = {'language': 'python'}
        results = rag.semantic_search(query, top_k=3, filters=filters)

        print(f"\nSearching for: '{query}' (Python only)")
        print(f"Found {len(results)} results:")

        for result in results:
            print(f"  - {result['name']} in {result['file_path']}")
            print(f"    Similarity: {result['similarity']:.3f}")

    finally:
        rag.close()


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print(" Code Review Tool - Example Usage")
    print("="*70)

    examples = [
        ("Ingest Repository", example_1_ingest_repository),
        ("Semantic Search", example_2_semantic_search),
        ("Code Review", example_3_code_review),
        ("Function Analysis", example_4_function_analysis),
        ("Compare Implementations", example_5_compare_implementations),
        ("Hybrid Search", example_6_hybrid_search),
        ("Graph Queries", example_7_graph_queries),
        ("Language Filter", example_8_filter_by_language),
    ]

    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\nNote: Update repository path in example_1_ingest_repository()")
    print("      before running the ingestion example.\n")

    try:
        choice = input("Select example to run (1-8, or 'all'): ").strip()

        if choice.lower() == 'all':
            for name, func in examples:
                func()
        elif choice.isdigit() and 1 <= int(choice) <= len(examples):
            _, func = examples[int(choice) - 1]
            func()
        else:
            print("Invalid choice")

    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
