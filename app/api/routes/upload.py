from pathlib import Path
from typing import List
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)

from app.core.deps import get_current_user

from app.db.mongodb import (
    projects_collection,
    sources_collection,
)


router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Sources"],
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}


MAX_FILES_PER_UPLOAD = 10

MAX_FILE_SIZE = 25 * 1024 * 1024   # 25 MB per file


# ============================================================
# SAVE ONE SOURCE
# ============================================================

async def save_one_source(
    project_id: str,
    user_id: str,
    file: UploadFile,
) -> dict:
    """
    Validate and store one uploaded file.

    Returns the stored source document, or raises
    ValueError with a client safe message.
    """

    # --------------------------------------------------------
    # a. Validate filename
    # --------------------------------------------------------

    original_filename = file.filename

    if not original_filename:
        raise ValueError("Filename is required")

    # --------------------------------------------------------
    # b. Validate extension
    # --------------------------------------------------------

    extension = (
        Path(original_filename)
        .suffix
        .lower()
    )

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. "
            "Only PDF, DOCX and TXT files are allowed."
        )

    # --------------------------------------------------------
    # c. Generate source ID and path
    # --------------------------------------------------------

    source_id = (
        f"source_{uuid4().hex[:12]}"
    )

    file_path = (
        UPLOAD_DIR /
        f"{source_id}{extension}"
    )

    # --------------------------------------------------------
    # d. Stream to disk, enforcing the size cap
    # --------------------------------------------------------

    written = 0

    try:

        with open(file_path, "wb") as buffer:

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                written += len(chunk)

                if written > MAX_FILE_SIZE:
                    raise ValueError(
                        "File exceeds the "
                        f"{MAX_FILE_SIZE // (1024 * 1024)} MB limit"
                    )

                buffer.write(chunk)

    except ValueError:

        file_path.unlink(missing_ok=True)
        raise

    except Exception as exc:

        file_path.unlink(missing_ok=True)

        raise ValueError(
            "Failed to save uploaded file: "
            f"{str(exc)}"
        )

    # --------------------------------------------------------
    # e. Reject empty files
    # --------------------------------------------------------

    if written == 0:

        file_path.unlink(missing_ok=True)

        raise ValueError("File is empty")

    # --------------------------------------------------------
    # f. Create source document
    # --------------------------------------------------------

    source_document = {

        "_id": source_id,

        "project_id": project_id,

        "user_id": user_id,

        "source_name": original_filename,

        "source_type": extension.replace(".", ""),

        "source_size": written,

        "file_path": str(file_path),
    }

    # --------------------------------------------------------
    # g. Insert into MongoDB
    # --------------------------------------------------------

    try:

        sources_collection.insert_one(
            source_document
        )

    except Exception as exc:

        file_path.unlink(missing_ok=True)

        raise ValueError(
            "Failed to create source: "
            f"{str(exc)}"
        )

    return source_document


# ============================================================
# SHAPE SOURCE
# ============================================================

def shape_source(
    source: dict,
) -> dict:
    """
    Convert a stored source document into the
    camelCase API shape.
    """

    return {

        "id":
            source["_id"],

        "projectId":
            source["project_id"],

        "userId":
            source["user_id"],

        "sourceName":
            source["source_name"],

        "sourceType":
            source["source_type"],

        "sourceSize":
            source["source_size"],

        "filePath":
            source["file_path"],
    }


# ============================================================
# UPLOAD SOURCES
# ============================================================

