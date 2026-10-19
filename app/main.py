from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from app.db.mongodb import ensure_collections, ping_mongodb
from app.db.seed_users import seed_company_users
from app.services.vector_index import ensure_vector_index
from app.api.routes.upload import router as upload_router
from app.api.routes.findings import router as findings_router
from app.api.routes.questions import router as questions_router
from app.api.routes.ai_review import router as ai_review_router
from app.api.routes.review_brief import router as review_brief_router
from app.api.routes.decisions import router as decisions_router
from app.api.routes.changes import router as changes_router
from app.api.routes import projects
from app.api.routes import auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Checking MongoDB...")
    ping_mongodb()
    ensure_collections()
    seed_company_users()
    print("MongoDB connected; company users ready for sign-in.")
    ensure_vector_index()
    yield

app = FastAPI(title="Engineering Manager Copilot", version="1.0.0", lifespan=lifespan)

app.include_router(auth.router)

app.include_router(projects.router)
app.include_router(upload_router)
app.include_router(findings_router)
app.include_router(questions_router)
app.include_router(ai_review_router)
app.include_router( review_brief_router)
app.include_router(decisions_router)
app.include_router(changes_router)


# ============================================================
# OPENAPI SCHEMA
# ============================================================

def custom_openapi():
    """
    Swagger UI does not render OpenAPI 3.1 binary array
    items as a file picker, so restore the 3.0 style
    "format": "binary" that it does understand.
    """

    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )

    def restore_binary_format(node):

        if isinstance(node, dict):

            if node.get("contentMediaType") == "application/octet-stream":
                node.pop("contentMediaType", None)
                node["format"] = "binary"

            for value in node.values():
                restore_binary_format(value)

        elif isinstance(node, list):

            for value in node:
                restore_binary_format(value)

    restore_binary_format(
        schema.get("components", {}).get("schemas", {})
    )

    app.openapi_schema = schema

    return schema


app.openapi = custom_openapi



@app.get("/")
def root():
    return {"success": True, "message": "Engineering Manager Copilot API"}

@app.get("/health")
def health():
    return {"success": True, "status": "healthy"}
