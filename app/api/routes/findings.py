from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from app.core.deps import get_current_user

from app.db.mongodb import (
    projects_collection,
    findings_collection,
)

from app.schemas.finding import FindingsResponse

router = APIRouter(prefix="/api/v1/projects", tags=["Findings"])


@router.get("/{project_id}/findings", response_model=FindingsResponse)
def get_findings(
    project_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    user_id = current_user["id"]

    try:
        finding_documents = list(
            findings_collection.find(
                {
                    "project_id": project_id,

                    "user_id": user_id,
                },
                {
                    "project_id": 0,

                    "source_id": 0,

                    "user_id": 0,
                },
            )
        )

        # _id is kept by the projection above and renamed
        # here, because a projection can drop a field but
        # cannot rename one. pop() runs before the spread,
        # so id lands first and no _id survives.

        findings = [
            {
                "id": finding.pop("_id"),
                **finding,
            }
            for finding in finding_documents
        ]

        return {"success": True, "message": "Findings fetched successfully", "data": {"projectId": project_id, "findingCount": len(findings), "findings": findings}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch findings: {exc}")




# ============================================================
# DELETE FINDING
# ============================================================

@router.delete(
    "/{project_id}/findings/{finding_id}"
)
async def delete_finding(
    project_id: str,
    finding_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Delete a finding belonging to the logged in user's
    project.

    Flow:

        project_id + finding_id
                ↓
        Validate project ownership
                ↓
          Find finding
                ↓
        Delete finding
                ↓
         Return success
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Check project exists
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 2. Find finding
    # --------------------------------------------------------

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
    # 3. Delete finding
    # --------------------------------------------------------

    try:

        result = findings_collection.delete_one(
            {
                "_id": finding_id,
                "project_id": project_id,
                "user_id": user_id,
            }
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to delete finding: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # 4. Verify deletion
    # --------------------------------------------------------

    if result.deleted_count == 0:

        raise HTTPException(
            status_code=404,
            detail="Finding not found",
        )

    # --------------------------------------------------------
    # 5. Return response
    # --------------------------------------------------------

    return {

        "status": "success",

        "message":
            "Finding deleted successfully",

        "finding": {

            "id":
                finding_id,

            "projectId":
                project_id,
        },
    }
