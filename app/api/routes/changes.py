from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.core.deps import get_current_user

from app.db.mongodb import (
    projects_collection,
    changes_collection,
)

from app.schemas.change import (
    ChangesResponse,
    ChangeResponse,
    DeleteChangeResponse,
)

router = APIRouter(prefix="/api/v1/projects", tags=["Changes"])


# ============================================================
# HELPERS
# ============================================================

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


def shape_change(
    change: dict,
) -> dict:
    """
    Convert a stored change document into the
    camelCase API shape.
    """

    return {

        "id":
            change.get("_id"),

        "title":
            change.get("title"),

        "detail":
            change.get("detail"),

        "changeType":
            change.get("changeType"),

        "section":
            change.get("section"),

        "page":
            change.get("page"),

        "createdAt":
            change.get("created_at"),
    }


# ============================================================
# GET CHANGES
# ============================================================

@router.get(
    "/{project_id}/changes",
    response_model=ChangesResponse,
)
def get_changes(
    project_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Fetch all changes belonging to a single project
    owned by the logged in user.
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
    # 2. Fetch changes for this project only
    # --------------------------------------------------------

    try:

        change_documents = list(
            changes_collection.find(
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
                "Failed to fetch changes: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # 3. Shape response
    # --------------------------------------------------------

    changes = [
        shape_change(change)
        for change in change_documents
    ]

    # --------------------------------------------------------
    # 4. Return response
    # --------------------------------------------------------

    return {

        "success": True,

        "message":
            "Changes fetched successfully",

        "data": {

            "projectId": project_id,

            "changeCount": len(changes),

            "changes": changes,
        },
    }


# ============================================================
# GET CHANGE
# ============================================================

@router.get(
    "/{project_id}/changes/{change_id}",
    response_model=ChangeResponse,
)
def get_change(
    project_id: str,
    change_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Fetch a single change belonging to the logged in
    user project.
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
    # 2. Find change
    # --------------------------------------------------------

    change = changes_collection.find_one(
        {
            "_id": change_id,
            "project_id": project_id,
            "user_id": user_id,
        }
    )

    if not change:

        raise HTTPException(
            status_code=404,
            detail="Change not found",
        )

    # --------------------------------------------------------
    # 3. Return response
    # --------------------------------------------------------

    return {

        "success": True,

        "message":
            "Change fetched successfully",

        "data": shape_change(
            change
        ),
    }


# ============================================================
# DELETE CHANGE
# ============================================================

@router.delete(
    "/{project_id}/changes/{change_id}",
    response_model=DeleteChangeResponse,
)
def delete_change(
    project_id: str,
    change_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Delete a change belonging to the logged in
    user project.

    Projects do not carry a change_count field, so
    there is no counter to decrement here.
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
    # 2. Find and delete change
    # --------------------------------------------------------

    try:

        change = changes_collection.find_one_and_delete(
            {
                "_id": change_id,
                "project_id": project_id,
                "user_id": user_id,
            }
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to delete change: "
                f"{str(exc)}"
            ),
        )

    if not change:

        raise HTTPException(
            status_code=404,
            detail="Change not found",
        )

    # --------------------------------------------------------
    # 3. Return response
    # --------------------------------------------------------

    return {

        "success": True,

        "message":
            "Change deleted successfully",

        "data": {

            "id": change_id,

            "projectId": project_id,
        },
    }
