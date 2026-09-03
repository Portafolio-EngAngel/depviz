from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import graphs

app = FastAPI(
    title="DepViz",
    description="Monorepo Dependency Graph Visualizer",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS — allow all origins so the frontend (served separately during dev)
# can reach the API without browser blocking.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static files — the compiled/vanilla frontend lives here.
# Mount at /static so assets (JS, CSS) are reachable at /static/<filename>.
# The root and /graph routes serve the HTML shells directly.
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(graphs.router)


# ---------------------------------------------------------------------------
# Frontend shell routes
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/graph", include_in_schema=False)
def serve_graph() -> FileResponse:
    return FileResponse("app/static/graph.html")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "depviz"}
