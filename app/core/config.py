import os
from dotenv import load_dotenv

load_dotenv()



MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "emc_db")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "document_chunks")
VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "vector_index")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash")
EMBEDDING_DIMENSIONS = 384



# ============================================================
# CHUNKING
# ============================================================

MAX_CHARACTERS = int(
    os.getenv(
        "MAX_CHARACTERS",
        "2000"
    )
)

NEW_AFTER_N_CHARS = int(
    os.getenv(
        "NEW_AFTER_N_CHARS",
        "1500"
    )
)

COMBINE_TEXT_UNDER_N_CHARS = int(
    os.getenv(
        "COMBINE_TEXT_UNDER_N_CHARS",
        "500"
    )
)

OVERLAP = int(
    os.getenv(
        "OVERLAP",
        "200"
    )
)


# ============================================================
# ATLAS VECTOR SEARCH INDEX SYNC
#
# Atlas builds and updates the vector index asynchronously, so
# chunks are not searchable the instant they are written and a
# newly created index is not queryable straight away. These
# settings bound how long the app waits for the index to catch
# up before it gives up.
# ============================================================

# How long a search waits for freshly written chunks to become
# searchable. Free / shared tiers need the higher end.
VECTOR_SEARCH_SYNC_TIMEOUT = int(
    os.getenv(
        "VECTOR_SEARCH_SYNC_TIMEOUT",
        "45"
    )
)

# Delay between search retries while waiting.
VECTOR_SEARCH_SYNC_INTERVAL = float(
    os.getenv(
        "VECTOR_SEARCH_SYNC_INTERVAL",
        "1.5"
    )
)

# How long startup waits for the vector index to become
# queryable. 0 disables the wait.
VECTOR_INDEX_READY_TIMEOUT = int(
    os.getenv(
        "VECTOR_INDEX_READY_TIMEOUT",
        "180"
    )
)
