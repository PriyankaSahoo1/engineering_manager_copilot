from fastapi import (
    Depends,
    HTTPException,
    status,
)

from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.security import (
    get_user_id_from_token,
)

from app.db.mongodb import users_collection


# ============================================================
# BEARER AUTHENTICATION
# ============================================================

security = HTTPBearer()


# ============================================================
# GET CURRENT USER
#
# Every protected route depends on this. The returned
# document always carries:
#
#     _id   -> internal MongoDB user id
#     id    -> same value, convenient for queries
#
# so routes and services can use current_user["id"]
# to scope every MongoDB query to the logged in user.
# ============================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):

    # --------------------------------------------------------
    # 1. Get token
    # --------------------------------------------------------

    token = credentials.credentials

    # --------------------------------------------------------
    # 2. Decode token
    # --------------------------------------------------------

    user_id = get_user_id_from_token(
        token
    )

    if not user_id:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # --------------------------------------------------------
    # 3. Find user
    # --------------------------------------------------------

    user = users_collection.find_one(
        {
            "_id": user_id
        }
    )

    if not user:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # --------------------------------------------------------
    # 4. Check user status
    # --------------------------------------------------------

    if user.get("status") != "active":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # --------------------------------------------------------
    # 5. Expose the id under both keys
    # --------------------------------------------------------

    user["id"] = user["_id"]

    return user
