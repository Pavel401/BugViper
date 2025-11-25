# Code Review Tool with GraphRAG

A powerful code review and analysis tool that combines Abstract Syntax Tree (AST) parsing, graph databases, and semantic search using RAG (Retrieval-Augmented Generation).

## Features

- **AST Parsing**: Uses Tree-sitter to parse code from multiple languages (Python, JavaScript, TypeScript, Java, Go)
- **Graph Database**: Stores code structure and relationships in Neo4j
- **Semantic Search**: Leverages Milvus vector database for embedding-based code search
- **RAG System**: Retrieval-Augmented Generation for intelligent code review and analysis
- **Multi-language Support**: Handles Python, JavaScript, TypeScript, Java, and Go

## Architecture

```
┌─────────────────┐
│  Code Repository │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  Tree-sitter    │      │   Code Chunks    │
│  AST Parser     │─────▶│   Extraction     │
└─────────────────┘      └────────┬─────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
         ┌──────────────────┐        ┌──────────────────┐
         │     Neo4j        │        │     Milvus       │
         │  Graph Database  │        │  Vector Database │
         │  (Relationships) │        │   (Embeddings)   │
         └──────────────────┘        └──────────────────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   RAG System    │
                         │  Code Review    │
                         └─────────────────┘
```

## Prerequisites

1. **Python 3.8+**
2. **Neo4j Database**
   - Download: https://neo4j.com/download/
   - Or use Docker: `docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest`

3. **Milvus Vector Database**
   - Install via Docker Compose: https://milvus.io/docs/install_standalone-docker.md
   - Quick start:
     ```bash
     wget https://github.com/milvus-io/milvus/releases/download/v2.3.4/milvus-standalone-docker-compose.yml -O docker-compose.yml
     docker-compose up -d
     ```

## Installation

1. Clone the repository:
   ```bash
   git clone <your-repo-url>
   cd graphrag
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` with your credentials:
   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password

   MILVUS_HOST=localhost
   MILVUS_PORT=19530

   EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
   ```

## Usage

### 1. Ingest a Repository

Ingest a code repository into the graph and vector databases:

```bash
python main.py ingest /path/to/your/repository
```

With clear existing data:
```bash
python main.py ingest /path/to/your/repository --clear
```

### 2. Search for Code

Semantic search across your codebase:

```bash
python main.py search "authentication function"
```

With language filter:
```bash
python main.py search "parse JSON" --language python
```

Get more results:
```bash
python main.py search "database connection" -k 10
```

### 3. Review Code Snippet

Get similar patterns and suggestions for a code snippet:

```bash
python main.py review "def login(username, password):" --language python
```

### 4. Analyze Function Usage

Find where and how a function is used:

```bash
python main.py function login
```

### 5. Interactive Mode

Start an interactive session:

```bash
python main.py interactive
```

Commands in interactive mode:
- `search <query>` - Search for code
- `function <name>` - Analyze function usage
- `exit` - Exit interactive mode

## Project Structure

```
graphrag/
├── main.py                          # Main entry point
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variables template
├── README.md                        # This file
└── src/
    ├── parsers/
    │   └── ast_parser.py           # Tree-sitter AST parser
    ├── graph/
    │   └── neo4j_handler.py        # Neo4j database handler
    ├── embeddings/
    │   └── embedding_handler.py    # Milvus embeddings handler
    ├── rag/
    │   └── rag_system.py           # RAG query system
    └── ingestion_pipeline.py       # Code ingestion pipeline
```

## API Usage

You can also use the components programmatically:

```python
from ingestion_pipeline import CodeIngestionPipeline
from rag.rag_system import CodeRAGSystem

# Ingest a repository
pipeline = CodeIngestionPipeline()
stats = pipeline.ingest_repository('/path/to/repo')
pipeline.close()

# Query the codebase
rag = CodeRAGSystem()

# Semantic search
results = rag.semantic_search("authentication logic", top_k=5)

# Review code
review = rag.review_code_snippet(code_snippet, language='python')

# Analyze function
analysis = rag.analyze_function_usage('login')

# Compare implementations
comparison = rag.compare_implementations("sorting algorithm")

rag.close()
```

## Supported Languages

| Language   | Extension | Status |
|------------|-----------|--------|
| Python     | .py       | ✅     |
| JavaScript | .js       | ✅     |
| TypeScript | .ts, .tsx | ✅     |
| Java       | .java     | ✅     |
| Go         | .go       | ✅     |

## Use Cases

1. **Code Review**: Find similar code patterns and suggest improvements
2. **Code Search**: Semantic search for functionality across your codebase
3. **Duplication Detection**: Identify similar implementations
4. **Impact Analysis**: Understand function usage and dependencies
5. **Code Navigation**: Explore relationships between code elements
6. **Pattern Discovery**: Find common patterns and best practices

## Advanced Configuration

### Custom Embedding Model

You can use different embedding models by changing the `EMBEDDING_MODEL` in `.env`:

```env
# Smaller, faster model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Larger, more accurate model
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2

# Code-specific model
EMBEDDING_MODEL=microsoft/codebert-base
```

### Neo4j Queries

You can extend the Neo4j handler with custom queries:

```python
from graph.neo4j_handler import Neo4jHandler

neo4j = Neo4jHandler()

# Custom query
query = """
MATCH (f:Function)-[:CALLS]->(called:Function)
WHERE f.name = $function_name
RETURN called.name as called_function, called.file as file
"""

with neo4j.driver.session() as session:
    results = session.run(query, {'function_name': 'login'})
```

## Troubleshooting

### Neo4j Connection Error
- Ensure Neo4j is running: `docker ps` or check Neo4j Desktop
- Verify credentials in `.env`
- Test connection: `http://localhost:7474`

### Milvus Connection Error
- Check Milvus is running: `docker ps`
- Verify port 19530 is accessible
- Restart Milvus: `docker-compose restart`

### Tree-sitter Language Errors
- Ensure all tree-sitter language packages are installed
- Try reinstalling: `pip install --upgrade tree-sitter-python tree-sitter-javascript`

### Memory Issues
- Process large repositories in batches
- Increase Docker memory limits
- Use a more efficient embedding model

## Performance Tips

1. **Batch Processing**: The ingestion pipeline processes files in batches
2. **Indexing**: Neo4j indexes are created automatically for faster queries
3. **Vector Search**: Milvus IVF_FLAT index provides good balance of speed and accuracy
4. **Caching**: Consider caching frequently accessed embeddings

## Contributing

Contributions are welcome! Areas for improvement:

- Add more programming languages
- Implement call graph analysis
- Add code complexity metrics
- Create web UI for visualization
- Add LLM integration for code review suggestions

## License

MIT License - feel free to use and modify for your needs.

## Acknowledgments

- [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) for AST parsing
- [Neo4j](https://neo4j.com/) for graph database
- [Milvus](https://milvus.io/) for vector database
- [Sentence Transformers](https://www.sbert.net/) for embeddings
