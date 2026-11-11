from __future__ import annotations

import os.path
import re
import sys
import tomllib
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from collections.abc import Mapping

_DRIVE_RE = re.compile(r"[A-Za-z]:")


def _read_toml(path: str) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def profile_from_uri(uri: str, env: Mapping[str, str]) -> dict[str, Any]:
    parsed = urlparse(uri)

    # `profile://C:/path/to/profile.toml` parses with the drive letter as the netloc
    path = f"{parsed.netloc}{parsed.path}" if _DRIVE_RE.fullmatch(parsed.netloc) else parsed.path
    if os.path.isabs(path):
        return _read_toml(path)

    # Use search locations
    profile_name = parsed.netloc
    locations = []

    # TODO: additional_profile_search_path_list

    list_sep = ";" if sys.platform == "win32" else ":"
    if paths := env.get("ADBC_PROFILE_PATH"):
        locations.extend(paths.split(list_sep))

    if sys.platform == "linux":
        config_dir = env.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        locations.append(os.path.join(config_dir, "adbc", "profiles"))

    if sys.platform == "darwin":
        locations.append(os.path.expanduser("~/Library/Application Support/ADBC/Profiles/"))

    if sys.platform == "win32" and (local_app_data := env.get("LOCALAPPDATA")):
        locations.append(os.path.join(local_app_data, "ADBC", "Profiles"))

    for loc in locations:
        profile_path = os.path.join(loc, f"{profile_name}.toml")
        if os.path.exists(profile_path):
            return _read_toml(profile_path)

    msg = f"Profile file '{profile_name}' could not be found"
    raise FileNotFoundError(msg)
