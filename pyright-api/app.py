import asyncio
import json
import os
import pathlib
import subprocess  # noqa: S404 # sanitized use
from typing import Any

import orjson
from litestar import Litestar, MediaType, Request, Response, post
from litestar.connection import ASGIConnection
from litestar.exceptions import HTTPException, NotAuthorizedException
from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult
from litestar.middleware.base import DefineMiddleware
from litestar.middleware.rate_limit import RateLimitConfig

from .shell_reader import ShellReader
from .types_ import PyrightPayload, PyrightResponse

OWNER_TOKEN_FILE = pathlib.Path("/run/secrets/api_key")
try:
    _token = OWNER_TOKEN_FILE.read_text("utf8")
except FileNotFoundError:
    _token = os.getenv("API_KEY")
if not _token:
    msg = "API key has not been allocated."
    raise RuntimeError(msg)

OWNER_TOKEN = _token


PYRIGHT_CONFIG = pathlib.Path() / "pyrightconfig.json"
if not PYRIGHT_CONFIG.exists():
    PYRIGHT_CONFIG.touch(0o777, exist_ok=True)
    with PYRIGHT_CONFIG.open("w") as fp:
        json.dump(
            {
                "pythonVersion": "3.13",
                "typeCheckingMode": "strict",
                "useLibraryCodeForTypes": False,
                "reportMissingImports": True,
            },
            fp,
            ensure_ascii=True,
            indent=2,
        )

__all__ = ("app",)


def _bypass_for_owner(request: Request[Any, Any, Any]) -> bool:
    auth = request.headers.get("Authorization")
    if not auth:
        return True

    return auth != OWNER_TOKEN


def _create_temp_file(content: str) -> pathlib.Path:
    rand = os.urandom(10).hex()
    path = pathlib.Path() / f"{rand}_pyrightexec.py"

    path.touch(exist_ok=True)

    with path.open("w") as fp:
        fp.write(content)

    return path


def _get_versions() -> PyrightResponse:
    py = subprocess.run(["/bin/bash", "-c", "python -V"], capture_output=True, check=False)
    node = subprocess.run(["/bin/bash", "-c", "node -v"], capture_output=True, check=False)
    pyright = subprocess.run(["/bin/bash", "-c", "pyright --version"], capture_output=True, check=False)

    return {
        "python_version": py.stdout.decode().split(" ")[1].strip(),
        "node_version": node.stdout.decode().strip(),
        "pyright_version": pyright.stdout.decode().split(" ")[1].strip(),
    }  # pyright: ignore[reportReturnType]


class TokenAuthMiddleware(AbstractAuthenticationMiddleware):
    async def authenticate_request(self, connection: ASGIConnection[Any, Any, Any, Any]) -> AuthenticationResult:
        auth_header = connection.headers.get("Authorization")
        if not auth_header or auth_header != OWNER_TOKEN:
            raise NotAuthorizedException

        return AuthenticationResult(user="Owner", auth=auth_header)


auth_middleware = DefineMiddleware(TokenAuthMiddleware)

rl_middleware = RateLimitConfig(
    ("minute", 4),
    check_throttle_handler=_bypass_for_owner,
    rate_limit_limit_header_key="X-Ratelimit-Limit",
    rate_limit_policy_header_key="X-Ratelimit-Policy",
    rate_limit_remaining_header_key="X-Ratelimit-Remaining",
    rate_limit_reset_header_key="X-Ratelimit-Reset",
)


@post(path="/submit")
async def perform_type_checking(data: PyrightPayload) -> Response[PyrightResponse]:
    file = _create_temp_file(data["content"])
    python_ver = data.get("version", "3.13")

    with ShellReader(f"pyright --outputjson {file.name} --pythonversion {python_ver}") as reader:
        lines = [line async for line in reader if not line.startswith("[stderr] ")]
    stringed = "".join(lines)

    file.unlink(missing_ok=True)

    result = _get_versions()

    try:
        parsed = orjson.loads("".join(stringed))
    except orjson.JSONDecodeError as err:
        raise HTTPException(detail="Unable to parse pyright response", status_code=500) from err

    result["result"] = parsed

    return Response(content=result, media_type=MediaType.JSON, status_code=200)


@post(path="/update", middleware=[auth_middleware])
async def update_pyright() -> Response[str]:
    proc = await asyncio.create_subprocess_shell("/bin/bash -c npm install -g pyright@latest")

    if proc.returncode == 0:
        return Response(content="OK", status_code=201)
    return Response(content="Error", status_code=500)


app = Litestar(route_handlers=[perform_type_checking, update_pyright], middleware=[rl_middleware.middleware])
