"""
RAG (Retrieval-Augmented Generation): answer questions from your own documents.

The model has never seen docs/handbook.txt, so on its own it cannot answer
questions about it. RAG fixes that:
  1. Index (once, at startup): split the documents into chunks and turn each
     chunk into an embedding - a list of numbers that captures its meaning.
  2. Retrieve (per question): embed the question and find the closest chunks.
  3. Generate: paste those chunks into the prompt. The model call is the
     same as 1.HelloLLM.
"""
import glob
import os

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

HERE = os.path.dirname(os.path.abspath(__file__))
TOP_K = 2  # how many chunks to put in the prompt


def embed(client, texts):
    """Turn each text into an embedding (a vector of 1536 numbers)."""
    response = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return np.array([item.embedding for item in response.data])


def main():
    load_dotenv(os.path.join(HERE, "..", ".env"))
    client = OpenAI()

    # 1. Index: one chunk per paragraph of every .txt file in docs/
    chunks = []
    for path in glob.glob(os.path.join(HERE, "docs", "*.txt")):
        with open(path) as f:
            chunks += [p.strip() for p in f.read().split("\n\n") if p.strip()]
    chunk_vectors = embed(client, chunks)
    print(f"Indexed {len(chunks)} chunks from docs/")

    while True:
        question = input("\nYou (empty line to quit): ").strip()
        if not question:
            break

        # 2. Retrieve: score every chunk against the question.
        # These embeddings have length 1, so the dot product is the cosine
        # similarity: close to 1 = similar meaning, close to 0 = unrelated.
        scores = chunk_vectors @ embed(client, [question])[0]
        best = np.argsort(scores)[::-1][:TOP_K]
        for i in best:
            print(f"  retrieved [{scores[i]:.2f}] {chunks[i][:60]}...")

        # 3. Generate: the same call as 1.HelloLLM, with the chunks in the prompt.
        context = "\n\n".join(chunks[i] for i in best)
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
