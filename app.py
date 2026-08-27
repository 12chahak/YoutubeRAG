"""
app.py
──────
YouTube RAG Chatbot — Streamlit Application

Entry point. Run with:
    streamlit run app.py
"""

from __future__ import annotations

import logging
import sys
import time

import streamlit as st

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ── Page config (MUST be the first Streamlit call) ───────────────────────────
st.set_page_config(
    page_title="YouTube RAG Chatbot",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Root variables ── */
:root {
    --bg-primary:       #0f0f1a;
    --bg-secondary:     #1a1a2e;
    --bg-card:          rgba(255,255,255,0.04);
    --border:           rgba(255,255,255,0.08);
    --accent-primary:   #7c3aed;
    --accent-secondary: #06b6d4;
    --accent-gradient:  linear-gradient(135deg, #7c3aed 0%, #06b6d4 100%);
    --text-primary:     #f1f5f9;
    --text-secondary:   #94a3b8;
    --text-muted:       #64748b;
    --success:          #10b981;
    --warning:          #f59e0b;
    --error:            #ef4444;
    --radius-sm:        8px;
    --radius-md:        12px;
    --radius-lg:        16px;
    --shadow-glow:      0 0 30px rgba(124,58,237,0.15);
}

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-primary);
}

/* ── Hide default Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── App background ── */
.stApp {
    background: radial-gradient(ellipse at top left, #1a0a3e 0%, #0f0f1a 50%, #001a2e 100%);
    min-height: 100vh;
}

/* ── Main container ── */
.main .block-container {
    padding: 1.5rem 2rem 4rem 2rem;
    max-width: 900px;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] .block-container {
    padding: 1.5rem 1.2rem;
}

/* ── Page header ── */
.rag-header {
    text-align: center;
    padding: 1.5rem 0 1rem;
    margin-bottom: 0.5rem;
}
.rag-header h1 {
    font-size: 2.4rem;
    font-weight: 700;
    background: var(--accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.3rem;
    line-height: 1.2;
}
.rag-header p {
    color: var(--text-secondary);
    font-size: 0.95rem;
    margin: 0;
}

/* ── Sidebar section headers ── */
.sidebar-section {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin: 1.2rem 0 0.5rem;
}

/* ── Video info card ── */
.video-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 0.9rem 1rem;
    margin: 0.8rem 0;
    backdrop-filter: blur(10px);
    transition: border-color 0.3s;
}
.video-card:hover { border-color: rgba(124,58,237,0.4); }
.video-card .label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.25rem;
}
.video-card .value {
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-primary);
    word-break: break-word;
}

/* ── Status badges ── */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.3rem 0.75rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
}
.badge-success { background: rgba(16,185,129,0.15); color: var(--success); border: 1px solid rgba(16,185,129,0.3); }
.badge-loading { background: rgba(245,158,11,0.15); color: var(--warning); border: 1px solid rgba(245,158,11,0.3); }
.badge-idle    { background: rgba(100,116,139,0.15); color: var(--text-muted); border: 1px solid rgba(100,116,139,0.3); }

/* ── Chat messages ── */
[data-testid="stChatMessage"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    padding: 1rem 1.2rem !important;
    margin: 0.5rem 0 !important;
    backdrop-filter: blur(10px);
    transition: border-color 0.2s;
}
[data-testid="stChatMessage"]:hover {
    border-color: rgba(124,58,237,0.25) !important;
}

/* ── Source citations block ── */
.sources-block {
    margin-top: 0.8rem;
    padding: 0.7rem 1rem;
    background: rgba(6,182,212,0.06);
    border: 1px solid rgba(6,182,212,0.2);
    border-radius: var(--radius-sm);
    font-size: 0.82rem;
}
.sources-block a {
    color: var(--accent-secondary) !important;
    text-decoration: none;
    font-weight: 500;
}
.sources-block a:hover { text-decoration: underline; }

