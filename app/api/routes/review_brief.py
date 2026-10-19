
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.core.deps import get_current_user

from app.services.ai_review_storage import (
    get_ai_review_brief,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["Review Brief"],
)


# ============================================================
# GET REVIEW BRIEF
# ============================================================

@router.get(
    "/projects/{project_id}/review-brief"
)
def get_review_brief(
    project_id: str,

    current_user=Depends(
        get_current_user
    ),
):

    user_id = current_user["id"]

    print("\n" + "=" * 70)
    print("[DEBUG] GET REVIEW BRIEF")
    print("=" * 70)

    print(
        f"[DEBUG] project_id = {project_id}"
    )

    print(
        f"[DEBUG] user_id = {user_id}"
    )

    try:

        review_brief = get_ai_review_brief(
            project_id=project_id,
            user_id=user_id,
        )

        print(
            "[SUCCESS] Review brief fetched"
        )

        print(
            f"[DEBUG] sourceCount = "
            f"{review_brief.get('sourceCount', 0)}"
        )

        print(
            f"[DEBUG] findingCount = "
            f"{review_brief.get('findingCount', 0)}"
        )

        print(
            f"[DEBUG] questionCount = "
            f"{review_brief.get('questionCount', 0)}"
        )

        print(
            f"[DEBUG] changeCount = "
            f"{review_brief.get('changeCount', 0)}"
        )

        print(
            f"[DEBUG] attentionCount = "
            f"{review_brief.get('attentionCount', 0)}"
        )

        return {
            "success": True,

            "message":
                "Review brief fetched successfully",

            "data":
                review_brief,
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to fetch review brief: "
                f"{str(exc)}"
            ),
        )