# GraphRAG Architecture - Cross-File Relationships

## Overview

This code analysis system uses a **two-pass ingestion pipeline** to create a fully interconnected knowledge graph of your codebase, with proper cross-file relationships.

## Architecture Components

### 1. AST Parser (`src/parsers/ast_parser.py`)

**Purpose**: Extract code entities and their relationships from source files

**Key Features**:
- Parses Python, JavaScript, TypeScript, Java, and Go
- Extracts:
  - Function definitions
  - Class definitions
  - Import statements
  - Function calls (including cross-file calls)
- Returns structured data with relationship information

### 2. Ingestion Pipeline (`src/ingestion_pipeline.py`)

**Purpose**: Two-pass system to create nodes and relationships

#### Pass 1: Node Creation
- Creates File, Function, Class, and CodeBlock nodes
- Builds indexes of all functions and classes by name
- Stores import and function call metadata for each file

#### Pass 2: Relationship Creation
- **IMPORTS relationships**: File → Module
  - Links files to their imported modules
  - Parses import statements for all supported languages

- **CALLS relationships**: Function → Function
  - Links functions that call other functions
  - Works across file boundaries
  - Uses function name index to resolve references

- **USES relationships**: Entity → Entity
  - General-purpose dependency links
  - Can be extended for class inheritance, variable references, etc.

### 3. Neo4j Handler (`src/graph/neo4j_handler.py`)

**Purpose**: Graph database operations and queries

**Key Methods**:
- `create_calls_relationship()`: Link caller to callee functions
- `create_imports_relationship()`: Link file to imported module
- `create_uses_relationship()`: General dependency links
- `get_function_dependencies()`: Get what a function depends on
- `get_function_dependents()`: Get what depends on a function
- `get_file_dependencies()`: Get all dependencies for a file
- `get_cross_file_relationships_summary()`: Statistics on relationships

## Graph Schema

```
(File)-[:CONTAINS]->(Function)
(File)-[:CONTAINS]->(Class)
(File)-[:CONTAINS]->(CodeBlock)
(File)-[:IMPORTS]->(Module)

(Function)-[:CALLS]->(Function)
(Function)-[:USES]->(Function|Class)
(Class)-[:USES]->(Class)
```

## How Cross-File Relationships Work

### Import Tracking

When a file imports from another module:
```python
# file_a.py
from module_b import some_function
```

**Result**: `(file_a.py)-[:IMPORTS]->(module_b)`

### Function Call Tracking

When a function calls another function:
```python
# file_a.py
def caller():
    some_function()  # calls function from file_b.py
```

**Result**: `(file_a:caller)-[:CALLS]->(file_b:some_function)`

### Index-Based Resolution

The system maintains indexes during ingestion:
- `function_index`: Maps function names → list of node IDs
- `class_index`: Maps class names → list of node IDs

When a function call is detected, the system:
1. Extracts the called function name
2. Looks up all functions with that name in the index
3. Creates CALLS relationships to matching functions
4. Handles cross-file calls automatically

## Usage Examples

### Ingest a Repository with Relationships

```bash
python main.py ingest /path/to/your/repo
```

Output shows:
- Pass 1: Node creation statistics
- Pass 2: Relationship creation statistics

### View Graph Summary

```bash
python main.py summary
```

Shows:
- Total nodes (files, functions, classes)
- Total relationships (imports, calls, uses)

### Analyze Function Dependencies

```python
from src.graph.neo4j_handler import Neo4jHandler

neo4j = Neo4jHandler()

# What does this function depend on?
deps = neo4j.get_function_dependencies("my_function_id")
print(f"Calls: {deps['calls']}")
print(f"Imports: {deps['imports']}")

# What depends on this function?
dependents = neo4j.get_function_dependents("my_function_id")
print(f"Called by: {dependents['called_by']}")
```

### Query Cross-File Relationships in Neo4j

```cypher
// Find all functions that call functions in other files
MATCH (f1:File)-[:CONTAINS]->(fn1:Function)
MATCH (fn1)-[:CALLS]->(fn2:Function)
MATCH (f2:File)-[:CONTAINS]->(fn2)
WHERE f1.path <> f2.path
RETURN f1.path, fn1.name, f2.path, fn2.name

// Find files with the most dependencies
MATCH (f:File)-[:IMPORTS]->(m:Module)
RETURN f.path, count(m) as import_count
ORDER BY import_count DESC
LIMIT 10

// Find highly coupled functions (called by many others)
MATCH (caller:Function)-[:CALLS]->(callee:Function)
RETURN callee.name, count(caller) as caller_count
ORDER BY caller_count DESC
LIMIT 10
```

## Benefits of Interconnected Graph

1. **Impact Analysis**: See what breaks when you change a function
2. **Dependency Tracking**: Understand module coupling
3. **Code Navigation**: Follow call chains across files
4. **Refactoring Safety**: Identify all usages before changing APIs
5. **Architecture Insights**: Visualize system structure
6. **Technical Debt**: Find highly coupled or unused code

## Extending the System

### Add New Relationship Types

1. Add method to `Neo4jHandler`:
```python
def create_inherits_relationship(self, child_class_id: str, parent_class_id: str):
    query = """
    MATCH (child:Class {id: $child_id})
    MATCH (parent:Class {id: $parent_id})
    MERGE (child)-[:INHERITS]->(parent)
    """
    with self.driver.session() as session:
        session.run(query, {'child_id': child_class_id, 'parent_id': parent_class_id})
```

2. Add extraction logic in `ASTParser.extract_definitions()`

3. Add relationship creation in `CodeIngestionPipeline.create_cross_file_relationships()`

### Improve Function Call Resolution

Current implementation uses simple name matching. To improve:
- Track import aliases
- Resolve qualified names (module.function)
- Handle method calls on objects
- Parse type information for better accuracy

## Performance Considerations

- **First pass** is file-by-file (parallelizable)
- **Second pass** creates relationships in batch
- Indexes prevent N×N lookups
- Neo4j MERGE ensures no duplicate relationships
- Large repos: Consider chunking relationship creation

## Troubleshooting

### No relationships created?

Check:
1. Are imports/calls being extracted? Add debug prints in `extract_definitions()`
2. Are function names in the index? Print `function_index` after Pass 1
3. Neo4j connection working? Test with `summary` command

### Too many relationships?

The current implementation creates CALLS relationships somewhat liberally. Refine by:
- Tracking which function contains each call (line number ranges)
- Using scope analysis to determine actual caller
- Filtering by import relationships

### Wrong relationships?

Name-based matching can create false positives. Improve by:
- Using qualified names
- Checking file imports before creating cross-file CALLS
- Adding type information
