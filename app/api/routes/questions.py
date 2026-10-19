from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.core.deps import get_current_user

from app.db.mongodb import (
    projects_collection,
    questions_collection,
)

from app.schemas.question import (
    QuestionsResponse,
    QuestionResponse,
    DeleteQuestionResponse,
)

router = APIRouter(prefix="/api/v1/projects", tags=["Questions"])


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


def shape_question(
    question: dict,
) -> dict:
    """
    Convert a stored question document into the
    camelCase API shape.
    """

    return {

        "id":
            question.get("_id"),

        "text":
            question.get("text")
            or question.get("question"),

        "priority":
            question.get("priority"),

        "findingId":
            question.get("finding_id"),

        "evidenceId":
            question.get("evidence_id"),

        "createdAt":
            question.get("created_at"),
    }


# ============================================================
# GET QUESTIONS
# ============================================================

@router.get(
    "/{project_id}/questions",
    response_model=QuestionsResponse,
)
def get_questions(
    project_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Fetch all questions belonging to a single project
    owned by the logged in user.

    Flow:

        project_id
             ↓
      Validate project ownership
             ↓
      Fetch questions for that project only
             ↓
         Return questions
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
    # 2. Fetch questions for this project only
    # --------------------------------------------------------

    try:

        question_documents = list(
            questions_collection.find(
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
                "Failed to fetch questions: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # 3. Shape response
    # --------------------------------------------------------

    questions = [
        shape_question(question)
        for question in question_documents
    ]

    # --------------------------------------------------------
    # 4. Return response
    # --------------------------------------------------------

    return {

        "success": True,

        "message":
            "Questions fetched successfully",

        "data": {

            "projectId": project_id,

            "questionCount": len(questions),

            "questions": questions,
        },
    }


# ============================================================
# GET QUESTION
# ============================================================

@router.get(
    "/{project_id}/questions/{question_id}",
    response_model=QuestionResponse,
)
def get_question(
    project_id: str,
    question_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Fetch a single question belonging to the logged in
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
    # 2. Find question
    # --------------------------------------------------------

    question = questions_collection.find_one(
        {
            "_id": question_id,
            "project_id": project_id,
            "user_id": user_id,
        }
    )

    if not question:

        raise HTTPException(
            status_code=404,
            detail="Question not found",
        )

    # --------------------------------------------------------
    # 3. Return response
    # --------------------------------------------------------

    return {

        "success": True,

        "message":
            "Question fetched successfully",

        "data": shape_question(
            question
        ),
    }


# ============================================================
# DELETE QUESTION
# ============================================================

@router.delete(
    "/{project_id}/questions/{question_id}",
    response_model=DeleteQuestionResponse,
)
def delete_question(
    project_id: str,
    question_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Delete a question belonging to the logged in
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
    # 2. Find and delete question
    # --------------------------------------------------------

    try:

        question = questions_collection.find_one_and_delete(
            {
                "_id": question_id,
                "project_id": project_id,
                "user_id": user_id,
            }
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to delete question: "
                f"{str(exc)}"
            ),
        )

    if not question:

        raise HTTPException(
            status_code=404,
            detail="Question not found",
        )

    # --------------------------------------------------------
    # 3. Decrement project question count
    # --------------------------------------------------------

    projects_collection.update_one(
        {
            "_id": project_id,

            "user_id": user_id,

            "question_count": {"$gt": 0},
        },
        {
            "$inc": {
                "question_count": -1,
            },
        },
    )

    # --------------------------------------------------------
    # 4. Return response
    # --------------------------------------------------------

    return {

        "success": True,

        "message":
            "Question deleted successfully",

        "data": {

            "id": question_id,

            "projectId": project_id,
        },
    }
