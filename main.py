#!/usr/bin/env python3
"""
Code Review Tool with GraphRAG
Uses Tree-sitter for AST parsing, Neo4j for graph storage, and Milvus for embeddings
"""

import argparse
import sys
from pathlib import Path

from src.ingestion_pipeline import CodeIngestionPipeline
from src.rag.rag_system import CodeRAGSystem
from src.rag.chat_interface import CodeChatInterface

sys.path.insert(0, str(Path(__file__).parent / 'src'))



#Method to ingest a repository
def ingest_repository(repo_path: str, clear: bool = False):
    """Ingest a code repository."""
    print(f"Starting repository ingestion: {repo_path}")
    print("="*60)

    pipeline = CodeIngestionPipeline()

    try:
        stats = pipeline.ingest_repository(repo_path, clear_existing=clear)
        print("\nRepository successfully ingested!")
        return stats
    except Exception as e:
        print(f"Error during ingestion: {e}")
        raise
    finally:
        pipeline.close()


def search_code(query: str, top_k: int = 5, language: str = None):
    """Search for code using semantic search."""
    print(f"Searching for: '{query}'")
    print("="*60)

    rag = CodeRAGSystem()

    try:
        filters = {}
        if language:
            filters['language'] = language

        results = rag.semantic_search(query, top_k=top_k, filters=filters)

        if not results:
            print("No results found.")
            return

        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['name']} ({result['code_type']})")
            print(f"   File: {result['file_path']}:{result['start_line']}")
            print(f"   Language: {result['language']}")
            print(f"   Similarity: {result['similarity']:.3f}")
            print(f"   Preview:")
            preview = result['content'][:200].replace('\n', '\n   ')
            print(f"   {preview}...")

    finally:
        rag.close()


def review_code(code_snippet: str, language: str = None):
    """Review a code snippet."""
    print("Reviewing code snippet...")
    print("="*60)

    rag = CodeRAGSystem()

    try:
        review = rag.review_code_snippet(code_snippet, language=language)

        print("\nSimilar Patterns Found:")
        if review['similar_patterns']:
            for pattern in review['similar_patterns']:
                print(f"  - {pattern['name']} in {pattern['file']}")
                print(f"    Similarity: {pattern['similarity']:.3f}")
        else:
            print("  No similar patterns found.")

        print("\nSuggestions:")
        for suggestion in review['suggestions']:
            print(f"  - {suggestion}")

    finally:
        rag.close()


def analyze_function(function_name: str):
    """Analyze function usage."""
    print(f"Analyzing function: {function_name}")
    print("="*60)

    rag = CodeRAGSystem()

    try:
        analysis = rag.analyze_function_usage(function_name)

        if not analysis['found']:
            print(analysis['message'])
            return

        print(f"\nFunction: {analysis['function'].get('name')}")
        print(f"File: {analysis['function'].get('id')}")
        print(f"Usage count: {analysis['usage_count']}")

        if analysis['callers']:
            print("\nCalled by:")
            for caller in analysis['callers'][:5]:
                print(f"  - {caller}")

    finally:
        rag.close()


def show_graph_summary():
    """Show summary of the code graph including relationships."""
    print("Code Graph Summary")
    print("="*60)

    rag = CodeRAGSystem()

    try:
        summary = rag.neo4j.get_cross_file_relationships_summary()

        print(f"\nNodes:")
        print(f"  Files: {summary.get('total_files', 0)}")
        print(f"  Functions: {summary.get('total_functions', 0)}")
        print(f"  Classes: {summary.get('total_classes', 0)}")

        print(f"\nRelationships:")
        print(f"  Import relationships: {summary.get('import_relationships', 0)}")
        print(f"  Function call relationships: {summary.get('call_relationships', 0)}")
        print(f"  Uses relationships: {summary.get('uses_relationships', 0)}")

        total_relationships = (summary.get('import_relationships', 0) +
                             summary.get('call_relationships', 0) +
                             summary.get('uses_relationships', 0))
        print(f"  Total: {total_relationships}")

    finally:
        rag.close()


