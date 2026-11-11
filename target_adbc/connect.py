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


def _open_connection(config: Mapping[str, Any]) -> adbc_driver_manager.dbapi.Connection:
    uri: str = config["uri"]
    scheme = urllib.parse.urlparse(uri).scheme
    db_kwargs: dict[str, Any] = dict(config.get(scheme, {}))

    return adbc_driver_manager.dbapi.connect(uri=uri, db_kwargs=db_kwargs)
