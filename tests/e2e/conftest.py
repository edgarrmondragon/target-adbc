"""Shared fixtures and parametrization for e2e BatchProcessor tests."""

from __future__ import annotations

import dataclasses
import re
from typing import TYPE_CHECKING

import pytest
from adbc_driver_manager import ProgrammingError, dbapi
from testcontainers.community.mssql import SqlServerContainer
from testcontainers.community.postgres import PostgresContainer

from target_adbc import target as target_module
from target_adbc.target import TargetADBC

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

BACKENDS = ["duckdb", "sqlite", "postgres", "mssql"]


@dataclasses.dataclass
class BackendConnection:
    connection: dbapi.Connection
    schema_name: str | None


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "backend_connection" in metafunc.fixturenames:
        metafunc.parametrize("backend_connection", BACKENDS, indirect=True)


@pytest.fixture(scope="session")
def _postgres_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def _mssql_container() -> Generator[SqlServerContainer, None, None]:
    with SqlServerContainer() as container:
        yield container


def _connect(uri: str) -> dbapi.Connection:
    """Connect using the same driver-resolution logic as TargetADBC itself.

    This is deliberately not reimplemented here: duplicating the
    PyPI-bundled-driver-vs-`dbc`-manifest resolution logic is exactly what let
    this fixture drift out of sync with target.py in the first place.
    """
    target = TargetADBC(config={"uri": uri})
    return dbapi.connect(**target.get_connect_kwargs())


def _driver_available(scheme: str, package: str | None) -> bool:
    """Cheaply check whether a driver can be resolved, without connecting."""
    if package is not None and target_module._bundled_driver_path(package) is not None:  # ruff:ignore[private-member-access]
        return True
    try:
        dbapi.connect(driver=scheme)
    except ProgrammingError:
        return True  # driver loaded, just needs more args
    except Exception:  # ruff:ignore[blind-except]
        return False
    return True


@pytest.fixture
def backend_connection(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> Generator[BackendConnection, None, None]:
    backend: str = request.param
    if backend == "duckdb":
        conn = _connect(f"duckdb://{tmp_path.joinpath('test.duckdb').as_posix()}")
        yield BackendConnection(connection=conn, schema_name=None)
        conn.close()
    elif backend == "sqlite":
        conn = _connect(f"sqlite://{tmp_path.joinpath('test.sqlite').as_posix()}")
        yield BackendConnection(connection=conn, schema_name=None)
        conn.close()
    elif backend == "postgres":
        if not _driver_available("postgresql", "adbc_driver_postgresql"):
            pytest.skip("PostgreSQL ADBC driver not available")
        pg: PostgresContainer = request.getfixturevalue("_postgres_container")
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        conn = _connect(f"postgresql://{pg.username}:{pg.password}@{host}:{port}/{pg.dbname}")
        yield BackendConnection(connection=conn, schema_name="public")
        conn.close()
    elif backend == "mssql":
        if not _driver_available("mssql", None):
            pytest.skip("MSSQL ADBC driver not available")
        mssql: SqlServerContainer = request.getfixturevalue("_mssql_container")
        host = mssql.get_container_host_ip()
        port = mssql.get_exposed_port(1433)
        conn = _connect(f"mssql://SA:{mssql.password}@{host}:{port}?database={mssql.dbname}")
        yield BackendConnection(connection=conn, schema_name="dbo")
        conn.close()


@pytest.fixture
def table_name(request: pytest.FixtureRequest) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", request.node.name)
    return safe[:63]
