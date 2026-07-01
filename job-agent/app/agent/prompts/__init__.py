"""Prompt 管理器 —— 集中管理 + 版本化."""

from __future__ import annotations

import hashlib
from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent
_CACHE: dict[str, str] = {}
CORE_PROMPT_NAMES = ("plan", "analyze", "rewrite")


def load_prompt(name: str, version: str | None = None) -> str:
    """
    加载 prompt 模板。
    - load_prompt("analyze") → v2_analyze.md（默认最新）
    - load_prompt("analyze", "v1") → v1_analyze.md
    """
    resolved_version = resolve_prompt_version(version, names=(name,))
    key = f"{resolved_version}_{name}"
    if key in _CACHE:
        return _CACHE[key]

    path = _prompt_path(name, resolved_version)
    content = path.read_text(encoding="utf-8")
    _CACHE[key] = content
    return content


def list_versions(name: str) -> list[str]:
    """列出某个 prompt 的所有版本."""
    return sorted(
        (
            path.name.removesuffix(f"_{name}.md")
            for path in _PROMPT_DIR.glob(f"*_{name}.md")
        ),
        key=_version_key,
    )


def resolve_prompt_version(
    version: str | None = None,
    *,
    names: tuple[str, ...] = CORE_PROMPT_NAMES,
) -> str:
    """Resolve a single prompt version that exists for all requested prompt names."""
    requested = None if version in (None, "", "latest") else version
    versions_by_name = {name: set(list_versions(name)) for name in names}

    if requested:
        missing = sorted(name for name, versions in versions_by_name.items() if requested not in versions)
        if missing:
            raise FileNotFoundError(f"prompt version {requested!r} missing for: {', '.join(missing)}")
        return requested

    common_versions = set.intersection(*versions_by_name.values()) if versions_by_name else set()
    if not common_versions:
        raise FileNotFoundError(f"no common prompt version for: {', '.join(names)}")
    return sorted(common_versions, key=_version_key)[-1]


def build_prompt_manifest(
    version: str | None = None,
    *,
    names: tuple[str, ...] = CORE_PROMPT_NAMES,
) -> dict:
    """Build a deterministic manifest for the prompt files used by one run."""
    resolved_version = resolve_prompt_version(version, names=names)
    files: dict[str, str] = {}
    file_hashes: dict[str, str] = {}
    digest = hashlib.sha256()

    for name in names:
        path = _prompt_path(name, resolved_version)
        content = path.read_text(encoding="utf-8")
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        files[name] = path.name
        file_hashes[name] = file_hash
        digest.update(f"{name}:{path.name}:{file_hash}\n".encode("utf-8"))

    return {
        "version": resolved_version,
        "fingerprint": digest.hexdigest(),
        "files": files,
        "file_hashes": file_hashes,
    }


def _prompt_path(name: str, version: str) -> Path:
    path = _PROMPT_DIR / f"{version}_{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt file not found: {path}")
    return path


def _version_key(version: str) -> tuple[int, int | str]:
    if version.startswith("v") and version[1:].isdigit():
        return 0, int(version[1:])
    return 1, version
