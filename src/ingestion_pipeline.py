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

            code_chunks = self.ast_parser.extract_code_chunks(rel_path, tree, source_code)

            for chunk in code_chunks:
                if chunk['type'] == 'function':
                    node_id = self.neo4j.create_function_node(rel_path, chunk)
                    stats['functions'] += 1
                elif chunk['type'] == 'class':
                    node_id = self.neo4j.create_class_node(rel_path, chunk)
                    stats['classes'] += 1
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
        print("Ingestion Complete!")
        print("="*60)
        print(f"Total files processed: {total_stats['files']}")
        print(f"Total functions: {total_stats['functions']}")
        print(f"Total classes: {total_stats['classes']}")
        print(f"Total code blocks: {total_stats['code_blocks']}")
        print(f"Total embeddings: {total_stats['embeddings']}")

        return total_stats

    def close(self):
        """Close all connections."""
        self.neo4j.close()
        self.embeddings.close()
