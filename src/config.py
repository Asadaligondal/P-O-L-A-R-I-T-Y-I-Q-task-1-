"""Paths and model names for the family-office RAG demo."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Source workbook (your deliverable).
DATA_XLSX = BASE_DIR / "family_office_dataset_50_records.xlsx"
DATA_SHEET = "Family Office Dataset"

# Pipeline output (created by `python -m src.pipeline.run_pipeline`).
ARTIFACTS_DIR = BASE_DIR / "artifacts"
DATA_ARTIFACT_XLSX = ARTIFACTS_DIR / "dataset_for_rag.xlsx"

CHROMA_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "family_offices"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

DEFAULT_CHAT_MODEL = "gpt-4o-mini"


def resolved_dataset_path() -> Path:
    """Prefer processed artifact when present."""
    if DATA_ARTIFACT_XLSX.is_file():
        return DATA_ARTIFACT_XLSX
    return DATA_XLSX
