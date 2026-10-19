
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from langchain_groq import ChatGroq
from app.core.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
)
from app.schemas.ai_review import (
    AIReviewLLMOutput,
)
from app.services.vector_store import (
    similarity_search,
    search_chunks,
    count_chunks,
)
from app.services.document_processor import (
    process_document,
)
from app.services.vector_store import (
    add_documents,
    get_vector_store,
)
from app.services.ai_review_storage import (
    store_ai_review,
    rebuild_review_brief,
)
from app.db.mongodb import (
    projects_collection,
    sources_collection,
    review_brief_collection
)


# ============================================================
# PARALLEL REVIEW CONFIGURATION
# ============================================================

# Every worker holds an open Groq request, so this is
# capped well below the upload limit to stay inside the
# Groq rate limit.

MAX_REVIEW_WORKERS = 4

REVIEW_TOP_K = 3
# from app.services.ai_review_service import (
#     get_ai_review_brief,
# )


# ============================================================
# AI REVIEW PROMPT
# ============================================================

AI_REVIEW_PROMPT = """
You are an Engineering Manager AI Review assistant.

Analyze ONLY the supplied project objective, analysis focus,
and retrieved source chunks.

Do not use outside knowledge.
Do not invent facts.
Do not invent evidence.


============================================================
PROJECT OBJECTIVE
============================================================

{objective}


============================================================
ANALYSIS FOCUS
============================================================

{analysis_focus}


============================================================
RETRIEVED SOURCE CHUNKS
============================================================

{retrieved_chunks}


============================================================
FINDINGS
============================================================

A finding is an evidence-supported observation, issue,
risk, gap, or important point.

For every finding:

- Provide a clear title.
- Provide a concise summary.
- Assign a priority. Use exactly one of:
  high, medium, low (lowercase).
- Assign a category.
- Provide the section number the finding refers to,
  for example "5.4". Use the section number only,
  without the section title.
- Provide the page number the finding refers to.
- Provide confidence between 0 and 1.
- Set needsAttention to true only when attention,
  clarification, or action is required.
- If needsAttention is true, provide suggestedQuestion.
- Provide evidence supporting the finding.

Every evidence item must contain:

- page
- section
- quote

Every evidence quote MUST be an exact quote from the
retrieved source chunks.

Do not invent evidence.

Do not generate:

- evidence ID
- source ID
- source name

The application will generate the evidence ID and obtain
the source ID and source name from the application context.


============================================================
CHANGES
============================================================

A change represents an actual or explicitly planned
modification described in the supplied source context.

For every change provide:

- title
- detail
- changeType
- section
- page

changeType must be exactly one of (lowercase):

- added        (something new was introduced)
- modified     (something existing was altered)
- removed      (something was deleted)
- unresolved   (still open since the previous review)
- planned      (an explicitly planned modification)

section must be the section number only,
for example "8.2", without the section title.

Only create a change when the supplied source chunks
support an actual or explicitly planned modification.

Do not create a change merely because a finding exists.

Do not invent changes.


============================================================
IMPORTANT
============================================================

Return ONLY structured output.

Return ONLY valid JSON.

Do not call any tools.
Do not use function calls.
Do not return markdown.
Do not wrap the JSON in ```json.

The output must contain:

- findings
- changes

Do not create unsupported findings.
Do not create unsupported changes.
Do not invent evidence.
"""


# ============================================================
# FORMAT RETRIEVED CHUNKS
# ============================================================

def _format_chunks(
    chunks: list[dict],
) -> str:
    """
    Convert retrieved vector chunks into readable
    context for the LLM.
    """

    parts = []

    for chunk in chunks:

        metadata = chunk.get(
            "metadata",
            {},
        )

        parts.append(
            f"""
CHUNK ID:
{metadata.get("chunk_id")}

SOURCE ID:
{metadata.get("source_id")}

SOURCE NAME:
{metadata.get("source_name")}

PAGE:
{metadata.get("page_number")}

SECTION:
{metadata.get("section")}

TEXT:
{chunk.get("text", "")}

------------------------------------------------------------
"""
        )

    return "\n".join(parts)


# ============================================================
# GENERATE AI REVIEW
# ============================================================

