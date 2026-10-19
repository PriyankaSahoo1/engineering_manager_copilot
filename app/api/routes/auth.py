# from uuid import uuid4

# from fastapi import (
#     APIRouter,
#     Depends,
#     Header,
#     HTTPException,
#     status,
# )

# from app.core.security import (
#     create_access_token,
#     get_user_id_from_token,
#     hash_password,
# )

# from app.db.mongodb import users_collection

# from app.schemas.auth import (
#     OnboardingCompleteRequest,
#     SignupRequest,
# )


# router = APIRouter(
#     prefix="/api/v1/auth",
#     tags=["Authentication"],
# )


# # ============================================================
# # AUTHENTICATION DEPENDENCY
# # ============================================================

# async def get_current_user(
#     authorization: str | None = Header(
#         default=None
#     ),
# ):

#     # --------------------------------------------------------
#     # 1. Check Authorization header
#     # --------------------------------------------------------

#     if not authorization:

#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Authorization header is required",
#         )

#     # --------------------------------------------------------
#     # 2. Check Bearer token
#     # --------------------------------------------------------

#     if not authorization.startswith(
#         "Bearer "
#     ):

#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid authorization format",
#         )

#     token = authorization[
#         len("Bearer "):
#     ].strip()

#     if not token:

#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Access token is required",
#         )

#     # --------------------------------------------------------
#     # 3. Decode token
#     # --------------------------------------------------------

#     user_id = get_user_id_from_token(
#         token
#     )

#     if not user_id:

#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid or expired token",
#         )

#     # --------------------------------------------------------
#     # 4. Find user
#     # --------------------------------------------------------

#     user = users_collection.find_one(
#         {
#             "_id": user_id
#         }
#     )

#     if not user:

#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="User not found",
#         )

#     # --------------------------------------------------------
#     # 5. Check user status
#     # --------------------------------------------------------

#     if user.get("status") != "active":

#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="User account is inactive",
#         )

#     return user


# # ============================================================
# # SIGNUP
# # ============================================================

# @router.post(
#     "/signup",
#     status_code=status.HTTP_201_CREATED,
# )
# async def signup(
#     payload: SignupRequest,
# ):
#     """
#     Create a new user account.
#     """

#     # --------------------------------------------------------
#     # 1. Clean input
#     # --------------------------------------------------------

#     name = payload.name.strip()

#     email = (
#         str(payload.email)
#         .lower()
#         .strip()
#     )

#     # --------------------------------------------------------
#     # 2. Validate name
#     # --------------------------------------------------------

#     if not name:

#         raise HTTPException(
#             status_code=400,
#             detail="Name is required",
#         )

#     # --------------------------------------------------------
#     # 3. Check existing email
#     # --------------------------------------------------------

#     existing_user = users_collection.find_one(
#         {
#             "email": email
#         }
#     )

#     if existing_user:

#         raise HTTPException(
#             status_code=409,
#             detail="Email already registered",
#         )

#     # --------------------------------------------------------
#     # 4. Generate user ID
#     # --------------------------------------------------------

#     user_id = (
#         f"user_{uuid4().hex[:12]}"
#     )

#     # --------------------------------------------------------
#     # 5. Hash password
#     # --------------------------------------------------------

#     password_hash = hash_password(
#         payload.password
#     )

#     # --------------------------------------------------------
#     # 6. Create user document
#     # --------------------------------------------------------

#     user_document = {

#         "_id":
#             user_id,

#         "name":
#             name,

#         "email":
#             email,

#         "password_hash":
#             password_hash,

#         "status":
#             "active",

#         "onboarding_completed":
#             False,

#         "role":
#             None,

#         "company":
#             None,

#         "job_title":
#             None,

#         "team_size":
#             None,
#     }

#     # --------------------------------------------------------
#     # 7. Insert into MongoDB
#     # --------------------------------------------------------

#     try:

#         users_collection.insert_one(
#             user_document
#         )

#     except Exception as exc:

