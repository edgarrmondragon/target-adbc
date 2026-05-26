"""Shared fixtures and parametrization for e2e BatchProcessor tests."""

from __future__ import annotations

import dataclasses
import re
from typing import TYPE_CHECKING

import pytest
from adbc_driver_manager import ProgrammingError, dbapi
from testcontainers.mssql import SqlServerContainer
from testcontainers.postgres import PostgresContainer

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


@pytest.fixture
def backend_connection(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> Generator[BackendConnection, None, None]:
    backend: str = request.param
    if backend == "duckdb":
        pytest.importorskip("duckdb")
        conn = dbapi.connect(driver="duckdb", db_kwargs={"path": str(tmp_path / "test.duckdb")})
        yield BackendConnection(connection=conn, schema_name=None)
        conn.close()
    elif backend == "sqlite":
        conn = dbapi.connect(
            driver="sqlite",
            db_kwargs={"uri": (tmp_path / "test.sqlite").as_uri()},
        )
        yield BackendConnection(connection=conn, schema_name=None)
        conn.close()
    elif backend == "postgres":
        try:
            dbapi.connect(driver="postgresql", db_kwargs={})
        except ProgrammingError:
            pass  # INVALID_STATE = driver loaded, just needs a URI
        except Exception as e:
            pytest.skip(f"PostgreSQL ADBC driver not available: {e}")
        pg_container: PostgresContainer = request.getfixturevalue("_postgres_container")
        host = pg_container.get_container_host_ip()
        port = pg_container.get_exposed_port(5432)
        uri = (
            f"postgresql://{pg_container.username}:{pg_container.password}"
            f"@{host}:{port}/{pg_container.dbname}"
        )
        conn = dbapi.connect(driver="postgresql", db_kwargs={"uri": uri})
        yield BackendConnection(connection=conn, schema_name="public")
        conn.close()
    elif backend == "mssql":
        try:
            dbapi.connect(driver="mssql", db_kwargs={})
        except ProgrammingError:
            pass  # INVALID_ARGUMENT = driver loaded, just needs a URI
        except Exception as e:
            pytest.skip(f"MSSQL ADBC driver not available: {e}")
        mssql_container: SqlServerContainer = request.getfixturevalue("_mssql_container")
        host = mssql_container.get_container_host_ip()
        port = mssql_container.get_exposed_port(1433)
        uri = f"sqlserver://SA:{mssql_container.password}@{host}:{port}?database={mssql_container.dbname}"
        conn = dbapi.connect(driver="mssql", db_kwargs={"uri": uri})
        yield BackendConnection(connection=conn, schema_name="dbo")
        conn.close()


@pytest.fixture
def table_name(request: pytest.FixtureRequest) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", request.node.name)
    return safe[:63]