def generate_ai_review(
    project_id: str,
    source_id: str,
    user_id: str,
    k: int = 3,
) -> AIReviewLLMOutput:

    """
    Complete AI review generation flow.

    Every MongoDB read and every vector search is scoped
    to user_id, so a review only ever sees the logged in
    user's own project and uploaded sources.

    project_id + user_id
        ↓
    project
        ↓
    source
        ↓
    file_path
        ↓
    document processing
        ↓
    vector storage
        ↓
    objective + analysis_focus
        ↓
    vector search
        ↓
    Groq
        ↓
    structured AI review
    """

    print("\n" + "=" * 70)
    print("[DEBUG] GENERATE AI REVIEW")
    print("=" * 70)

    print(
        f"[DEBUG] user_id = {user_id}"
    )

    # ========================================================
    # 1. GET PROJECT
    # ========================================================

    print(
        "\n[DEBUG] Step 1: Getting project"
    )

    project = projects_collection.find_one(
        {
            "_id": project_id,
            "user_id": user_id,
        }
    )

    if not project:

        raise ValueError(
            "Project not found."
        )

    print(
        "[SUCCESS] Project found"
    )

    # ========================================================
    # 2. GET SOURCE
    # ========================================================

    print(
        "\n[DEBUG] Step 2: Getting source"
    )

    source = sources_collection.find_one(
        {
            "_id": source_id,
            "project_id": project_id,
            "user_id": user_id,
        }
    )

    if not source:

        raise ValueError(
            "Source not found for this project."
        )

    print(
        "[SUCCESS] Source found"
    )

    # ========================================================
    # 3. GET FILE PATH
    # ========================================================

    file_path = source.get(
        "file_path"
    )

    if not file_path:

        raise ValueError(
            "File path is missing from source."
        )

    print(
        f"[DEBUG] file_path = {file_path}"
    )

    # ========================================================
    # 4. PROCESS DOCUMENT
    # 5. STORE DOCUMENTS + EMBEDDINGS
    #
    # Ingestion runs once per source. Re-triggering a review
    # used to re-chunk and re-insert the same file every time,
    # which piled up duplicate chunks and pushed near
    # identical text into the top k results.
    # ========================================================

    stored_count = count_chunks(
        project_id=project_id,
        source_id=source_id,
        user_id=user_id,
    )

    if stored_count:

        print(
            f"\n[DEBUG] Step 3-4: Source already has "
            f"{stored_count} stored chunks, skipping "
            f"processing"
        )

    else:

        print(
            "\n[DEBUG] Step 3: Processing document"
        )

        documents = process_document(
            file_path=file_path,
            project_id=project_id,
            source_id=source_id,
            user_id=user_id,
        )

        if not documents:

            raise ValueError(
                "No documents were created from source."
            )

        print(
            f"[SUCCESS] Documents created = "
            f"{len(documents)}"
        )

        print(
            "\n[DEBUG] Step 4: Storing documents"
        )

        add_documents(
            documents
        )

        stored_count = len(
            documents
        )

        print(
            "[SUCCESS] Documents stored"
        )

    # ========================================================
    # 6. GET OBJECTIVE
    # ========================================================

    objective = project.get(
        "objective",
        "",
    )

    print(
        f"[DEBUG] objective = {objective}"
    )

    # ========================================================
    # 7. GET ANALYSIS FOCUS
    # ========================================================

    analysis_focus = project.get(
        "analysis_focus",
        "",
    )

    print(
        f"[DEBUG] analysis_focus = "
        f"{analysis_focus}"
    )

    # ========================================================
    # 8. BUILD QUERY
    # ========================================================

    query = f"""
Objective:
{objective}

Analysis Focus:
{analysis_focus}
""".strip()

    if not query.strip():

        raise ValueError(
            "Project objective and analysis_focus "
            "are missing."
        )

    # ========================================================
    # 9. VECTOR SEARCH
    # ========================================================

    print(
        "\n[DEBUG] Step 5: Vector search"
    )

    # Atlas indexes new chunks asynchronously, so the chunks
    # written a moment ago are not searchable straight away.
    # search_chunks() waits for the index to catch up and
    # falls back to a direct read, instead of failing the
    # first review of a newly uploaded source.

    chunks = search_chunks(
        query=query,
        k=k,
        project_id=project_id,
        source_id=source_id,
        user_id=user_id,
        expected=stored_count,
    )

    if not chunks:

        raise ValueError(
            "No vector chunks found "
            "for this project and source."
        )

    print(
        f"[SUCCESS] Vector chunks found = "
        f"{len(chunks)}"
    )

    # ========================================================
    # 10. FORMAT CHUNKS
    # ========================================================

    retrieved_chunks = _format_chunks(
        chunks
    )

    # ========================================================
    # 11. BUILD PROMPT
    # ========================================================

    prompt = AI_REVIEW_PROMPT.format(
        objective=objective,
        analysis_focus=analysis_focus,
        retrieved_chunks=retrieved_chunks,
    )

    # ========================================================
    # 12. CHECK GROQ CONFIG
    # ========================================================

    if not GROQ_API_KEY:

        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    if not GROQ_MODEL:

        raise RuntimeError(
            "GROQ_MODEL is not configured."
        )

    # ========================================================
    # 13. CREATE GROQ LLM
    # ========================================================

    print(
        "\n[DEBUG] Step 6: Calling Groq"
    )

    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0,
    )

    # ========================================================
    # 14. STRUCTURED OUTPUT
    # ========================================================

    structured_llm = (
        llm.with_structured_output(
            AIReviewLLMOutput,
            method="json_mode",
        )
    )

    # ========================================================
    # 15. CALL GROQ
    # ========================================================

    review = structured_llm.invoke(
        prompt
    )

    print(
        "[SUCCESS] Groq response received"
    )

    # ========================================================
    # 16. RETURN REVIEW
    # ========================================================

    print(
        f"[DEBUG] findings = "
        f"{len(review.findings)}"
    )

    print(
        f"[DEBUG] changes = "
        f"{len(review.changes)}"
    )

    return review


