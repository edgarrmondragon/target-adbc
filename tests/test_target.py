"""Tests for the ADBC target."""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, Any, TypeAlias
from unittest import mock

import adbc_driver_manager
import pytest
from adbc_driver_manager import dbapi
from singer_sdk.testing import SuiteConfig, TargetTestRunner, get_target_test_class

from target_adbc import target as target_module
from target_adbc.target import TargetADBC

if TYPE_CHECKING:
    from pathlib import Path


# Standard Target Tests
StandardTargetTests = get_target_test_class(
    target_class=TargetADBC,
    config={
        "uri": "duckdb:./tmp.db",
    },
)

Config: TypeAlias = dict[str, Any]


class TestTargetStandard(StandardTargetTests):  # type: ignore[misc,valid-type] # ty: ignore[unsupported-base]
    """Standard Target Tests."""

    @pytest.mark.xfail(
        reason="Schema evolution is not supported",
        raises=adbc_driver_manager.InternalError,
        strict=True,
    )
    def test_target_schema_updates(
        self,
        config: SuiteConfig,
        resource: Any,
        runner: TargetTestRunner,
    ) -> None:
        super().test_target_schema_updates(config, resource, runner)


def test_target_initialization(duckdb_config: Config) -> None:
    """Test that the target can be initialized."""
    target = TargetADBC(config=duckdb_config)
    assert target.name == "target-adbc"
    assert target.config["uri"].startswith("duckdb://")
    assert target.config["uri"].endswith("test.duckdb")


def test_parallelism_disabled() -> None:
    """Test that parallel processing is disabled by default."""
    target = TargetADBC(config={"uri": "duckdb://"})
    assert target.max_parallelism == 1


def test_append_mode(
    duckdb_config: Config,
    singer_messages: list[str],
    tmp_path: Path,
) -> None:
    """Test that append mode adds to existing tables."""
    input_file = tmp_path / "input.jsonl"
    input_file.write_text("\n".join(singer_messages))

    # First load
    target = TargetADBC(config=duckdb_config)
    with input_file.open() as f:
        target.listen(f)

    # Check count after first load
    with dbapi.connect(**target.get_connect_kwargs()) as conn, conn.cursor() as cur:
        res = cur.execute("SELECT COUNT(*) FROM users").fetchone()
        assert res
        assert res[0] == 2

    # Second load (should append)
    target = TargetADBC(config=duckdb_config)
    with input_file.open() as f:
        target.listen(f)

    # Check count after second load
    with dbapi.connect(**target.get_connect_kwargs()) as conn, conn.cursor() as cur:
        res = cur.execute("SELECT COUNT(*) FROM users").fetchone()
        assert res
        assert res[0] == 4  # 2 original + 2 appended


def test_replace_mode(
    duckdb_config: Config,
    singer_messages: list[str],
    tmp_path: Path,
) -> None:
    """Test that replace mode drops and recreates tables."""
    input_file = tmp_path / "input.jsonl"
    input_file.write_text("\n".join(singer_messages))

    # First load
    target = TargetADBC(config=duckdb_config)
    with input_file.open() as f:
        target.listen(f)

    # Check count after first load
    with dbapi.connect(**target.get_connect_kwargs()) as conn, conn.cursor() as cur:
        res = cur.execute("SELECT COUNT(*) FROM users").fetchone()
        assert res
        assert res[0] == 2

    # Second load with replace mode
    replace_config = duckdb_config.copy()
    replace_config["overwrite_behavior"] = "replace"
    target = TargetADBC(config=replace_config)
    with input_file.open() as f:
        target.listen(f)

    # Check count after second load (should be 2, not 4)
    with dbapi.connect(**target.get_connect_kwargs()) as conn, conn.cursor() as cur:
        res = cur.execute("SELECT COUNT(*) FROM users").fetchone()
        assert res
        assert res[0] == 2  # Table was replaced


def test_connection_uses_bundled_duckdb_driver_when_available() -> None:
    """When the `duckdb` package is importable, connect via its bundled driver."""
    fake_spec = mock.Mock(origin="/fake/path/_duckdb.so")
    with (
        mock.patch.object(importlib.util, "find_spec", return_value=fake_spec) as mock_find_spec,
        mock.patch.object(dbapi, "connect", return_value=mock.Mock()) as mock_connect,
    ):
        target = TargetADBC(config={"uri": "duckdb://"})
        _ = target.connection

    mock_find_spec.assert_called_once_with("_duckdb")
    mock_connect.assert_called_once_with(
        driver="/fake/path/_duckdb.so",
        uri="duckdb://",
        entrypoint="duckdb_adbc_init",
        db_kwargs={},
    )


def test_connection_falls_back_to_driver_manager_when_duckdb_module_missing() -> None:
    """When the `duckdb` package isn't installed, fall back to the compact URI form."""
    with (
        mock.patch.object(importlib.util, "find_spec", return_value=None) as mock_find_spec,
        mock.patch.object(dbapi, "connect", return_value=mock.Mock()) as mock_connect,
    ):
        target = TargetADBC(config={"uri": "duckdb://"})
        _ = target.connection

    mock_find_spec.assert_called_once_with("_duckdb")
    mock_connect.assert_called_once_with(driver="duckdb://", db_kwargs={})