#         raise HTTPException(
#             status_code=500,
#             detail=(
#                 "Failed to create user: "
#                 f"{str(exc)}"
#             ),
#         )

#     # --------------------------------------------------------
#     # 8. Create access token
#     # --------------------------------------------------------

#     access_token = create_access_token(
#         user_id
#     )

#     # --------------------------------------------------------
#     # 9. Return response
#     # --------------------------------------------------------

#     return {

#         "status":
#             "success",

#         "message":
#             "Signup successful",

#         "access_token":
#             access_token,

#         "token_type":
#             "bearer",

#         "user": {

#             "id":
#                 user_id,

#             "name":
#                 name,

#             "email":
#                 email,

#             "status":
#                 "active",

#             "onboardingCompleted":
#                 False,
#         },
#     }


# # ============================================================
# # GET CURRENT USER
# # ============================================================

# @router.get(
#     "/me"
# )
# async def get_me(
#     current_user=Depends(
#         get_current_user
#     ),
# ):
#     """
#     Get currently authenticated user.
#     """

#     return {

#         "status":
#             "success",

#         "user": {

#             "id":
#                 current_user.get(
#                     "_id"
#                 ),

#             "name":
#                 current_user.get(
#                     "name"
#                 ),

#             "email":
#                 current_user.get(
#                     "email"
#                 ),

#             "status":
#                 current_user.get(
#                     "status"
#                 ),

#             "onboardingCompleted":
#                 current_user.get(
#                     "onboarding_completed",
#                     False,
#                 ),

#             "role":
#                 current_user.get(
#                     "role"
#                 ),

#             "company":
#                 current_user.get(
#                     "company"
#                 ),

#             "jobTitle":
#                 current_user.get(
#                     "job_title"
#                 ),

#             "teamSize":
#                 current_user.get(
#                     "team_size"
#                 ),
#         },
#     }


# # ============================================================
# # COMPLETE ONBOARDING
# # ============================================================

# @router.post(
#     "/onboarding/complete"
# )
# async def complete_onboarding(
#     payload: OnboardingCompleteRequest,
#     current_user=Depends(
#         get_current_user
#     ),
# ):
#     """
#     Complete user onboarding.
#     """

#     user_id = current_user["_id"]

#     # --------------------------------------------------------
#     # 1. Prepare update
#     # --------------------------------------------------------

#     update_data = {

#         "onboarding_completed":
#             True,

#         "role":
#             payload.role,

#         "company":
#             payload.company,

#         "job_title":
#             payload.job_title,

#         "team_size":
#             payload.team_size,
#     }

#     # --------------------------------------------------------
#     # 2. Update MongoDB
#     # --------------------------------------------------------

#     try:

#         result = users_collection.update_one(
#             {
#                 "_id": user_id
#             },
#             {
#                 "$set": update_data
#             },
#         )

#     except Exception as exc:

#         raise HTTPException(
#             status_code=500,
#             detail=(
#                 "Failed to complete onboarding: "
#                 f"{str(exc)}"
#             ),
#         )

#     # --------------------------------------------------------
#     # 3. Check user
#     # --------------------------------------------------------

#     if result.matched_count == 0:

#         raise HTTPException(
#             status_code=404,
#             detail="User not found",
#         )

#     # --------------------------------------------------------
#     # 4. Return response
#     # --------------------------------------------------------

#     return {

#         "status":
#             "success",

#         "message":
#             "Onboarding completed successfully",

#         "user": {

#             "id":
#                 user_id,

#             "onboardingCompleted":
#                 True,

#             "role":
#                 payload.role,

#             "company":
#                 payload.company,

#             "jobTitle":
#                 payload.job_title,

#             "teamSize":
#                 payload.team_size,
#         },
#     }



from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.core.deps import get_current_user

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)

from app.db.mongodb import users_collection

