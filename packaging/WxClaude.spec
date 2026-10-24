# PyInstaller recipe: one folder (onedir), no console. Build with build.bat from the repo root.
from pathlib import Path

root = Path(SPECPATH).parent
package = root / "src" / "wxclaude"


def data(pattern: str, folder: str) -> list[tuple[str, str]]:
    """Files of the package kept at the same place, since the code reads them with resources."""
    return [(str(path), f"wxclaude/{folder}") for path in package.glob(pattern)]


datas = (
    data("locale/*/LC_MESSAGES/*.mo", "locale/fr/LC_MESSAGES")
    + data("data/*.txt", "data")
    + data("help/*.html", "help")
    + data("sounds/*.wav", "sounds")
)

analysis = Analysis(
    [str(package / "__main__.py")],
    pathex=[str(root / "src")],
    datas=datas,
    hiddenimports=[],
    excludes=["tkinter", "pytest", "mypy", "ruff"],
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="WxClaude",
    console=False,
)
coll = COLLECT(exe, analysis.binaries, analysis.datas, name="WxClaude")
