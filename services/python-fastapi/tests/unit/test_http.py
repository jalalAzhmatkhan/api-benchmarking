"""The HTTP contract through the real app, routes and repository, with an in-memory pool."""

from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from app.main import create_app
from tests.unit.fakes import FakePool

BODY = {"name": "Widget", "description": "Blue", "price_cents": 1999, "quantity": 5}
ERROR_CODES = {"VALIDATION_ERROR", "NOT_FOUND", "INTERNAL_ERROR"}


@pytest.fixture
def pool() -> FakePool:
    return FakePool()


@pytest.fixture
def client(pool: FakePool) -> Iterator[TestClient]:
    pool_sizes: list[tuple[str, int]] = []

    async def factory(dsn: str, size: int) -> FakePool:
        pool_sizes.append((dsn, size))
        return pool

    app = create_app({"DATABASE_URL": "postgres://t", "DB_POOL_SIZE": "10", "WORKER_DB_POOL_SIZE": "5"}, factory)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        assert pool_sizes == [("postgres://t", 5)]
        yield test_client
    assert pool.closed


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == code
    assert set(response.json()) == {"error"} and response.json()["error"]["code"] in ERROR_CODES


def test_create_get_put_delete_journey(client: TestClient) -> None:
    created = client.post("/items", json=BODY)
    assert created.status_code == 201
    assert created.headers["location"] == "/items/100001"
    item = created.json()
    assert item == {
        **BODY,
        "id": 100001,
        "created_at": "2026-10-03T10:00:00.123Z",
        "updated_at": "2026-10-03T10:00:00.123Z",
    }
    assert client.get("/items/100001").json() == item
    updated = client.put("/items/100001", json={"name": "N", "price_cents": 0, "quantity": 0, "ignored": True})
    assert updated.status_code == 200
    assert (updated.json()["name"], updated.json()["description"]) == ("N", None)
    deleted = client.delete("/items/100001")
    assert (deleted.status_code, deleted.content) == (204, b"")
    assert_error(client.get("/items/100001"), 404, "NOT_FOUND")


def test_missing_items_are_404(client: TestClient) -> None:
    assert_error(client.get("/items/5"), 404, "NOT_FOUND")
    assert_error(client.put("/items/5", json=BODY), 404, "NOT_FOUND")
    assert_error(client.delete("/items/5"), 404, "NOT_FOUND")


@pytest.mark.parametrize("raw_id", ["0", "abc", "-1", "+5", "1.5", "1_0", "%205", "9007199254740992", "١٢٣"])
def test_invalid_ids_are_400(client: TestClient, raw_id: str, pool: FakePool) -> None:
    for call in (
        client.get(f"/items/{raw_id}"),
        client.put(f"/items/{raw_id}", json=BODY),
        client.delete(f"/items/{raw_id}"),
    ):
        assert_error(call, 400, "VALIDATION_ERROR")
    assert pool.statements == []


@pytest.mark.parametrize(
    "body",
    [
        {**BODY, "name": ""},
        {**BODY, "name": "x" * 101},
        {**BODY, "description": "x" * 1001},
        {**BODY, "price_cents": -1},
        {**BODY, "price_cents": 2**53},
        {**BODY, "quantity": 2**31},
        {**BODY, "price_cents": "10"},
        {**BODY, "price_cents": 1.5},
        {**BODY, "price_cents": 10.0},
        {**BODY, "quantity": True},
        {**BODY, "name": 5},
        {**BODY, "description": 5},
        {"description": "x", "price_cents": 1, "quantity": 1},
        {"name": "n", "quantity": 1},
        {"name": "n", "price_cents": 1},
        [],
        "text",
        None,
    ],
)
def test_invalid_bodies_are_400(client: TestClient, body: object, pool: FakePool) -> None:
    assert_error(client.post("/items", json=body), 400, "VALIDATION_ERROR")
    assert_error(client.put("/items/1", json=body), 400, "VALIDATION_ERROR")
    assert pool.statements == []


def test_malformed_and_empty_bodies_are_400(client: TestClient) -> None:
    for content, content_type in [
        (b"{not json", "application/json"),
        (b"", "application/json"),
        (b'{"name":"n","price_cents":1,"quantity":1}', "text/plain"),
        (b'{"name":"n","price_cents":NaN,"quantity":1}', "application/json"),
    ]:
        assert_error(
            client.post("/items", content=content, headers={"content-type": content_type}), 400, "VALIDATION_ERROR"
        )


def test_unknown_routes_and_methods(client: TestClient) -> None:
    assert_error(client.get("/nope"), 404, "NOT_FOUND")
    assert_error(client.get("/items"), 405, "VALIDATION_ERROR")
    assert client.get("/items").headers["allow"] == "POST"
    assert_error(client.get("/items/"), 404, "NOT_FOUND")  # no trailing-slash redirect
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_unexpected_failures_are_500_without_leaking(client: TestClient, pool: FakePool) -> None:
    pool.fail = True
    response = client.get("/items/1")
    assert_error(response, 500, "INTERNAL_ERROR")
    assert "database" not in response.text


def test_no_cache_or_compression_headers(client: TestClient) -> None:
    response = client.post("/items", json=BODY, headers={"accept-encoding": "gzip"})
    assert not {"etag", "cache-control", "content-encoding"} & set(response.headers)
