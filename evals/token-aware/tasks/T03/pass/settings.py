"""Runtime settings for the export worker.

Values may come from environment-style mappings, so numbers and
booleans can arrive as text. Missing keys keep their defaults and
unknown keys are ignored.
"""

from dataclasses import dataclass

TRUE_WORDS = {"1", "true", "yes", "on"}
FALSE_WORDS = {"0", "false", "no", "off"}


@dataclass
class Settings:
    timeout_s: int = 30
    retries: int = 3
    verbose: bool = False
    max_batch: int = 500


def _as_int(name: str, value) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a whole number, got {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    raise ValueError(f"{name} must be a whole number, got {value!r}")


def _as_bool(name: str, value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        word = value.strip().lower()
        if word in TRUE_WORDS:
            return True
        if word in FALSE_WORDS:
            return False
    raise ValueError(f"{name} must be a boolean, got {value!r}")


def load_settings(mapping: dict) -> Settings:
    """Build Settings from a mapping. Missing keys keep defaults."""
    settings = Settings()
    if "timeout_s" in mapping:
        settings.timeout_s = _as_int("timeout_s", mapping["timeout_s"])
    if "retries" in mapping:
        settings.retries = _as_int("retries", mapping["retries"])
    if "verbose" in mapping:
        settings.verbose = _as_bool("verbose", mapping["verbose"])
    if "max_batch" in mapping:
        value = _as_int("max_batch", mapping["max_batch"])
        if not 1 <= value <= 10000:
            raise ValueError("max_batch must be between 1 and 10000, got %d" % value)
        settings.max_batch = value
    return settings
