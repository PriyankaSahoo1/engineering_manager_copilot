import time

from langchain_mongodb import MongoDBAtlasVectorSearch
from app.core.config import (
    VECTOR_INDEX_NAME,
    VECTOR_SEARCH_SYNC_TIMEOUT,
    VECTOR_SEARCH_SYNC_INTERVAL,
)
# from app.db.mongodb import collection
from app.db.mongodb import document_chunks_collection
from app.services.embeddings import get_embeddings

# from app.db.mongodb import (
#     document_chunks_collection,
# )

from app.services.embeddings import (
    get_embeddings,
)

_vector_store = None


# ============================================================
# GET VECTOR STORE
# ============================================================

def get_vector_store():

    global _vector_store

    if _vector_store is None:

        _vector_store = MongoDBAtlasVectorSearch(

            collection=document_chunks_collection,

            embedding=get_embeddings(),

            index_name=VECTOR_INDEX_NAME,

            text_key="text",

            embedding_key="embedding",
        )

    return _vector_store

# ============================================================
# ADD DOCUMENTS
# ============================================================

def add_documents(
    documents
):

    vector_store = get_vector_store()

    return vector_store.add_documents(
        documents
    )

def similarity_search(
    query: str,
    k: int = 5,
    project_id: str | None = None,
    source_id: str | None = None,
    user_id: str | None = None,
):
    """
    Vector search over document chunks.

    Passing user_id keeps retrieval inside the chunks of
    the files that user uploaded, so one user's document
    text can never reach another user's AI review.
    """

    pre_filter = {}

    if project_id:
        pre_filter["project_id"] = {"$eq": project_id}

    if source_id:
        pre_filter["source_id"] = {"$eq": source_id}

    if user_id:
        pre_filter["user_id"] = {"$eq": user_id}

    docs = get_vector_store().similarity_search(query, k=k, pre_filter=pre_filter or None)
    return [{"text": doc.page_content, "metadata": doc.metadata} for doc in docs]


# ============================================================
# CHUNK FILTER
# ============================================================

def _chunk_filter(
    project_id: str | None = None,
    source_id: str | None = None,
    user_id: str | None = None,
):
    """
    Plain MongoDB filter over the chunks collection.

    Mirrors the pre_filter used by similarity_search(), so a
    direct read is scoped exactly like a vector search.
    """

    query = {}

    if project_id:
        query["project_id"] = project_id

    if source_id:
        query["source_id"] = source_id

    if user_id:
        query["user_id"] = user_id

    return query


# ============================================================
# COUNT CHUNKS
# ============================================================

def count_chunks(
    project_id: str | None = None,
    source_id: str | None = None,
    user_id: str | None = None,
) -> int:
    """
    Number of chunks already stored for a source.

    Reads the collection directly, so it is immediately
    consistent and never affected by vector index lag.
    """

    return document_chunks_collection.count_documents(
        _chunk_filter(
            project_id=project_id,
            source_id=source_id,
            user_id=user_id,
        )
    )


# ============================================================
# FETCH CHUNKS (NO VECTOR INDEX)
# ============================================================

def fetch_chunks(
    k: int = 5,
    project_id: str | None = None,
    source_id: str | None = None,
    user_id: str | None = None,
):
    """
    Read chunks straight from the collection, in document order.

    No ranking and no vector index involved. Used as a fallback
    when the chunks are stored but Atlas has not indexed them
    yet, so a lagging index cannot fail a review.

    Returns the same shape as similarity_search().
    """

    cursor = (
        document_chunks_collection
        .find(
            _chunk_filter(
                project_id=project_id,
                source_id=source_id,
                user_id=user_id,
            ),
            {"embedding": 0},
        )
        .sort("chunk_id", 1)
        .limit(k)
    )

    results = []

    for doc in cursor:

        text = doc.pop("text", "")

        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

        results.append(
            {
                "text": text,
                "metadata": doc,
            }
        )

    return results


# ============================================================
# SEARCH CHUNKS (INDEX LAG TOLERANT)
# ============================================================

def search_chunks(
    query: str,
    k: int = 5,
    project_id: str | None = None,
    source_id: str | None = None,
    user_id: str | None = None,
    expected: int = 0,
    timeout: int | None = None,
    interval: float | None = None,
):
    """
    similarity_search() that tolerates Atlas Vector Search lag.

    Atlas maintains the vector index asynchronously, so chunks
    written a moment ago are not searchable straight away and a
    freshly created index is not queryable at all. Searching
    once and giving up is what made the first AI review of a
    newly uploaded source fail with "No vector chunks found".

    Strategy:

        1. Retry the vector search until the index catches up.
        2. Fall back to a direct collection read if it does not.
        3. Re-raise the search error only when nothing is stored,
           so a genuinely broken index still surfaces.
    """

    if timeout is None:
        timeout = VECTOR_SEARCH_SYNC_TIMEOUT

    if interval is None:
        interval = VECTOR_SEARCH_SYNC_INTERVAL

    # Wait for as many chunks as the caller can actually use.
    target = (
        max(1, min(k, expected))
        if expected
        else 1
    )

    deadline = time.monotonic() + timeout

    chunks = []
    last_error = None
    attempt = 0

    while True:

        attempt += 1

        try:

            chunks = similarity_search(
                query=query,
                k=k,
                project_id=project_id,
                source_id=source_id,
                user_id=user_id,
            )

            last_error = None

            if len(chunks) >= target:

                if attempt > 1:
                    print(
                        f"[DEBUG] Vector index caught up "
                        f"on attempt {attempt}"
                    )

                return chunks

        except Exception as exc:

            # A still-building index can reject the query
            # outright. Keep waiting rather than failing.
            chunks = []
            last_error = exc

        if time.monotonic() >= deadline:
            break

        print(
            f"[DEBUG] Waiting for vector index "
            f"(attempt {attempt}, "
            f"{len(chunks)}/{target} chunks)"
        )

        time.sleep(interval)

    # Partial results are still usable.
    if chunks:

        print(
            f"[WARN] Vector index returned only "
            f"{len(chunks)}/{target} chunks after {timeout}s"
        )

        return chunks

    # Indexing is behind. The chunks themselves are stored,
    # so read them directly instead of failing the review.
    fallback = fetch_chunks(
        k=k,
        project_id=project_id,
        source_id=source_id,
        user_id=user_id,
    )

    if fallback:

        print(
            f"[WARN] Vector index still not ready after "
            f"{timeout}s. Falling back to a direct chunk "
            f"read ({len(fallback)} chunks, unranked)."
        )

        return fallback

    # Nothing stored either, so any search error was real.
    if last_error is not None:
        raise last_error

    return []