@router.post(
    "/{project_id}/sources/upload"
)
async def upload_sources(
    project_id: str,

    files: List[UploadFile] = File(...),

    current_user=Depends(
        get_current_user
    ),
):
    """
    Upload one or more PDF, DOCX, or TXT sources for
    a project.

    Each source is stamped with the uploader user id, so
    only the uploader can read, review or delete it.

    Each file is processed independently, so one bad
    file does not fail the rest of the batch.

    Flow:

        project_id
             |
        Validate project ownership
             |
        Validate the batch
             |
        Save each file independently
             |
        Return uploaded and failed sources
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Validate project ownership
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 2. Validate the batch
    # --------------------------------------------------------

    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one file is required",
        )

    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=(
                "Too many files. At most "
                f"{MAX_FILES_PER_UPLOAD} files "
                "per upload."
            ),
        )

    # --------------------------------------------------------
    # 3. Process each file independently
    # --------------------------------------------------------

    uploaded = []
    failed = []

    for file in files:

        try:

            source_document = await save_one_source(
                project_id,
                user_id,
                file,
            )

        except ValueError as exc:

            failed.append({
                "sourceName": file.filename,
                "error": str(exc),
            })

            continue

        uploaded.append(
            shape_source(source_document)
        )

    # --------------------------------------------------------
    # 4. Fail the request when nothing landed
    # --------------------------------------------------------

    if not uploaded:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "No files were uploaded",
                "failed": failed,
            },
        )

    # --------------------------------------------------------
    # 5. Keep project.source_count in sync
    # --------------------------------------------------------

    projects_collection.update_one(
        {
            "_id": project_id,
            "user_id": user_id,
        },
        {
            "$inc": {
                "source_count": len(uploaded),
            },
        },
    )

    # --------------------------------------------------------
    # 6. Return response
    # --------------------------------------------------------

    return {

        "status":
            "success" if not failed else "partial",

        "message":
            f"{len(uploaded)} of {len(files)} "
            "sources uploaded successfully",

        "projectId": project_id,

        "uploadedCount": len(uploaded),

        "failedCount": len(failed),

        "sources": uploaded,

        "failed": failed,
    }


# ============================================================
# GET SOURCES FOR PROJECT
# ============================================================

@router.get(
    "/{project_id}/sources"
)
async def get_project_sources(
    project_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Get all sources the logged in user uploaded to
    a project.

    Flow:

        project_id
             ↓
        Validate project ownership
             ↓
        Find sources
             ↓
        Return source list
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Validate project ownership
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 2. Get sources
    # --------------------------------------------------------

    sources = sources_collection.find(
        {
            "project_id": project_id,

            "user_id": user_id,
        }
    )

    # --------------------------------------------------------
    # 3. Build response
    # --------------------------------------------------------

    source_list = []

    for source in sources:

        source_list.append(
            {
                "id": source.get("_id"),

                "projectId": source.get(
                    "project_id"
                ),

                "sourceName": source.get(
                    "source_name"
                ),

                "sourceType": source.get(
                    "source_type"
                ),

                "sourceSize": source.get(
                    "source_size"
                ),

                "filePath": source.get(
                    "file_path"
                ),
            }
        )

    # --------------------------------------------------------
    # 4. Return response
    # --------------------------------------------------------

    return {

        "status": "success",

        "projectId": project_id,

        "count": len(source_list),

        "sources": source_list,
    }


# ============================================================
# DELETE SOURCE
# ============================================================

@router.delete(
    "/{project_id}/sources/{source_id}"
)
async def delete_source(
    project_id: str,
    source_id: str,

    current_user=Depends(
        get_current_user
    ),
):
    """
    Delete a source the logged in user uploaded.

    Flow:

        project_id + source_id
                 ↓
        Validate project ownership
                 ↓
           Find source
                 ↓
        Delete physical file
                 ↓
        Delete MongoDB source
                 ↓
          Return success
    """

    user_id = current_user["id"]

    # --------------------------------------------------------
    # 1. Validate project ownership
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 2. Find source
    # --------------------------------------------------------

    source = sources_collection.find_one(
        {
            "_id": source_id,

            "project_id": project_id,

            "user_id": user_id,
        }
    )

    if not source:

        raise HTTPException(
            status_code=404,
            detail="Source not found",
        )

    # --------------------------------------------------------
    # 3. Delete physical file
    # --------------------------------------------------------

    file_path = source.get(
        "file_path"
    )

    if file_path:

        try:

            Path(
                file_path
            ).unlink(
                missing_ok=True
            )

        except Exception as exc:

            raise HTTPException(
                status_code=500,
                detail=(
                    "Failed to delete source file: "
                    f"{str(exc)}"
                ),
            )

    # --------------------------------------------------------
    # 4. Delete source from MongoDB
    # --------------------------------------------------------

    try:

        result = sources_collection.delete_one(
            {
                "_id": source_id,

                "project_id": project_id,

                "user_id": user_id,
            }
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to delete source: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # 5. Verify deletion
    # --------------------------------------------------------

    if result.deleted_count == 0:

        raise HTTPException(
            status_code=404,
            detail="Source not found",
        )

    # --------------------------------------------------------
    # 6. Keep project.source_count in sync
    # --------------------------------------------------------

    projects_collection.update_one(
        {
            "_id": project_id,
            "user_id": user_id,
            "source_count": {"$gt": 0},
        },
        {
            "$inc": {
                "source_count": -1,
            },
        },
    )

    # --------------------------------------------------------
    # 7. Return response
    # --------------------------------------------------------

    return {

        "status": "success",

        "message":
            "Source deleted successfully",

        "source": {

            "id":
                source_id,

            "projectId":
                project_id,

            "sourceName":
                source.get(
                    "source_name"
                ),
        },
    }



















