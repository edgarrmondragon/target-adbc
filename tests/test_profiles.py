import sys
from pathlib import Path

import pytest

from target_adbc._profiles import profile_from_uri  # ruff: ignore[import-private-name]

PROFILE = """\
profile_version = 1
driver = "postgresql"

[Options]
uri = "postgresql://localhost:5432/dev_db?sslmode=disable"
username = "dev_user"
password = "{{ env_var(POSTGRES_DEV_PASSWORD) }}"
"""


def test_absolute_path(tmp_path: Path) -> None:
    profile_path = tmp_path / "abs.toml"
    profile_path.write_text(PROFILE)
    profile = profile_from_uri(f"profile://{profile_path.as_posix()}", env={})
    assert profile["driver"] == "postgresql"


def test_adbc_profile_path_env_var(tmp_path: Path) -> None:
    profile_path = tmp_path / "my_profile.toml"
    profile_path.write_text(PROFILE)
    profile = profile_from_uri(
        f"profile://{profile_path.stem}",
        env={"ADBC_PROFILE_PATH": tmp_path.as_posix()},
    )
    assert profile["driver"] == "postgresql"

    list_sep = ";" if sys.platform == "win32" else ":"

    paths = (tmp_path / "sub1", tmp_path / "sub2")
    paths[0].mkdir()
    paths[1].mkdir()
    profile_path = paths[1] / "my_profile.toml"
    profile_path.write_text(PROFILE)
    profile = profile_from_uri(
        f"profile://{profile_path.stem}",
        env={"ADBC_PROFILE_PATH": list_sep.join(map(Path.as_posix, paths))},
    )
    assert profile["driver"] == "postgresql"


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="$XDG_CONFIG_HOME/adbc/profiles is only searched on Linux",
)
def test_xdg_config_home(tmp_path: Path) -> None:
    profiles = tmp_path / "adbc" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "xdg_profile.toml").write_text(PROFILE)
    profile = profile_from_uri(
        "profile://xdg_profile",
        env={"XDG_CONFIG_HOME": tmp_path.as_posix()},
    )
    assert profile["driver"] == "postgresql"


@pytest.mark.skipif(
    sys.platform != "darwin",
    reason="~/Library/Application Support/ADBC/Profiles is only searched on macOS",
)
def test_macos_user_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", tmp_path.as_posix())
    profiles = tmp_path / "Library" / "Application Support" / "ADBC" / "Profiles"
    profiles.mkdir(parents=True)
    (profiles / "macos_profile.toml").write_text(PROFILE)
    profile = profile_from_uri("profile://macos_profile", env={})
    assert profile["driver"] == "postgresql"


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="%LOCALAPPDATA%\\ADBC\\Profiles is only searched on Windows",
)
def test_windows_local_app_data(tmp_path: Path) -> None:
    profiles = tmp_path / "ADBC" / "Profiles"
    profiles.mkdir(parents=True)
    (profiles / "windows_profile.toml").write_text(PROFILE)
    profile = profile_from_uri(
        "profile://windows_profile",
        env={"LOCALAPPDATA": str(tmp_path)},
    )
    assert profile["driver"] == "postgresql"


def test_profile_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        profile_from_uri("profile://missing", env={"ADBC_PROFILE_PATH": tmp_path.as_posix()})
