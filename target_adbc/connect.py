import os
import tempfile
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

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


def _open_connection(config: Mapping[str, Any]) -> adbc_driver_manager.dbapi.Connection:
    uri: str = config["uri"]
    scheme = urllib.parse.urlparse(uri).scheme
    db_kwargs: dict[str, Any] = dict(config.get(scheme, {}))

    if scheme == "profile":
        profile = profile_from_uri(uri, env=os.environ)

        # A named temp file can't be reopened by the driver on Windows, so use a directory.
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile_path = Path(tmp_dir, "profile.toml")
            with profile_path.open("wb") as f:
                tomli_w.dump(profile, f)
            return adbc_driver_manager.dbapi.connect(uri=f"profile://{profile_path.as_posix()}")

    return adbc_driver_manager.dbapi.connect(driver=scheme, uri=uri, db_kwargs=db_kwargs)
