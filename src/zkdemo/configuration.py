"""Process-local dotenv configuration and validation."""

import ast
import math
import os
import re
from pathlib import Path

SUPPORTED_SETTINGS = {
    "ZKTEST_HOSTS",
    "ZKTEST_TIMEOUT",
    "ZKTEST_CLUSTER",
    "ZKTEST_NODE_NAME",
    "ZKTEST_DELAY",
    "ZKTEST_FILE",
}
_SETTING_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
_HOST_RE = re.compile(r"^[A-Za-z0-9.-]+$")
_FILE_DEFAULTS: dict[str, str] = {}


class ConfigurationError(ValueError):
    """A selected dotenv file is unreadable or contains an invalid setting."""


def _selected_file() -> Path | None:
    candidates = [
        Path.cwd() / ".env",
        Path(os.environ.get("HOME", "")) / ".zktest.ini",
        Path("/etc/zktest.ini"),
    ]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def _parse_value(raw: str, path: Path, line_number: int, key: str) -> str:
    value = raw.strip()
    if value.startswith(("'", '"')):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError) as error:
            raise ConfigurationError(
                f"{path}: {key}: invalid quoted dotenv value on line {line_number}"
            ) from error
        if not isinstance(parsed, str):
            raise ConfigurationError(f"{path}: {key}: dotenv value must be a string")
        return parsed
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def _validate_hosts(value: str, path: Path, key: str) -> None:
    entries = value.split(",")
    for entry in entries:
        if not entry:
            raise ConfigurationError(f"{path}: {key}: empty host entry")
        if entry.startswith("["):
            closing = entry.find("]")
            if closing <= 1 or entry[closing + 1 : closing + 2] != ":":
                raise ConfigurationError(f"{path}: {key}: invalid host {entry!r}")
            host = entry[1:closing]
            port_text = entry[closing + 2 :]
        else:
            if entry.count(":") != 1:
                raise ConfigurationError(f"{path}: {key}: invalid host {entry!r}")
            host, port_text = entry.rsplit(":", 1)
        if not host or not _HOST_RE.fullmatch(host):
            raise ConfigurationError(f"{path}: {key}: invalid host {entry!r}")
        try:
            port = int(port_text)
        except ValueError as error:
            raise ConfigurationError(
                f"{path}: {key}: invalid port in {entry!r}"
            ) from error
        if not 1 <= port <= 65535:
            raise ConfigurationError(f"{path}: {key}: port out of range in {entry!r}")


def _validate_setting(path: Path, key: str, value: str) -> None:
    if key in {"ZKTEST_DELAY", "ZKTEST_TIMEOUT"}:
        try:
            number = float(value)
        except ValueError as error:
            raise ConfigurationError(f"{path}: {key}: invalid number") from error
        if not math.isfinite(number) or number < 0:
            raise ConfigurationError(
                f"{path}: {key}: must be a finite non-negative number"
            )
    elif key == "ZKTEST_HOSTS":
        _validate_hosts(value, path, key)
    elif key in {"ZKTEST_CLUSTER", "ZKTEST_NODE_NAME"}:
        if not value or "/" in value or value in {".", ".."} or "\x00" in value:
            raise ConfigurationError(
                f"{path}: {key}: must be a valid single ZooKeeper path component"
            )
        if "\r" in value or "\n" in value:
            raise ConfigurationError(f"{path}: {key}: must not contain newlines")
    elif key == "ZKTEST_FILE" and not value:
        raise ConfigurationError(f"{path}: {key}: must not be empty")


def load_configuration() -> dict[str, str]:
    """Load the first existing dotenv file without modifying the environment."""
    global _FILE_DEFAULTS
    _FILE_DEFAULTS = {}
    path = _selected_file()
    if path is None:
        return _FILE_DEFAULTS
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ConfigurationError(
            f"{path}: cannot read configuration: {error}"
        ) from error

    parsed: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _SETTING_RE.match(stripped)
        if match is None:
            raise ConfigurationError(
                f"{path}: invalid dotenv syntax on line {line_number}"
            )
        key, raw_value = match.groups()
        if key not in SUPPORTED_SETTINGS:
            raise ConfigurationError(f"{path}: {key}: unsupported setting")
        value = _parse_value(raw_value, path, line_number, key)
        _validate_setting(path, key, value)
        parsed[key] = value
    _FILE_DEFAULTS = parsed
    return parsed


def configured(name: str, default: str | None = None) -> str | None:
    """Return a process environment value, then a loaded-file default."""
    return os.environ.get(name, _FILE_DEFAULTS.get(name, default))
