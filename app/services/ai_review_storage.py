import re
from datetime import datetime, timezone
from uuid import uuid4

from app.db.mongodb import (
    sources_collection,
    findings_collection,
    questions_collection,
    changes_collection,
    review_brief_collection,
)

from app.schemas.ai_review import (
    AIReviewLLMOutput,
)


# ============================================================
# RESPONSE CONTRACT
#
# The Review Brief response shape is fixed:
#
#     id
#     projectId
#     status
#     generatedAt
#     sourceCount
#     findingCount
#     questionCount
#     changeCount
#     attentionCount
#     findings[]
#     questions[]
#     changes[]
# ============================================================

PRIORITY_VALUES = {
    "high",
    "medium",
    "low",
}

DEFAULT_PRIORITY = "medium"


CHANGE_TYPE_VALUES = {
    "added",
    "modified",
    "removed",
    "unresolved",
    "planned",
}

CHANGE_TYPE_SYNONYMS = {

    "add": "added",
    "addition": "added",
    "new": "added",
    "introduced": "added",
    "implementation": "added",
    "implemented": "added",

    "change": "modified",
    "changed": "modified",
    "modification": "modified",
    "update": "modified",
    "updated": "modified",
    "partial": "modified",

    "delete": "removed",
    "deleted": "removed",
    "removal": "removed",

    "open": "unresolved",
    "outstanding": "unresolved",
    "pending": "unresolved",
    "incomplete": "unresolved",

    "plan": "planned",
    "proposed": "planned",
    "future": "planned",
}

DEFAULT_CHANGE_TYPE = "modified"


SECTION_NUMBER_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)*)"
)


# ============================================================
# CURRENT TIME
# ============================================================

def get_current_time():
    return datetime.now(
        timezone.utc
    )


# ============================================================
# NEW REVIEW BRIEF ID
# ============================================================

def new_review_brief_id() -> str:
    """
    Random UUID for the Review Brief document.
    """

    return str(
        uuid4()
    )


# ============================================================
# ISO 8601 TIMESTAMP
# 2026-08-18T10:30:00Z
# ============================================================

