import zipfile
import json
import io
import re
from pathlib import Path


# Regex to strip leading version specifier characters from npm dependency values
_VERSION_PREFIX_RE = re.compile(r"^[\^~>=<!\s*]+")

# Common npm-scope or well-known pip package indicators — used for ecosystem heuristic
_PIP_KNOWN_INDICATORS = {
    "flask", "django", "fastapi", "sqlalchemy", "requests", "numpy", "pandas",
    "scipy", "pytest", "uvicorn", "pydantic", "celery", "redis", "boto3",
    "pillow", "aiohttp", "httpx", "starlette", "alembic", "click", "rich",
}


def _strip_npm_version(version_str: str) -> str:
    """Remove leading version qualifier characters from an npm version string."""
    return _VERSION_PREFIX_RE.sub("", version_str).strip()


def _package_name_from_path(zip_path: str) -> str:
    """
    Derive a logical package name from the path inside the ZIP.
    For 'apps/web/package.json' → 'apps/web'.
    For 'package.json' at root → 'root'.
    """
    parts = Path(zip_path).parts
    # Drop the filename itself (last part)
    directory_parts = parts[:-1]
    if not directory_parts:
        return "root"
    return "/".join(directory_parts)


def _is_node_modules(path: str) -> bool:
    """Return True if the path contains a node_modules segment."""
    return "node_modules" in Path(path).parts


def _parse_package_json(content: bytes, zip_path: str) -> tuple[str, list[str]]:
    """
    Parse a package.json file and return (package_name, [dependency_names]).
    Uses the 'name' field when present; otherwise derives from path.
    Merges 'dependencies' and 'devDependencies'.
    """
    data = json.loads(content.decode("utf-8", errors="replace"))

    package_name = data.get("name") or _package_name_from_path(zip_path)

    deps: list[str] = []
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        section_data = data.get(section)
        if isinstance(section_data, dict):
            for dep_name in section_data:
                cleaned = dep_name.strip()
                if cleaned:
                    deps.append(cleaned)

    return package_name, deps


def _parse_requirements_txt(content: bytes, zip_path: str) -> tuple[str, list[str]]:
    """
    Parse a requirements.txt file and return (package_name, [dependency_names]).
    The 'package_name' is derived from the directory containing requirements.txt.
    Handles inline comments, extras, version specifiers, and -r includes (skipped).
    """
    owner = _package_name_from_path(zip_path)

    deps: list[str] = []
    for raw_line in content.decode("utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        # Skip empty lines, comments, and pip options (-r, -c, --index-url, etc.)
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip inline comment
        line = line.split("#")[0].strip()
        if not line:
            continue
        # Strip extras like package[extra1,extra2]
        base = re.split(r"[\[;=<>!~@\s]", line)[0].strip()
        if base:
            deps.append(base.lower())  # pip is case-insensitive; normalise to lower

    return owner, deps


def parse_zip(content: bytes) -> dict[str, list[str]]:
    """
    Parse a ZIP archive and extract dependency information.

    Returns a dict mapping each package name to its list of direct dependencies:
        { "package-name": ["dep1", "dep2", ...], ... }

    Scans all package.json (excluding node_modules) and requirements.txt files
    found anywhere in the ZIP.
    """
    graph: dict[str, list[str]] = {}

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for name in zf.namelist():
            path = Path(name)
            filename = path.name

            # --- package.json handling ---
            if filename == "package.json" and not _is_node_modules(name):
                try:
                    raw = zf.read(name)
                    pkg_name, deps = _parse_package_json(raw, name)
                    # Merge if the same package name was already seen
                    existing = graph.setdefault(pkg_name, [])
                    for dep in deps:
                        if dep not in existing:
                            existing.append(dep)
                except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
                    # Skip malformed files silently; don't crash the whole parse
                    continue

            # --- requirements.txt handling ---
            elif filename == "requirements.txt":
                try:
                    raw = zf.read(name)
                    pkg_name, deps = _parse_requirements_txt(raw, name)
                    existing = graph.setdefault(pkg_name, [])
                    for dep in deps:
                        if dep not in existing:
                            existing.append(dep)
                except (KeyError, UnicodeDecodeError):
                    continue

    return graph
