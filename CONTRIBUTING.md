# Cómo colaborar

## Ramas
- Nadie hace commits directo en `main`.
- Cada persona trabaja en ramas `feature/<nombre>-<tema>` y **solo hace commits en las suyas**.
- Antes de empezar una rama: `git switch main`, `git pull` y `git switch -c <rama>`.

## Commits
- Un commit por tarea. Primera línea en imperativo y de menos de 72 caracteres (qué cambia).
- En el cuerpo: por qué se hizo y las decisiones de seguridad.
- Cada commit queda con el nombre de quien lo hizo; no se reescribe la autoría.
- Antes de cada commit: `pytest`, `bandit -r .` y `pip-audit -r requirements.txt`.

## Pull Requests
- Un Pull Request por rama, con capturas, lista de archivos y resultado de las pruebas.
- Se fusionan con **Create a merge commit** o **Rebase and merge**. Nunca con *Squash and merge*, porque junta todos los commits en uno y borra el trabajo individual.

## Secretos
- Nunca se versiona `.env`, claves, tokens ni contraseñas.
- Los archivos se agregan por nombre (`git add <archivo>`), no con `git add .`.
