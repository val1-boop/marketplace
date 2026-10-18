"""Configuración de Gunicorn para producción (detrás de Nginx o un ALB)."""
import os

import gunicorn
import gunicorn.http.wsgi

# Oculta "gunicorn/x.y.z" de la cabecera Server. En Nginx usar además
# `server_tokens off;` y `proxy_hide_header Server;`.
gunicorn.SERVER = "webserver"
gunicorn.http.wsgi.SERVER = "webserver"

bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = 2
timeout = 30
graceful_timeout = 30
keepalive = 5
# Límites del protocolo HTTP (mitigación DoS básica)
limit_request_line = 4094
limit_request_fields = 50
limit_request_field_size = 8190
# Solo se confía en X-Forwarded-* del proxy local
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")
accesslog = "-"
errorlog = "-"
