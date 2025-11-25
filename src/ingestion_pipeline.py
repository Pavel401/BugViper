import os
from pathlib import Path
from typing import List, Optional, Dict
import pathspec

from .parsers.ast_parser import ASTParser
from .graph.neo4j_handler import Neo4jHandler
from .embeddings.embedding_handler import EmbeddingHandler


class CodeIngestionPipeline:
    """Pipeline to ingest code repository into Neo4j and Milvus."""

    def __init__(self, neo4j_handler: Neo4jHandler = None,
                 embedding_handler: EmbeddingHandler = None):
        self.ast_parser = ASTParser()
        self.neo4j = neo4j_handler or Neo4jHandler()
        self.embeddings = embedding_handler or EmbeddingHandler()

        # Store metadata for second pass relationship creation
        self.file_metadata = {}  # {file_path: {imports: [], function_calls: []}}
        self.function_index = {}  # {function_name: [node_ids]}
        self.class_index = {}  # {class_name: [node_ids]}

    def load_gitignore(self, repo_path: str) -> Optional[pathspec.PathSpec]:
        """Load .gitignore patterns if exists."""
        gitignore_path = os.path.join(repo_path, '.gitignore')
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                patterns = f.read().splitlines()
            return pathspec.PathSpec.from_lines('gitwildmatch', patterns)
        return None

    def should_ignore_file(self, file_path: str, gitignore_spec: Optional[pathspec.PathSpec]) -> bool:
        """Check if file should be ignored."""
        ignore_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv',
                       'dist', 'build', '.eggs', '*.egg-info'}

        for ignore_dir in ignore_dirs:
            if ignore_dir in file_path:
                return True

        if gitignore_spec and gitignore_spec.match_file(file_path):
            return True

        return False

    def get_repository_files(self, repo_path: str) -> List[str]:
        """Get all code files from repository."""
        supported_extensions = {'.py', '.js', '.ts', '.tsx', '.java', '.go'}
        files = []

        gitignore_spec = self.load_gitignore(repo_path)

        for root, dirs, filenames in os.walk(repo_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                      {'node_modules', '__pycache__', 'venv', '.venv', 'dist', 'build'}]

            for filename in filenames:
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, repo_path)

                if self.should_ignore_file(rel_path, gitignore_spec):
                    continue

                ext = os.path.splitext(filename)[1]
                if ext in supported_extensions:
                    files.append(file_path)

        return files

    def _parse_import_module(self, import_text: str, language: str) -> Optional[str]:
        """Extract module/file path from import statement."""
        try:
            if language == 'python':
                # Handle: from module import func, import module, from .relative import func
                if 'from' in import_text:
                    parts = import_text.split('from')[1].split('import')[0].strip()
                    # Convert relative imports like .module to module
                    parts = parts.lstrip('.')
                    return parts
                elif 'import' in import_text:
                    parts = import_text.split('import')[1].split('as')[0].strip()
                    return parts.split('.')[0]

            elif language in ['javascript', 'typescript', 'tsx']:
                # Handle: import {foo} from './module', import * from 'module'
                if 'from' in import_text:
                    module = import_text.split('from')[1].strip().strip("'\"").strip(';')
                    # Remove relative path indicators and extensions
                    module = module.lstrip('./').replace('.js', '').replace('.ts', '').replace('.tsx', '')
                    return module

            elif language == 'java':
                # Handle: import com.example.module;
                if 'import' in import_text:
                    module = import_text.split('import')[1].strip().rstrip(';').strip()
                    return module.split('.')[-1]  # Get the class name

            elif language == 'go':
                # Handle: import "module" or import ("module1" "module2")
                if '"' in import_text:
                    parts = import_text.split('"')
                    if len(parts) >= 2:
                        return parts[1].split('/')[-1]  # Get last part of path

        except Exception:
            pass

        return None

    def _extract_function_name(self, call_text: str) -> str:
        """Extract clean function name from call expression."""
        # Remove method chaining, get last part
        if '.' in call_text:
            return call_text.split('.')[-1]
        # Remove parentheses if present
        if '(' in call_text:
            return call_text.split('(')[0]
        return call_text

    def _create_import_relationships(self):
        """Create IMPORTS relationships between files."""
        print("\nCreating import relationships...")
        import_count = 0

        for file_path, metadata in self.file_metadata.items():
            for import_data in metadata['imports']:
                module_name = self._parse_import_module(import_data['text'], metadata['language'])
                if module_name:
                    self.neo4j.create_imports_relationship(file_path, module_name)
                    import_count += 1

        print(f"  Created {import_count} import relationships")
        return import_count

    def _create_function_call_relationships(self):
        """Create CALLS relationships between functions."""
        print("\nCreating function call relationships...")
        call_count = 0

        for file_path, metadata in self.file_metadata.items():
            # Get all functions in this file
            file_functions = [
                func_data for func_name, func_list in self.function_index.items()
                for func_data in func_list if func_data['file'] == file_path
            ]

            for call_data in metadata['function_calls']:
                called_func_name = self._extract_function_name(call_data['name'])

                # Find matching function definitions
                if called_func_name in self.function_index:
                    for target_func in self.function_index[called_func_name]:
                        # For each function in current file, create CALLS relationship
                        # We use a heuristic: function call at line X likely belongs to
                        # the function that contains that line
                        for caller_func in file_functions:
                            caller_id = caller_func['id']
                            callee_id = target_func['id']

                            # Avoid self-calls within same function
                            if caller_id != callee_id:
                                self.neo4j.create_calls_relationship(caller_id, callee_id)
                                call_count += 1

        print(f"  Created {call_count} function call relationships")
        return call_count

    def create_cross_file_relationships(self):
        """Second pass: Create all cross-file relationships."""
        print("\n" + "="*60)
        print("Creating Cross-File Relationships")
        print("="*60)

        stats = {
            'imports': self._create_import_relationships(),
            'calls': self._create_function_call_relationships()
        }

        print(f"\nRelationship creation complete!")
        print(f"  Total import relationships: {stats['imports']}")
        print(f"  Total call relationships: {stats['calls']}")

        return stats

    def ingest_file(self, file_path: str, repo_root: str) -> Dict[str, int]:
        """Ingest a single file into Neo4j and Milvus."""
        stats = {
            'functions': 0,
            'classes': 0,
            'code_blocks': 0,
            'embeddings': 0
        }

        try:
            with open(file_path, 'rb') as f:
                source_code = f.read()

            language = self.ast_parser.get_language_from_extension(file_path)
            if not language:
                print(f"  ⚠ Skipping: Unknown language for {os.path.relpath(file_path, repo_root)}")
                return stats

            tree = self.ast_parser.parse_file(file_path, source_code.decode('utf-8', errors='ignore'))
            if not tree:
                print(f"  ⚠ Skipping: Failed to parse {os.path.relpath(file_path, repo_root)}")
                return stats

            rel_path = os.path.relpath(file_path, repo_root)

            self.neo4j.create_file_node(rel_path, language)

            extraction_result = self.ast_parser.extract_code_chunks(rel_path, tree, source_code)
            code_chunks = extraction_result['chunks']
            imports = extraction_result['imports']
            function_calls = extraction_result['function_calls']

            # Store metadata for relationship creation
            self.file_metadata[rel_path] = {
                'imports': imports,
                'function_calls': function_calls,
                'language': language
            }

            for chunk in code_chunks:
                if chunk['type'] == 'function':
                    node_id = self.neo4j.create_function_node(rel_path, chunk)
                    stats['functions'] += 1

                    # Index function by name for cross-file references
                    func_name = chunk.get('name', '')
                    if func_name:
                        if func_name not in self.function_index:
                            self.function_index[func_name] = []
                        self.function_index[func_name].append({
                            'id': node_id,
                            'file': rel_path,
                            'name': func_name
                        })

                elif chunk['type'] == 'class':
                    node_id = self.neo4j.create_class_node(rel_path, chunk)
                    stats['classes'] += 1

                    # Index class by name for cross-file references
                    class_name = chunk.get('name', '')
                    if class_name:
                        if class_name not in self.class_index:
                            self.class_index[class_name] = []
                        self.class_index[class_name].append({
                            'id': node_id,
                            'file': rel_path,
                            'name': class_name
                        })

                elif chunk['type'] == 'code_block':
                    node_id = self.neo4j.create_code_block_node(rel_path, chunk)
                    stats['code_blocks'] += 1

            embedding_ids = self.embeddings.insert_batch(code_chunks)
            stats['embeddings'] = len(embedding_ids)

            print(f"✓ Ingested {rel_path}: {stats['functions']} functions, "
                  f"{stats['classes']} classes, {stats['embeddings']} embeddings")

        except Exception as e:
            print(f"✗ Error ingesting {file_path}: {e}")

        return stats

    def ingest_repository(self, repo_path: str, clear_existing: bool = False):
        """Ingest entire repository into Neo4j and Milvus."""
        if not os.path.exists(repo_path):
            raise ValueError(f"Repository path does not exist: {repo_path}")

        if clear_existing:
            print("Clearing existing data...")
            self.neo4j.clear_database()
            self.embeddings.clear_collection()

        print("Creating Neo4j schema...")
        self.neo4j.create_schema()

        print(f"Scanning repository: {repo_path}")
        files = self.get_repository_files(repo_path)
        print(f"Found {len(files)} code files to process")

        total_stats = {
            'files': 0,
            'functions': 0,
            'classes': 0,
            'code_blocks': 0,
            'embeddings': 0
        }

        for i, file_path in enumerate(files, 1):
            print(f"\n[{i}/{len(files)}] Processing {os.path.relpath(file_path, repo_path)}")
            stats = self.ingest_file(file_path, repo_path)

            total_stats['files'] += 1
            total_stats['functions'] += stats['functions']
            total_stats['classes'] += stats['classes']
            total_stats['code_blocks'] += stats['code_blocks']
            total_stats['embeddings'] += stats['embeddings']

        print("\n" + "="*60)
        print("Node Creation Complete!")
        print("="*60)
        print(f"Total files processed: {total_stats['files']}")
        print(f"Total functions: {total_stats['functions']}")
        print(f"Total classes: {total_stats['classes']}")
        print(f"Total code blocks: {total_stats['code_blocks']}")
        print(f"Total embeddings: {total_stats['embeddings']}")

        # Second pass: Create cross-file relationships
        relationship_stats = self.create_cross_file_relationships()
        total_stats['import_relationships'] = relationship_stats['imports']
        total_stats['call_relationships'] = relationship_stats['calls']

        print("\n" + "="*60)
        print("Ingestion Complete!")
        print("="*60)
        print(f"Total nodes: {total_stats['functions'] + total_stats['classes'] + total_stats['code_blocks']}")
        print(f"Total relationships: {relationship_stats['imports'] + relationship_stats['calls']}")

        return total_stats

    def close(self):
        """Close all connections."""
        self.neo4j.close()
        self.embeddings.close()
