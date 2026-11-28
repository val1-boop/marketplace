# Bases de datos del marketplace

Esta carpeta reúne los scripts de las tres bases de datos. Son **copias** de los archivos de `aws/sql/` y
`aws/dynamodb/` (la fuente es `aws/`; si cambia un script allá, se actualiza aquí).

## RDS MySQL (`rds-mkt-identity-db`, base `marketplace`)
Se ejecutan como usuario administrador, en este orden:

| Orden | Archivo | Qué hace |
|---|---|---|
| 1 | `00_mysql_schema.sql` | Crea la base y las tablas `users`, `addresses`, `reports` y `admin_actions` |
| 2 | `01_mysql_marketplace.sql` | Agrega `session_nonce`, amplía las acciones de administración y crea el usuario `mkt_app` con permisos mínimos |
| 3 | `03_mysql_addresses.sql` | Da a `mkt_app` permiso sobre `addresses` |
| 4 | `04_mysql_sellers.sql` | Crea la tabla `sellers` (perfil de la tienda) y da permisos a `mkt_app` |
| 5 | `05_mysql_datos_iniciales.sql` | Datos iniciales (DML): crea una tienda por cada cuenta con código de vendedor |

Las contraseñas **no** van en los archivos: se reemplaza `CAMBIA_ESTA_CLAVE` solo al pegar el script en el
cliente SQL.

## RDS PostgreSQL (`rds-mkt-security-db`, base `security`)

| Orden | Archivo | Qué hace |
|---|---|---|
| 1 | `00_postgres_schema.sql` | Crea `login_attempts` y `auth_events` |
| 2 | `02_postgres_security.sql` | Crea el usuario `mkt_app` con permisos mínimos |

## DynamoDB (4 tablas, modo bajo demanda)
`dynamodb/crear_tablas_dynamodb.sh` crea `Products`, `Orders`, `Marketplace` y `Community` con sus índices y
su TTL, e inserta un ítem de ejemplo en cada una. Se ejecuta en AWS CloudShell: `bash crear_tablas_dynamodb.sh`.

## Dónde está cada dato
- **MySQL:** cuentas, direcciones y acciones del administrador.
- **PostgreSQL:** intentos de inicio de sesión y eventos de acceso (rastro de seguridad aislado).
- **DynamoDB:** productos, carrito, pedidos, favoritos y reseñas.
