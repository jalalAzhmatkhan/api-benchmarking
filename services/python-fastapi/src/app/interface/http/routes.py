from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.application.use_cases import ItemUseCases
from app.domain.errors import NotFoundError, ValidationError
from app.interface.http.wire import ItemBody, error_body, parse_id, to_response

router = APIRouter()


def _use_cases(request: Request) -> ItemUseCases:
    return request.app.state.use_cases


@router.post("/items")
async def create_item(body: ItemBody, request: Request) -> Response:
    item = await _use_cases(request).create_item(body.to_input())
    return JSONResponse(to_response(item), status_code=201, headers={"Location": f"/items/{item.id}"})


@router.get("/items/{item_id}")
async def get_item(item_id: str, request: Request) -> Response:
    return JSONResponse(to_response(await _use_cases(request).get_item(parse_id(item_id))))


@router.put("/items/{item_id}")
async def replace_item(item_id: str, body: ItemBody, request: Request) -> Response:
    item = await _use_cases(request).replace_item(parse_id(item_id), body.to_input())
    return JSONResponse(to_response(item))


@router.delete("/items/{item_id}")
async def delete_item(item_id: str, request: Request) -> Response:
    await _use_cases(request).delete_item(parse_id(item_id))
    return Response(status_code=204)


def _error(status: int, code: str, message: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(error_body(code, message), status_code=status, headers=headers)


async def _on_validation_error(_: Request, exc: ValidationError) -> JSONResponse:
    return _error(400, "VALIDATION_ERROR", str(exc))


async def _on_not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return _error(404, "NOT_FOUND", str(exc))


async def _on_request_validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
    # FastAPI answers 422 with its own body; the contract says 400 with the shared error shape.
    return _error(400, "VALIDATION_ERROR", "invalid request body")


async def _on_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Framework-level errors (unknown route, wrong method...) keep their status in the contract's shape."""
    code = "NOT_FOUND" if exc.status_code == 404 else "VALIDATION_ERROR"
    return _error(exc.status_code, code, "invalid request", dict(exc.headers or {}))


async def _on_unexpected_error(_: Request, __: Exception) -> JSONResponse:
    return _error(500, "INTERNAL_ERROR", "internal error")


def install(app: FastAPI) -> None:
    """Routes and the error mapping of the contract. No middleware, no docs endpoints (benchmark-rules.md)."""
    app.include_router(router)
    app.add_exception_handler(ValidationError, _on_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(NotFoundError, _on_not_found)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _on_request_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _on_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _on_unexpected_error)
