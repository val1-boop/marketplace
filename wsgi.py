"""Punto de entrada WSGI: `gunicorn -c gunicorn.conf.py wsgi:app`."""
from Core import create_app

app = create_app()
