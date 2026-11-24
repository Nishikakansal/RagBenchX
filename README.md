# ⚡ RAG BenchX

**RAG BenchX** benchmarks 5 different Retrieval-Augmented Generation (RAG) techniques directly on **your uploaded document** (PDF, Markdown, or plain text) to determine which retrieval strategy performs best for that specific content.

Everything runs on free, lightweight models with an estimated benchmark runtime of **~60 seconds**.

---

## 🚀 Key Features

1. **Document Ingestion & Feature Detection**:
   - Parses PDF, TXT, and MD files.
   - Caps sample at 50,000 words spread evenly across the document.
   - Displays a doc-type badge (`technical`, `plain-text`, or `long-hierarchical`) based on length, heading depth, and code/table density.

2. **Synthetic Question Generation (Groq API)**:
   - Single batched API call returning ~15 paraphrased evaluation questions.
   - Questions are tied to specific chunk IDs distributed throughout the text.
   - Built-in exponential backoff retry and robust JSON schema parsing.

3. **5 Retrieval Techniques Compared**:
   - **Naive Vector Search**: Dense semantic search with `sentence-transformers/all-MiniLM-L6-v2` and FAISS / cosine similarity.
   - **BM25**: Probabilistic keyword retrieval using `rank_bm25`.
   - **Hybrid Search**: Fuses BM25 and Vector rankings via Reciprocal Rank Fusion (RRF, $k=60$).
   - **Vector + Cross-Encoder Reranker**: Dense vector search retrieves top 20 candidates, then reranked with `cross-encoder/ms-marco-MiniLM-L-6-v2` down to top-$k$.
   - **Parent-Document / Hierarchical**: Indexes 300-word child chunks for granular matching, returns 900-word parent passages for context.

4. **Transparent Evaluation & Metrics**:
   - **Hit Rate@k**: Fraction of queries where the true source passage was in the top-$k$.
   - **MRR (Mean Reciprocal Rank)**: Quality metric rewarding hits closer to rank 1.
   - **Recall@k**: Relevant passages retrieved over total relevant passages.
   - **Latency (ms)**: Query latency and index construction times.

5. **Interactive UI & Visualizations**:
   - Dark-mode Streamlit dashboard with responsive layout.
   - Interactive Plotly charts: Retrieval Quality (Hit Rate & MRR), Latency Breakdown, Quality vs. Speed Scatter.
   - Automatic winner recommendation with margin analysis and close-call warnings.

---

## 🛠️ Project Structure

```
d:/IMD_rag/
├── app.py                     # Streamlit web application
├── config.py                  # Models, chunk sizes, and benchmark parameters
├── ingestion.py               # Document parsing, chunking, and doc-type detection
├── question_generator.py      # Groq API question generation
├── evaluation.py              # Metric calculation (Hit Rate, MRR, latency)
├── viz.py                     # Plotly chart builders & recommendation engine
├── techniques/
│   ├── base.py                # Abstract retriever interface
│   ├── naive_vector.py        # Dense vector search
│   ├── bm25_retriever.py      # BM25 keyword search
│   ├── hybrid.py              # Reciprocal Rank Fusion (BM25 + Vector)
│   ├── reranker.py            # Vector + Cross-Encoder reranking
│   └── parent_document.py     # Child chunk search -> Parent chunk return
├── test_step1.py              # Ingestion & Naive Vector smoke test
├── test_step3.py              # Question generator unit & live API test
├── test_techniques.py         # Test suite for all 5 retrieval techniques
├── test_end_to_end.py         # Complete end-to-end pipeline test
├── requirements.txt           # Python dependencies
└── .env                       # API keys (GROQ_API_KEY)
```

---

## 📦 Getting Started

### 1. Prerequisites & Virtual Environment

Activate the virtual environment:
```powershell
.\venv\Scripts\Activate.ps1
```

### 2. Configure Environment Variables

Create `.env` (or copy from `.env.example`):
```env
GROQ_API_KEY=your_groq_api_key_here
```
Get a free Groq API key at [console.groq.com](https://console.groq.com).

### 3. Run the Streamlit App

```powershell
.\venv\Scripts\streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 🧪 Running Tests

- **Ingestion & Vector Smoke Test:**
  ```powershell
  .\venv\Scripts\python test_step1.py
  ```

- **Question Generator Test (Unit & Groq API):**
  ```powershell
  .\venv\Scripts\python test_step3.py
  ```

- **Techniques Verification Suite (all 5 techniques):**
  ```powershell
  .\venv\Scripts\python test_techniques.py
  ```

- **Full End-to-End Test:**
  ```powershell
  .\venv\Scripts\python test_end_to_end.py
  ```
