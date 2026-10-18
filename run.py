"""Servidor de desarrollo local. Nunca usa debug (el debugger de Werkzeug permite RCE)."""
import os

from Core import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
