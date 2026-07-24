"""Shared fixtures and parametrization for e2e BatchProcessor tests."""

from __future__ import annotations

import dataclasses
import importlib.util
import os
import re
import sys
from typing import TYPE_CHECKING

import pytest
from adbc_driver_manager import ProgrammingError, dbapi
from testcontainers.community.mssql import SqlServerContainer
from testcontainers.community.postgres import PostgresContainer

from target_adbc.connect import get_connection

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

BACKENDS = ["duckdb", "sqlite", "postgres", "mssql"]

# testcontainers needs a Docker daemon, which isn't available on the macOS/Windows
# GitHub Actions runners. Only skip in CI so local runs on those platforms still work.
_SKIP_CONTAINER_BACKENDS = bool(os.environ.get("CI")) and sys.platform != "linux"


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


def _file_uri(scheme: str, path: Path) -> str:
    """Build a `scheme:///path` URI, including the empty-authority slash Windows needs.

    `PureWindowsPath.as_posix()` yields drive-letter paths like ``C:/Users/...``,
    which don't start with ``/``. Without a forced leading slash, `scheme://C:/...`
    parses `C:` as the URI authority instead of part of the path.
    """
    posix = path.as_posix()
    if not posix.startswith("/"):
        posix = f"/{posix}"
    return f"{scheme}://{posix}"


def _driver_available(scheme: str, package: str | None) -> bool:
    """Cheaply check whether a driver can be resolved, without connecting."""
    if package is not None and importlib.util.find_spec(package) is not None:
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
        conn = get_connection({"uri": f"duckdb://{tmp_path / 'test.duckdb'}"})
        yield BackendConnection(connection=conn, schema_name=None)
        conn.close()
    elif backend == "sqlite":
        conn = get_connection({"uri": f"sqlite://{tmp_path / 'test.sqlite'}"})
        yield BackendConnection(connection=conn, schema_name=None)
        conn.close()
    elif backend == "postgres":
        if _SKIP_CONTAINER_BACKENDS:
            pytest.skip("Container-based backends are skipped on non-Linux CI runners")
        if not _driver_available("postgresql", "adbc_driver_postgresql"):
            pytest.skip("PostgreSQL ADBC driver not available")
        pg: PostgresContainer = request.getfixturevalue("_postgres_container")
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        uri = f"postgresql://{pg.username}:{pg.password}@{host}:{port}/{pg.dbname}"
        conn = get_connection({"uri": uri})
        yield BackendConnection(connection=conn, schema_name="public")
        conn.close()
    elif backend == "mssql":
        if _SKIP_CONTAINER_BACKENDS:
            pytest.skip("Container-based backends are skipped on non-Linux CI runners")
        if not _driver_available("mssql", None):
            pytest.skip("MSSQL ADBC driver not available")
        mssql: SqlServerContainer = request.getfixturevalue("_mssql_container")
        host = mssql.get_container_host_ip()
        port = mssql.get_exposed_port(1433)
        uri = f"mssql://SA:{mssql.password}@{host}:{port}?database={mssql.dbname}"
        conn = get_connection({"uri": uri})
        yield BackendConnection(connection=conn, schema_name="dbo")
        conn.close()


@pytest.fixture
def table_name(request: pytest.FixtureRequest) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", request.node.name)
    return safe[:63]
