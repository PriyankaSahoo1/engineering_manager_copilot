

from pathlib import Path

from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from unstructured.partition.text import partition_text
from unstructured.chunking.title import chunk_by_title

from langchain_core.documents import Document

from app.core.config import (
    MAX_CHARACTERS,
    NEW_AFTER_N_CHARS,
    COMBINE_TEXT_UNDER_N_CHARS,
    OVERLAP,
)


# ============================================================
# PARTITION DOCUMENT
# ============================================================

def partition_document(file_path):

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    if not file_path.is_file():
        raise ValueError(
            f"Path is not a file: {file_path}"
        )

    extension = file_path.suffix.lower()

    if extension not in {
        ".pdf",
        ".docx",
        ".txt",
    }:
        raise ValueError(
            f"Unsupported file type '{extension}'. "
            "Supported types: .pdf, .docx, .txt"
        )

    print(
        f"[1/3] Partitioning {file_path.name}..."
    )

    if extension == ".pdf":

        elements = partition_pdf(
            filename=str(file_path),
            strategy="hi_res",
            infer_table_structure=False,
        )

    elif extension == ".docx":

        elements = partition_docx(
            filename=str(file_path)
        )

    else:

        elements = partition_text(
            filename=str(file_path)
        )

    if not elements:
        raise ValueError(
            f"No elements extracted from {file_path.name}"
        )

    print(
        f"Extracted elements: {len(elements)}"
    )

    return elements


# ============================================================
# FILTER TEXT ELEMENTS
# ============================================================

def filter_text_elements(elements):

    allowed = {
        "Title",
        "NarrativeText",
        "Text",
        "ListItem",
        "Header",
        "Footer",
        "UncategorizedText",
    }

    filtered = []

    for element in elements:

        if type(element).__name__ not in allowed:
            continue

        text = getattr(
            element,
            "text",
            None
        )

        if text and text.strip():
            filtered.append(element)

    if not filtered:
        raise ValueError(
            "No text elements found after filtering."
        )

    print(
        "Text elements after filtering: "
        f"{len(filtered)}"
    )

    return filtered


# ============================================================
# CREATE CHUNKS
# ============================================================

def create_chunks(elements):

    print(
        "[2/3] Chunking by title..."
    )

    chunks = chunk_by_title(
        elements,
        max_characters=MAX_CHARACTERS,
        new_after_n_chars=NEW_AFTER_N_CHARS,
        combine_text_under_n_chars=COMBINE_TEXT_UNDER_N_CHARS,
        overlap=OVERLAP,
        include_orig_elements=True,
    )

    if not chunks:
        raise ValueError(
            "No chunks were created."
        )

    print(
        f"Created chunks: {len(chunks)}"
    )

    return chunks


# ============================================================
# GET SECTION
# ============================================================

def get_section(chunk):

    orig_elements = getattr(
        chunk.metadata,
        "orig_elements",
        None
    )

    if not orig_elements:
        return None

    section = None

    for element in orig_elements:

        if type(element).__name__ == "Title":

            text = getattr(
                element,
                "text",
                None
            )

            if text and text.strip():
                section = text.strip()

    return section


# ============================================================
# GET PAGE NUMBER
# ============================================================

def get_page_number(chunk):

    metadata = chunk.metadata.to_dict()

    page_number = metadata.get(
        "page_number"
    )

    if page_number is not None:
        return page_number

    orig_elements = getattr(
        chunk.metadata,
        "orig_elements",
        None
    )

    if not orig_elements:
        return None

    page_numbers = []

    for element in orig_elements:

        element_metadata = getattr(
            element,
            "metadata",
            None
        )

        if not element_metadata:
            continue

        page_number = getattr(
            element_metadata,
            "page_number",
            None
        )

        if page_number is not None:
            page_numbers.append(page_number)

    return (
        min(page_numbers)
        if page_numbers
        else None
    )


# ============================================================
# GET SOURCE NAME
# ============================================================

def get_source(chunk, file_path):

    source = (
        chunk.metadata
        .to_dict()
        .get("filename")
    )

    if source:
        return source

    return Path(file_path).name


# ============================================================
# CREATE LANGCHAIN DOCUMENTS
# ============================================================

def create_documents(
    chunks,
    file_path,
    project_id,
    source_id,
    user_id,
):

    print(
        "[3/3] Creating LangChain documents..."
    )

    documents = []

    for chunk_id, chunk in enumerate(chunks):

        text = getattr(
            chunk,
            "text",
            None
        )

        if not text or not text.strip():
            continue

        text = text.strip()

        document = Document(
            page_content=text,
            metadata={
                "project_id": str(project_id),
                "source_id": str(source_id),
                "user_id": str(user_id),
                "chunk_id": chunk_id,
                "page_number": get_page_number(chunk),
                "section": get_section(chunk),
                "source": get_source(
                    chunk,
                    file_path
                ),
            },
        )

        documents.append(document)

    if not documents:
        raise ValueError(
            "No valid LangChain documents were created."
        )

    print(
        f"Created {len(documents)} "
        "LangChain documents."
    )

    return documents


# ============================================================
# PROCESS DOCUMENT
# ============================================================

def process_document(
    file_path,
    project_id,
    source_id,
    user_id,
):

    try:

        elements = partition_document(
            file_path
        )

        elements = filter_text_elements(
            elements
        )

        chunks = create_chunks(
            elements
        )

        return create_documents(
            chunks,
            file_path,
            project_id,
            source_id,
            user_id,
        )

    except Exception as exc:

        raise RuntimeError(
            "Document processing failed "
            f"for '{file_path}': {exc}"
        ) from exc
