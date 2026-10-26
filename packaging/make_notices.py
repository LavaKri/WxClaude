"""Write THIRD-PARTY-NOTICES.txt: the software the packaged WxClaude carries, with its licenses.

Usage: python packaging/make_notices.py <output file>

The Python packages are the runtime dependencies of wxclaude (read from the installed metadata, so
the list follows pyproject.toml), with the license files they ship. The runtime of Python and its
native libraries are named with their license and where to read it. Run from the virtual
environment that builds the application (``build.bat`` does it).
"""

import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement

_LICENSE_FILE = re.compile(r"(^|/)(LICEN[CS]E|COPYING|NOTICE)[^/]*$", re.IGNORECASE)

# Native parts of the Python runtime that the application carries (python314.dll and its
# libraries); the other modules of the standard library are under the license of Python itself.
_RUNTIME = (
    ("OpenSSL (libcrypto, libssl)", "Apache-2.0", "https://openssl-library.org/source/license/"),
    ("libffi", "MIT", "https://github.com/libffi/libffi/blob/master/LICENSE"),
    ("Expat (pyexpat)", "MIT", "https://github.com/libexpat/libexpat/blob/master/expat/COPYING"),
    (
        "Microsoft Visual C++ runtime (MSVCP140.dll, VCRUNTIME140.dll)",
        "Microsoft redistributable terms",
        "https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files",
    ),
)
_SEPARATOR = "=" * 78


def project_dependencies() -> list[str]:
    """The names of the runtime dependencies of wxclaude, from pyproject.toml (the installed
    metadata of the project may be older than the file)."""
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return [Requirement(line).name for line in data["project"]["dependencies"]]


def runtime_requirements(name: str, seen: set[str]) -> list[str]:
    """The distributions ``name`` needs to run here (extras and conditions that do not apply left
    out), itself first, each once."""
    key = name.lower().replace("_", "-")
    if key in seen:
        return []
    seen.add(key)
    found = [name]
    for line in metadata.requires(name) or []:
        requirement = Requirement(line)
        if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
            continue
        found += runtime_requirements(requirement.name, seen)
    return found


def license_label(name: str) -> str:
    """The license of a distribution, as its metadata says it (first line, not too long)."""
    info = metadata.metadata(name)
    expression = info.get("License-Expression") or info.get("License") or ""
    first = expression.strip().splitlines()[0] if expression.strip() else ""
    if first:
        return first[:80]
    classifiers = [c for c in info.get_all("Classifier") or [] if c.startswith("License ::")]
    return classifiers[0].rsplit("::", 1)[-1].strip() if classifiers else "not stated"


def license_texts(name: str) -> list[tuple[str, str]]:
    """The license files that the distribution ships: (file name, text)."""
    texts: list[tuple[str, str]] = []
    for file in metadata.files(name) or []:
        posix = file.as_posix()
        if _LICENSE_FILE.search(posix):
            path = Path(str(file.locate()))
            if path.is_file():
                texts.append((posix, path.read_text(encoding="utf-8", errors="replace").strip()))
    return texts


def python_license() -> str:
    """The text of the license of the Python that the application carries."""
    for folder in (Path(sys.base_prefix), Path(sys.base_prefix) / "Lib"):
        path = folder / "LICENSE.txt"
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace").strip()
    return "See https://docs.python.org/3/license.html"


def build() -> str:
    """The whole text of the notices."""
    parts = [
        "THIRD-PARTY NOTICES",
        "",
        "WxClaude is free software under the GNU General Public License version 3 (file LICENSE).",
        "It carries the software below, each under its own license.",
        "The source code of WxClaude is published with the license, see the file README.md.",
        "",
        _SEPARATOR,
        f"Python {sys.version.split()[0]}",
        "License: Python Software Foundation License (https://docs.python.org/3/license.html)",
        "",
        python_license(),
        "",
    ]
    for name, license_name, url in _RUNTIME:
        parts += [_SEPARATOR, name, f"License: {license_name}", f"See: {url}", ""]
    seen: set[str] = set()
    for direct in project_dependencies():
        for name in runtime_requirements(direct, seen):
            parts += [
                _SEPARATOR,
                f"{name} {metadata.version(name)}",
                f"License: {license_label(name)}",
                "",
            ]
            for file_name, text in license_texts(name):
                parts += [f"--- {file_name} ---", text, ""]
    return "\n".join(parts).rstrip() + "\n"


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: python packaging/make_notices.py <output file>\n")
        return 2
    Path(sys.argv[1]).write_text(build(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
