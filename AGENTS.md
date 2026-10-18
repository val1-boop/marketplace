# Instrucciones para el asistente de IA (Claude Code, Codex, Copilot, Gemini, ChatGPT…)

Estás ayudando a una persona a **replicar exactamente** este proyecto (marketplace seguro en
Flask + AWS) en su propio laboratorio de AWS Academy y en su propia computadora. Varias personas
hacen lo mismo por separado, y todas deben terminar con **el mismo resultado**.

## Antes de hacer cualquier cosa

1. Lee `GUIA_REPLICA.md` completo. Es el plan maestro: inventario exacto de recursos (sección 4) y
   fases con puntos de control (sección 5).
2. `GUIA_AWS.md` es un resumen complementario; si no coincide con el GUIA_REPLICA.md, manda el GUIA_REPLICA.md.
3. Pregunta al usuario en qué fase va. Si empieza de cero, comienza por la Fase 0.

## Reglas del profesor (obligatorias, también en la sección inicial del GUIA_REPLICA.md)

- **Seguridad en cada cambio:** al agregar código, analiza sus vulnerabilidades y explica cómo
  quedan cubiertas; si un cambio abre un riesgo, no se entrega.
- **Commit al terminar cada flujo completo:** pide permiso al usuario para hacer commit; nunca
  hagas commits por tu cuenta.
- **Mensajes de commit descriptivos y precisos:** primera línea en imperativo (< 72 caracteres)
  con qué cambia; en el cuerpo, el porqué y las decisiones de seguridad.
- **Pruebas automáticas** antes de probar o depurar: `pytest`, `bandit -r .` y
  `pip-audit -r requirements.txt`, y muestra el resultado.
- **Estructura:** `Services/` (rutas), `Interfaces/` (contrato + DTO), `Implementation/`
  (lógica y datos), `View/<Modulo>Views/` con PY, HTML, CSS, JS y Utils. No vuelvas a juntar
  capas ni crees carpetas fuera de este esquema.

## Reglas de trabajo

- **El código ya está escrito. No lo regeneres, no lo reescribas y no "lo mejores".** Las
  Lambdas, la app y las pruebas deben ser idénticas en todas las copias.
- **Nombres de AWS en inglés:** las Lambdas empiezan con `lambda` (`lambdaListProducts`) y el
  API se llama `apiGatewayMarketplace`; el nombre de cada Lambda es igual al de su archivo.
- **API Gateway como lo pide el profesor:** una Lambda por ruta; primero se crean todas las
  rutas una por una y después la integración de cada ruta; **implementación automática siempre
  desactivada** (se implementa a mano después de cada cambio). Ver Fase 7 del GUIA_REPLICA.md.
- **Lambdas:** se pega el archivo de `aws/lambdas/` (completo e independiente). `aws/lambdas_src/`
  es la fuente que usa el dueño con `tools/build_lambdas.py`; no se pega en la consola.
- **No cambies nombres:** tablas, atributos, índices, funciones Lambda, rutas, variables de
  entorno, usuarios de BD y usuarios de prueba son los de la sección 4 del GUIA_REPLICA.md.
- **Una fase a la vez.** Al terminar cada una, verifica su punto de control (✅) antes de seguir.
  Pide capturas o salidas de comandos cuando no puedas comprobarlo tú.
- **Las acciones en la consola de AWS las hace el usuario.** Tú le das los pasos exactos (clic
  por clic, como en las Fases 3 a 9 del GUIA_REPLICA.md) y revisas sus capturas. Ejecuta tú los comandos locales
  (venv, pip, pytest, bandit, pip-audit, flask) si tienes terminal; si no la tienes, dale al
  usuario el comando exacto y pídele la salida completa.
- **Antes de empezar, verifica que la copia es idéntica a la del dueño:**
  `python tools/verificar_integridad.py` debe terminar con "Copia idéntica". Si no, no sigas:
  el usuario debe volver a descargar el proyecto.
- **Usa exactamente Python 3.13** y las versiones fijadas de `requirements.txt` (árbol completo).
  No actualices ni agregues paquetes.
- **Comandos en PowerShell** para Windows, salvo que el usuario diga otro sistema. Da comandos
  completos listos para pegar; para editar `.env`, prefiere los comandos de una línea con Python
  del GUIA_REPLICA.md (Fase 1.5) en lugar de pedir copiar y pegar a mano.
- **Si algo falla:**
  1. Identifica la causa con la salida exacta del error.
  2. Busca primero en la sección 9 del GUIA_REPLICA.md y en "Problemas frecuentes" de `GUIA_AWS.md`.
  3. Si hay que corregir código o versiones, haz el cambio **mínimo**, explica qué cambiaste y
     por qué, y pide al usuario que se lo comunique al dueño del proyecto para que todas las
     copias se mantengan iguales.
- Responde en **español**.

## Seguridad (no negociable)

- Nunca muestres, registres ni escribas en archivos versionados: `SECRET_KEY`, el token del API,
  ni las contraseñas de `admin`, `postgres` o `mkt_app`. Solo van en `.env`, que está en
  `.gitignore`.
- Nunca ejecutes Flask con `debug=True` ni `flask run --debug`.
- Nunca abras puertos a `0.0.0.0/0`; siempre **Mi IP**.
- La app usa el usuario `mkt_app` en RDS, nunca `admin` ni `postgres`.
- No configures CORS en el API ni quites el autorizador de ninguna ruta.
- No agregues `|safe`, `Markup()`, `render_template_string`, `innerHTML`, `eval`, `os.system`,
  `shell=True` ni `pickle`.

## Comandos útiles

```powershell
.venv\Scripts\Activate.ps1          # activar entorno
pytest                              # 346 pruebas (no usan AWS)
bandit -r .                         # análisis estático (sin hallazgos; usa .bandit)
pip-audit -r requirements.txt       # dependencias vulnerables
flask --app wsgi check-aws          # conexión a MySQL, PostgreSQL y API
flask --app wsgi seed-demo          # usuarios y productos de prueba
flask --app wsgi seed-descriptions  # descripciones (si sembraste con la entrega 1)
python run.py                       # http://localhost:5000
```
