"""Tests for the ADBC target."""

from __future__ import annotations

import tempfile
import uuid
from typing import TYPE_CHECKING, Any
from unittest import mock

import adbc_driver_manager
import pytest
from adbc_driver_manager import dbapi
from singer_sdk.testing import SuiteConfig, TargetTestRunner, get_target_test_class

from target_adbc import connect
from target_adbc.target import TargetADBC

if TYPE_CHECKING:
    from pathlib import Path


# Standard Target Tests
StandardTargetTests = get_target_test_class(
    target_class=TargetADBC,
    config={
        "uri": f"duckdb:{tempfile.gettempdir()}/{uuid.uuid4().hex[:6]}.db",
    },
)

type Config = dict[str, Any]


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


@pytest.mark.parametrize("driver", ["duckdb", "sqlite"])
def test_parallelism_disabled(driver: str) -> None:
    """Test that parallel processing is disabled by default."""
    target = TargetADBC(config={"uri": f"{driver}://"})
    assert target.max_parallelism == 1


def test_use_profile(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    singer_messages: list[str],
    tmp_path: Path,
) -> None:
    """Test that a connection profile URI is correctly used."""
    input_file = tmp_path / "input.jsonl"
    input_file.write_text("\n".join(singer_messages))

    profile = request.config.rootpath.joinpath("profiles/duckdb.toml")
    config = {"uri": f"profile://{profile.as_posix()}"}
    target = TargetADBC(config=config)

    with monkeypatch.context() as m, input_file.open() as f:
        m.setenv("MELTANO_PROJECT_ROOT", value=tmp_path.as_posix())
        db_path = target.connection.adbc_database.get_option("path")
        target.listen(f)
        assert not db_path.startswith("/local.duckdb") and db_path.endswith("/local.duckdb")

    with monkeypatch.context() as m:
        m.setenv("MELTANO_PROJECT_ROOT", value=tmp_path.as_posix())
        with connect.get_connection(config) as conn, conn.cursor() as cur:
            res = cur.execute("SELECT COUNT(*) FROM users").fetchone()
            assert res
            assert res[0] == 2


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
    with connect.get_connection(duckdb_config) as conn, conn.cursor() as cur:
        res = cur.execute("SELECT COUNT(*) FROM users").fetchone()
        assert res
        assert res[0] == 2

    # Second load (should append)
    target = TargetADBC(config=duckdb_config)
    with input_file.open() as f:
        target.listen(f)

    # Check count after second load
    with connect.get_connection(duckdb_config) as conn, conn.cursor() as cur:
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
    with connect.get_connection(duckdb_config) as conn, conn.cursor() as cur:
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
    with connect.get_connection(duckdb_config) as conn, conn.cursor() as cur:
        res = cur.execute("SELECT COUNT(*) FROM users").fetchone()
        assert res
        assert res[0] == 2  # Table was replaced


@pytest.mark.parametrize(
    "uri",
    [
        pytest.param("duckdb://", id="duckdb"),
        pytest.param("sqlite:///path/to/foo.db", id="sqlite"),
        pytest.param("postgresql://localhost/db", id="postgresql"),
        pytest.param("sqlserver://localhost/db", id="mssql"),
    ],
)
def test_connection_uses_driver_manager(uri: str) -> None:
    """Drivers are resolved by name through the driver manager."""
    with mock.patch.object(dbapi, "connect", return_value=mock.Mock()) as mock_connect:
        target = TargetADBC(config={"uri": uri})
        _ = target.connection

    mock_connect.assert_called_once_with(uri=uri, db_kwargs={})


def test_config_schema() -> None:
    """Test that config schema is properly defined."""
    schema = TargetADBC.config_jsonschema

    assert "uri" in schema["properties"]
    assert schema["properties"]["batch_size_rows"]["default"] == 25_000
    assert schema["properties"]["overwrite_behavior"]["default"] == "append"
    assert schema["properties"]["add_record_metadata"]["default"] is True

    allowed = schema["properties"]["overwrite_behavior"].get("enum")
    assert set(allowed) == {"append", "replace"}
