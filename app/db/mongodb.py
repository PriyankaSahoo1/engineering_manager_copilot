import os

from dotenv import load_dotenv
from pymongo import MongoClient


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

MONGODB_URI = os.getenv("MONGODB_URI")

MONGODB_DATABASE = os.getenv(
    "MONGODB_DATABASE",
    "emc_db",
)


if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI is not configured in .env"
    )


# ============================================================
# MONGODB CLIENT
# ============================================================

client = MongoClient(
    MONGODB_URI
)


# ============================================================
# DATABASE
# ============================================================

Emc_db = client[
    MONGODB_DATABASE
]


# ============================================================
# COLLECTIONS
# ============================================================

users_collection = Emc_db[
"users"]

projects_collection = Emc_db[
    "projects"
]

sources_collection = Emc_db[
    "sources"
]

document_chunks_collection = Emc_db[
    "document_chunks"
]

findings_collection = Emc_db[
    "findings"
]


questions_collection = Emc_db[
    "questions"
]

decisions_collection = Emc_db[
    "decisions"
]

changes_collection = Emc_db[
    "changes"
]

# NEW
review_brief_collection = Emc_db[
    "review_brief"
]





# ============================================================
# ALL COLLECTIONS
# ============================================================

ALL_COLLECTIONS = {

    "projects":
        projects_collection,

    "sources":
        sources_collection,

    "document_chunks":
        document_chunks_collection,

    "findings":
        findings_collection,

    "questions":
        questions_collection,

    "decisions":
        decisions_collection,

    "changes":
        changes_collection,

    "review_brief":review_brief_collection
}


# ============================================================
# PING MONGODB
# ============================================================

def ping_mongodb():

    try:

        client.admin.command(
            "ping"
        )

        print(
            "MongoDB connected successfully."
        )

        return True

    except Exception as exc:

        print(
            "MongoDB connection failed:",
            exc
        )

        return False


# ============================================================
# ENSURE COLLECTIONS
# ============================================================

def ensure_collections():

    existing_collections = (
        Emc_db.list_collection_names()
    )

    for collection_name in ALL_COLLECTIONS:

        if collection_name not in existing_collections:

            Emc_db.create_collection(
                collection_name
            )

            print(
                f"Created collection: "
                f"{collection_name}"
            )

        else:

            print(
                f"Collection already exists: "
                f"{collection_name}"
            )


# ============================================================
# GET COLLECTION
# ============================================================

def get_collection(
    collection_name: str,
):

    if collection_name not in ALL_COLLECTIONS:

        raise ValueError(
            f"Unknown collection: "
            f"{collection_name}"
        )

    return ALL_COLLECTIONS[
        collection_name
    ]