/* ── Input area ── */
[data-testid="stChatInput"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    background: rgba(255,255,255,0.05) !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: var(--accent-primary) !important;
    box-shadow: 0 0 0 2px rgba(124,58,237,0.2) !important;
}

/* ── Buttons ── */
.stButton > button {
    background: var(--accent-gradient) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.6rem 1.2rem !important;
    transition: opacity 0.2s, transform 0.1s !important;
    width: 100%;
}
.stButton > button:hover { opacity: 0.88 !important; transform: translateY(-1px) !important; }
.stButton > button:active { transform: translateY(0px) !important; }

/* ── Text inputs ── */
.stTextInput > div > div > input {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-size: 0.88rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: var(--accent-primary) !important;
    box-shadow: 0 0 0 2px rgba(124,58,237,0.2) !important;
}

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 1rem 0 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(124,58,237,0.4); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(124,58,237,0.7); }

/* ── Spinner ── */
.stSpinner > div { border-top-color: var(--accent-primary) !important; }

/* ── Welcome / empty state ── */
.welcome-card {
    text-align: center;
    padding: 3rem 2rem;
    background: var(--bg-card);
    border: 1px dashed var(--border);
    border-radius: var(--radius-lg);
    margin: 2rem 0;
}
.welcome-card .icon { font-size: 3rem; margin-bottom: 0.8rem; }
.welcome-card h3 {
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 0.5rem;
}
.welcome-card p {
    color: var(--text-secondary);
    font-size: 0.88rem;
    margin: 0;
    line-height: 1.6;
}

/* ── Pipeline steps ── */
.pipeline-step {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.4rem 0;
    font-size: 0.8rem;
    color: var(--text-secondary);
}
.step-num {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--accent-gradient);
    color: white;
    font-size: 0.65rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Session state initialisation ──────────────────────────────────────────────
