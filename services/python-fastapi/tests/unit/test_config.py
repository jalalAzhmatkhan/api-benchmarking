import pytest

from app.infrastructure.config import DEFAULT_DATABASE_URL, load_config, worker_pool_size


def test_defaults() -> None:
    config = load_config({})
    assert (config.database_url, config.port, config.pool_size, config.worker_pool_size) == (
        DEFAULT_DATABASE_URL,
        8080,
        10,
        10,
    )


def test_empty_values_count_as_unset() -> None:
    config = load_config({"DATABASE_URL": "", "PORT": "", "DB_POOL_SIZE": "", "WORKER_DB_POOL_SIZE": ""})
    assert (config.database_url, config.port, config.pool_size, config.worker_pool_size) == (
        DEFAULT_DATABASE_URL,
        8080,
        10,
        10,
    )


def test_explicit_values() -> None:
    config = load_config(
        {"DATABASE_URL": "postgres://x", "PORT": "9000", "DB_POOL_SIZE": "20", "WORKER_DB_POOL_SIZE": "7"}
    )
    assert (config.database_url, config.port, config.pool_size, config.worker_pool_size) == (
        "postgres://x",
        9000,
        20,
        7,
    )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("PORT", "0"),
        ("PORT", "65536"),
        ("PORT", "abc"),
        ("PORT", "-1"),
        ("DB_POOL_SIZE", "0"),
        ("DB_POOL_SIZE", "1.5"),
        ("DB_POOL_SIZE", "²"),
        ("WORKER_DB_POOL_SIZE", "x"),
    ],
)
def test_invalid_values(key: str, value: str) -> None:
    with pytest.raises(ValueError, match=key):
        load_config({key: value})


@pytest.mark.parametrize(
    ("total", "workers", "expected"),
    [(10, 1, [10]), (10, 2, [5, 5]), (10, 3, [4, 3, 3]), (10, 5, [2] * 5), (4, 2, [2, 2]), (20, 2, [10, 10])],
)
def test_worker_pool_split(total: int, workers: int, expected: list[int]) -> None:
    shares = [worker_pool_size(total, workers, slot) for slot in range(workers)]
    assert shares == expected
    assert sum(shares) == total