def test_connection_uses_bundled_sqlite_driver_when_extra_installed(tmp_path: Path) -> None:
    """When `adbc-driver-sqlite` is installed, use its bundled `.so`."""
    db_path = tmp_path / "foo.db"
    with (
        mock.patch.object(
            target_module,
            "_bundled_driver_path",
            return_value="/fake/path/libadbc_driver_sqlite.so",
        ) as mock_bundled_driver_path,
        mock.patch.object(dbapi, "connect", return_value=mock.Mock()) as mock_connect,
    ):
        target = TargetADBC(config={"uri": f"sqlite://{db_path}"})
        _ = target.connection

    mock_bundled_driver_path.assert_called_once_with("adbc_driver_sqlite")
    mock_connect.assert_called_once_with(
        driver="/fake/path/libadbc_driver_sqlite.so",
        uri=str(db_path),
        db_kwargs={},
    )


def test_connection_uses_bundled_postgres_driver_when_extra_installed() -> None:
    """When `adbc-driver-postgresql` is installed, use its bundled `.so`."""
    with (
        mock.patch.object(
            target_module,
            "_bundled_driver_path",
            return_value="/fake/path/libadbc_driver_postgresql.so",
        ) as mock_bundled_driver_path,
        mock.patch.object(dbapi, "connect", return_value=mock.Mock()) as mock_connect,
    ):
        target = TargetADBC(config={"uri": "postgresql://localhost/db"})
        _ = target.connection

    mock_bundled_driver_path.assert_called_once_with("adbc_driver_postgresql")
    mock_connect.assert_called_once_with(
        driver="/fake/path/libadbc_driver_postgresql.so",
        uri="postgresql://localhost/db",
        db_kwargs={},
    )


def test_connection_falls_back_to_driver_manager_when_sqlite_extra_missing(
    tmp_path: Path,
) -> None:
    """Without `adbc-driver-sqlite` installed, fall back to manifest-based resolution."""
    db_path = tmp_path / "foo.db"
    with (
        mock.patch.object(
            target_module,
            "_bundled_driver_path",
            return_value=None,
        ) as mock_bundled_driver_path,
        mock.patch.object(dbapi, "connect", return_value=mock.Mock()) as mock_connect,
    ):
        target = TargetADBC(config={"uri": f"sqlite://{db_path}"})
        _ = target.connection

    mock_bundled_driver_path.assert_called_once_with("adbc_driver_sqlite")
    mock_connect.assert_called_once_with(driver="sqlite", uri=str(db_path), db_kwargs={})


def test_connection_falls_back_to_driver_manager_when_postgres_extra_missing() -> None:
    """Without `adbc-driver-postgresql` installed, fall back to the compact URI form."""
    with (
        mock.patch.object(
            target_module,
            "_bundled_driver_path",
            return_value=None,
        ) as mock_bundled_driver_path,
        mock.patch.object(dbapi, "connect", return_value=mock.Mock()) as mock_connect,
    ):
        target = TargetADBC(config={"uri": "postgresql://localhost/db"})
        _ = target.connection

    mock_bundled_driver_path.assert_called_once_with("adbc_driver_postgresql")
    mock_connect.assert_called_once_with(driver="postgresql://localhost/db", db_kwargs={})


def test_connection_mssql_scheme_skips_all_bundled_driver_lookups() -> None:
    """Schemes without a bundled-driver branch should use the compact URI form as-is."""
    with (
        mock.patch.object(importlib.util, "find_spec") as mock_find_spec,
        mock.patch.object(
            target_module,
            "_bundled_driver_path",
        ) as mock_bundled_driver_path,
        mock.patch.object(dbapi, "connect", return_value=mock.Mock()) as mock_connect,
    ):
        target = TargetADBC(config={"uri": "sqlserver://localhost/db"})
        _ = target.connection

    mock_find_spec.assert_not_called()
    mock_bundled_driver_path.assert_not_called()
    mock_connect.assert_called_once_with(driver="sqlserver://localhost/db", db_kwargs={})


def test_bundled_driver_path_returns_none_when_package_missing() -> None:
    """`_bundled_driver_path` should return None for a package that isn't installed."""
    assert target_module._bundled_driver_path("not_a_real_adbc_driver_package") is None  # ruff:ignore[private-member-access]


def test_bundled_driver_path_finds_installed_extra() -> None:
    """`_bundled_driver_path` should locate the `.so` bundled with an installed extra."""
    pytest.importorskip("adbc_driver_sqlite")
    path = target_module._bundled_driver_path("adbc_driver_sqlite")  # ruff:ignore[private-member-access]
    assert path is not None
    assert path.endswith("libadbc_driver_sqlite.so")


def test_config_schema() -> None:
    """Test that config schema is properly defined."""
    schema = TargetADBC.config_jsonschema

    assert "uri" in schema["properties"]
    assert schema["properties"]["batch_size_rows"]["default"] == 25_000
    assert schema["properties"]["overwrite_behavior"]["default"] == "append"
    assert schema["properties"]["add_record_metadata"]["default"] is True

    allowed = schema["properties"]["overwrite_behavior"].get("enum")
    assert set(allowed) == {"append", "replace"}
