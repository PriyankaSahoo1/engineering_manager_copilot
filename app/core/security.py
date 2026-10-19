from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext


# ============================================================
# JWT CONFIGURATION
# ============================================================

JWT_SECRET = "change-this-secret-key"

JWT_ALGORITHM = "HS256"

JWT_EXPIRES_MINUTES = 10080


# ============================================================
# PASSWORD HASHING
# ============================================================

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(
    password: str,
) -> str:

    return pwd_context.hash(
        password
    )


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:

    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


# ============================================================
# CREATE ACCESS TOKEN
# ============================================================

def create_access_token(
    user_id: str,
) -> str:

    expire = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=JWT_EXPIRES_MINUTES
        )
    )

    payload = {
        "sub": user_id,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


# ============================================================
# GET USER ID FROM TOKEN
# ============================================================

def get_user_id_from_token(
    token: str,
) -> str | None:

    try:

        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

        return payload.get("sub")

    except JWTError:

        return None