from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.db.mongodb import projects_collection, sources_collection
from app.schemas.project import CreateProjectRequest


router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Projects"],
)


# ============================================================
# CREATE PROJECT
# ============================================================

@router.post("")
async def create_project(
    payload: CreateProjectRequest,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Create a new project owned by the logged in user.

    Flow:

        Request
            ↓
        Validate project details
            ↓
        Generate project ID
            ↓
        Create project document
            ↓
        Insert into MongoDB
            ↓
        Return project details
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Validate project name
    # --------------------------------------------------------

    project_name = payload.name.strip()

    if not project_name:
        raise HTTPException(
            status_code=400,
            detail="Project name is required",
        )

    # --------------------------------------------------------
    # 2. Validate objective
    # --------------------------------------------------------

    objective = payload.objective.strip()

    if not objective:
        raise HTTPException(
            status_code=400,
            detail="Project objective is required",
        )

    # --------------------------------------------------------
    # 3. Clean analysis focus
    # --------------------------------------------------------

    analysis_focus = payload.analysis_focus

    if analysis_focus:
        analysis_focus = analysis_focus.strip()

    # --------------------------------------------------------
    # 4. Generate project ID
    # --------------------------------------------------------

    project_id = (
        f"project_{uuid4().hex[:12]}"
    )

    # Example:
    #
    # project_8f4a72c91b32

    # --------------------------------------------------------
    # 5. Create project document
    # --------------------------------------------------------

    project_document = {
        "_id": project_id,

        "user_id": user_id,

        "project_name": project_name,

        "objective": objective,

        "analysis_focus": analysis_focus,

        "status": "active",

        "ai_review_status": "not_started",

        "ai_review_error": None,

        "source_count": 0,

        "finding_count": 0,

        "question_count": 0,

        "decision_count": 0,
    }

    # --------------------------------------------------------
    # 6. Insert project into MongoDB
    # --------------------------------------------------------

    try:

        projects_collection.insert_one(
            project_document
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create project: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # 7. Return response
    # --------------------------------------------------------

    return {
        "status": "success",

        "message": "Project created successfully",

        "project": {
            "id": project_id,

            "userId": user_id,

            "projectName": project_name,

            "objective": objective,

            "analysisFocus": analysis_focus,

            "status": "active",

            "aiReviewStatus": "not_started",

            "sourceCount": 0,

            "findingCount": 0,

            "questionCount": 0,

            "decisionCount": 0,
        },
    }




# ============================================================
# GET ALL PROJECTS
# ============================================================

@router.get("")
async def get_projects(
    current_user=Depends(
        get_current_user
    ),
):
    """
    Get all projects owned by the logged in user.

    Flow:

        Request
            ↓
        Read projects from MongoDB
            ↓
        Convert MongoDB documents
            ↓
        Return project list
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Get projects from MongoDB
    # --------------------------------------------------------

    try:

        projects = list(
            projects_collection.find(
                {
                    "user_id": user_id
                }
            )
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to fetch projects: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # 2. Count sources live so list matches project detail
    # --------------------------------------------------------

    source_counts = {}

    for row in sources_collection.aggregate(
        [
            {
                "$match": {
                    "user_id": user_id,
                }
            },
            {
                "$group": {
                    "_id": "$project_id",
                    "count": {"$sum": 1},
                }
            },
        ]
    ):
        source_counts[row["_id"]] = row["count"]

    # --------------------------------------------------------
    # 3. Format projects
    # --------------------------------------------------------

    project_list = []

    for project in projects:

        project_id = project.get("_id")

        project_list.append(
            {
                "id":
                    project_id,

                "projectName":
                    project.get(
                        "project_name"
                    ),

                "objective":
                    project.get(
                        "objective"
                    ),

                "analysisFocus":
                    project.get(
                        "analysis_focus"
                    ),

                "status":
                    project.get(
                        "status",
                        "active"
                    ),

                "aiReviewStatus":
                    project.get(
                        "ai_review_status",
                        "not_started"
                    ),

                "sourceCount":
                    source_counts.get(
                        project_id,
                        0
                    ),

                "findingCount":
                    project.get(
                        "finding_count",
                        0
                    ),

                "questionCount":
                    project.get(
                        "question_count",
                        0
                    ),

                "decisionCount":
                    project.get(
                        "decision_count",
                        0
                    ),
            }
        )

    # --------------------------------------------------------
    # 4. Return response
    # --------------------------------------------------------

    return {

        "status":
            "success",

        "message":
            "Projects fetched successfully",

        "count":
            len(project_list),

        "projects":
            project_list,
    }


# ============================================================
# GET PROJECT BY PROJECT ID
# ============================================================

@router.get("/{project_id}")
async def get_project_by_id(
    project_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Get project details using project ID.

    Only returns the project when it belongs to the
    logged in user.

    Example:

        GET /api/v1/projects/project_a83f91c42d10
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Validate project ID
    # --------------------------------------------------------

    if not project_id.strip():

        raise HTTPException(
            status_code=400,
            detail="Project ID is required",
        )

    # --------------------------------------------------------
    # 2. Find project from MongoDB
    # --------------------------------------------------------

    project = projects_collection.find_one(
        {
            "_id": project_id,

            "user_id": user_id,
        }
    )

    # --------------------------------------------------------
    # 3. Project not found
    # --------------------------------------------------------

    if not project:

        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    # --------------------------------------------------------
    # 4. Load sources for this project
    # --------------------------------------------------------

    source_list = []

    for source in sources_collection.find(
        {
            "project_id": project_id,
            "user_id": user_id,
        }
    ):
        source_list.append(
            {
                "id": source.get("_id"),
                "projectId": source.get("project_id"),
                "sourceName": source.get("source_name"),
                "sourceType": source.get("source_type"),
                "sourceSize": source.get("source_size"),
                "filePath": source.get("file_path"),
            }
        )

    # --------------------------------------------------------
    # 5. Return project (with sources)
    # --------------------------------------------------------

    return {
        "status": "success",

        "message": "Project fetched successfully",

        "project": {
            "id": project.get("_id"),

            "projectName": project.get(
                "project_name"
            ),

            "objective": project.get(
                "objective"
            ),

            "analysisFocus": project.get(
                "analysis_focus"
            ),

            "status": project.get(
                "status",
                "active"
            ),

            "aiReviewStatus": project.get(
                "ai_review_status",
                "not_started"
            ),

            "sourceCount": len(source_list),

            "findingCount": project.get(
                "finding_count",
                0
            ),

            "questionCount": project.get(
                "question_count",
                0
            ),

            "decisionCount": project.get(
                "decision_count",
                0
            ),

            "sources": source_list,
        },
    }


# ============================================================
# DELETE PROJECT BY PROJECT ID
# ============================================================

@router.delete("/{project_id}")
async def delete_project(
    project_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Delete a project using project ID.

    Only deletes the project when it belongs to the
    logged in user.

    Example:

        DELETE /api/v1/projects/project_a83f91c42d10
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Validate project ID
    # --------------------------------------------------------

    if not project_id.strip():

        raise HTTPException(
            status_code=400,
            detail="Project ID is required",
        )

    # --------------------------------------------------------
    # 2. Check if project exists
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
    # 3. Delete project
    # --------------------------------------------------------

    try:

        result = projects_collection.delete_one(
            {
                "_id": project_id,

                "user_id": user_id,
            }
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to delete project: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # 4. Check deletion result
    # --------------------------------------------------------

    if result.deleted_count == 0:

        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    # --------------------------------------------------------
    # 5. Return response
    # --------------------------------------------------------

    return {
        "status": "success",
        "message": "Project deleted successfully",
        "projectId": project_id,
    }