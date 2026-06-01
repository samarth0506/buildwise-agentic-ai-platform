"""
BuildWise RAG data loader.

Loads CSV and TXT files from the project ``data/`` folder and converts them
into LangChain ``Document`` objects with consistent metadata for retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import pandas as pd
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Project root is one level above this package (buildwise-agentic-ai-platform/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Expected data files and their RAG categories
CSV_SOURCES = [
    ("property_data.csv", "property"),
    ("construction_status.csv", "construction"),
    ("maintenance_issues.csv", "maintenance"),
    ("documentation_cases.csv", "documentation"),
]

TXT_SOURCES = [
    ("documentation_faq.txt", "documentation_faq"),
]


def _format_csv_row(row: pd.Series) -> str:
    """Turn one pandas row into readable text for embedding."""
    parts = []
    for column, value in row.items():
        if pd.isna(value):
            continue
        parts.append(f"{column}: {value}")
    return " | ".join(parts) if parts else ""


def load_csv_as_documents(file_path: str | Path, category: str) -> List[Document]:
    """
    Load a CSV file and return one LangChain Document per data row.

    Args:
        file_path: Path to the CSV file.
        category: Metadata category label (e.g. ``construction``, ``property``).

    Returns:
        List of Documents with metadata: source, category, row_number.
    """
    path = Path(file_path)
    if not path.is_file():
        logger.warning("CSV file not found, skipping: %s", path)
        return []

    try:
        dataframe = pd.read_csv(path)
    except Exception as exc:
        logger.error("Failed to read CSV %s: %s", path, exc)
        return []

    documents: List[Document] = []
    source_name = path.name

    for index, row in dataframe.iterrows():
        content = _format_csv_row(row)
        if not content.strip():
            continue

        # row_number is 1-based for human-friendly debugging
        row_number = int(index) + 1 if isinstance(index, (int, float)) else len(documents) + 1

        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source": source_name,
                    "category": category,
                    "row_number": row_number,
                },
            )
        )

    logger.info("Loaded %d documents from %s", len(documents), path.name)
    return documents


def load_txt_as_documents(file_path: str | Path, category: str) -> List[Document]:
    """
    Load a plain-text file and split it into paragraph-based Documents.

    Paragraphs are separated by blank lines (double newline). Each non-empty
    paragraph becomes one Document.

    Args:
        file_path: Path to the text file.
        category: Metadata category label (e.g. ``documentation_faq``).

    Returns:
        List of Documents with metadata: source, category, chunk_number.
    """
    path = Path(file_path)
    if not path.is_file():
        logger.warning("TXT file not found, skipping: %s", path)
        return []

    try:
        raw_text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to read TXT %s: %s", path, exc)
        return []

    # Split on blank lines; filter empty chunks
    paragraphs = [chunk.strip() for chunk in raw_text.split("\n\n") if chunk.strip()]

    documents: List[Document] = []
    source_name = path.name

    for chunk_number, paragraph in enumerate(paragraphs, start=1):
        documents.append(
            Document(
                page_content=paragraph,
                metadata={
                    "source": source_name,
                    "category": category,
                    "chunk_number": chunk_number,
                },
            )
        )

    logger.info("Loaded %d chunks from %s", len(documents), path.name)
    return documents


def load_all_documents() -> List[Document]:
    """
    Load all configured CSV and TXT sources from ``data/``.

    Missing files are skipped with a warning; the function never raises
    for missing data. Returns an empty list only when no files exist or
    all files are empty.

    Returns:
        Combined list of Documents from every available source.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_documents: List[Document] = []

    for filename, category in CSV_SOURCES:
        file_path = DATA_DIR / filename
        all_documents.extend(load_csv_as_documents(file_path, category))

    for filename, category in TXT_SOURCES:
        file_path = DATA_DIR / filename
        all_documents.extend(load_txt_as_documents(file_path, category))

    logger.info("Total documents loaded: %d", len(all_documents))
    return all_documents


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Data directory: {DATA_DIR}\n")

    docs = load_all_documents()
    print(f"Loaded {len(docs)} document(s).\n")

    if docs:
        print("--- Sample document ---")
        sample = docs[0]
        print(f"Content: {sample.page_content[:200]}...")
        print(f"Metadata: {sample.metadata}")
    else:
        print(
            "No documents loaded. Add CSV/TXT files under data/:\n"
            "  - property_data.csv\n"
            "  - construction_status.csv\n"
            "  - maintenance_issues.csv\n"
            "  - documentation_cases.csv\n"
            "  - documentation_faq.txt"
        )