def chat_mode(use_llm: bool = False):
    """Start interactive chat mode with the RAG system."""
    print("Code RAG Chat Interface")
    print("="*60)

    if use_llm:
        print("🤖 LLM-enhanced mode (requires OPENAI_API_KEY)")
    else:
        print("💬 Basic chat mode (use --llm flag to enable AI responses)")

    print("\nCommands:")
    print("  Ask any question about your codebase")
    print("  'function <name>' - Analyze a specific function")
    print("  'file <path>' - Analyze a specific file")
    print("  'similar <description>' - Find similar implementations")
    print("  'history' - Show conversation history")
    print("  'clear' - Clear conversation history")
    print("  'exit' or 'quit' - Exit chat mode")
    print()

    chat = CodeChatInterface(use_llm=use_llm)

    try:
        while True:
            try:
                user_input = input("\n💬 You: ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() in ['exit', 'quit']:
                    print("Goodbye! 👋")
                    break

                elif user_input.lower() == 'history':
                    history = chat.get_conversation_history()
                    if not history:
                        print("No conversation history yet.")
                    else:
                        print(f"\n📜 Conversation History ({len(history)} exchanges):")
                        for i, entry in enumerate(history, 1):
                            print(f"\n{i}. Q: {entry['query']}")
                            print(f"   A: {entry['response'][:150]}...")
                    continue

                elif user_input.lower() == 'clear':
                    chat.clear_history()
                    print("✓ Conversation history cleared.")
                    continue

                elif user_input.lower().startswith('function '):
                    func_name = user_input[9:].strip()
                    result = chat.ask_about_function(func_name)
                    print(f"\n🤖 Assistant:\n{result['answer']}")
                    continue

                elif user_input.lower().startswith('file '):
                    file_path = user_input[5:].strip()
                    result = chat.ask_about_file(file_path)
                    print(f"\n🤖 Assistant:\n{result['answer']}")
                    continue

                elif user_input.lower().startswith('similar '):
                    description = user_input[8:].strip()
                    result = chat.find_similar_implementations(description)
                    print(f"\n🤖 Assistant:\n{result['answer']}")
                    continue

                # Regular chat query
                print("\n🔍 Searching codebase...")
                result = chat.chat(user_input)

                print(f"\n🤖 Assistant:\n{result['answer']}")

                # Optionally show sources
                if result['sources'] and len(result['sources']) > 0:
                    show_sources = input("\nShow source files? (y/n): ").strip().lower()
                    if show_sources == 'y':
                        print("\n📚 Sources:")
                        for i, source in enumerate(result['sources'][:3], 1):
                            print(f"\n{i}. {source['file_path']}:{source['start_line']}")
                            print(f"   {source['name']} ({source['code_type']})")

            except KeyboardInterrupt:
                print("\n\nExiting chat... 👋")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("Please try rephrasing your question.")

    finally:
        chat.close()


def interactive_mode():
    """Interactive query mode."""
    print("Code Review Tool - Interactive Mode")
    print("="*60)
    print("Commands:")
    print("  search <query> - Search for code")
    print("  function <name> - Analyze function usage")
    print("  exit - Exit interactive mode")
    print()

    rag = CodeRAGSystem()

    try:
        while True:
            try:
                user_input = input("\n> ").strip()

                if not user_input:
                    continue

                if user_input.lower() == 'exit':
                    break

                parts = user_input.split(maxsplit=1)
                command = parts[0].lower()

                if command == 'search' and len(parts) > 1:
                    query = parts[1]
                    results = rag.semantic_search(query, top_k=5)
                    for i, result in enumerate(results, 1):
                        print(f"{i}. {result['name']} - {result['file_path']}:{result['start_line']}")

                elif command == 'function' and len(parts) > 1:
                    func_name = parts[1]
                    analysis = rag.analyze_function_usage(func_name)
                    if analysis['found']:
                        print(f"Usage count: {analysis['usage_count']}")
                    else:
                        print("Function not found")

                else:
                    print("Unknown command or missing arguments")

            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

    finally:
        rag.close()


def main():
    parser = argparse.ArgumentParser(
        description='Code Review Tool with GraphRAG',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Ingest a repository:
    python main.py ingest /path/to/repo

  Show graph summary (nodes and relationships):
    python main.py summary

  Chat with your codebase (recommended):
    python main.py chat
    python main.py chat --llm  # AI-powered responses

  Search for code:
    python main.py search "authentication function"

  Analyze a function:
    python main.py function login

  Interactive mode:
    python main.py interactive
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    ingest_parser = subparsers.add_parser('ingest', help='Ingest a code repository')
    ingest_parser.add_argument('repo_path', help='Path to the repository')
    ingest_parser.add_argument('--clear', action='store_true', help='Clear existing data before ingestion')

    search_parser = subparsers.add_parser('search', help='Search for code')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('-k', '--top-k', type=int, default=5, help='Number of results')
    search_parser.add_argument('-l', '--language', help='Filter by language')

    review_parser = subparsers.add_parser('review', help='Review code snippet')
    review_parser.add_argument('code', help='Code snippet to review')
    review_parser.add_argument('-l', '--language', help='Programming language')

    function_parser = subparsers.add_parser('function', help='Analyze function usage')
    function_parser.add_argument('name', help='Function name')

    subparsers.add_parser('summary', help='Show graph summary with relationship statistics')

    chat_parser = subparsers.add_parser('chat', help='Start conversational chat mode')
    chat_parser.add_argument('--llm', action='store_true', help='Enable LLM for enhanced responses (requires OPENAI_API_KEY)')

    subparsers.add_parser('interactive', help='Start interactive mode')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == 'ingest':
            ingest_repository(args.repo_path, clear=args.clear)

        elif args.command == 'search':
            search_code(args.query, top_k=args.top_k, language=args.language)

        elif args.command == 'review':
            review_code(args.code, language=args.language)

        elif args.command == 'function':
            analyze_function(args.name)

        elif args.command == 'summary':
            show_graph_summary()

        elif args.command == 'chat':
            chat_mode(use_llm=args.llm)

        elif args.command == 'interactive':
            interactive_mode()

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
