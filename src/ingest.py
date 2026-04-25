"""Load the Excel dataset and upsert into Chroma (one chunk per family office row)."""
from __future__ import annotations

import argparse

import chromadb
import pandas as pd
from chromadb.utils import embedding_functions

from .config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    DATA_SHEET,
    DATA_XLSX,
    EMBEDDING_MODEL,
)
from .documents import dataframe_to_documents


def load_family_office_df() -> pd.DataFrame:
    if not DATA_XLSX.is_file():
        raise FileNotFoundError(
            f"Dataset not found at {DATA_XLSX}. Place family_office_dataset_50_records.xlsx in the repo root."
        )
    df = pd.read_excel(DATA_XLSX, sheet_name=DATA_SHEET)
    df = df.dropna(how="all")
    return df


def ingest(reset: bool = True) -> int:
    df = load_family_office_df()
    texts, metadatas, ids = dataframe_to_documents(df)

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
    )

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )
    # Chroma recommends batching; 53 rows is tiny.
    collection.add(documents=texts, metadatas=metadatas, ids=ids)
    return len(ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest family office XLSX into Chroma.")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not delete the collection before add (may cause ID conflicts on re-run).",
    )
    args = parser.parse_args()
    n = ingest(reset=not args.no_reset)
    print(f"Ingested {n} records into {CHROMA_DIR} (collection={COLLECTION_NAME}).")


if __name__ == "__main__":
    main()
