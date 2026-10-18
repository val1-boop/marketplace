"""Genera los archivos de aws/lambdas/ (uno por Lambda, listos para pegar en la consola).

Cada Lambda debe ser un solo archivo autónomo, así que los ayudantes comunes (validación,
respuestas, actor, transacciones) se escriben UNA vez en aws/lambdas_src/common.py y este
script los combina con el código propio de cada función (aws/lambdas_src/handlers/).

Uso (desde la carpeta del proyecto):
    python tools/build_lambdas.py           -> regenera aws/lambdas/*.py
    python tools/build_lambdas.py --check   -> solo verifica que estén al día (lo usa pytest)

El autorizador (lambdaAuthorizer.py) es independiente y no se genera.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "aws" / "lambdas_src"
OUT = ROOT / "aws" / "lambdas"


def build(handler_path):
    source = handler_path.read_text(encoding="utf-8")
    module = ast.parse(source)
    docstring = ast.get_docstring(module, clean=False)
    if not docstring:
        raise SystemExit(f"{handler_path.name}: falta el docstring de cabecera")
    first = module.body[0]
    body = "\n".join(source.splitlines()[first.end_lineno:]).strip("\n")
    common = (SRC / "common.py").read_text(encoding="utf-8").strip("\n")
    return f'"""{docstring}"""\n{common}\n\n\n{body}\n'


def main():
    check = "--check" in sys.argv
    stale = []
    for handler in sorted((SRC / "handlers").glob("lambda*.py")):
        target = OUT / handler.name
        content = build(handler)
        current = target.read_text(encoding="utf-8").replace("\r\n", "\n") if target.exists() else None
        if current != content:
            stale.append(handler.name)
            if not check:
                target.write_text(content, encoding="utf-8")
    if check and stale:
        print("Lambdas desactualizadas (ejecuta python tools/build_lambdas.py):", ", ".join(stale))
        return 1
    print("Lambdas al día." if check else f"Lambdas generadas: {len(list((SRC / 'handlers').glob('lambda*.py')))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
