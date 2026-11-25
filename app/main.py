"""Application factory. Run with `uvicorn --factory app.main:create_app`."""

from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from app.api import api_router
from app.security import require_api_key
from app.settings import Settings

# Kept equal to the project version in pyproject.toml (checked by a test).
API_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Without settings, they are read from the environment.

    Authentication is a dependency of the whole application, so every route, including
    routes added later, is protected unless its path is in security.PUBLIC_PATHS. The default
    docs routes are disabled and served again below, behind the same dependency.
    """
    settings = settings or Settings()
    app = FastAPI(
        title="Cordel Vivo API",
        version=API_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(require_api_key)],
    )
    app.state.api_keys = settings.api_keys

    app.include_router(api_router)

    @app.get("/openapi.json", include_in_schema=False)
    def openapi() -> JSONResponse:
        return JSONResponse(app.openapi())

    @app.get("/docs", include_in_schema=False)
    def docs() -> HTMLResponse:
        return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} docs")

    return app