# ============================================================
# REVIEW ONE SOURCE
# ============================================================

def review_one_source(
    project_id: str,
    user_id: str,
    source: dict,
) -> dict:
    """
    Generate and store the AI review for a single source.

    Runs inside a worker thread, so it raises on failure and
    the caller records which source failed.

    The Review Brief is deliberately NOT built here. It is
    built once, after every source has been stored.
    """

    source_id = source.get(
        "_id"
    )

    if not source_id:

        raise ValueError(
            "Source ID is missing."
        )

    print(
        f"[DEBUG] Reviewing source {source_id}"
    )

    review = generate_ai_review(
        project_id=project_id,
        source_id=source_id,
        user_id=user_id,
        k=REVIEW_TOP_K,
    )

    store_result = store_ai_review(
        project_id=project_id,
        source_id=source_id,
        user_id=user_id,
        review=review,
        build_brief=False,
    )

    print(
        f"[SUCCESS] Reviewed source {source_id}"
    )

    return {

        "sourceId":
            source_id,

        "sourceName":
            source.get("source_name"),

        "findingCount":
            store_result.get(
                "findingCount",
                0,
            ),

        "questionCount":
            store_result.get(
                "questionCount",
                0,
            ),

        "changeCount":
            store_result.get(
                "changeCount",
                0,
            ),
    }


# ============================================================
# RUN AI TRIGGER
# ============================================================

