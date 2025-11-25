from neo4j import GraphDatabase
from typing import Dict, List, Any, Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Neo4jHandler:
    """Handle Neo4j graph database operations for code repository."""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.user = user or os.getenv('NEO4J_USER', 'neo4j')
        self.password = password or os.getenv('NEO4J_PASSWORD', 'password')
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()

    def create_schema(self):
        """Create schema constraints and indexes for the code graph."""
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT file_path IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE")
            session.run("CREATE CONSTRAINT function_id IF NOT EXISTS FOR (fn:Function) REQUIRE fn.id IS UNIQUE")
            session.run("CREATE CONSTRAINT class_id IF NOT EXISTS FOR (c:Class) REQUIRE c.id IS UNIQUE")
            session.run("CREATE INDEX file_name IF NOT EXISTS FOR (f:File) ON (f.name)")
            session.run("CREATE INDEX function_name IF NOT EXISTS FOR (fn:Function) ON (fn.name)")
            session.run("CREATE INDEX class_name IF NOT EXISTS FOR (c:Class) ON (c.name)")

    def clear_database(self):
        """Clear all nodes and relationships from the database."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def create_file_node(self, file_path: str, language: str, metadata: Dict = None) -> str:
        """Create a File node in the graph."""
        query = """
        MERGE (f:File {path: $path})
        SET f.language = $language,
            f.name = $name,
            f.extension = $extension
        RETURN f.path as path
        """
        with self.driver.session() as session:
            result = session.run(query, {
                'path': file_path,
                'language': language,
                'name': os.path.basename(file_path),
                'extension': os.path.splitext(file_path)[1]
            })
            record = result.single()
            return record['path'] if record else None

    def create_function_node(self, file_path: str, function_data: Dict) -> str:
        """Create a Function node and link it to a File."""
        query = """
        MATCH (f:File {path: $file_path})
        MERGE (fn:Function {id: $function_id})
        SET fn.name = $name,
            fn.start_line = $start_line,
            fn.end_line = $end_line,
            fn.content = $content,
            fn.language = $language
        MERGE (f)-[:CONTAINS]->(fn)
        RETURN fn.id as id
        """
        function_id = f"{file_path}:{function_data.get('name', 'unknown')}:{function_data['start_line']}"

        with self.driver.session() as session:
            result = session.run(query, {
                'file_path': file_path,
                'function_id': function_id,
                'name': function_data.get('name', ''),
                'start_line': function_data['start_line'],
                'end_line': function_data['end_line'],
                'content': function_data['content'],
                'language': function_data.get('language', '')
            })
            record = result.single()
            return record['id'] if record else None

    def create_class_node(self, file_path: str, class_data: Dict) -> str:
        """Create a Class node and link it to a File."""
        query = """
        MATCH (f:File {path: $file_path})
        MERGE (c:Class {id: $class_id})
        SET c.name = $name,
            c.start_line = $start_line,
            c.end_line = $end_line,
            c.content = $content,
            c.language = $language
        MERGE (f)-[:CONTAINS]->(c)
        RETURN c.id as id
        """
        class_id = f"{file_path}:{class_data.get('name', 'unknown')}:{class_data['start_line']}"

        with self.driver.session() as session:
            result = session.run(query, {
                'file_path': file_path,
                'class_id': class_id,
                'name': class_data.get('name', ''),
                'start_line': class_data['start_line'],
                'end_line': class_data['end_line'],
                'content': class_data['content'],
                'language': class_data.get('language', '')
            })
            record = result.single()
            return record['id'] if record else None

    def create_code_block_node(self, file_path: str, block_data: Dict) -> str:
        """Create a CodeBlock node for general code chunks."""
        query = """
        MATCH (f:File {path: $file_path})
        MERGE (cb:CodeBlock {id: $block_id})
        SET cb.name = $name,
            cb.start_line = $start_line,
            cb.end_line = $end_line,
            cb.content = $content,
            cb.language = $language,
            cb.type = $type
        MERGE (f)-[:CONTAINS]->(cb)
        RETURN cb.id as id
        """
        block_id = f"{file_path}:block:{block_data['start_line']}"

        with self.driver.session() as session:
            result = session.run(query, {
                'file_path': file_path,
                'block_id': block_id,
                'name': block_data.get('name', ''),
                'start_line': block_data['start_line'],
                'end_line': block_data['end_line'],
                'content': block_data['content'],
                'language': block_data.get('language', ''),
                'type': block_data.get('type', 'code_block')
            })
            record = result.single()
            return record['id'] if record else None

    def create_calls_relationship(self, caller_id: str, callee_id: str):
        """Create a CALLS relationship between functions."""
        query = """
        MATCH (caller:Function {id: $caller_id})
        MATCH (callee:Function {id: $callee_id})
        MERGE (caller)-[:CALLS]->(callee)
        """
        with self.driver.session() as session:
            session.run(query, {'caller_id': caller_id, 'callee_id': callee_id})

    def create_imports_relationship(self, file_path: str, imported_module: str):
        """Create an IMPORTS relationship between files."""
        query = """
        MATCH (f:File {path: $file_path})
        MERGE (m:Module {name: $module_name})
        MERGE (f)-[:IMPORTS]->(m)
        """
        with self.driver.session() as session:
            session.run(query, {'file_path': file_path, 'module_name': imported_module})

    def link_embedding(self, node_id: str, embedding_id: str, node_type: str = 'Function'):
        """Link a code node to its embedding in Milvus."""
        query = f"""
        MATCH (n:{node_type} {{id: $node_id}})
        SET n.embedding_id = $embedding_id
        """
        with self.driver.session() as session:
            session.run(query, {'node_id': node_id, 'embedding_id': embedding_id})

    def query_related_code(self, node_id: str, depth: int = 2) -> List[Dict]:
        """Query related code nodes up to a certain depth."""
        query = """
        MATCH path = (n {id: $node_id})-[*1..%d]-(related)
        RETURN related, relationships(path) as rels, length(path) as depth
        ORDER BY depth
        """ % depth

        with self.driver.session() as session:
            result = session.run(query, {'node_id': node_id})
            return [dict(record) for record in result]

    def get_file_structure(self, file_path: str) -> Dict:
        """Get the complete structure of a file."""
        query = """
        MATCH (f:File {path: $file_path})
        OPTIONAL MATCH (f)-[:CONTAINS]->(element)
        RETURN f, collect(element) as elements
        """
        with self.driver.session() as session:
            result = session.run(query, {'file_path': file_path})
            record = result.single()
            if record:
                return {
                    'file': dict(record['f']),
                    'elements': [dict(el) for el in record['elements']]
                }
            return {}

    def find_functions_by_name(self, name: str) -> List[Dict]:
        """Find all functions matching a name pattern."""
        query = """
        MATCH (fn:Function)
        WHERE fn.name CONTAINS $name
        RETURN fn
        """
        with self.driver.session() as session:
            result = session.run(query, {'name': name})
            return [dict(record['fn']) for record in result]

    def find_classes_by_name(self, name: str) -> List[Dict]:
        """Find all classes matching a name pattern."""
        query = """
        MATCH (c:Class)
        WHERE c.name CONTAINS $name
        RETURN c
        """
        with self.driver.session() as session:
            result = session.run(query, {'name': name})
            return [dict(record['c']) for record in result]

    def create_uses_relationship(self, source_id: str, target_id: str, source_type: str = 'Function', target_type: str = 'Function'):
        """Create a USES relationship between code entities."""
        query = f"""
        MATCH (source:{source_type} {{id: $source_id}})
        MATCH (target:{target_type} {{id: $target_id}})
        MERGE (source)-[:USES]->(target)
        """
        with self.driver.session() as session:
            session.run(query, {'source_id': source_id, 'target_id': target_id})

    def get_function_dependencies(self, function_id: str) -> Dict[str, Any]:
        """Get all dependencies for a function (what it calls, imports, etc)."""
        query = """
        MATCH (fn:Function {id: $function_id})
        OPTIONAL MATCH (fn)-[:CALLS]->(called:Function)
        OPTIONAL MATCH (fn)-[:USES]->(used)
        OPTIONAL MATCH (file:File)-[:CONTAINS]->(fn)
        OPTIONAL MATCH (file)-[:IMPORTS]->(module:Module)
        RETURN fn,
               collect(DISTINCT called) as called_functions,
               collect(DISTINCT used) as used_entities,
               collect(DISTINCT module) as imported_modules,
               file
        """
        with self.driver.session() as session:
            result = session.run(query, {'function_id': function_id})
            record = result.single()
            if record:
                return {
                    'function': dict(record['fn']),
                    'file': dict(record['file']) if record['file'] else None,
                    'calls': [dict(f) for f in record['called_functions'] if f],
                    'uses': [dict(u) for u in record['used_entities'] if u],
                    'imports': [dict(m) for m in record['imported_modules'] if m]
                }
            return {}

    def get_function_dependents(self, function_id: str) -> Dict[str, Any]:
        """Get all code that depends on this function (what calls it, etc)."""
        query = """
        MATCH (fn:Function {id: $function_id})
        OPTIONAL MATCH (caller:Function)-[:CALLS]->(fn)
        OPTIONAL MATCH (user)-[:USES]->(fn)
        RETURN fn,
               collect(DISTINCT caller) as calling_functions,
               collect(DISTINCT user) as using_entities
        """
        with self.driver.session() as session:
            result = session.run(query, {'function_id': function_id})
            record = result.single()
            if record:
                return {
                    'function': dict(record['fn']),
                    'called_by': [dict(f) for f in record['calling_functions'] if f],
                    'used_by': [dict(u) for u in record['using_entities'] if u]
                }
            return {}

    def get_file_dependencies(self, file_path: str) -> Dict[str, Any]:
        """Get all dependencies for a file."""
        query = """
        MATCH (f:File {path: $file_path})
        OPTIONAL MATCH (f)-[:IMPORTS]->(module:Module)
        OPTIONAL MATCH (f)-[:CONTAINS]->(entity)
        OPTIONAL MATCH (entity)-[:CALLS|USES]->(external)
        OPTIONAL MATCH (external_file:File)-[:CONTAINS]->(external)
        WHERE external_file.path <> f.path
        RETURN f,
               collect(DISTINCT module) as imported_modules,
               collect(DISTINCT entity) as internal_entities,
               collect(DISTINCT external) as external_dependencies,
               collect(DISTINCT external_file) as dependent_files
        """
        with self.driver.session() as session:
            result = session.run(query, {'file_path': file_path})
            record = result.single()
            if record:
                return {
                    'file': dict(record['f']),
                    'imports': [dict(m) for m in record['imported_modules'] if m],
                    'entities': [dict(e) for e in record['internal_entities'] if e],
                    'external_deps': [dict(e) for e in record['external_dependencies'] if e],
                    'dependent_files': [dict(f) for f in record['dependent_files'] if f]
                }
            return {}

    def get_cross_file_relationships_summary(self) -> Dict[str, int]:
        """Get a summary of all cross-file relationships."""
        queries = {
            'total_files': "MATCH (f:File) RETURN count(f) as count",
            'total_functions': "MATCH (fn:Function) RETURN count(fn) as count",
            'total_classes': "MATCH (c:Class) RETURN count(c) as count",
            'import_relationships': "MATCH ()-[r:IMPORTS]->() RETURN count(r) as count",
            'call_relationships': "MATCH ()-[r:CALLS]->() RETURN count(r) as count",
            'uses_relationships': "MATCH ()-[r:USES]->() RETURN count(r) as count",
        }

        summary = {}
        with self.driver.session() as session:
            for key, query in queries.items():
                result = session.run(query)
                record = result.single()
                summary[key] = record['count'] if record else 0

        return summary
