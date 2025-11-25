import tree_sitter
from tree_sitter import Parser, Language
import os
from pathlib import Path
from typing import Dict, List, Optional, Any


class ASTParser:
    """Parse source code using tree-sitter to extract AST nodes and relationships."""

    def __init__(self):
        self.parsers = {}
        self.languages = {}
        self._setup_languages()

    def _setup_languages(self):
        """Initialize tree-sitter parsers for supported languages."""
        try:
            import tree_sitter_python
            import tree_sitter_javascript
            import tree_sitter_typescript
            import tree_sitter_java
            import tree_sitter_go

            # Wrap language capsules with Language class
            self.languages = {
                'python': Language(tree_sitter_python.language()),
                'javascript': Language(tree_sitter_javascript.language()),
                'typescript': Language(tree_sitter_typescript.language_typescript()),
                'tsx': Language(tree_sitter_typescript.language_tsx()),
                'java': Language(tree_sitter_java.language()),
                'go': Language(tree_sitter_go.language()),
            }

            for lang_name, language in self.languages.items():
                parser = Parser(language)
                self.parsers[lang_name] = parser

        except Exception as e:
            print(f"Error setting up languages: {e}")

    def get_language_from_extension(self, file_path: str) -> Optional[str]:
        """Determine language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'tsx',
            '.java': 'java',
            '.go': 'go',
        }
        ext = Path(file_path).suffix
        return ext_map.get(ext)

    def parse_file(self, file_path: str, content: Optional[str] = None) -> Optional[tree_sitter.Tree]:
        """Parse a file and return its AST."""
        language = self.get_language_from_extension(file_path)
        if not language:
            print(f"Warning: Unknown file extension for {file_path}")
            return None

        if language not in self.parsers:
            print(f"Warning: No parser available for language '{language}'. Available languages: {list(self.parsers.keys())}")
            return None

        if content is None:
            with open(file_path, 'rb') as f:
                content = f.read()
        else:
            content = content.encode('utf-8')

        parser = self.parsers[language]
        tree = parser.parse(content)
        return tree

    def extract_nodes(self, tree: tree_sitter.Tree, source_code: bytes) -> List[Dict[str, Any]]:
        """Extract relevant nodes from AST for graph database."""
        nodes = []

        def traverse(node: tree_sitter.Node, parent_id: Optional[str] = None):
            node_id = f"{node.type}_{node.start_point[0]}_{node.start_point[1]}"

            node_info = {
                'id': node_id,
                'type': node.type,
                'start_line': node.start_point[0],
                'start_col': node.start_point[1],
                'end_line': node.end_point[0],
                'end_col': node.end_point[1],
                'text': source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore'),
                'parent_id': parent_id,
                'children': []
            }

            if node.is_named:
                nodes.append(node_info)

                for child in node.children:
                    if child.is_named:
                        traverse(child, node_id)

        traverse(tree.root_node)
        return nodes

    def extract_definitions(self, tree: tree_sitter.Tree, source_code: bytes, language: str) -> Dict[str, List[Dict]]:
        """Extract function, class, and variable definitions by traversing AST."""
        definitions = {
            'functions': [],
            'classes': [],
            'variables': [],
            'imports': []
        }

        def traverse(node: tree_sitter.Node):
            """Recursively traverse the AST to find definitions."""
            if language == 'python':
                if node.type == 'function_definition':
                    # Find the function name
                    name_node = None
                    for child in node.children:
                        if child.type == 'identifier':
                            name_node = child
                            break

                    if name_node:
                        definitions['functions'].append({
                            'name': source_code[name_node.start_byte:name_node.end_byte].decode('utf-8', errors='ignore'),
                            'start_line': node.start_point[0],
                            'end_line': node.end_point[0],
                            'text': source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                        })

                elif node.type == 'class_definition':
                    # Find the class name
                    name_node = None
                    for child in node.children:
                        if child.type == 'identifier':
                            name_node = child
                            break

                    if name_node:
                        definitions['classes'].append({
                            'name': source_code[name_node.start_byte:name_node.end_byte].decode('utf-8', errors='ignore'),
                            'start_line': node.start_point[0],
                            'end_line': node.end_point[0],
                            'text': source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                        })

            elif language in ['javascript', 'typescript', 'tsx']:
                if node.type in ['function_declaration', 'method_definition']:
                    name_node = None
                    for child in node.children:
                        if child.type in ['identifier', 'property_identifier']:
                            name_node = child
                            break

                    if name_node:
                        definitions['functions'].append({
                            'name': source_code[name_node.start_byte:name_node.end_byte].decode('utf-8', errors='ignore'),
                            'start_line': node.start_point[0],
                            'end_line': node.end_point[0],
                            'text': source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                        })

                elif node.type == 'class_declaration':
                    name_node = None
                    for child in node.children:
                        if child.type == 'type_identifier':
                            name_node = child
                            break

                    if name_node:
                        definitions['classes'].append({
                            'name': source_code[name_node.start_byte:name_node.end_byte].decode('utf-8', errors='ignore'),
                            'start_line': node.start_point[0],
                            'end_line': node.end_point[0],
                            'text': source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                        })

            elif language == 'java':
                if node.type == 'method_declaration':
                    name_node = None
                    for child in node.children:
                        if child.type == 'identifier':
                            name_node = child
                            break

                    if name_node:
                        definitions['functions'].append({
                            'name': source_code[name_node.start_byte:name_node.end_byte].decode('utf-8', errors='ignore'),
                            'start_line': node.start_point[0],
                            'end_line': node.end_point[0],
                            'text': source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                        })

                elif node.type == 'class_declaration':
                    name_node = None
                    for child in node.children:
                        if child.type == 'identifier':
                            name_node = child
                            break

                    if name_node:
                        definitions['classes'].append({
                            'name': source_code[name_node.start_byte:name_node.end_byte].decode('utf-8', errors='ignore'),
                            'start_line': node.start_point[0],
                            'end_line': node.end_point[0],
                            'text': source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                        })

            elif language == 'go':
                if node.type == 'function_declaration':
                    name_node = None
                    for child in node.children:
                        if child.type == 'identifier':
                            name_node = child
                            break

                    if name_node:
                        definitions['functions'].append({
                            'name': source_code[name_node.start_byte:name_node.end_byte].decode('utf-8', errors='ignore'),
                            'start_line': node.start_point[0],
                            'end_line': node.end_point[0],
                            'text': source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                        })

            # Recursively traverse children
            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        return definitions

    def _get_queries_for_language(self, language: str) -> Dict[str, str]:
        """Get tree-sitter queries for extracting definitions by language."""
        queries = {}

        if language == 'python':
            queries = {
                'functions': '(function_definition name: (identifier) @function.name)',
                'classes': '(class_definition name: (identifier) @class.name)',
                'imports': '(import_statement) @import',
            }
        elif language in ['javascript', 'typescript', 'tsx']:
            queries = {
                'functions': '''
                    [
                        (function_declaration name: (identifier) @function.name)
                        (method_definition name: (property_identifier) @function.name)
                        (arrow_function) @function
                    ]
                ''',
                'classes': '(class_declaration name: (type_identifier) @class.name)',
                'imports': '(import_statement) @import',
            }
        elif language == 'java':
            queries = {
                'functions': '(method_declaration name: (identifier) @function.name)',
                'classes': '(class_declaration name: (identifier) @class.name)',
                'imports': '(import_declaration) @import',
            }
        elif language == 'go':
            queries = {
                'functions': '(function_declaration name: (identifier) @function.name)',
                'imports': '(import_declaration) @import',
            }

        return queries

    def extract_code_chunks(self, file_path: str, tree: tree_sitter.Tree, source_code: bytes,
                           chunk_size: int = 500) -> List[Dict[str, Any]]:
        """Extract code chunks for embedding generation."""
        chunks = []
        language = self.get_language_from_extension(file_path)

        definitions = self.extract_definitions(tree, source_code, language)

        for func in definitions['functions']:
            chunks.append({
                'type': 'function',
                'name': func.get('name', ''),
                'file': file_path,
                'start_line': func['start_line'],
                'end_line': func['end_line'],
                'content': func['text'],
                'language': language
            })

        for cls in definitions['classes']:
            chunks.append({
                'type': 'class',
                'name': cls.get('name', ''),
                'file': file_path,
                'start_line': cls['start_line'],
                'end_line': cls['end_line'],
                'content': cls['text'],
                'language': language
            })

        lines = source_code.decode('utf-8', errors='ignore').split('\n')
        covered_lines = set()
        for chunk in chunks:
            for line in range(chunk['start_line'], chunk['end_line'] + 1):
                covered_lines.add(line)

        current_chunk = []
        chunk_start = 0
        for i, line in enumerate(lines):
            if i not in covered_lines:
                if not current_chunk:
                    chunk_start = i
                current_chunk.append(line)

                if len('\n'.join(current_chunk)) >= chunk_size:
                    chunks.append({
                        'type': 'code_block',
                        'name': f'block_{chunk_start}',
                        'file': file_path,
                        'start_line': chunk_start,
                        'end_line': i,
                        'content': '\n'.join(current_chunk),
                        'language': language
                    })
                    current_chunk = []
            else:
                if current_chunk:
                    chunks.append({
                        'type': 'code_block',
                        'name': f'block_{chunk_start}',
                        'file': file_path,
                        'start_line': chunk_start,
                        'end_line': i - 1,
                        'content': '\n'.join(current_chunk),
                        'language': language
                    })
                    current_chunk = []

        if current_chunk:
            chunks.append({
                'type': 'code_block',
                'name': f'block_{chunk_start}',
                'file': file_path,
                'start_line': chunk_start,
                'end_line': len(lines) - 1,
                'content': '\n'.join(current_chunk),
                'language': language
            })

        return chunks
