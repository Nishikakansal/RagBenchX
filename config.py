# config.py - Central configuration for RAG BenchX

# Models
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
GROQ_MODEL = "qwen/qwen3.8-27b"

# Chunking
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
PARENT_CHUNK_SIZE = 900

# Evaluation
RETRIEVAL_K = 5
RERANKER_INITIAL_K = 20

# Sampling
MAX_WORDS = 50000
NUM_QUESTIONS = 15

# Reproducibility
RANDOM_SEED = 42
