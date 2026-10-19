from datetime import datetime, timezone
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.core.deps import get_current_user

from app.db.mongodb import (
    projects_collection,
    findings_collection,
    decisions_collection,
)

from app.schemas.decision import (
    CreateDecisionRequest,
    UpdateDecisionRequest,
    DecisionResponse,
    DecisionsResponse,
    DeleteDecisionResponse,
    DecisionStatus,
)

router = APIRouter(prefix="/api/v1/projects", tags=["Decisions"])


# ============================================================
# HELPERS
# ============================================================

def get_current_time():
    return datetime.now(
        timezone.utc
    )


def get_owned_project(
    project_id: str,
    user_id: str,
):
    """
    Fetch a project owned by the logged in user or
    raise 404.
    """

    project = projects_collection.find_one(
        {
            "_id": project_id,

            "user_id": user_id,
        }
    )

    if not project:

        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    return project


def shape_decision(
    decision: dict,
) -> dict:
    """
    Convert a stored decision document into the
    camelCase API shape.
    """

    return {

        "id":
            decision.get("_id"),

        "projectId":
            decision.get("project_id"),

        "title":
            decision.get("title"),

        "description":
            decision.get("description"),

        "ownerName":
            decision.get("owner_name"),

        "findingId":
            decision.get("finding_id"),

        "status":
            decision.get("status"),

        "createdAt":
            decision.get("created_at"),

        "updatedAt":
            decision.get("updated_at"),

        "resolvedAt":
            decision.get("resolved_at"),
    }


# ============================================================
# GET DECISIONS
# ============================================================

