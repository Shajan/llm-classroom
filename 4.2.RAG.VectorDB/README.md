# RAG with a Vector Database

The same as 4.1.RAG, but the chunks and their embeddings are stored in **Chroma**, a vector database, instead of a NumPy array. The documents, the embeddings and the model call are unchanged.

## What Changes from 4.1

| | 4.1 (NumPy) | 4.2 (Chroma) |
|---|---|---|
| Store | an array in memory, rebuilt on every start | `chroma_db/` on disk, built once |
| Search | `chunk_vectors @ question_vector`, then sort | `collection.query(...)` |
| Scale | compares the question with every chunk | an index finds the closest chunks quickly, even among millions |

Chroma is set to cosine distance, so it returns the same chunks with the same scores as 4.1.

## Files

| File | What it shows |
|---|---|
| `docs/handbook.txt` | The same made-up handbook as 4.1 |
| `rag_chat.py` | Indexes `docs/` into Chroma once, then answers questions in a chat loop |

## Setup

From the repository root:

```bash
pip install -r 4.2.RAG.VectorDB/requirements.txt
```

The script reads `OPENAI_API_KEY` from the `.env` file in the repository root.

## Run

```bash
python 4.2.RAG.VectorDB/rag_chat.py
```

The first run prints `Indexed 6 chunks from docs/ into chroma_db/`. Later runs print `Loaded 6 chunks from chroma_db/` and make no embedding calls for the documents.

Try the same questions as 4.1:

```
How many vacation days do I get?
Can I work from home on Wednesday?
Who won the 2022 World Cup?
```

If you change the files in `docs/`, delete the `chroma_db` folder so they are indexed again. Press Enter on an empty line to quit.
