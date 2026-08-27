# 🎬 YouTube RAG Chatbot

An industry-grade **Retrieval-Augmented Generation (RAG)** chatbot that answers questions exclusively from YouTube video transcripts — with timestamped citations and clickable jump links.

---

## 🏗️ Architecture

```
YouTube URL → Transcript API → Document + Timestamps
    → Text Chunking → NVIDIA llama-nemotron-embed-1b-v2
    → Pinecone Serverless → Semantic Retrieval
    → Groq Qwen-2.5-32B → Answer + YouTube Jump Link
```

---

## ✨ Features

- 📝 **Transcript extraction** with per-segment timestamp metadata
- ✂️ **Smart chunking** with overlap — preserves context across splits
- 🧠 **NVIDIA embeddings** — `llama-nemotron-embed-1b-v2` (2048-dim, MRL)
- 🌲 **Pinecone Serverless** — scalable vector database with video-scoped filtering
- ⚡ **Groq Qwen-2.5-32B** — ultra-fast LLM inference
- 🔗 **Timestamp jump links** — click to jump to the exact moment in the video
- 🚫 **No hallucinations** — strict grounding prompt; falls back gracefully
- ♻️ **Smart caching** — skips re-indexing if the same video was already loaded

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10+
- API keys for: **NVIDIA NIM**, **Pinecone**, **Groq**

### 2. Clone & Setup

```bash
# Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\activate          # Windows
# source venv/bin/activate       # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure API Keys

```bash
# Copy the template
copy .env.example .env           # Windows
# cp .env.example .env           # macOS / Linux

# Edit .env and fill in your actual keys:
#   NVIDIA_API_KEY  → https://build.nvidia.com
#   PINECONE_API_KEY → https://app.pinecone.io
#   GROQ_API_KEY     → https://console.groq.com
```

### 4. Run

```bash
streamlit run app.py
```

Open your browser at **http://localhost:8501**

---

## 📁 Project Structure

```
youtube-rag/
├── .env.example            # API key template
├── .gitignore
├── requirements.txt
├── app.py                  # Streamlit UI (entry point)
├── config/
│   └── settings.py         # Pydantic-Settings config
├── core/
│   ├── transcript_loader.py  # Custom YouTube transcript loader
│   ├── chunker.py            # RecursiveCharacterTextSplitter pipeline
│   ├── embeddings.py         # NVIDIA NIM embedding singleton
│   ├── vector_store.py       # Pinecone index management
│   ├── retriever.py          # Video-scoped semantic retriever
│   └── rag_chain.py          # LCEL RAG chain
└── utils/
    ├── url_parser.py          # YouTube URL → video_id
    └── timestamp_formatter.py # seconds → MM:SS + jump link
```

---

## 🔑 Required API Keys

| Service | URL | Free Tier |
|---------|-----|-----------|
| NVIDIA NIM | https://build.nvidia.com | ✅ Free credits |
| Pinecone | https://app.pinecone.io | ✅ Serverless free tier |
| Groq | https://console.groq.com | ✅ Free tier |

---

## ⚙️ Configuration

All settings are in `.env`. Key parameters:

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_MODEL` | `nvidia/llama-nemotron-embed-1b-v2` | NVIDIA NIM embedding model |
| `EMBEDDING_DIM` | `2048` | Vector dimensions |
| `LLM_MODEL` | `qwen-2.5-32b` | Groq LLM model |
| `CHUNK_SIZE` | `500` | Characters per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `TOP_K` | `5` | Retrieved chunks per query |

---

## 🧑‍💻 Tech Stack

- **LangChain** — LCEL chains, document loaders, text splitters
- **NVIDIA NIM** — `llama-nemotron-embed-1b-v2` embeddings
- **Pinecone** — Serverless vector database
- **Groq** — `qwen-2.5-32b` LLM inference
- **Streamlit** — Chat UI
- **youtube-transcript-api** — Transcript fetching
- **pytubefix** — Video metadata
- **Pydantic-Settings** — Config management
