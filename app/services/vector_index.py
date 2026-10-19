import time

from app.db.mongodb import document_chunks_collection
from app.core.config import (
    VECTOR_INDEX_NAME,
    VECTOR_INDEX_READY_TIMEOUT,
)


VECTOR_INDEX_DEFINITION = {
    "fields": [
        {
            "type": "vector",
            "path": "embedding",
            "numDimensions": 384,
            "similarity": "cosine",
        },
        {
            "type": "filter",
            "path": "project_id",
        },
        {
            "type": "filter",
            "path": "source_id",
        },
        {
            "type": "filter",
            "path": "user_id",
        },
    ]
}


# ============================================================
# REQUIRED FILTER PATHS
#
# similarity_search() pre-filters on these paths. Atlas
# rejects a pre-filter on a path the index does not declare
# as a filter, so an index created before user_id existed
# has to be updated in place.
# ============================================================

REQUIRED_FILTER_PATHS = {
    field["path"]
    for field in VECTOR_INDEX_DEFINITION["fields"]
    if field["type"] == "filter"
}


# ============================================================
# WAIT UNTIL THE INDEX IS QUERYABLE
#
# create_search_index() and update_search_index() are
# asynchronous: they only start the build. Querying a PENDING
# or BUILDING index returns nothing, which is why the very
# first AI review after a fresh database failed with
# "No vector chunks found".
# ============================================================

def wait_until_queryable(
    timeout: int | None = None,
    interval: float = 2.0,
) -> bool:

    if timeout is None:
        timeout = VECTOR_INDEX_READY_TIMEOUT

    if timeout <= 0:
        return False

    deadline = time.monotonic() + timeout

    while True:

        try:

            index = next(
                (
                    i
                    for i in document_chunks_collection
                    .list_search_indexes()
                    if i.get("name") == VECTOR_INDEX_NAME
                ),
                None,
            )

            if index and index.get("queryable"):

                print(
                    f"Vector Search index "
                    f"'{VECTOR_INDEX_NAME}' is queryable."
                )

                return True

            status = (
                index.get("status")
                if index
                else "MISSING"
            )

        except Exception as exc:

            # Never let a readiness check break startup.
            print(
                f"Could not read Vector Search index "
                f"status: {exc}"
            )

            return False

        if time.monotonic() >= deadline:

            print(
                f"Vector Search index "
                f"'{VECTOR_INDEX_NAME}' is still "
                f"'{status}' after {timeout}s. "
                "Continuing startup; searches retry until "
                "it becomes queryable."
            )

            return False

        print(
            f"Waiting for Vector Search index "
            f"'{VECTOR_INDEX_NAME}' (status: {status})..."
        )

        time.sleep(interval)


def ensure_vector_index():

    print(
        f"Checking Vector Search index: "
        f"{VECTOR_INDEX_NAME}"
    )

    existing_indexes = list(
        document_chunks_collection.list_search_indexes()
    )

    for index in existing_indexes:

        if index.get("name") == VECTOR_INDEX_NAME:

            print(
                f"Vector Search index "
                f"'{VECTOR_INDEX_NAME}' already exists."
            )

            definition = (
                index.get("latestDefinition")
                or {}
            )

            print(
                "Existing index definition:"
            )

            print(
                definition
            )

            # ------------------------------------------------
            # Check the existing filter paths
            # ------------------------------------------------

            existing_filter_paths = {
                field.get("path")
                for field in definition.get(
                    "fields",
                    [],
                )
                if field.get("type") == "filter"
            }

            missing_filter_paths = (
                REQUIRED_FILTER_PATHS
                - existing_filter_paths
            )

            if not missing_filter_paths:

                # The index may still be building from an
                # earlier run, so confirm it is queryable.
                wait_until_queryable()

                return

            # ------------------------------------------------
            # Update the index so the missing filter paths
            # become usable in pre-filters
            # ------------------------------------------------

            print(
                f"Missing filter paths: "
                f"{sorted(missing_filter_paths)}"
            )

            document_chunks_collection.update_search_index(
                VECTOR_INDEX_NAME,
                VECTOR_INDEX_DEFINITION,
            )

            print(
                f"Vector Search index "
                f"'{VECTOR_INDEX_NAME}' update started. "
                "Filtering by user_id works once the "
                "index finishes rebuilding."
            )

            wait_until_queryable()

            return

    document_chunks_collection.create_search_index(
        {
            "name": VECTOR_INDEX_NAME,
            "type": "vectorSearch",
            "definition": VECTOR_INDEX_DEFINITION,
        }
    )

    print(
        f"Vector Search index "
        f"'{VECTOR_INDEX_NAME}' creation started."
    )

    wait_until_queryable()