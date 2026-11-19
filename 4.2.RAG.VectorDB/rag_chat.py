"""
RAG with a vector database: the same as 4.1.RAG, but the chunks and their
embeddings are stored in Chroma instead of a NumPy array.

What changes:
  1. Index: the vectors are saved to disk (chroma_db/), so they are computed
     once, not on every start.
  2. Retrieve: collection.query() finds the closest chunks. 4.1 did this with
     a dot product; a vector database uses an index that stays fast with
     millions of chunks.
  3. Generate: unchanged.
"""
import glob
import os

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

HERE = os.path.dirname(os.path.abspath(__file__))
TOP_K = 2  # how many chunks to put in the prompt


def embed(client, texts):
    """Turn each text into an embedding (a vector of 1536 numbers). Same as 4.1."""
    response = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [item.embedding for item in response.data]


def main():
    load_dotenv(os.path.join(HERE, "..", ".env"))
    client = OpenAI()

    # The database lives in chroma_db/. A collection is like a table of chunks.
    # "cosine" makes it compare vectors the same way as 4.1.
    db = chromadb.PersistentClient(path=os.path.join(HERE, "chroma_db"))
    collection = db.get_or_create_collection("docs", metadata={"hnsw:space": "cosine"})

    # 1. Index: only the first time. Later runs reuse the saved vectors.
    # (If you change docs/, delete the chroma_db folder to re-index.)
    if collection.count() == 0:
        chunks = []
        for path in glob.glob(os.path.join(HERE, "docs", "*.txt")):
            with open(path) as f:
                chunks += [p.strip() for p in f.read().split("\n\n") if p.strip()]
        collection.add(ids=[str(i) for i in range(len(chunks))], documents=chunks,
                       embeddings=embed(client, chunks))
        print(f"Indexed {len(chunks)} chunks from docs/ into chroma_db/")
    else:
        print(f"Loaded {collection.count()} chunks from chroma_db/")

    while True:
        question = input("\nYou (empty line to quit): ").strip()
        if not question:
            break

        # 2. Retrieve: the database returns the TOP_K closest chunks.
        # Its distance is 1 - cosine similarity, so we print 1 - distance
        # to show the same score as 4.1.
        results = collection.query(query_embeddings=embed(client, [question]), n_results=TOP_K)
        best = results["documents"][0]
        for chunk, distance in zip(best, results["distances"][0]):
            print(f"  retrieved [{1 - distance:.2f}] {chunk[:60]}...")

        # 3. Generate: the same as 4.1.
        context = "\n\n".join(best)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Answer using only the context below. "
                 "If the answer is not there, say you don't know.\n\nContext:\n" + context},
                {"role": "user", "content": question},
            ],
        )
        print(f"\nAssistant: {response.choices[0].message.content}")


if __name__ == "__main__":
    main()
