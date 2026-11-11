import importlib.util
import os
import tempfile
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple, TypedDict

import adbc_driver_manager.dbapi
import tomli_w

from target_adbc._profiles import profile_from_uri


class ConnectKwargs(TypedDict, total=False):
    driver: str | Path | None
    entrypoint: str
    db_kwargs: dict[str, str] | None


def get_connection(config: Mapping[str, Any]) -> adbc_driver_manager.dbapi.Connection:
    conn = _open_connection(config)

    if init_sql := config.get("connection_init_sql"):
        try:
            with conn.cursor() as cur:
                for statement in init_sql:
                    cur.execute(statement)
            conn.commit()
        except Exception:
            conn.close()
            raise

    return conn


class _PyPIDriver(NamedTuple):
    """Location of a driver shipped in a PyPI package."""

    module: str
    path_func: str
    entrypoint: str | None = None


_PYPI_DRIVERS: dict[str, _PyPIDriver] = {
    # The default entrypoint derived from the DuckDB library path (`AdbcDuckdbInit`) isn't the
    # one DuckDB exports.
    "duckdb": _PyPIDriver("adbc_driver_duckdb", "driver_path", "duckdb_adbc_init"),
    "sqlite": _PyPIDriver("adbc_driver_sqlite", "_driver_path"),
    "postgresql": _PyPIDriver("adbc_driver_postgresql", "_driver_path"),
}


def _find_pypi_driver(name: str) -> tuple[str, str | None] | None:
    """Return the shared library path and entrypoint of an installed PyPI driver, if any."""
    if (spec := _PYPI_DRIVERS.get(name)) is None or importlib.util.find_spec(spec.module) is None:
        return None

    module = importlib.import_module(spec.module)
    return getattr(module, spec.path_func)(), spec.entrypoint


def _open_connection(config: Mapping[str, Any]) -> adbc_driver_manager.dbapi.Connection:
    uri: str = config["uri"]
    scheme = urllib.parse.urlparse(uri).scheme
    db_kwargs: dict[str, Any] = dict(config.get(scheme, {}))

    if scheme == "profile":
        profile = profile_from_uri(uri, env=os.environ)
        entrypoint: str | None = None

        if found := _find_pypi_driver(profile["driver"]):
            profile["driver"], entrypoint = found

        # A named temp file can't be reopened by the driver on Windows, so use a directory.
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile_path = Path(tmp_dir, "profile.toml")
            with profile_path.open("wb") as f:
                tomli_w.dump(profile, f)
            return adbc_driver_manager.dbapi.connect(
                uri=f"profile://{profile_path.as_posix()}",
                entrypoint=entrypoint,
            )

    if found := _find_pypi_driver(scheme):
        driver, entrypoint = found
        if scheme == "duckdb":
            # DuckDB takes a database path rather than a URI.
            db_kwargs["path"] = uri.removeprefix("duckdb://")
        else:
            db_kwargs["uri"] = uri
        return adbc_driver_manager.dbapi.connect(
            driver=driver,
            entrypoint=entrypoint,
            db_kwargs=db_kwargs,
        )

    return adbc_driver_manager.dbapi.connect(driver=scheme, uri=uri, db_kwargs=db_kwargs)
