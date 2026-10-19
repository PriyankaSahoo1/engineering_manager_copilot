"""Seed company users for sign-in (no public registration)."""

from uuid import uuid4

from app.core.security import hash_password
from app.db.mongodb import users_collection


COMPANY_USERS = [
    {
        "email": "akanksha@gmail.com",
        "password": "Qwerty@123",
        "name": "Akanksha",
    },
    {
        "email": "raju@gmail.com",
        "password": "Qwerty@123",
        "name": "Raju",
    },
]


def seed_company_users() -> None:
    users_collection.create_index("email", unique=True)

    for spec in COMPANY_USERS:
        email = spec["email"].lower().strip()
        existing = users_collection.find_one({"email": email})

        if existing:
            users_collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "password_hash": hash_password(spec["password"]),
                        "status": "active",
                        "name": spec.get("name"),
                    }
                },
            )
            print(f"Updated user: {email}")
            continue

        users_collection.insert_one(
            {
                "_id": f"user_{uuid4().hex[:12]}",
                "name": spec.get("name"),
                "email": email,
                "password_hash": hash_password(spec["password"]),
                "status": "active",
                "onboarding_completed": False,
                "role": None,
                "company": None,
                "job_title": None,
                "team_size": None,
            }
        )
        print(f"Seeded user: {email}")