def _init_session() -> None:
    defaults = {
        "messages": [],
        "video_loaded": False,
        "video_id": None,
        "video_title": "Unknown Title",
        "video_author": "Unknown Author",
        "video_url": "",
        "indexing_complete": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_init_session()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo / Title
    st.markdown(
        """
        <div style="text-align:center; padding: 0.5rem 0 1rem;">
            <div style="font-size:2.5rem;">🎬</div>
            <div style="font-weight:700; font-size:1.1rem; color:#f1f5f9;">YouTube RAG</div>
            <div style="font-size:0.72rem; color:#64748b; letter-spacing:0.05em;">
                AI-Powered Video Q&amp;A
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── URL Input section ──────────────────────────────────────────────────
    st.markdown('<div class="sidebar-section">📹 Video Source</div>', unsafe_allow_html=True)

    url_input = st.text_input(
        label="YouTube URL",
        placeholder="https://www.youtube.com/watch?v=...",
        value=st.session_state.video_url,
        label_visibility="collapsed",
        key="url_input_field",
    )

    load_button = st.button("🚀 Load & Index Video", use_container_width=True)

    # ── Load & index logic ─────────────────────────────────────────────────
    if load_button and url_input.strip():
        with st.spinner("Processing video…"):
            try:
                from utils.url_parser import extract_video_id
                from core.transcript_loader import YouTubeTranscriptLoader
                from core.chunker import chunk_documents
                from core.vector_store import is_video_indexed, upsert_documents

                video_id = extract_video_id(url_input.strip())

                # ── Step 1: Check cache ──────────────────────────────────
                progress_bar = st.progress(0, text="🔍 Checking index…")

                already_indexed = is_video_indexed(video_id)

                if already_indexed:
                    progress_bar.progress(100, text="✅ Already indexed!")
                    time.sleep(0.5)
                    progress_bar.empty()
                    st.success("Video already indexed. Ready to chat! ✨")
                    # Still load metadata for display
                    loader = YouTubeTranscriptLoader(url_input.strip(), fetch_metadata=True)
                    sample_docs = loader.load()
                    title = sample_docs[0].metadata.get("video_title", "Unknown Title") if sample_docs else "Unknown Title"
                    author = sample_docs[0].metadata.get("video_author", "Unknown Author") if sample_docs else "Unknown Author"
                else:
                    # ── Step 2: Fetch transcript ─────────────────────────
                    progress_bar.progress(15, text="📝 Fetching transcript…")
                    loader = YouTubeTranscriptLoader(url_input.strip(), fetch_metadata=True)
                    docs = loader.load()

                    if not docs:
                        st.error("❌ No transcript found. Please try a different video.")
                        st.stop()

                    title = docs[0].metadata.get("video_title", "Unknown Title")
                    author = docs[0].metadata.get("video_author", "Unknown Author")

                    # ── Step 3: Chunk ────────────────────────────────────
                    progress_bar.progress(35, text="✂️  Chunking transcript…")
                    chunks = chunk_documents(docs)

                    # ── Step 4: Embed & Upsert ───────────────────────────
                    progress_bar.progress(55, text="🧠 Generating embeddings…")
                    n_upserted = upsert_documents(chunks)

                    progress_bar.progress(100, text=f"✅ Indexed {n_upserted} chunks!")
                    time.sleep(0.8)
                    progress_bar.empty()
                    st.success(f"✅ Indexed **{n_upserted}** chunks successfully!")

                # ── Update session state ─────────────────────────────────
                st.session_state.video_loaded = True
                st.session_state.video_id = video_id
                st.session_state.video_url = url_input.strip()
                st.session_state.video_title = title
                st.session_state.video_author = author
                st.session_state.messages = []  # Clear chat for new video
                st.session_state.indexing_complete = True

            except ValueError as ve:
                st.error(f"❌ {ve}")
            except Exception as exc:
                logger.exception("Error during video loading.")
                st.error(f"❌ Unexpected error: {exc}")

    elif load_button and not url_input.strip():
        st.warning("⚠️ Please enter a YouTube URL first.")

    # ── Status indicator ──────────────────────────────────────────────────
    st.markdown('<div class="sidebar-section">📊 Status</div>', unsafe_allow_html=True)

    if st.session_state.video_loaded:
        st.markdown(
            '<span class="badge badge-success">● Ready to Chat</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="badge badge-idle">○ No video loaded</span>',
            unsafe_allow_html=True,
        )

    # ── Video metadata card ────────────────────────────────────────────────
    if st.session_state.video_loaded:
        st.markdown('<div class="sidebar-section">🎞️ Current Video</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="video-card">
                <div class="label">Title</div>
                <div class="value">{st.session_state.video_title}</div>
            </div>
            <div class="video-card">
                <div class="label">Channel</div>
                <div class="value">{st.session_state.video_author}</div>
            </div>
            <div class="video-card">
                <div class="label">Video ID</div>
                <div class="value" style="font-family:monospace; font-size:0.78rem;">
                    {st.session_state.video_id}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        watch_url = f"https://www.youtube.com/watch?v={st.session_state.video_id}"
        st.markdown(f"[🔗 Open on YouTube]({watch_url})", unsafe_allow_html=False)

        # Clear chat button
        st.markdown("")
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    # ── Pipeline info ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="sidebar-section">⚙️ Pipeline</div>', unsafe_allow_html=True)
    steps = [
        "YouTube Transcript API",
        "Document + Timestamp",
        "Text Chunking",
        "NVIDIA llama-nemotron",
        "Pinecone Vector DB",
        "Semantic Retrieval",
        "Groq Qwen-2.5-32B",
        "Answer + Jump Link",
    ]
    for i, step in enumerate(steps, 1):
        st.markdown(
            f'<div class="pipeline-step">'
            f'<div class="step-num">{i}</div>{step}'
            f"</div>",
            unsafe_allow_html=True,
        )

# ── Main area ─────────────────────────────────────────────────────────────────

# Header
st.markdown(
    """
    <div class="rag-header">
        <h1>🎬 YouTube RAG Chatbot</h1>
        <p>Ask any question about the video — get precise answers with timestamped sources</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Welcome state (no video loaded) ──────────────────────────────────────────
if not st.session_state.video_loaded:
    st.markdown(
        """
        <div class="welcome-card">
            <div class="icon">🚀</div>
            <h3>Get Started</h3>
            <p>
                Paste a YouTube URL in the sidebar and click<br>
                <strong>Load &amp; Index Video</strong> to begin.<br><br>
                The chatbot will answer questions <em>exclusively</em> from the video's content
                with clickable timestamp jump links.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Feature cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
            <div class="video-card" style="text-align:center; padding: 1.2rem;">
                <div style="font-size:1.8rem; margin-bottom:0.5rem;">🧠</div>
                <div style="font-weight:600; margin-bottom:0.3rem;">NVIDIA Embeddings</div>
                <div style="font-size:0.78rem; color:#94a3b8;">llama-nemotron-embed-1b-v2<br>2048-dim semantic search</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
            <div class="video-card" style="text-align:center; padding: 1.2rem;">
                <div style="font-size:1.8rem; margin-bottom:0.5rem;">🌲</div>
                <div style="font-weight:600; margin-bottom:0.3rem;">Pinecone Vector DB</div>
                <div style="font-size:0.78rem; color:#94a3b8;">Serverless, scalable<br>cosine similarity search</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            """
            <div class="video-card" style="text-align:center; padding: 1.2rem;">
                <div style="font-size:1.8rem; margin-bottom:0.5rem;">⚡</div>
                <div style="font-weight:600; margin-bottom:0.3rem;">Groq Qwen-2.5-32B</div>
                <div style="font-size:0.78rem; color:#94a3b8;">Ultra-fast inference<br>zero hallucinations</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

else:
    # ── Chat interface ─────────────────────────────────────────────────────

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    # ── Chat input ─────────────────────────────────────────────────────────
    if user_question := st.chat_input(
        f"Ask anything about: {st.session_state.video_title[:50]}…"
    ):
        # Append user message
        st.session_state.messages.append({"role": "user", "content": user_question})

        with st.chat_message("user"):
            st.markdown(user_question)

        # Generate assistant response
        with st.chat_message("assistant"):
            is_summary_q = any(w in user_question.lower() for w in [
                "summar", "overview", "outline", "brief", "recap",
                "what is this video", "what does this video", "what did they",
                "main point", "key point", "explain the video", "tell me about",
            ])
            spinner_msg = (
                "📋 Analysing full video for summary…"
                if is_summary_q
                else "🔍 Searching transcript and generating answer…"
            )
            with st.spinner(spinner_msg):
                try:
                    from core.rag_chain import run_rag_query
                    from utils.timestamp_formatter import format_sources_block

                    result = run_rag_query(
                        question=user_question,
                        video_id=st.session_state.video_id,
                    )

                    answer: str = result["answer"]
                    source_docs = result["source_documents"]
                    is_summary_result: bool = result.get("is_summary", False)

                    # For summaries show more sources (5), for Q&A show 3
                    max_src = 5 if is_summary_result else 3
                    sources_md = format_sources_block(
                        source_docs,
                        video_id=st.session_state.video_id,
                        max_sources=max_src,
                    )

                    # Compose full response
                    full_response = answer
                    if sources_md and "couldn't find" not in answer.lower():
                        full_response = f"{answer}\n\n{sources_md}"

                    st.markdown(full_response, unsafe_allow_html=False)

                    # Store in history
                    st.session_state.messages.append(
                        {"role": "assistant", "content": full_response}
                    )

                except Exception as exc:
                    logger.exception("Error during RAG query.")
                    err_msg = (
                        f"❌ An error occurred while generating the answer: `{exc}`\n\n"
                        "Please try again or reload the video."
                    )
                    st.error(err_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": err_msg}
                    )