def to_iso_z(value):

    if value is None:
        return None

    if isinstance(value, str):
        return value

    if value.tzinfo is None:

        value = value.replace(
            tzinfo=timezone.utc
        )

    return (
        value
        .astimezone(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


# ============================================================
# NORMALIZE PRIORITY
# high | medium | low
# ============================================================

def normalize_priority(value):

    if not value:
        return DEFAULT_PRIORITY

    normalized = str(value).strip().lower()

    if normalized in PRIORITY_VALUES:
        return normalized

    return DEFAULT_PRIORITY


# ============================================================
# NORMALIZE CHANGE TYPE
# added | modified | removed | unresolved | planned
# ============================================================

def normalize_change_type(value):

    if not value:
        return DEFAULT_CHANGE_TYPE

    normalized = str(value).strip().lower()

    if normalized in CHANGE_TYPE_VALUES:
        return normalized

    return CHANGE_TYPE_SYNONYMS.get(
        normalized,
        DEFAULT_CHANGE_TYPE,
    )


# ============================================================
# NORMALIZE SECTION
# "5.4 Database Recovery" -> "5.4"
# ============================================================

def normalize_section(value):

    if not value:
        return None

    text = str(value).strip()

    if not text:
        return None

    match = SECTION_NUMBER_PATTERN.match(
        text
    )

    if match:
        return match.group(1)

    return text


# ============================================================
# SHAPE EVIDENCE
# ============================================================

def shape_evidence(
    evidence: dict,
    source_id=None,
    source_name=None,
):

    return {

        "id":
            evidence.get("id"),

        "sourceId":
            evidence.get("sourceId")
            or evidence.get("sourceID")
            or source_id,

        "sourceName":
            evidence.get("sourceName")
            or source_name,

        "page":
            evidence.get("page"),

        "section":
            evidence.get("section"),

        "quote":
            evidence.get("quote"),
    }


# ============================================================
# SHAPE FINDING
#
# Accepts either a findings_collection document
# or an already stored Review Brief finding.
# ============================================================

def shape_finding(
    finding: dict,
):

    evidence_list = [
        shape_evidence(
            evidence,
            source_id=finding.get("source_id"),
        )
        for evidence in (
            finding.get("evidence") or []
        )
    ]

    # --------------------------------------------------------
    # SECTION / PAGE
    #
    # Fall back to the first evidence item when the model
    # did not attach them to the finding itself.
    # --------------------------------------------------------

    section = normalize_section(
        finding.get("section")
    )

    page = finding.get("page")

    if evidence_list:

        if not section:

            section = normalize_section(
                evidence_list[0].get("section")
            )

        if page is None:

            page = evidence_list[0].get("page")

    return {

        "id":
            finding.get("id")
            or finding.get("_id"),

        "title":
            finding.get("title"),

        "summary":
            finding.get("summary"),

        "priority":
            normalize_priority(
                finding.get("priority")
            ),

        "category":
            finding.get("category"),

        "section":
            section,

        "page":
            page,

        "confidence":
            finding.get("confidence"),

        "needsAttention":
            bool(
                finding.get(
                    "needsAttention",
                    False,
                )
            ),

        "suggestedQuestion":
            finding.get("suggestedQuestion"),

        "evidence":
            evidence_list,
    }


# ============================================================
# SHAPE QUESTION
# ============================================================

def shape_question(
    question: dict,
):

    return {

        "id":
            question.get("id")
            or question.get("_id"),

        "text":
            question.get("text")
            or question.get("question"),

        "priority":
            normalize_priority(
                question.get("priority")
            ),

        "findingId":
            question.get("findingId")
            or question.get("finding_id"),

        "evidenceId":
            question.get("evidenceId")
            or question.get("evidence_id"),
    }


# ============================================================
# SHAPE CHANGE
# ============================================================

def shape_change(
    change: dict,
):

    return {

        "id":
            change.get("id")
            or change.get("_id"),

        "title":
            change.get("title"),

        "detail":
            change.get("detail"),

        "changeType":
            normalize_change_type(
                change.get("changeType")
            ),

        "section":
            normalize_section(
                change.get("section")
            ),

        "page":
            change.get("page"),
    }


# ============================================================
# STORE AI REVIEW
# ============================================================

def store_ai_review(
    project_id: str,
    source_id: str,
    user_id: str,
    review: AIReviewLLMOutput,
    build_brief: bool = True,
) -> dict:
    """
    Store structured AI review.

    Stores:

        findings
        questions
        changes

    Every stored document carries user_id so the Review
    Brief and all read APIs stay scoped to the owner.

    Evidence is embedded inside findings.

    Review Brief is generated after
    findings/questions/changes are stored.
    """

    print("\n" + "=" * 70)
    print("[DEBUG] STORE AI REVIEW")
    print("=" * 70)

    print(
        f"[DEBUG] user_id = {user_id}"
    )

    # ========================================================
    # 1. GET SOURCE
    # ========================================================

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

    # ========================================================
    # 2. GET SOURCE NAME
    # ========================================================

    source_name = (
        source.get("name")
        or source.get("file_name")
        or source.get("filename")
        or source.get("source_name")
        or "Unknown source"
    )

    print(
        f"[DEBUG] source_name = {source_name}"
    )

    # ========================================================
    # COUNTERS
    # ========================================================

    finding_count = 0
    evidence_count = 0
    question_count = 0
    change_count = 0

    # ========================================================
    # 3. STORE FINDINGS
    # ========================================================

    print(
        "\n[DEBUG] Storing findings"
    )

    for finding in review.findings:

        # ----------------------------------------------------
        # FINDING ID
        # ----------------------------------------------------

        finding_id = (
            f"finding_{uuid4().hex[:12]}"
        )

        # ----------------------------------------------------
        # EVIDENCE
        # ----------------------------------------------------

        evidence_list = []

        for evidence in finding.evidence:

            evidence_id = (
                f"EV-{uuid4().hex[:8]}"
            )

            evidence_document = {

                "id":
                    evidence_id,

                "sourceId":
                    source_id,

                "sourceName":
                    source_name,

                "page":
                    evidence.page,

                "section":
                    evidence.section,

                "quote":
                    evidence.quote,
            }

            evidence_list.append(
                evidence_document
            )

            evidence_count += 1

        # ----------------------------------------------------
        # FINDING DOCUMENT
        # ----------------------------------------------------

        finding_document = {

            "_id":
                finding_id,

            "project_id":
                project_id,

            "source_id":
                source_id,

            "user_id":
                user_id,

            "title":
                finding.title,

            "summary":
                finding.summary,

            "priority":
                normalize_priority(
                    finding.priority
                ),

            "category":
                finding.category,

            "section":
                finding.section,

            "page":
                finding.page,

            "confidence":
                finding.confidence,

            "needsAttention":
                finding.needsAttention,

            "suggestedQuestion":
                finding.suggestedQuestion,

            "evidence":
                evidence_list,

            "created_at":
                get_current_time()
        }

        # ----------------------------------------------------
        # INSERT FINDING
        # ----------------------------------------------------

        findings_collection.insert_one(
            finding_document
        )

        finding_count += 1

        print(
            f"[SUCCESS] Finding stored: "
            f"{finding_id}"
        )

        # ====================================================
        # 4. CREATE QUESTION
        # ====================================================

        if (
            finding.needsAttention
            and finding.suggestedQuestion
        ):

            evidence_id = None

            if evidence_list:

                evidence_id = (
                    evidence_list[0]["id"]
                )

            question_id = (
                f"Q-{uuid4().hex[:8]}"
            )

            question_document = {

                "_id":
                    question_id,

                "project_id":
                    project_id,

                "source_id":
                    source_id,

                "user_id":
                    user_id,

                "finding_id":
                    finding_id,

                "evidence_id":
                    evidence_id,

                "text":
                    finding.suggestedQuestion,

                "priority":
                    normalize_priority(
                        finding.priority
                    ),

                "created_at":
                    get_current_time(),
            }

            questions_collection.insert_one(
                question_document
            )

            question_count += 1

            print(
                f"[SUCCESS] Question stored: "
                f"{question_id}"
            )

    # ========================================================
    # 5. STORE CHANGES
    # ========================================================

    print(
        "\n[DEBUG] Storing changes"
    )

    for change in review.changes:

        change_id = (
            f"C-{uuid4().hex[:8]}"
        )

        change_document = {

            "_id":
                change_id,

            "project_id":
                project_id,

            "source_id":
                source_id,

            "user_id":
                user_id,

            "title":
                change.title,

            "detail":
                change.detail,

            "changeType":
                normalize_change_type(
                    change.changeType
                ),

            "section":
                change.section,

            "page":
                change.page,

            "created_at":
                get_current_time(),
        }

        changes_collection.insert_one(
            change_document
        )

        change_count += 1

        print(
            f"[SUCCESS] Change stored: "
            f"{change_id}"
        )

    # ========================================================
    # 6. BUILD REVIEW BRIEF
    #
    # Skipped when several sources are reviewed in
    # parallel. The caller then builds the brief once,
    # after every source has been stored, so no worker
    # ever rebuilds it from a partial snapshot.
    # ========================================================

    review_brief_id = None

    if build_brief:

        print(
            "\n[DEBUG] Building Review Brief"
        )

        review_brief = rebuild_review_brief(
            project_id=project_id,
            user_id=user_id,
        )

        review_brief_id = review_brief["id"]

        print(
            f"[SUCCESS] Review Brief stored: "
            f"{review_brief_id}"
        )

    else:

        print(
            "\n[DEBUG] Skipping Review Brief "
            "(built once by the caller)"
        )

    # ========================================================
    # 8. RETURN
    # ========================================================

    result = {

        "reviewBriefId":
            review_brief_id,

        "projectId":
            project_id,

        "userId":
            user_id,

        "sourceId":
            source_id,

        "aiReviewReady":
            True,

        "status":
            "completed",

        "findingCount":
            finding_count,

        "evidenceCount":
            evidence_count,

        "questionCount":
            question_count,

        "changeCount":
            change_count,
    }

    print(
        "\n[DEBUG] STORE RESULT"
    )

    print(
        result
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "[SUCCESS] STORE AI REVIEW COMPLETED"
    )

    print(
        "=" * 70
    )

    return result


# ============================================================
# REBUILD REVIEW BRIEF
# ============================================================

def rebuild_review_brief(
    project_id: str,
    user_id: str,
) -> dict:
    """
    Build and upsert the Review Brief from everything
    currently stored for the project.

    Called once per AI trigger, after every source has
    been stored.
    """

    review_brief = build_review_brief(
        project_id=project_id,
        user_id=user_id,
    )

    review_brief_collection.update_one(
        {
            "projectId":
                project_id,

            "userId":
                user_id,
        },
        {
            "$set":
                review_brief
        },
        upsert=True,
    )

    return review_brief


# ============================================================
# BUILD REVIEW BRIEF
# ============================================================

def build_review_brief(
    project_id: str,
    user_id: str,
) -> dict:

    print(
        "\n[DEBUG] BUILD REVIEW BRIEF"
    )

    # ========================================================
    # 1. REVIEW BRIEF ID
    #
    # Reuse the existing id so the brief keeps a stable
    # identity across regenerations. A random UUID is
    # generated the first time.
    # ========================================================

    existing_brief = (
        review_brief_collection.find_one(
            {
                "projectId":
                    project_id,

                "userId":
                    user_id,
            },
            {
                "id": 1
            },
        )
    )

    brief_id = (
        (existing_brief or {}).get("id")
        or new_review_brief_id()
    )

    print(
        f"[DEBUG] review brief id = {brief_id}"
    )

    # ========================================================
    # 2. SOURCES
    # ========================================================

    source_count = (
        sources_collection.count_documents(
            {
                "project_id":
                    project_id,

                "user_id":
                    user_id,
            }
        )
    )

    # ========================================================
    # 3. FINDINGS
    # ========================================================

    findings = [
        shape_finding(finding)
        for finding in findings_collection.find(
            {
                "project_id":
                    project_id,

                "user_id":
                    user_id,
            }
        )
    ]

    # ========================================================
    # 4. QUESTIONS
    # ========================================================

    questions = [
        shape_question(question)
        for question in questions_collection.find(
            {
                "project_id":
                    project_id,

                "user_id":
                    user_id,
            }
        )
    ]

    # ========================================================
    # 5. CHANGES
    # ========================================================

    changes = [
        shape_change(change)
        for change in changes_collection.find(
            {
                "project_id":
                    project_id,

                "user_id":
                    user_id,
            }
        )
    ]

    # ========================================================
    # 6. ATTENTION COUNT
    # ========================================================

    attention_count = sum(
        1
        for finding in findings
        if finding["needsAttention"]
    )

    # ========================================================
    # 7. BUILD BRIEF
    # ========================================================

    review_brief = {

        "id":
            brief_id,

        "projectId":
            project_id,

        "userId":
            user_id,

        "status":
            "completed",

        "generatedAt":
            get_current_time(),

        "sourceCount":
            source_count,

        "findingCount":
            len(findings),

        "questionCount":
            len(questions),

        "changeCount":
            len(changes),

        "attentionCount":
            attention_count,

        "findings":
            findings,

        "questions":
            questions,

        "changes":
            changes,
    }

    print(
        "[SUCCESS] Review Brief built"
    )

    return review_brief


# ============================================================
# GET REVIEW BRIEF
# ============================================================

def get_ai_review_brief(
    project_id: str,
    user_id: str,
):

    review_brief = (
        review_brief_collection.find_one(
            {
                "projectId":
                    project_id,

                "userId":
                    user_id,
            },
            {
                "_id": 0
            },
        )
    )

    if not review_brief:

        raise ValueError(
            "Review brief not found."
        )

    # ========================================================
    # BACKFILL ID
    #
    # Briefs stored before the id was introduced get a
    # random UUID assigned and persisted on first read.
    # ========================================================

    brief_id = review_brief.get("id")

    if not brief_id:

        brief_id = new_review_brief_id()

        review_brief_collection.update_one(
            {
                "projectId":
                    project_id,

                "userId":
                    user_id,
            },
            {
                "$set": {
                    "id": brief_id
                }
            },
        )

        print(
            f"[DEBUG] backfilled review brief id = "
            f"{brief_id}"
        )

    # ========================================================
    # RESPONSE
    #
    # Re-shaped on read so briefs stored by an older
    # version still match the response contract.
    # ========================================================

    findings = [
        shape_finding(finding)
        for finding in (
            review_brief.get("findings") or []
        )
    ]

    questions = [
        shape_question(question)
        for question in (
            review_brief.get("questions") or []
        )
    ]

    changes = [
        shape_change(change)
        for change in (
            review_brief.get("changes") or []
        )
    ]

    attention_count = sum(
        1
        for finding in findings
        if finding["needsAttention"]
    )

    return {

        "id":
            brief_id,

        "projectId":
            review_brief.get(
                "projectId",
                project_id,
            ),

        "userId":
            review_brief.get(
                "userId",
                user_id,
            ),

        "status":
            review_brief.get(
                "status",
                "completed",
            ),

        "generatedAt":
            to_iso_z(
                review_brief.get(
                    "generatedAt"
                )
            ),

        "sourceCount":
            review_brief.get(
                "sourceCount",
                0,
            ),

        "findingCount":
            len(findings),

        "questionCount":
            len(questions),

        "changeCount":
            len(changes),

        "attentionCount":
            attention_count,

        "findings":
            findings,

        "questions":
            questions,

        "changes":
            changes,
    }
