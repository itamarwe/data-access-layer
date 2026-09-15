"""FastAPI composition root and packaged single-page application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dal.curation import CurationError
from dal.repository import RecordNotFound, RepositoryError, RevisionConflict

from .config import ServerConfig
from .routes import catalog_router, curation_router, system_router
from .security import authentication_error
from .services import APIServices


def create_app(
    config: ServerConfig,
    *,
    services: APIServices | None = None,
    static_directory: Path | None = None,
) -> FastAPI:
    app = FastAPI(
        title="DAL context API",
        version="1.0.0",
        description="Search and curate trusted organizational data context.",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.state.config = config
    app.state.services = services or APIServices.create(config)

    @app.middleware("http")
    async def protect_api(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            error = authentication_error(request.headers.get("Authorization"), config.auth_token)
            if error:
                return JSONResponse({"detail": error[1]}, status_code=error[0])
        return await call_next(request)

    app.include_router(catalog_router)
    app.include_router(curation_router)
    app.include_router(system_router)
    _errors(app)
    _static(app, static_directory or Path(__file__).with_name("static"))
    return app


def _errors(app: FastAPI) -> None:
    @app.exception_handler(RevisionConflict)
    async def revision_conflict(_request: Request, error: RevisionConflict):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(RecordNotFound)
    async def missing_record(_request: Request, error: RecordNotFound):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @app.exception_handler(CurationError)
    async def invalid_curation(_request: Request, error: CurationError):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(RepositoryError)
    async def repository_error(_request: Request, error: RepositoryError):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(ValueError)
    async def invalid_request(_request: Request, error: ValueError):
        return JSONResponse({"detail": str(error)}, status_code=400)


def _static(app: FastAPI, directory: Path) -> None:
    if not (directory / "index.html").is_file():
        return
    assets = directory / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{path:path}", include_in_schema=False)
    async def application_shell(path: str = ""):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return FileResponse(directory / "index.html")
