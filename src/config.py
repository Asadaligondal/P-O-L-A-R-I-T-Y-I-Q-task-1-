"""Paths and model names for the family-office RAG demo."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Production dataset only (FO-MAX sample is not used anywhere in code).
DATA_XLSX = BASE_DIR / "family_office_dataset_50_records.xlsx"
DATA_SHEET = "Family Office Dataset"

CHROMA_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "family_offices"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
