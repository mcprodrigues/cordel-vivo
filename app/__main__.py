"""Run the API: `uv run python -m app` (host and port from CORDEL_API_HOST/PORT)."""

import uvicorn

from app.settings import ServerSettings


def main() -> None:
    server = ServerSettings()
    uvicorn.run("app.main:create_app", factory=True, host=server.host, port=server.port)


if __name__ == "__main__":
    main()
