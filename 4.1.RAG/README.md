# RAG Example

RAG (Retrieval-Augmented Generation) lets the model answer questions about documents it has never seen. Before each question goes to the model, the most relevant pieces of your documents are found and pasted into the prompt.

## Files

| File | What it shows |
|---|---|
| `docs/handbook.txt` | A made-up company handbook. The model cannot know it, so correct answers must come from RAG. |
| `rag_chat.py` | Indexes `docs/`, then answers questions in a chat loop |

## How It Works

1. **Index (once):** split each `.txt` file in `docs/` into chunks (one per paragraph). Turn each chunk into an **embedding**: a vector of numbers that captures its meaning. Texts with similar meanings get similar vectors.
2. **Retrieve (per question):** embed the question and score it against every chunk (cosine similarity). Keep the best `TOP_K` (2).
3. **Generate:** put those chunks in the system prompt and ask the model, with the same `chat.completions` call as 1.HelloLLM.

The vectors are kept in a NumPy array so every step is visible. 4.2.RAG.VectorDB does the same thing with a vector database.

## Setup

From the repository root:

```bash
pip install -r 4.1.RAG/requirements.txt
```

The script reads `OPENAI_API_KEY` from the `.env` file in the repository root.

## Run

```bash
python 4.1.RAG/rag_chat.py
```

Try:

```
How many vacation days do I get?
Can I work from home on Wednesday?
Who won the 2022 World Cup?
```

For each question it prints the retrieved chunks and their scores. The last question has nothing to do with the handbook, so the scores are low and the model says it doesn't know.

To use your own documents, add `.txt` files to `docs/`. Press Enter on an empty line to quit.
