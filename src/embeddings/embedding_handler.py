from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from openai import OpenAI
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
import numpy as np

load_dotenv()


class EmbeddingHandler:
    """Handle embedding generation and storage in Milvus."""

    def __init__(self, collection_name: str = "code_embeddings",
                 host: str = None, port: str = None,
                 model_name: str = None):
        self.collection_name = collection_name
        self.host = host or os.getenv('MILVUS_HOST', 'localhost')
        self.port = port or os.getenv('MILVUS_PORT', '19530')
        self.model_name = model_name or os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')

        # Initialize embedding model (prefer local model for now)
        use_openai = os.getenv('USE_OPENAI_EMBEDDINGS', 'false').lower() == 'true'
        api_key = os.getenv('OPENAI_API_KEY')

        if use_openai and api_key and api_key != 'your_openai_api_key_here':
            print("Using OpenAI embeddings")
            self.use_local_model = False
            self.client = OpenAI(api_key=api_key)
        else:
            if not use_openai:
                print("Using local sentence-transformers for embeddings (set USE_OPENAI_EMBEDDINGS=true to use OpenAI)")
            else:
                print("Warning: OPENAI_API_KEY not set properly. Falling back to local sentence-transformers")
            self.use_local_model = True
            from sentence_transformers import SentenceTransformer
            self.local_model = SentenceTransformer('all-MiniLM-L6-v2')

        # Set embedding dimension based on model
        if self.use_local_model:
            self.embedding_dim = 384  # all-MiniLM-L6-v2 dimension
        elif 'text-embedding-3-large' in self.model_name:
            self.embedding_dim = 3072
        else:
            self.embedding_dim = 1536

        self.collection = None
        self._connect()

    def _connect(self):
        """Connect to Milvus and create/load collection."""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            print(f"Connected to Milvus at {self.host}:{self.port}")

            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                self.collection.load()
                print(f"Loaded existing collection: {self.collection_name}")
            else:
                self._create_collection()

        except Exception as e:
            print(f"Error connecting to Milvus: {e}")
            raise

    def _create_collection(self):
        """Create a new Milvus collection for multi-tenant code embeddings."""
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=512),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
            # Multi-tenancy fields
            FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="repo_id", dtype=DataType.VARCHAR, max_length=256),
            # Code metadata fields
            FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="code_type", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="language", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="start_line", dtype=DataType.INT64),
            FieldSchema(name="end_line", dtype=DataType.INT64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
        ]

        schema = CollectionSchema(fields=fields, description="Multi-tenant code embeddings for RAG")
        self.collection = Collection(name=self.collection_name, schema=schema)

        # Create index on embedding field for similarity search
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        self.collection.create_index(field_name="embedding", index_params=index_params)
        self.collection.load()
        print(f"Created new collection: {self.collection_name}")

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a piece of text using OpenAI API or local model."""
        if self.use_local_model:
            embedding = self.local_model.encode(text)
            return embedding.tolist()
        else:
            response = self.client.embeddings.create(
                input=text,
                model=self.model_name
            )
            return response.data[0].embedding

    def insert_code_chunk(self, chunk: Dict[str, Any], user_id: str, repo_id: str) -> str:
        """Insert a code chunk with its embedding into Milvus."""
        chunk_id = f"{repo_id}:{chunk['file']}:{chunk['type']}:{chunk['start_line']}"
        embedding = self.generate_embedding(chunk['content'])

        data = [{
            'id': chunk_id,
            'embedding': embedding,
            'user_id': user_id,
            'repo_id': repo_id,
            'file_path': chunk['file'],
            'code_type': chunk['type'],
            'name': chunk.get('name', ''),
            'language': chunk.get('language', ''),
            'start_line': chunk['start_line'],
            'end_line': chunk['end_line'],
            'content': chunk['content'][:65535]
        }]

        self.collection.insert(data)
        return chunk_id

    def insert_batch(self, chunks: List[Dict[str, Any]], user_id: str, repo_id: str) -> List[str]:
        """Insert multiple code chunks in batch for a specific user and repository."""
        if not chunks:
            return []

        chunk_ids = []
        data = {
            'id': [],
            'embedding': [],
            'user_id': [],
            'repo_id': [],
            'file_path': [],
            'code_type': [],
            'name': [],
            'language': [],
            'start_line': [],
            'end_line': [],
            'content': []
        }

        for chunk in chunks:
            chunk_id = f"{repo_id}:{chunk['file']}:{chunk['type']}:{chunk['start_line']}"
            chunk_ids.append(chunk_id)

            embedding = self.generate_embedding(chunk['content'])

            data['id'].append(chunk_id)
            data['embedding'].append(embedding)
            data['user_id'].append(user_id)
            data['repo_id'].append(repo_id)
            data['file_path'].append(chunk['file'])
            data['code_type'].append(chunk['type'])
            data['name'].append(chunk.get('name', ''))
            data['language'].append(chunk.get('language', ''))
            data['start_line'].append(chunk['start_line'])
            data['end_line'].append(chunk['end_line'])
            data['content'].append(chunk['content'][:65535])

        self.collection.insert(list(data.values()))
        self.collection.flush()
        return chunk_ids

    def search_similar_code(self, query: str, user_id: str = None, repo_id: str = None,
                           top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for similar code using semantic similarity with multi-tenant filtering."""
        query_embedding = self.generate_embedding(query)

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}

        # Build filter expression for multi-tenancy
        conditions = []
        if user_id:
            conditions.append(f'user_id == "{user_id}"')
        if repo_id:
            conditions.append(f'repo_id == "{repo_id}"')

        # Add additional filters
        if filters:
            if 'language' in filters:
                conditions.append(f'language == "{filters["language"]}"')
            if 'code_type' in filters:
                conditions.append(f'code_type == "{filters["code_type"]}"')
            if 'file_path' in filters:
                conditions.append(f'file_path like "%{filters["file_path"]}%"')

        expr = ' and '.join(conditions) if conditions else None

        results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["id", "user_id", "repo_id", "file_path", "code_type", "name",
                          "language", "start_line", "end_line", "content"]
        )

        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    'id': hit.entity.get('id'),
                    'user_id': hit.entity.get('user_id'),
                    'repo_id': hit.entity.get('repo_id'),
                    'file_path': hit.entity.get('file_path'),
                    'code_type': hit.entity.get('code_type'),
                    'name': hit.entity.get('name'),
                    'language': hit.entity.get('language'),
                    'start_line': hit.entity.get('start_line'),
                    'end_line': hit.entity.get('end_line'),
                    'content': hit.entity.get('content'),
                    'similarity': hit.score
                })

        return formatted_results

    def get_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a code chunk by ID."""
        results = self.collection.query(
            expr=f'id == "{chunk_id}"',
            output_fields=["id", "file_path", "code_type", "name", "language",
                          "start_line", "end_line", "content"]
        )

        if results:
            return results[0]
        return None

    def delete_by_file(self, file_path: str, repo_id: str = None):
        """Delete all embeddings for a specific file."""
        if repo_id:
            expr = f'file_path == "{file_path}" and repo_id == "{repo_id}"'
        else:
            expr = f'file_path == "{file_path}"'
        self.collection.delete(expr)
        self.collection.flush()

    def delete_by_repo(self, repo_id: str):
        """Delete all embeddings for a specific repository."""
        expr = f'repo_id == "{repo_id}"'
        self.collection.delete(expr)
        self.collection.flush()

    def clear_collection(self):
        """Clear all data from the collection."""
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
            self._create_collection()

    def close(self):
        """Close the connection to Milvus."""
        connections.disconnect("default")
