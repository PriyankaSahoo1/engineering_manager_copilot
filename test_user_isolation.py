"""
End-to-end user isolation test against a RUNNING server.

Start the API first:

    uvicorn app.main:app --reload

Then run:

    python test_user_isolation.py

To also exercise the AI trigger (calls Groq, costs tokens):

    python test_user_isolation.py --ai

What it proves:

    - two fresh users are created via signup
    - login returns a working token
    - user A's project, uploaded file, findings and review
      brief are invisible to user B
    - requests with no token / a bad token are rejected
    - user A still has full access to their own data
"""

import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx


BASE_URL = "http://127.0.0.1:8000"

RUN_AI = "--ai" in sys.argv

FAILURES = []


# ============================================================
# HELPERS
# ============================================================

def check(label, actual, expected):

    ok = actual == expected

    if not ok:
        FAILURES.append(
            f"{label}: got {actual!r}, expected {expected!r}"
        )

    print(
        f"{'PASS' if ok else 'FAIL'}  "
        f"{label:38} -> {actual}"
    )


def headers_for(token):
    return {
        "Authorization": f"Bearer {token}"
    }


def signup(client, tag):
    """
    Create a fresh user and return (token, user_id, email).
    """

    email = f"iso_{tag}_{uuid4().hex[:8]}@example.com"

    password = "Password123"

    response = client.post(
        "/api/v1/auth/signup",
        json={
            "name": f"Isolation User {tag}",
            "email": email,
            "password": password,
        },
    )

    if response.status_code != 201:
        raise SystemExit(
            f"Signup failed ({response.status_code}): "
            f"{response.text}"
        )

    body = response.json()

    return (
        body["accessToken"],
        body["user"]["id"],
        email,
        password,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    client = httpx.Client(
        base_url=BASE_URL,
        timeout=120.0,
    )

    # --------------------------------------------------------
    # Server reachable?
    # --------------------------------------------------------

    try:
        client.get("/health")
    except httpx.ConnectError:
        raise SystemExit(
            f"Cannot reach {BASE_URL}. Start the server "
            "with: uvicorn app.main:app --reload"
        )

    # --------------------------------------------------------
    # Two users
    # --------------------------------------------------------

    token_a, uid_a, email_a, password_a = signup(
        client,
        "a",
    )

    token_b, uid_b, _, _ = signup(
        client,
        "b",
    )

    headers_a = headers_for(token_a)
    headers_b = headers_for(token_b)

    print(f"user A = {uid_a}")
    print(f"user B = {uid_b}")

    # --------------------------------------------------------
    # Login
    # --------------------------------------------------------

    print("\n--- login ---")

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email_a,
            "password": password_a,
        },
    )

    check(
        "login A correct password",
        response.status_code,
        200,
    )

    check(
        "login A returns own id",
        response.json()["user"]["id"],
        uid_a,
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email_a,
            "password": "wrong-password",
        },
    )

    check(
        "login A wrong password",
        response.status_code,
        401,
    )

    # --------------------------------------------------------
    # User A creates data
    # --------------------------------------------------------

    print("\n--- user A creates a project and uploads a file ---")

    response = client.post(
        "/api/v1/projects",
        headers=headers_a,
        json={
            "name": "Isolation test project",
            "objective": (
                "Confirm that project data stays private "
                "to the owning user."
            ),
            "analysis_focus": (
                "Access control, data ownership, "
                "per-user scoping."
            ),
        },
    )

    check(
        "A create project",
        response.status_code,
        200,
    )

    project_a = response.json()["project"]["id"]

    check(
        "A project carries userId",
        response.json()["project"]["userId"],
        uid_a,
    )

    # A real temp file so document processing can run.

    temp_dir = Path(
        tempfile.mkdtemp()
    )

    upload_path = temp_dir / "a_confidential.txt"

    upload_path.write_text(
        "Section 1. Overview\n\n"
        "This document belongs to user A only.\n\n"
        "Section 2. Access Control\n\n"
        "Every record must be scoped to the owning user.\n"
        "Uploaded files must never be readable by another "
        "user.\n\n"
        "Section 3. Open Items\n\n"
        "The retention period has not been agreed yet.\n",
        encoding="utf-8",
    )

    with open(upload_path, "rb") as handle:

        response = client.post(
            f"/api/v1/projects/{project_a}/sources/upload",
            headers=headers_a,
            files={
                "file": (
                    upload_path.name,
                    handle,
                    "text/plain",
                )
            },
        )

    check(
        "A upload source",
        response.status_code,
        200,
    )

    source_a = response.json()["source"]["id"]

    check(
        "A source carries userId",
        response.json()["source"]["userId"],
        uid_a,
    )

    # --------------------------------------------------------
    # Optional AI trigger
    # --------------------------------------------------------

    if RUN_AI:

        print("\n--- AI trigger (user A) ---")

        response = client.post(
            f"/api/v1/projects/{project_a}/ai-trigger",
            headers=headers_a,
        )

        check(
            "A ai-trigger",
            response.status_code,
            200,
        )

        if response.status_code == 200:

            data = response.json()["data"]

            print(
                f"      findings={data['findingCount']} "
                f"questions={data['questionCount']} "
                f"changes={data['changeCount']}"
            )

            check(
                "A ai-trigger returns own userId",
                data["userId"],
                uid_a,
            )

    # --------------------------------------------------------
    # User B reaching for user A's data
    # --------------------------------------------------------

    print("\n--- user B reaching for user A's data ---")

    response = client.get(
        "/api/v1/projects",
        headers=headers_b,
    )

    check(
        "B sees A's project in list",
        any(
            project["id"] == project_a
            for project in response.json()["projects"]
        ),
        False,
    )

    check(
        "B GET A's project",
        client.get(
            f"/api/v1/projects/{project_a}",
            headers=headers_b,
        ).status_code,
        404,
    )

    check(
        "B GET A's sources",
        client.get(
            f"/api/v1/projects/{project_a}/sources",
            headers=headers_b,
        ).status_code,
        404,
    )

    with open(upload_path, "rb") as handle:

        check(
            "B upload into A's project",
            client.post(
                f"/api/v1/projects/{project_a}/sources/upload",
                headers=headers_b,
                files={
                    "file": (
                        "b.txt",
                        handle,
                        "text/plain",
                    )
                },
            ).status_code,
            404,
        )

    check(
        "B DELETE A's source",
        client.delete(
            f"/api/v1/projects/{project_a}"
            f"/sources/{source_a}",
            headers=headers_b,
        ).status_code,
        404,
    )

    response = client.get(
        f"/api/v1/projects/{project_a}/findings",
        headers=headers_b,
    )

    check(
        "B findings of A's project",
        response.json()["data"]["findingCount"],
        0,
    )

    check(
        "B GET A's review brief",
        client.get(
            f"/api/v1/projects/{project_a}/review-brief",
            headers=headers_b,
        ).status_code,
        404,
    )

    check(
        "B ai-trigger on A's project",
        client.post(
            f"/api/v1/projects/{project_a}/ai-trigger",
            headers=headers_b,
        ).status_code,
        400,
    )

    check(
        "B DELETE A's project",
        client.delete(
            f"/api/v1/projects/{project_a}",
            headers=headers_b,
        ).status_code,
        404,
    )

    # --------------------------------------------------------
    # No token / bad token
    # --------------------------------------------------------

    print("\n--- no token ---")

    check(
        "anon project list",
        client.get(
            "/api/v1/projects"
        ).status_code,
        401,
    )

    check(
        "bad token project list",
        client.get(
            "/api/v1/projects",
            headers={
                "Authorization": "Bearer not-a-real-token"
            },
        ).status_code,
        401,
    )

    # --------------------------------------------------------
    # Owner still has access
    # --------------------------------------------------------

    print("\n--- user A still has access ---")

    response = client.get(
        "/api/v1/projects",
        headers=headers_a,
    )

    check(
        "A sees own project in list",
        any(
            project["id"] == project_a
            for project in response.json()["projects"]
        ),
        True,
    )

    check(
        "A GET own project",
        client.get(
            f"/api/v1/projects/{project_a}",
            headers=headers_a,
        ).status_code,
        200,
    )

    response = client.get(
        f"/api/v1/projects/{project_a}/sources",
        headers=headers_a,
    )

    check(
        "A own source count",
        response.json()["count"],
        1,
    )

    if RUN_AI:

        response = client.get(
            f"/api/v1/projects/{project_a}/findings",
            headers=headers_a,
        )

        check(
            "A sees own findings",
            response.json()["data"]["findingCount"] > 0,
            True,
        )

        check(
            "A GET own review brief",
            client.get(
                f"/api/v1/projects/{project_a}"
                f"/review-brief",
                headers=headers_a,
            ).status_code,
            200,
        )

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    print("\n--- cleanup ---")

    check(
        "A DELETE own source",
        client.delete(
            f"/api/v1/projects/{project_a}"
            f"/sources/{source_a}",
            headers=headers_a,
        ).status_code,
        200,
    )

    check(
        "A DELETE own project",
        client.delete(
            f"/api/v1/projects/{project_a}",
            headers=headers_a,
        ).status_code,
        200,
    )

    upload_path.unlink(
        missing_ok=True
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    print("\n" + "=" * 60)

    if FAILURES:

        print(f"{len(FAILURES)} FAILURE(S):")

        for failure in FAILURES:
            print(f"  - {failure}")

        raise SystemExit(1)

    print("ALL ISOLATION CHECKS PASSED")


if __name__ == "__main__":
    main()
