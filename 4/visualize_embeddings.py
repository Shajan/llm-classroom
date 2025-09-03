"""
Visualize sentence embeddings stored in ChromaDB for the RAG app.

How to run (Streamlit):
  streamlit run 4/visualize_embeddings.py

What this does:
- Connects to the same ChromaDB persistent store used by rag_app.py (./chroma_db)
- Loads the 'rag_documents' collection and fetches embeddings + metadata
- Reduces embeddings to 2D using PCA (no extra dependencies)
- Plots an interactive scatter chart colored by source with basic filtering
- Lets you sample a subset if you have many points

Notes:
- Hover tooltips show source, chunk id, timestamp, and a text preview
- If there are no vectors yet, you'll see a helpful message
"""

from __future__ import annotations

import os
import sys
import random
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd
import streamlit as st
import chromadb
import altair as alt


def load_embeddings(db_path: str, collection_name: str = "rag_documents", limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Load embeddings, metadatas, documents, and ids from a ChromaDB collection.

    Returns a dict with keys: embeddings (NxD), metadatas (N), documents (N), ids (N)
    """
    client = chromadb.PersistentClient(path=db_path)

    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        raise RuntimeError(
            f"Collection '{collection_name}' not found at {db_path}. Add documents in rag_app first."
        ) from e

    count = collection.count()
    if count == 0:
        return {"embeddings": [], "metadatas": [], "documents": [], "ids": []}

    fetch_limit = limit if limit is not None else count
    # Fetch embeddings in batches if very large
    # Note: 'ids' is not a valid value for `include` in Chroma get(); ids are returned by default.
    include = ["embeddings", "metadatas", "documents"]

    # Chroma get supports limit+offset; do simple batching
    batch_size = min(fetch_limit, 5000)
    remaining = fetch_limit
    offset = 0

    all_embeddings: List[List[float]] = []
    all_metadatas: List[Dict[str, Any]] = []
    all_documents: List[str] = []
    all_ids: List[str] = []

    while remaining > 0:
        cur = min(batch_size, remaining)
        results = collection.get(include=include, limit=cur, offset=offset)
        # Results are lists aligned across keys
        all_embeddings.extend(results.get("embeddings", []))
        all_metadatas.extend(results.get("metadatas", []))
        all_documents.extend(results.get("documents", []))
        all_ids.extend(results.get("ids", []))
        remaining -= cur
        offset += cur
        if cur == 0:
            break

    return {
        "embeddings": all_embeddings,
        "metadatas": all_metadatas,
        "documents": all_documents,
        "ids": all_ids,
    }


def pca_2d(x: np.ndarray, normalize: bool = False) -> np.ndarray:
    """
    Reduce vectors to 2D using PCA via SVD.

    x: (N, D)
    returns: (N, 2)
    """
    if x.ndim != 2:
        raise ValueError("x must be 2D array")
    if normalize:
        # L2 normalize rows to unit length
        norms = np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
        x = x / norms
    # Center
    mu = x.mean(axis=0, keepdims=True)
    x_centered = x - mu
    # SVD
    u, s, vt = np.linalg.svd(x_centered, full_matrices=False)
    # Project to first 2 PCs
    pcs = x_centered @ vt[:2].T
    return pcs


def build_dataframe(embeddings: List[List[float]], metadatas: List[Dict[str, Any]], documents: List[str], ids: List[str],
                    normalize: bool, sample_n: Optional[int], seed: int) -> pd.DataFrame:
    # Basic safety checks
    if not embeddings:
        return pd.DataFrame(columns=["x", "y", "source", "chunk_id", "timestamp", "text_preview", "id"]) 

    n = len(embeddings)
    idx = list(range(n))
    if sample_n is not None and sample_n < n:
        random.seed(seed)
        idx = random.sample(idx, sample_n)

    emb = np.array([embeddings[i] for i in idx], dtype=np.float32)
    pcs = pca_2d(emb, normalize=normalize)

    def meta_value(i, key, default=None):
        try:
            val = metadatas[i].get(key, default)
        except Exception:
            val = default
        return val

    rows = []
    for j, i in enumerate(idx):
        source = meta_value(i, "source", "unknown")
        chunk_id = meta_value(i, "chunk_id", None)
        ts = meta_value(i, "timestamp", None)
        text = documents[i] if i < len(documents) else ""
        preview = (text[:180] + "…") if text and len(text) > 180 else text
        rows.append({
            "x": float(pcs[j, 0]),
            "y": float(pcs[j, 1]),
            "source": str(source),
            "chunk_id": chunk_id,
            "timestamp": ts,
            "text_preview": preview,
            "id": ids[i] if i < len(ids) else None,
        })

    df = pd.DataFrame(rows)
    return df


def main():
    st.set_page_config(page_title="Embedding Visualizer", page_icon="🧭", layout="wide")
    st.title("🧭 Embedding Visualizer (ChromaDB)")
    st.caption("Visualize sentence embeddings stored by the RAG app")

    # Locate DB path next to this file (same as rag_app)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, "chroma_db")

    # Sidebar controls
    st.sidebar.header("Settings")
    st.sidebar.write(f"DB Path: {db_path}")
    collection_name = st.sidebar.text_input("Collection", value="rag_documents")
    limit = st.sidebar.number_input("Max records to load (0 = all)", value=0, min_value=0, step=100)
    normalize = st.sidebar.checkbox("L2-normalize before PCA", value=False)
    sample_n = st.sidebar.number_input("Sample N points (0 = no sampling)", value=0, min_value=0, step=100)
    seed = st.sidebar.number_input("Sample seed", value=42, min_value=0, step=1)

    # Load data
    try:
        with st.spinner("Loading embeddings from ChromaDB…"):
            raw = load_embeddings(
                db_path,
                collection_name=collection_name,
                limit=(None if limit == 0 else int(limit)),
            )
    except Exception as e:
        st.error(str(e))
        st.stop()

    embeddings = raw.get("embeddings", [])
    metadatas = raw.get("metadatas", [])
    documents = raw.get("documents", [])
    ids = raw.get("ids", [])

    total = len(embeddings)
    if total == 0:
        st.warning("No embeddings found. Add documents via rag_app.py first.")
        st.stop()

    st.info(f"Loaded {total} vector(s)")

    # Build DataFrame with PCA 2D coords
    df = build_dataframe(
        embeddings=embeddings,
        metadatas=metadatas,
        documents=documents,
        ids=ids,
        normalize=normalize,
        sample_n=(None if sample_n == 0 else int(sample_n)),
        seed=int(seed),
    )

    if df.empty:
        st.warning("Nothing to display after sampling/filters.")
        st.stop()

    # Filters
    sources = sorted(df["source"].dropna().unique().tolist())
    selected_sources = st.multiselect("Filter by source", options=sources, default=sources)
    text_filter = st.text_input("Search in text preview (case-insensitive)", value="")

    filtered = df[df["source"].isin(selected_sources)] if selected_sources else df.copy()
    if text_filter:
        filtered = filtered[filtered["text_preview"].str.contains(text_filter, case=False, na=False)]

    st.subheader("Scatter plot (PCA 2D)")
    # Build Altair chart with tooltips and interactivity
    # Disable row limit in case there are many points
    alt.data_transformers.disable_max_rows()

    chart = (
        alt.Chart(filtered, height=600)
        .mark_circle(opacity=0.8, size=60)
        .encode(
            x=alt.X("x", title="PC1"),
            y=alt.Y("y", title="PC2"),
            color=alt.Color("source", legend=alt.Legend(title="Source")),
            tooltip=[
                alt.Tooltip("source", title="Source"),
                alt.Tooltip("chunk_id", title="Chunk"),
                alt.Tooltip("timestamp", title="Timestamp"),
                alt.Tooltip("id", title="ID"),
                alt.Tooltip("text_preview", title="Preview"),
                alt.Tooltip("x", title="PC1", format=".3f"),
                alt.Tooltip("y", title="PC2", format=".3f"),
            ],
        )
        .interactive()
    )

    st.altair_chart(chart, use_container_width=True)

    with st.expander("Data table"):
        st.dataframe(filtered, use_container_width=True, height=350)

    # Export options
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export visible points to CSV"):
            csv = filtered.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="embeddings_pca2d.csv",
                mime="text/csv",
            )
    with col2:
        # Offer HTML export of the current chart
        if st.button("Export chart to HTML"):
            html = chart.to_html()
            st.download_button(
                label="Download HTML",
                data=html,
                file_name="embeddings_pca2d.html",
                mime="text/html",
            )
        st.caption("Tip: Use the sidebar to sample if you have many vectors")


if __name__ == "__main__":
    main()
