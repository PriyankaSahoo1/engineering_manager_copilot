from app.core.config import MONGODB_COLLECTION
from app.db.mongodb import Emc_db


# ============================================================
# COLLECTIONS TO DELETE
# ============================================================

COLLECTIONS = [
    "projects",
    "sources",
    "findings",
    "evidence",
    "questions",
    "decisions",
    "changes",
    "review_brief",
    "users",

    # Vector chunks collection
    MONGODB_COLLECTION,
]


# ============================================================
# DELETE ALL VECTOR SEARCH INDEXES
# ============================================================

def delete_vector_indexes():

    if MONGODB_COLLECTION not in Emc_db.list_collection_names():
        print(
            f"Collection '{MONGODB_COLLECTION}' does not exist."
        )
        return

    collection = Emc_db[MONGODB_COLLECTION]

    try:
        indexes = list(
            collection.list_search_indexes()
        )

        if not indexes:
            print("No Vector Search indexes found.")
            return

        for index in indexes:

            index_name = index.get("name")

            if not index_name:
                continue

            print(
                f"Deleting Vector Search index: "
                f"{index_name}"
            )

            collection.drop_search_index(
                index_name
            )

        print("All Vector Search indexes deleted.")

    except Exception as exc:

        print(
            "Failed to delete Vector Search indexes:"
        )

        print(exc)


# ============================================================
# DELETE COLLECTIONS
# ============================================================

def delete_collections():

    existing_collections = set(
        Emc_db.list_collection_names()
    )

    for collection_name in COLLECTIONS:

        if collection_name not in existing_collections:

            print(
                f"Collection '{collection_name}' "
                f"does not exist."
            )

            continue

        print(
            f"Dropping collection: "
            f"{collection_name}"
        )

        Emc_db.drop_collection(
            collection_name
        )

        print(
            f"Deleted: {collection_name}"
        )


# ============================================================
# MAIN CLEANUP
# ============================================================

def cleanup_database():

    print("=" * 60)

    print(
        "ENGINEERING MANAGER COPILOT "
        "DATABASE CLEANUP"
    )

    print("=" * 60)

    print()

    # --------------------------------------------------------
    # 1. Delete Vector Search indexes first
    # --------------------------------------------------------

    print(
        "Step 1: Deleting Vector Search indexes..."
    )

    delete_vector_indexes()

    print()

    # --------------------------------------------------------
    # 2. Delete collections
    # --------------------------------------------------------

    print(
        "Step 2: Deleting MongoDB collections..."
    )

    delete_collections()

    print()

    # --------------------------------------------------------
    # 3. Verify
    # --------------------------------------------------------

    print(
        "Step 3: Verifying cleanup..."
    )

    remaining = Emc_db.list_collection_names()

    application_collections = [
        name
        for name in remaining
        if name in COLLECTIONS
    ]

    if not application_collections:

        print(
            "All Engineering Manager Copilot "
            "collections deleted successfully."
        )

    else:

        print(
            "Some collections still exist:"
        )

        for name in application_collections:
            print(f"  - {name}")

    print()

    print("=" * 60)

    print("CLEANUP COMPLETED")

    print("=" * 60)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    cleanup_database()

