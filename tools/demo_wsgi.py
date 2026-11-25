"""Entrada WSGI de una DEMOSTRACIÓN publicada (sin AWS, con datos de ejemplo).

    gunicorn -c gunicorn.conf.py tools.demo_wsgi:app

Importante: la demostración usa el DynamoDB SIMULADO en memoria, así que se queda en UN solo
proceso (GUNICORN_WORKERS=1) y sus datos se borran cada vez que se reinicia. No se conecta a
las bases de datos de AWS del proyecto.
"""
from tools.dev_fake_aws import ACCOUNTS, build_app

app, _passwords = build_app()

# Las contraseñas se generan al arrancar y se muestran SOLO en el registro del servidor.
print("=== Cuentas de la demostración (cambian en cada reinicio) ===")
for key, (email, _first, _last) in ACCOUNTS.items():
    print(f" {key:<10} {email:<28} {_passwords[key]}")
