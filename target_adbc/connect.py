import importlib.util
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

import adbc_driver_manager.dbapi


class ConnectKwargs(TypedDict, total=False):
    driver: str | Path | None
    entrypoint: str
    db_kwargs: dict[str, str] | None


def get_connection(config: Mapping[str, Any]) -> adbc_driver_manager.dbapi.Connection:
    uri: str = config["uri"]
    parsed = urllib.parse.urlparse(uri)
    driver = parsed.scheme
    db_kwargs: dict[str, Any] = config.get(parsed.scheme, {})

    if (
        driver == "duckdb"
        and importlib.util.find_spec("adbc_driver_duckdb")
        and (spec := importlib.util.find_spec("adbc_driver_duckdb.dbapi"))
        and spec.loader
    ):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module.connect(uri.removeprefix("duckdb://"), **db_kwargs)  # type: ignore[no-any-return]

    if (
        driver == "sqlite"
        and importlib.util.find_spec("adbc_driver_sqlite")
        and (spec := importlib.util.find_spec("adbc_driver_sqlite.dbapi"))
        and spec.loader
    ):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module.connect(uri, **db_kwargs)  # type: ignore[no-any-return]

    if (
        driver == "postgresql"
        and importlib.util.find_spec("adbc_driver_postgresql")
        and (spec := importlib.util.find_spec("adbc_driver_postgresql.dbapi"))
        and spec.loader
    ):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module.connect(uri, **db_kwargs)  # type: ignore[no-any-return]

    return adbc_driver_manager.dbapi.connect(driver=driver, uri=uri, db_kwargs=db_kwargs)
