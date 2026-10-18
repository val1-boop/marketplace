"""Verifica que esta copia del proyecto es idéntica a la del dueño.

Uso (desde la carpeta del proyecto):
    python tools/verificar_integridad.py            -> compara contra MANIFEST.sha256
    python tools/verificar_integridad.py --generar  -> (solo el dueño) regenera el manifiesto

Compara el SHA-256 de cada archivo del proyecto. Ignora lo que cada persona genera
localmente: .env, .venv, instance/, certs/, cachés y bases SQLite.
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "MANIFEST.sha256"
IGNORED_DIRS = {".venv", "venv", "instance", "certs", "__pycache__", ".pytest_cache", ".git", "migrations"}
IGNORED_FILES = {".env", "MANIFEST.sha256"}
IGNORED_SUFFIXES = {".pyc", ".db", ".pem"}


def project_files():
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if not path.is_file() or any(part in IGNORED_DIRS for part in rel.parts):
            continue
        if rel.name in IGNORED_FILES or path.suffix in IGNORED_SUFFIXES:
            continue
        yield rel


def digest(path):
    # Normaliza saltos de línea para que Windows (CRLF) y Linux (LF) den el mismo hash.
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def main():
    current = {rel.as_posix(): digest(ROOT / rel) for rel in project_files()}
    if "--generar" in sys.argv:
        lines = [f"{h}  {name}" for name, h in sorted(current.items())]
        MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Manifiesto generado con {len(lines)} archivos.")
        return 0
    if not MANIFEST.exists():
        print("No existe MANIFEST.sha256.")
        return 1
    expected = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            h, name = line.split("  ", 1)
            expected[name] = h
    missing = sorted(set(expected) - set(current))
    extra = sorted(set(current) - set(expected))
    changed = sorted(n for n in set(expected) & set(current) if expected[n] != current[n])
    for title, items in (("Faltan", missing), ("Sobran", extra), ("Modificados", changed)):
        for item in items:
            print(f"{title}: {item}")
    if missing or extra or changed:
        print("La copia NO es idéntica a la del dueño. Vuelve a descargar el proyecto.")
        return 1
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    print(f"Copia idéntica ({len(expected)} archivos, versión {version}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