from app.schemas.auth import (
    OnboardingCompleteRequest,
    SignInRequest,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


# ============================================================
# AUTHENTICATION DEPENDENCY
#
# get_current_user now lives in app/core/deps.py so every
# router can depend on it without importing this module.
# ============================================================


# ============================================================
# SIGN IN (company users seeded in DB — no public signup)
# ============================================================

@router.post(
    "/signin",
)
async def signin(
    payload: SignInRequest,
):
    """
    POST /api/v1/auth/signin

    Body: emailId + password for a user that already exists in MongoDB.
    Matches the mobile Sign In screen (work email + password only).
    """

    email = (
        str(payload.email_id)
        .lower()
        .strip()
    )

    user = users_collection.find_one(
        {
            "email": email
        }
    )

    if not user:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(
        payload.password,
        user.get(
            "password_hash",
            "",
        ),
    ):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.get("status") != "active":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    user_id = user["_id"]

    access_token = create_access_token(
        user_id
    )

    return {

        "status":
            "success",

        "message":
            "Sign in successful",

        "accessToken":
            access_token,

        "tokenType":
            "bearer",

        "user": {

            "id":
                user_id,

            "name":
                user.get("name"),

            "email":
                user.get("email"),

            "emailId":
                user.get("email"),

            "status":
                user.get("status"),

            "onboardingCompleted":
                user.get(
                    "onboarding_completed",
                    False,
                ),
        },
    }


# ============================================================
# GET ME
# ============================================================

@router.get(
    "/me"
)
async def get_me(
    current_user=Depends(
        get_current_user
    ),
):
    """
    Get currently authenticated EMC user.

    GET /api/v1/auth/me
    """

    return {

        "status":
            "success",

        "user": {

            "id":
                current_user.get(
                    "_id"
                ),

            "name":
                current_user.get(
                    "name"
                ),

            "email":
                current_user.get(
                    "email"
                ),

            "status":
                current_user.get(
                    "status"
                ),

            "onboardingCompleted":
                current_user.get(
                    "onboarding_completed",
                    False,
                ),

            "role":
                current_user.get(
                    "role"
                ),

            "company":
                current_user.get(
                    "company"
                ),

            "jobTitle":
                current_user.get(
                    "job_title"
                ),

            "teamSize":
                current_user.get(
                    "team_size"
                ),
        },
    }


# ============================================================
# COMPLETE ONBOARDING
# ============================================================

# @router.post(
#     "/onboarding/complete"
# )
# async def complete_onboarding(
#     payload: OnboardingCompleteRequest,

#     current_user=Depends(
#         get_current_user
#     ),
# ):
#     """
#     Complete EMC user onboarding.

#     POST /api/v1/auth/onboarding/complete
#     """

#     user_id = current_user.get(
#         "_id"
#     )

#     # --------------------------------------------------------
#     # 1. Update onboarding information
#     # --------------------------------------------------------

#     update_data = {

#         "onboarding_completed":
#             True,

#         "role":
#             payload.role,

#         "company":
#             payload.company,

#         "job_title":
#             payload.job_title,

#         "team_size":
#             payload.team_size,
#     }

#     # --------------------------------------------------------
#     # 2. Update MongoDB
#     # --------------------------------------------------------

#     try:

#         result = users_collection.update_one(

#             {
#                 "_id":
#                     user_id
#             },

#             {
#                 "$set":
#                     update_data
#             },
#         )

#     except Exception as exc:

#         raise HTTPException(
#             status_code=500,
#             detail=(
#                 "Failed to complete onboarding: "
#                 f"{str(exc)}"
#             ),
#         )

#     # --------------------------------------------------------
#     # 3. Check user
#     # --------------------------------------------------------

#     if result.matched_count == 0:

#         raise HTTPException(
#             status_code=404,
#             detail="User not found",
#         )

#     # --------------------------------------------------------
#     # 4. Return response
#     # --------------------------------------------------------

#     return {

#         "status":
#             "success",

#         "message":
#             "Onboarding completed successfully",

#         "user": {

#             "id":
#                 user_id,

#             "onboardingCompleted":
#                 True,

#             "role":
#                 payload.role,

#             "company":
#                 payload.company,

#             "jobTitle":
#                 payload.job_title,

#             "teamSize":
#                 payload.team_size,
#         },
#     }