def run_ai_trigger(
    project_id: str,
    user_id: str,
):
    """
    Entry point for:

    POST /api/v1/projects/{project_id}/ai-trigger

    Every source uploaded to the project is reviewed, and
    the sources are reviewed in parallel.

    Flow:

        project_id + user_id
             |
        get project
             |
        get every source
             |
        status = processing
             |
        warm shared singletons
             |
        review sources in parallel
             |
        build Review Brief once
             |
        status = completed / partial
             |
        return aggregated result
    """

    print("\n" + "=" * 70)
    print("[DEBUG] RUN AI TRIGGER")
    print("=" * 70)

    print(
        f"[DEBUG] project_id = {project_id}"
    )

    print(
        f"[DEBUG] user_id = {user_id}"
    )

    # ========================================================
    # 1. GET PROJECT
    # ========================================================

    project = projects_collection.find_one(
        {
            "_id": project_id,
            "user_id": user_id,
        }
    )

    if not project:

        print(
            "[ERROR] Project not found"
        )

        raise ValueError(
            "Project not found."
        )

    print(
        "[SUCCESS] Project found"
    )

    # ========================================================
    # 2. GET EVERY SOURCE
    # ========================================================

    sources = list(
        sources_collection.find(
            {
                "project_id": project_id,
                "user_id": user_id,
            }
        )
    )

    if not sources:

        raise ValueError(
            "No sources found for this project."
        )

    print(
        f"[DEBUG] sources to review = {len(sources)}"
    )

    # ========================================================
    # 3. UPDATE PROJECT -> PROCESSING
    # ========================================================

    print(
        "\n[DEBUG] Setting AI review status = processing"
    )

    projects_collection.update_one(
        {
            "_id": project_id,
            "user_id": user_id,
        },
        {
            "$set": {

                "ai_review_status":
                    "processing",

                "ai_review_started_at":
                    datetime.now(
                        timezone.utc
                    ),

                "ai_review_error":
                    None,
            },

            # Remove the old nested AI review object
            # and the derived counters so the project
            # keeps a single flat shape.
            "$unset": {
                "ai_review": "",
                "ai_review_ready": "",
                "evidence_count": "",
                "change_count": "",
            },
        },
    )

    print(
        "[SUCCESS] Project status = processing"
    )

    try:

        # ====================================================
        # 4. WARM SHARED SINGLETONS
        #
        # get_vector_store() and get_embeddings() are lazy
        # singletons with no locking. Letting four worker
        # threads race to build them would load the
        # embedding model several times over, so build them
        # here, on one thread, before the fan out.
        # ====================================================

        print(
            "\n[DEBUG] Warming vector store and embeddings"
        )

        get_vector_store()

        # ====================================================
        # 5. REVIEW EVERY SOURCE IN PARALLEL
        # ====================================================

        reviewed = []
        failed = []

        workers = min(
            MAX_REVIEW_WORKERS,
            len(sources),
        )

        print(
            f"\n[DEBUG] Reviewing {len(sources)} sources "
            f"with {workers} workers"
        )

        with ThreadPoolExecutor(
            max_workers=workers,
        ) as executor:

            futures = {
                executor.submit(
                    review_one_source,
                    project_id,
                    user_id,
                    source,
                ): source
                for source in sources
            }

            for future in as_completed(futures):

                source = futures[future]

                try:

                    reviewed.append(
                        future.result()
                    )

                except Exception as exc:

                    traceback.print_exc()

                    failed_id = source.get(
                        "_id"
                    )

                    print(
                        f"[ERROR] Source {failed_id} "
                        f"failed: {exc}"
                    )

                    failed.append({

                        "sourceId":
                            failed_id,

                        "sourceName":
                            source.get("source_name"),

                        "error":
                            str(exc),
                    })

        # ====================================================
        # 6. FAIL WHEN NOTHING SUCCEEDED
        # ====================================================

        if not reviewed:

            raise ValueError(
                "AI review failed for every source."
            )

        # ====================================================
        # 7. BUILD REVIEW BRIEF ONCE
        #
        # Built here, on one thread, after every source has
        # been stored. Building it inside the workers would
        # race, because each build reads the whole project
        # back out of MongoDB and upserts the same document.
        # ====================================================

        print(
            "\n[DEBUG] Building Review Brief"
        )

        rebuild_review_brief(
            project_id=project_id,
            user_id=user_id,
        )

        print(
            "[SUCCESS] Review Brief stored"
        )

        # ====================================================
        # 8. AGGREGATE COUNTS
        # ====================================================

        finding_count = sum(
            item["findingCount"]
            for item in reviewed
        )

        question_count = sum(
            item["questionCount"]
            for item in reviewed
        )

        change_count = sum(
            item["changeCount"]
            for item in reviewed
        )

        status = (
            "completed"
            if not failed
            else "partial"
        )

        # ====================================================
        # 9. UPDATE PROJECT
        # ====================================================

        print(
            f"\n[DEBUG] Setting AI review status = {status}"
        )

        projects_collection.update_one(
            {
                "_id": project_id,
                "user_id": user_id,
            },
            {
                "$set": {

                    "ai_review_status":
                        status,

                    "ai_review_generated_at":
                        datetime.now(
                            timezone.utc
                        ),

                    "source_count":
                        len(sources),

                    "finding_count":
                        finding_count,

                    "question_count":
                        question_count,

                    "ai_review_error":
                        None,
                },

                "$unset": {
                    "ai_review": "",
                    "ai_review_ready": "",
                    "evidence_count": "",
                    "change_count": "",
                },
            },
        )

        # ====================================================
        # 10. FINAL RESULT
        # ====================================================

        result = {

            "projectId":
                project_id,

            "userId":
                user_id,

            "status":
                status,

            "aiReviewReady":
                True,

            "sourceCount":
                len(sources),

            "reviewedCount":
                len(reviewed),

            "failedCount":
                len(failed),

            "findingCount":
                finding_count,

            "questionCount":
                question_count,

            "changeCount":
                change_count,

            "sources":
                reviewed,

            "failed":
                failed,
        }

        print(
            "\n[DEBUG] FINAL AI REVIEW RESULT"
        )

        print(
            result
        )

        print(
            "\n" + "=" * 70
        )

        print(
            "[SUCCESS] AI TRIGGER COMPLETED"
        )

        print(
            "=" * 70
        )

        return result

    except Exception as exc:

        # ====================================================
        # 11. UPDATE PROJECT -> FAILED
        # ====================================================

        projects_collection.update_one(
            {
                "_id": project_id,
                "user_id": user_id,
            },
            {
                "$set": {

                    "ai_review_status":
                        "failed",

                    "ai_review_failed_at":
                        datetime.now(
                            timezone.utc
                        ),

                    "ai_review_error":
                        str(exc),
                },

                "$unset": {
                    "ai_review": "",
                    "ai_review_ready": "",
                    "evidence_count": "",
                    "change_count": "",
                },
            },
        )

        raise


def get_ai_review_brief(
    project_id: str,
    user_id: str,
):

    review_brief = (
        review_brief_collection.find_one(
            {
                "projectId": project_id,
                "userId": user_id,
            },
            {
                "_id": 0
            }
        )
    )

    if not review_brief:

        raise ValueError(
            f"Review brief not found "
            f"for project '{project_id}'."
        )

    return review_brief