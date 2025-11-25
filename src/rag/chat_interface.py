"""
Chat interface for conversational interaction with the code RAG system.
"""

from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv

from src.rag.rag_system import CodeRAGSystem

load_dotenv()


class CodeChatInterface:
    """Conversational interface for querying the code knowledge graph."""

    def __init__(self, rag_system: CodeRAGSystem = None, use_llm: bool = False):
        self.rag = rag_system or CodeRAGSystem()
        self.use_llm = use_llm
        self.conversation_history = []

        # Optional: Initialize LLM (OpenAI, Anthropic, etc.)
        self.llm_client = None
        if use_llm:
            self._initialize_llm()

    def _initialize_llm(self):
        """Initialize LLM client for enhanced responses."""
        try:
            import openai
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                self.llm_client = openai.OpenAI(api_key=api_key)
                print("✓ LLM integration enabled (OpenAI)")
            else:
                print("⚠ OPENAI_API_KEY not found, using basic responses")
                self.use_llm = False
        except ImportError:
            print("⚠ OpenAI package not installed, using basic responses")
            self.use_llm = False

    def chat(self, user_query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Process a user query and return a conversational response.

        Args:
            user_query: Natural language question about the codebase
            top_k: Number of relevant code chunks to retrieve

        Returns:
            Dictionary with answer, sources, and context
        """
        # Step 1: Semantic search for relevant code
        search_results = self.rag.semantic_search(user_query, top_k=top_k)

        # Step 2: Enrich with graph relationships
        enriched_results = []
        for result in search_results:
            enriched = result.copy()

            # Get related code from graph
            if result['code_type'] in ['function', 'class']:
                node_id = result['id']
                related = self.rag.neo4j.query_related_code(node_id, depth=1)
                enriched['related_code'] = related[:3]  # Limit to top 3

            enriched_results.append(enriched)

        # Step 3: Generate response
        if self.use_llm and self.llm_client:
            response = self._generate_llm_response(user_query, enriched_results)
        else:
            response = self._generate_basic_response(user_query, enriched_results)

        # Step 4: Store in conversation history
        self.conversation_history.append({
            'query': user_query,
            'response': response,
            'sources': search_results
        })

        return {
            'answer': response,
            'sources': enriched_results,
            'query': user_query
        }

    def _generate_basic_response(self, query: str, results: List[Dict]) -> str:
        """Generate a basic response without LLM."""
        if not results:
            return "I couldn't find any relevant code for your query. Try rephrasing or being more specific."

        response_parts = [
            f"I found {len(results)} relevant code sections related to your query:\n"
        ]

        for i, result in enumerate(results, 1):
            response_parts.append(
                f"\n{i}. **{result['name']}** ({result['code_type']}) in `{result['file_path']}`"
            )
            response_parts.append(f"   Location: Line {result['start_line']}-{result['end_line']}")
            response_parts.append(f"   Similarity: {result['similarity']:.2%}\n")

            # Show a preview
            preview = result['content'][:150].replace('\n', ' ')
            response_parts.append(f"   Preview: {preview}...")

            # Show related code if available
            if 'related_code' in result and result['related_code']:
                response_parts.append(f"   Related: {len(result['related_code'])} connected components")

        return '\n'.join(response_parts)

    def _generate_llm_response(self, query: str, results: List[Dict]) -> str:
        """Generate an enhanced response using LLM."""
        # Build context from search results
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"\n--- Code Section {i} ---\n"
                f"File: {result['file_path']}\n"
                f"Type: {result['code_type']}\n"
                f"Name: {result['name']}\n"
                f"Content:\n{result['content'][:500]}\n"
            )

        context = '\n'.join(context_parts)

        # Create prompt for LLM
        system_prompt = """You are a helpful code analysis assistant. You have access to a codebase
through a knowledge graph. Answer questions about the code based on the provided context.
Be specific, reference file names and function names, and provide actionable insights."""

        user_prompt = f"""Based on the following code sections from the codebase, please answer this question:

Question: {query}

Relevant Code:
{context}

Please provide a clear, concise answer that:
1. Directly answers the question
2. References specific files and functions
3. Explains any relationships or dependencies
4. Suggests related areas to explore if relevant
"""

        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",  # or gpt-3.5-turbo for faster/cheaper
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"LLM error: {e}, falling back to basic response")
            return self._generate_basic_response(query, results)

    def ask_about_function(self, function_name: str) -> Dict[str, Any]:
        """Ask about a specific function."""
        # Find the function
        functions = self.rag.neo4j.find_functions_by_name(function_name)

        if not functions:
            return {
                'found': False,
                'answer': f"I couldn't find a function named '{function_name}' in the codebase."
            }

        func = functions[0]
        func_id = func.get('id')

        # Get dependencies and dependents
        deps = self.rag.neo4j.get_function_dependencies(func_id)
        dependents = self.rag.neo4j.get_function_dependents(func_id)

        # Build response
        response_parts = [
            f"**Function: {func.get('name')}**\n",
            f"Location: `{func_id}`",
            f"Lines: {func.get('start_line')} - {func.get('end_line')}\n"
        ]

        if deps.get('calls'):
            response_parts.append(f"\nThis function calls {len(deps['calls'])} other functions:")
            for called in deps['calls'][:5]:
                response_parts.append(f"  - {called.get('name', 'Unknown')}")

        if dependents.get('called_by'):
            response_parts.append(f"\nThis function is called by {len(dependents['called_by'])} other functions:")
            for caller in dependents['called_by'][:5]:
                response_parts.append(f"  - {caller.get('name', 'Unknown')}")

        if deps.get('imports'):
            response_parts.append(f"\nFile imports {len(deps['imports'])} modules:")
            for module in deps['imports'][:5]:
                response_parts.append(f"  - {module.get('name', 'Unknown')}")

        return {
            'found': True,
            'answer': '\n'.join(response_parts),
            'function': func,
            'dependencies': deps,
            'dependents': dependents
        }

    def ask_about_file(self, file_path: str) -> Dict[str, Any]:
        """Ask about a specific file."""
        deps = self.rag.neo4j.get_file_dependencies(file_path)

        if not deps or not deps.get('file'):
            return {
                'found': False,
                'answer': f"I couldn't find the file '{file_path}' in the codebase."
            }

        file_info = deps['file']

        response_parts = [
            f"**File: {file_info.get('path')}**\n",
            f"Language: {file_info.get('language')}",
            f"Name: {file_info.get('name')}\n"
        ]

        if deps.get('imports'):
            response_parts.append(f"\nImports {len(deps['imports'])} modules:")
            for module in deps['imports'][:10]:
                response_parts.append(f"  - {module.get('name', 'Unknown')}")

        if deps.get('entities'):
            functions = [e for e in deps['entities'] if e.get('name')]
            response_parts.append(f"\nContains {len(functions)} functions/classes:")
            for entity in functions[:10]:
                response_parts.append(f"  - {entity.get('name', 'Unknown')}")

        if deps.get('dependent_files'):
            response_parts.append(f"\nDepends on {len(deps['dependent_files'])} other files:")
            for dep_file in deps['dependent_files'][:5]:
                response_parts.append(f"  - {dep_file.get('path', 'Unknown')}")

        return {
            'found': True,
            'answer': '\n'.join(response_parts),
            'file': file_info,
            'dependencies': deps
        }

    def find_similar_implementations(self, description: str) -> Dict[str, Any]:
        """Find similar implementations of a feature."""
        results = self.rag.compare_implementations(description, top_k=5)

        if not results['implementations']:
            return {
                'answer': f"I couldn't find any implementations matching '{description}'."
            }

        response_parts = [
            f"I found {len(results['implementations'])} similar implementations:\n"
        ]

        for i, impl in enumerate(results['implementations'], 1):
            response_parts.append(
                f"\n{i}. **{impl['name']}** in `{impl['file']}`"
            )
            response_parts.append(f"   Language: {impl['language']}")
            response_parts.append(f"   Lines of code: {impl['loc']}")
            response_parts.append(f"   Similarity: {impl['similarity']:.2%}")

        if results.get('insights'):
            insights = results['insights']
            response_parts.append(f"\n**Insights:**")
            response_parts.append(f"  Average lines: {insights.get('avg_lines', 0):.1f}")
            if insights.get('shortest'):
                response_parts.append(f"  Most concise: {insights['shortest']['name']} ({insights['shortest']['loc']} lines)")

        return {
            'answer': '\n'.join(response_parts),
            'implementations': results['implementations']
        }

    def get_conversation_history(self) -> List[Dict]:
        """Get the conversation history."""
        return self.conversation_history

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []

    def close(self):
        """Close the RAG system connections."""
        self.rag.close()
