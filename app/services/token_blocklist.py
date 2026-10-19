from datetime import datetime, timedelta, timezone

from app.core.security import JWT_EXPIRES_MINUTES
from app.db.mongodb import revoked_tokens_collection


# ============================================================
# TTL INDEX
#
# A revoked token only needs to be remembered until it would
# have expired on its own. MongoDB deletes each entry once
# expires_at passes, so the collection stays small.
# ============================================================

def ensure_token_blocklist_index():

    revoked_tokens_collection.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="revoked_token_ttl",
    )

    print(
        "Revoked token TTL index ready."
    )


# ============================================================
# REVOKE TOKEN
# ============================================================

def revoke_token(
    payload: dict,
    user_id: str,
) -> bool:
    """
    Record a token as signed out.

    The jti is stored as _id, so revoking the same token
    twice is a no-op rather than a duplicate row.

    Returns False for a legacy token issued before jti
    existed, which cannot be revoked individually.
    """

    jti = payload.get(
        "jti"
    )

    if not jti:
        return False

    exp = payload.get(
        "exp"
    )

    expires_at = (
        datetime.fromtimestamp(
            exp,
            tz=timezone.utc,
        )
        if exp
        else datetime.now(timezone.utc)
        + timedelta(
            minutes=JWT_EXPIRES_MINUTES
        )
    )

    revoked_tokens_collection.update_one(
        {
            "_id": jti
        },
        {
            "$setOnInsert": {

                "user_id":
                    user_id,

                "expires_at":
                    expires_at,

                "revoked_at":
                    datetime.now(
                        timezone.utc
                    ),
            }
        },
        upsert=True,
    )

    return True


# ============================================================
# IS TOKEN REVOKED
# ============================================================

def is_token_revoked(
    jti: str | None,
) -> bool:

    if not jti:
        return False

    return (
        revoked_tokens_collection.find_one(
            {
                "_id": jti
            },
            {
                "_id": 1
            },
        )
        is not None
    )
