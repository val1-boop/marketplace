# Marketplace seguro (Flask + AWS)

Marketplace web multivendedor donde **una misma cuenta compra y vende** tecnología,
construido con la **seguridad como prioridad** (seguridad > funcionalidad > legibilidad > diseño).

## Funciones

- **Catálogo público** sin necesidad de cuenta: portada, búsqueda, filtros por departamento,
  categoría y disponibilidad, orden y ficha de producto con opiniones.
- **Cuenta de usuario:** publicar, editar y administrar tus productos (con buscador y filtros),
  carrito, favoritos y direcciones de envío.
- **Compras:** un pedido por vendedor, con fecha y entrega estimada de 3 a 7 días, y estados
  Confirmado → En preparación → Enviado → Entregado (o Cancelado).
- **Pago simulado:** el botón Pagar pide confirmación y registra el pago (sin tarjeta ni datos bancarios)
  dentro de la misma transacción que crea el pedido y descuenta el stock.
- **Tienda del vendedor:** cada vendedor pone nombre y descripción a su tienda; los compradores ven
  "Vendido por <tienda>".
- **Procedimientos almacenados (RDS MySQL):** `sp_guardar_tienda` guarda la tienda del vendedor de forma atómica y
  validada, y `sp_resumen_cuentas` entrega el resumen de cuentas del panel del administrador. Se ejecutan con los
  permisos de `mkt_app` (solo recibe `EXECUTE`).
- **Catálogo grande:** el API entrega los productos por páginas y `tools/load_products.py` carga 17,000
  productos de demostración con `BatchWriteItem`.
- **Reseñas verificadas:** calificación con estrellas solo de compras entregadas, con promedio
  e histograma.
- **Administración:** panel de moderación (bloquear o retirar productos, gestionar usuarios) y
  bitácoras de seguridad.

## Tecnologías

- **Backend web:** Python + Flask (Application Factory + Blueprints), Jinja2, Flask-SQLAlchemy,
  Flask-Login, Flask-WTF, Flask-Limiter, Flask-Talisman, Flask-Migrate.
- **Nube (AWS):** DynamoDB (productos, carrito, pedidos y reseñas), Lambda + API Gateway
  (API protegida) y RDS MySQL/PostgreSQL (cuentas y bitácoras de seguridad).

## Seguridad

- Contraseñas con **Argon2id** y política de complejidad; límite de intentos y bloqueo temporal.
- Control de acceso por rol y verificación de dueño (anti-IDOR) en la app y de nuevo en la base de datos.
- **CSRF** global, autoescape de plantillas, cabeceras de seguridad (**CSP/HSTS**, entre otras) y
  validación estricta de entradas.
- API protegida con autorizador y token; el precio, las existencias y el dueño los decide el
  servidor, nunca el navegador.

## Cómo ejecutarlo

Requiere **Python 3.13** y un laboratorio de AWS. Los pasos completos (crear los recursos en AWS,
configurar el `.env`, sembrar datos de demostración y correr la app) están en:

- 📘 **[GUIA_REPLICA.md](GUIA_REPLICA.md)** — guía de instalación y réplica, paso a paso.
- 🤖 **[AGENTS.md](AGENTS.md)** — reglas para asistentes de IA que trabajen en el proyecto.

La configuración local (claves, endpoints y tokens) vive en un archivo `.env` que **no se incluye**
en el repositorio; usa [`.env.example`](.env.example) como plantilla.

## Ver la aplicación sin AWS (para desarrollar)

```bash
python tools/dev_fake_aws.py   # http://localhost:5000
```

Usa SQLite y un DynamoDB simulado en memoria: no se conecta a AWS y sus datos se borran al detenerlo. Las cuentas de prueba y sus contraseñas aleatorias se muestran en la terminal.

## Pruebas

```bash
pytest          # suite completa (no requiere AWS)
bandit -r .     # análisis estático de seguridad
```
