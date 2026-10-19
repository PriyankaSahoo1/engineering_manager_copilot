# from fastapi import APIRouter, HTTPException

# from app.services.ai_review_service import (
#     get_ai_review_brief,
# )


# router = APIRouter(
#     prefix="/api/v1/projects",
#     tags=["AI Review"],
# )


# # ============================================================
# # POST - AI TRIGGER
# # ============================================================
# from fastapi import APIRouter, HTTPException

# from app.services.ai_review_service import (
#     run_ai_trigger,
# )


# @router.post(
#     "/{project_id}/ai-trigger"
# )
# def ai_trigger(
#     project_id: str,
# ):

#     try:

#         result = run_ai_trigger(
#             project_id=project_id
#         )

#         return {
#             "success": True,
#             "message": "AI review is ready",
#             "data": result,
#         }

#     except ValueError as exc:

#         raise HTTPException(
#             status_code=400,
#             detail=str(exc),
#         )

#     except Exception as exc:

#         import traceback

#         traceback.print_exc()

#         raise HTTPException(
#             status_code=500,
#             detail=f"AI review failed: {str(exc)}",
#         )


from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.core.deps import get_current_user

from app.services.ai_review_service import (
    run_ai_trigger,
)


router = APIRouter(
    prefix="/api/v1/projects",
    tags=["AI Review"],
)


# ============================================================
# POST - AI TRIGGER
# ============================================================

@router.post(
    "/{project_id}/ai-trigger"
)
def ai_trigger(
    project_id: str,

    current_user=Depends(
        get_current_user
    ),
):

    user_id = current_user["id"]

    print("\n" + "=" * 70)
    print("[DEBUG] POST AI TRIGGER")
    print("=" * 70)

    print(
        f"[DEBUG] project_id = {project_id}"
    )

    print(
        f"[DEBUG] user_id = {user_id}"
    )

    try:

        result = run_ai_trigger(
            project_id=project_id,
            user_id=user_id,
        )

        return {

            "success":
                True,

            "message":
                "AI review is ready",

            "data":
                result,
        }

    except ValueError as exc:

        print(
            f"[ERROR] Validation error: {exc}"
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                f"AI review failed: "
                f"{str(exc)}"
            ),
        )