@router.get(
    "/{project_id}/decisions",
    response_model=DecisionsResponse,
)
def get_decisions(
    project_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Fetch all decisions belonging to a single project
    owned by the logged in user.

    Flow:

        project_id
             |
      Validate project ownership
             |
      Fetch decisions for that project only
             |
        Return decisions
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Check project exists
    # --------------------------------------------------------

    get_owned_project(
        project_id,
        user_id,
    )

    # --------------------------------------------------------
    # 2. Fetch decisions for this project only
    # --------------------------------------------------------

    try:

        decision_documents = list(
            decisions_collection.find(
                {
                    "project_id": project_id,

                    "user_id": user_id,
                }
            ).sort(
                "created_at", 1
            )
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to fetch decisions: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # 3. Shape response
    # --------------------------------------------------------

    decisions = [
        shape_decision(decision)
        for decision in decision_documents
    ]

    # --------------------------------------------------------
    # 4. Return response
    # --------------------------------------------------------

    return {

        "success": True,

        "message":
            "Decisions fetched successfully",

        "data": {

            "projectId": project_id,

            "decisionCount": len(decisions),

            "decisions": decisions,
        },
    }


# ============================================================
# CREATE DECISION
# ============================================================

@router.post(
    "/{project_id}/decisions",
    response_model=DecisionResponse,
)
def create_decision(
    project_id: str,

    payload: CreateDecisionRequest,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Create a decision inside the logged in user's
    project.

    Flow:

        project_id + payload
                |
        Validate project ownership
                |
        Validate finding (optional)
                |
        Build decision document
                |
        Insert decision
                |
        Increment project decision count
                |
        Return decision
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Check project exists
    # --------------------------------------------------------

    get_owned_project(
        project_id,
        user_id,
    )

    # --------------------------------------------------------
    # 2. Validate title
    # --------------------------------------------------------

    title = payload.title.strip()

    if not title:

        raise HTTPException(
            status_code=400,
            detail="Decision title is required",
        )

    # --------------------------------------------------------
    # 3. Clean optional fields
    # --------------------------------------------------------

    description = payload.description

    if description:
        description = description.strip() or None

    owner_name = payload.owner_name

    if owner_name:
        owner_name = owner_name.strip() or None

    finding_id = payload.finding_id

    if finding_id:
        finding_id = finding_id.strip() or None

    # --------------------------------------------------------
    # 4. Validate finding when supplied
    # --------------------------------------------------------

    if finding_id:

        finding = findings_collection.find_one(
            {
                "_id": finding_id,
                "project_id": project_id,
                "user_id": user_id,
            }
        )

        if not finding:

            raise HTTPException(
                status_code=404,
                detail="Finding not found",
            )

    # --------------------------------------------------------
    # 5. Build decision document
    # --------------------------------------------------------

    decision_id = (
        f"decision_{uuid4().hex[:12]}"
    )

    # Example:
    #
    # decision_8f4a72c91b32

    now = get_current_time()

    decision_document = {

        "_id": decision_id,

        "project_id": project_id,

        "user_id": user_id,

        "finding_id": finding_id,

        "title": title,

        "description": description,

        "owner_name": owner_name,

        "status": DecisionStatus.open.value,

        "created_at": now,

        "updated_at": now,

        "resolved_at": None,
    }

    # --------------------------------------------------------
    # 6. Insert decision
    # --------------------------------------------------------

    try:

        decisions_collection.insert_one(
            decision_document
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create decision: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # 7. Increment project decision count
    # --------------------------------------------------------

    projects_collection.update_one(
        {
            "_id": project_id,
            "user_id": user_id,
        },
        {
            "$inc": {
                "decision_count": 1,
            },
        },
    )

    # --------------------------------------------------------
    # 8. Return response
    # --------------------------------------------------------

    return {

        "success": True,

        "message":
            "Decision created successfully",

        "data": shape_decision(
            decision_document
        ),
    }


# ============================================================
# UPDATE DECISION
# ============================================================

@router.patch(
    "/{project_id}/decisions/{decision_id}",
    response_model=DecisionResponse,
)
def update_decision(
    project_id: str,
    decision_id: str,

    payload: UpdateDecisionRequest,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Update a decision belonging to the logged in
    user's project.

    Only the fields sent in the request body are
    changed.

    Flow:

        project_id + decision_id + payload
                |
        Validate project ownership
                |
        Find decision
                |
        Build update from supplied fields
                |
        Apply status transition
                |
        Update decision
                |
        Return updated decision
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Check project exists
    # --------------------------------------------------------

    get_owned_project(
        project_id,
        user_id,
    )

    # --------------------------------------------------------
    # 2. Find decision
    # --------------------------------------------------------

    decision = decisions_collection.find_one(
        {
            "_id": decision_id,
            "project_id": project_id,
            "user_id": user_id,
        }
    )

    if not decision:

        raise HTTPException(
            status_code=404,
            detail="Decision not found",
        )

    # --------------------------------------------------------
    # 3. Collect supplied fields only
    # --------------------------------------------------------

    supplied_fields = payload.model_dump(
        exclude_unset=True
    )

    if not supplied_fields:

        raise HTTPException(
            status_code=400,
            detail="No fields provided to update",
        )

    updates = {}

    # --------------------------------------------------------
    # 4. Title
    # --------------------------------------------------------

    if "title" in supplied_fields:

        title = supplied_fields["title"]

        if title is not None:
            title = title.strip()

        if not title:

            raise HTTPException(
                status_code=400,
                detail="Decision title is required",
            )

        updates["title"] = title

    # --------------------------------------------------------
    # 5. Description
    # --------------------------------------------------------

    if "description" in supplied_fields:

        description = supplied_fields["description"]

        if description:
            description = description.strip() or None

        updates["description"] = description

    # --------------------------------------------------------
    # 6. Owner name
    # --------------------------------------------------------

    if "owner_name" in supplied_fields:

        owner_name = supplied_fields["owner_name"]

        if owner_name:
            owner_name = owner_name.strip() or None

        updates["owner_name"] = owner_name

    # --------------------------------------------------------
    # 7. Status transition
    # --------------------------------------------------------

    now = get_current_time()

    if "status" in supplied_fields:

        status = supplied_fields["status"]

        if status is None:

            raise HTTPException(
                status_code=400,
                detail="Decision status cannot be null",
            )

        status = DecisionStatus(status).value

        updates["status"] = status

        if status == DecisionStatus.resolved.value:

            updates["resolved_at"] = (
                decision.get("resolved_at")
                or now
            )

        else:

            updates["resolved_at"] = None

    # --------------------------------------------------------
    # 8. Update decision
    # --------------------------------------------------------

    updates["updated_at"] = now

    try:

        decisions_collection.update_one(
            {
                "_id": decision_id,
                "project_id": project_id,
                "user_id": user_id,
            },
            {
                "$set": updates,
            },
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update decision: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # 9. Return updated decision
    # --------------------------------------------------------

    decision.update(updates)

    return {

        "success": True,

        "message":
            "Decision updated successfully",

        "data": shape_decision(
            decision
        ),
    }


# ============================================================
# DELETE DECISION
# ============================================================

@router.delete(
    "/{project_id}/decisions/{decision_id}",
    response_model=DeleteDecisionResponse,
)
def delete_decision(
    project_id: str,
    decision_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Delete a decision belonging to the logged in
    user project.

    Flow:

        project_id + decision_id
                |
        Validate project ownership
                |
        Find and delete decision
                |
        Decrement project decision count
                |
        Return deleted decision
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Check project exists
    # --------------------------------------------------------

    get_owned_project(
        project_id,
        user_id,
    )

    # --------------------------------------------------------
    # 2. Find and delete decision
    # --------------------------------------------------------

    try:

        decision = decisions_collection.find_one_and_delete(
            {
                "_id": decision_id,
                "project_id": project_id,
                "user_id": user_id,
            }
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to delete decision: "
                f"{str(exc)}"
            ),
        )

    if not decision:

        raise HTTPException(
            status_code=404,
            detail="Decision not found",
        )

    # --------------------------------------------------------
    # 3. Decrement project decision count
    # --------------------------------------------------------

    projects_collection.update_one(
        {
            "_id": project_id,

            "user_id": user_id,

            "decision_count": {"$gt": 0},
        },
        {
            "$inc": {
                "decision_count": -1,
            },
        },
    )

    # --------------------------------------------------------
    # 4. Return response
    # --------------------------------------------------------

    return {

        "success": True,

        "message":
            "Decision deleted successfully",

        "data": {

            "id": decision_id,

            "projectId": project_id,
        },
    }
