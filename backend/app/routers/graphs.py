from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.graph import GraphResult
from app.services.graph import build_graph
from app.services.parser import parse_zip

router = APIRouter(prefix="/graphs", tags=["graphs"])


@router.post(
    "/analyze",
    response_model=GraphResult,
    summary="Analyze a monorepo ZIP archive",
    description=(
        "Upload a ZIP file containing a monorepo. "
        "The service scans all package.json and requirements.txt files, "
        "builds a dependency graph, detects circular dependencies, "
        "and returns the full graph result."
    ),
)
async def analyze_repo(file: UploadFile = File(...)) -> GraphResult:
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Only ZIP files are supported. Please upload a file ending in .zip.",
        )

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        dep_map = parse_zip(content)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse ZIP archive: {exc}",
        ) from exc

    if not dep_map:
        raise HTTPException(
            status_code=422,
            detail=(
                "No package.json or requirements.txt files were found in the ZIP. "
                "Make sure your archive contains at least one dependency manifest."
            ),
        )

    return build_graph(dep_map)
