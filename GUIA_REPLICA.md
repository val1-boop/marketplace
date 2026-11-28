# Marketplace seguro en Flask + AWS — Guía de réplica completa

Este repositorio contiene **todo** lo necesario para reproducir, en tu propio laboratorio de
AWS Academy y en tu propia computadora, exactamente el mismo proyecto: mismas tablas, mismo
diseño, misma estructura y mismo plan. Cada persona trabaja por separado, con su propio
laboratorio y su propio Claude Code.

> **Si eres un asistente de IA** (Claude Code, Codex, Copilot, Gemini, ChatGPT…): lee también
> [`AGENTS.md`](AGENTS.md); Claude Code lo carga solo a través de `CLAUDE.md`. Contiene las reglas
> de trabajo. La más importante: **el código ya está escrito y no se regenera**. Tu trabajo es
> guiar al usuario fase por fase, ejecutar los comandos locales y verificar cada punto de control.
>
> **Si eres una persona usando otra IA sin acceso a tus archivos:** pégale primero el contenido de
> `AGENTS.md` y después el de este README.

**Versión del proyecto:** ver el archivo [`VERSION`](VERSION). Todas las réplicas deben tener la
misma versión y pasar `python tools/verificar_integridad.py` (Fase 1).

---

## Reglas obligatorias para el agente (pedidas por el profesor)

Todo asistente de IA que escriba o cambie código en este proyecto **lee este README antes de
empezar** y cumple siempre estas reglas:

1. **Seguridad en cada cambio.** Al agregar o modificar código, analiza sus vulnerabilidades
   (inyección, XSS, CSRF, IDOR, control de acceso, secretos, exposición de datos) y explica cómo
   quedan cubiertas. Si un cambio abre un riesgo, no se entrega.
2. **Commit al terminar cada flujo completo.** Cuando un flujo quede terminado (por ejemplo,
   "agregar al carrito" de punta a punta), el agente **pide permiso al usuario** para hacer commit;
   no hace commits por su cuenta.
3. **Mensajes de commit descriptivos y precisos.** Primera línea en imperativo y menor a 72
   caracteres que diga qué cambia; después, en el cuerpo, el porqué y las decisiones de seguridad.
   Ejemplo: `Agrega carrito con precio tomado de DynamoDB y validación de existencias`.
4. **Pruebas automáticas antes de probar o depurar.** Cuando el proyecto esté listo para probar,
   corre `pytest` (todas las pruebas deben pasar), `bandit -r .` (sin hallazgos) y
   `pip-audit -r requirements.txt`, y muestra el resultado.
5. **Respeta la estructura de carpetas** (sección 3): cada módulo con su servicio en `Services/`,
   su contrato y DTO en `Interfaces/`, su lógica en `Implementation/` y su presentación en
   `View/<Modulo>Views/` (PY, HTML, CSS, JS, Utils).

Las reglas de trabajo completas (no regenerar el código, nombres de AWS, secretos) están en
[`AGENTS.md`](AGENTS.md).

---

## Índice

1. [Qué es el proyecto](#1-qué-es-el-proyecto)
2. [Arquitectura](#2-arquitectura)
3. [Estructura del repositorio](#3-estructura-del-repositorio)
4. [Inventario exacto de recursos](#4-inventario-exacto-de-recursos)
5. [Plan de inicio a fin](#5-plan-de-inicio-a-fin)
6. [Usuarios de prueba](#6-usuarios-de-prueba)
7. [Funcionalidad y rutas](#7-funcionalidad-y-rutas)
8. [Seguridad](#8-seguridad)
9. [Problemas conocidos y soluciones](#9-problemas-conocidos-y-soluciones)
10. [Costos y apagado](#10-costos-y-apagado)
11. [Estado de verificación](#11-estado-de-verificación)
12. [Actualizaciones del proyecto (solo el dueño)](#12-actualizaciones-del-proyecto-solo-el-dueño)

---

## 1. Qué es el proyecto

Proyecto de laboratorio universitario: un **marketplace multivendedor** con interfaz web, basado
en el documento *DocumentacionHastaRDS_Completa* (Prácticas DynamoDB, Partes 1 a 5). El profesor
intentará vulnerar la aplicación, así que la prioridad es:

**seguridad > funcionalidad > legibilidad del código > diseño visual**

Funciones:
- **Cuentas:** login y logout, registro, perfil, cambio de contraseña, CRUD de usuarios (solo admin)
  y bitácoras de seguridad.
- **Catálogo público** (sin cuenta, como Mercado Libre): búsqueda, filtros, orden y ficha de producto
  con ID, nombre, descripción, precio, existencias y **opiniones con estrellas**.
- **Una sola cuenta compra y vende:** publicar, editar y borrar productos propios; **carrito**,
  **favoritos**, **direcciones de envío**, **comprar** (un pedido por vendedor, con fecha y fecha
  estimada de entrega), **Mis compras** y **Mis ventas** con estados *Confirmado → En preparación →
  Enviado → Entregado* (o *Cancelado*).
- **Reseñas como Amazon:** de 1 a 5 estrellas con opinión; solo quien recibió el producto, una
  vez; el producto muestra el promedio y el histograma.
- **Moderación:** bloquear, desbloquear y eliminar productos; ver y cancelar pedidos.
- **Pago:** fuera del alcance por ahora (pendiente de confirmar con el profesor); al comprar, el
  pedido nace *Confirmado*.

Diseño visual inspirado en la plantilla "Stuffus Shop" (blanco, negro y mosaicos grises).

**Stack:** Python 3 + Flask (Application Factory + Blueprints), Jinja2, Flask-SQLAlchemy,
Flask-Login, Flask-WTF, Flask-Limiter, Flask-Talisman, Flask-Migrate y argon2-cffi;
AWS DynamoDB, Lambda (Python 3.14), API Gateway (HTTP API), RDS MySQL 8.4 y RDS PostgreSQL.

**Convención de nombres (requisito del profesor):** todos los recursos de AWS se nombran **en
inglés**. Las funciones Lambda empiezan con `lambda` seguido de su identificador
(`lambdaListProducts`) y el API empieza con `apiGateway` (`apiGatewayMarketplace`). Las tablas
(`Products`, `Orders`, `Marketplace`, `Community`, `users`…), las bases (`marketplace`,
`security`) y las instancias RDS ya están en inglés desde la Parte 5. La interfaz web y la
documentación siguen en español.

---

## 2. Arquitectura

```
                    ┌──────────────────────────── tu computadora ───────────────────────────┐
 Navegador ───────► │ Flask (localhost:5000)                                                 │
 (solo habla        │  login, roles, CSRF, validación, rate limit, cabeceras de seguridad    │
  con Flask)        └───────┬───────────────────────┬───────────────────────────┬────────────┘
                            │ TLS                   │ TLS                       │ HTTPS + x-mkt-token
                            ▼                       ▼                           ▼
              RDS MySQL rds-mkt-identity-db   RDS PostgreSQL           apiGatewayMarketplace
              base marketplace                rds-mkt-security-db      autorizador lambdaAuthorizer
              users, addresses,               base security            throttling 10 rps / 20 ráfaga
              admin_actions (mkt_app)         login_attempts,                   │
                                              auth_events (mkt_app)             ▼
                                                              18 Lambdas (una por ruta) ──► DynamoDB
                                                              Products · Orders · Marketplace · Community
```

| Dato | Dónde vive | Por qué |
|---|---|---|
| Usuarios y bitácora de moderación | RDS MySQL `marketplace` | Relacional: llaves foráneas, unicidad de correo garantizada por el motor |
| Intentos de login y eventos de acceso | RDS PostgreSQL `security` | Bitácora de seguridad aislada, con credenciales propias |
| Productos (con promedio de estrellas) | DynamoDB `Products` | Lectura por clave, atributos variables, índices `bySeller` y `byCategoryPrice` |
| Direcciones de envío | RDS MySQL `addresses` | Relacional: dueño por llave foránea y "una sola predeterminada" garantizada por índice único |
| Carrito | DynamoDB `Marketplace` (`USER#id / CART#producto`, caduca a los 30 días) | Patrón de la Parte 5 con TTL |
| Pedidos, renglones, envío e historial de estados | DynamoDB `Orders` (`ORDER#id / ORDER · ITEM# · SHIPMENT · STATUS#`) | Un pedido se lee en una consulta; `GSI1` da "Mis compras" y "Mis ventas" |
| Favoritos, compras entregadas y reseñas | DynamoDB `Community` | `USER#id / FAV#`, `USER#id / PURCHASED#` y `PRODUCT#id / REVIEW#` |
| `reports` | MySQL | Se crea igual que en la Parte 5; la interfaz actual no la usa |

**Decisiones de diseño (todas tomadas eligiendo la opción más segura):**

1. **El catálogo es público, como en Mercado Libre:** sin cuenta se ve la portada, el catálogo,
   la búsqueda, los filtros y la ficha de cada producto. Lo público **solo lee**: publicar,
   editar, borrar, moderar y administrar exigen sesión y rol. Los productos bloqueados nunca se
   muestran al público, y del vendedor solo se muestra "Nombre A." (nunca su correo). Para que
   muchas visitas anónimas no se vuelvan muchas llamadas a Lambda, el listado se guarda en
   caché 10 segundos (`PRODUCT_LIST_CACHE_SECONDS`) y se vacía en cada escritura.
2. El `seller_id` lo asigna el servidor desde la sesión, nunca el formulario.
3. El `product_id` lo genera la Lambda (`PROD-` + 8 dígitos), con `attribute_not_exists`.
4. Roles `user` y `admin`. Un admin no tiene tienda (restricción `chk_staff_no_store`): modera,
   no vende.
5. Eliminar usuario es borrado lógico: `status='deleted'`, datos anonimizados y productos `DELISTED`.
6. Sin "Recordarme"; sesión de 30 min de inactividad y máximo 8 h.
7. Registrar un correo existente muestra el mismo mensaje que un registro exitoso (anti-enumeración).
8. Columna `users.session_nonce` para invalidar sesiones en el servidor (logout, cambio de contraseña, rol o estado).
9. Se usa la tabla `Products` (inglés, Parte 5), no `Productos` (Partes 1–4).
10. API protegido con autorizador Lambda y token secreto; las Lambdas vuelven a validar y
    comprueban el dueño con `ConditionExpression`.
11. `lambdaListProducts` (`GET /products`) se agregó porque el catálogo la necesita.
12. Los identificadores se generan en el servidor de forma aleatoria (`PROD-########`,
    `SEL-######`, UUID de usuario, ULID de pedidos y reseñas). Por eso **los IDs serán distintos
    en cada réplica**; es intencional. Todo lo demás (estructura, nombres, datos de demostración y
    comportamiento) es idéntico.
13. **Comprar es una sola transacción de DynamoDB** (`TransactWriteItems`): crear los pedidos,
    descontar existencias (solo si alcanzan), y vaciar el carrito ocurre todo o nada. Si dos
    personas compran la última pieza al mismo tiempo, una recibe "las existencias cambiaron".
14. **El precio nunca viene del navegador:** la Lambda lo lee de `Products` al mostrar el carrito
    y al comprar. Del navegador solo llegan el ID del producto, la cantidad (1 a 10) y el ID de
    una dirección **propia** (Flask la busca filtrando por el usuario en sesión).
15. **Un pedido por vendedor**, como Mercado Libre: cada vendedor prepara y envía lo suyo. El
    vendedor marca *En preparación* y *Enviado*; el comprador confirma *Entregado*. Cancelar:
    el comprador mientras está *Confirmado*, el vendedor hasta *En preparación* y un admin hasta
    *Enviado*; al cancelar, las piezas regresan al inventario. Entrega estimada: 3 a 7 días.
16. **Reseñas verificadas:** al confirmar la entrega se guarda `PURCHASED#producto`; la reseña
    exige ese registro y lo marca como usado en la misma transacción (una por compra). El
    promedio sale de `rating_sum / rating_count` en `Products`, actualizado con `ADD` atómico.
17. Las cuentas de administración no compran (no tienen tienda); solo moderan y pueden ver o
    cancelar un pedido.

---

## 3. Estructura del repositorio

```
marketplace/
├── README.md                 ← descripción del proyecto (página principal del repo)
├── GUIA_REPLICA.md           ← esta guía de réplica (plan completo)
├── AGENTS.md                 ← reglas para cualquier asistente de IA
├── CLAUDE.md                 ← importa AGENTS.md (Claude Code lo carga automáticamente)
├── VERSION                   ← versión del proyecto (todas las réplicas deben coincidir)
├── MANIFEST.sha256           ← huella SHA-256 de cada archivo (verificación de copia idéntica)
├── tools/verificar_integridad.py ← compara tu copia contra MANIFEST.sha256
├── GUIA_AWS.md               ← detalle clic por clic de Lambdas, API Gateway, Postman y Flask
├── SECURITY.md               ← matriz de vulnerabilidades, checklist AWS y riesgos residuales
├── requirements.txt          ← árbol COMPLETO de dependencias con versión exacta
├── requirements-dev.txt      ← + pytest, bandit, pip-audit
├── .env.example              ← plantilla de configuración (copiar a .env)
├── .bandit  pytest.ini  .gitignore
├── wsgi.py                   ← entrada WSGI (gunicorn wsgi:app)
├── run.py                    ← servidor local, siempre con debug=False
├── gunicorn.conf.py          ← producción
│
├── Core/                       ← núcleo de la app
│   ├── AppFactory.py           ← create_app(): config, Talisman (CSP), binds, hooks, errores
│   ├── Config.py               ← configuración por entorno (development / production / testing)
│   ├── Extensions.py           ← db, login_manager, csrf, limiter, migrate, talisman
│   ├── ServiceRegistry.py      ← une cada interfaz con su implementación
│   ├── Catalog.py              ← listas blancas: departamentos, categorías, condición, orden
│   └── Cli.py                  ← comandos: init-db, check-aws, seed-demo, seed-descriptions, create-admin
├── Models/                     ← modelos SQL: IdentityModels (users, admin_actions · MySQL),
│                                 AddressModels (addresses · MySQL),
│                                 SecurityModels (login_attempts, auth_events · PostgreSQL)
├── Security/SecurityUtils.py   ← Argon2id, política de contraseñas, open redirect, roles, logs
│
├── Services/                   ← RUTAS de cada módulo (la puerta de entrada de cada servicio)
│   ├── MainService/MainService.py        ← portada pública, inicio personal, panel admin, perfil
│   ├── AuthService/AuthService.py        ← login, logout, registro, cambio de contraseña
│   ├── ProductService/ProductService.py  ← catálogo público, publicar, editar, borrar, moderar
│   ├── UserService/UserService.py        ← CRUD de usuarios (solo admin)
│   ├── CartService/CartService.py        ← carrito: ver, agregar, comprar ahora, cantidad, quitar
│   ├── FavoriteService/FavoriteService.py← favoritos
│   ├── AddressService/AddressService.py  ← direcciones de envío (CRUD, predeterminada)
│   ├── OrderService/OrderService.py      ← confirmar compra, Mis compras, detalle y estados, Mis ventas
│   └── ReviewService/ReviewService.py    ← publicar reseña con estrellas
├── Interfaces/                 ← CONTRATO de cada servicio (clase abstracta) + sus DTO
│   ├── MainServiceInterface/     IMainService.py + MainDTO.py
│   ├── AuthServiceInterface/     IAuthService.py + AuthDTO.py
│   ├── ProductServiceInterface/  IProductService.py + ProductDTO.py + ProductErrors.py
│   ├── UserServiceInterface/     IUserService.py + UserDTO.py
│   ├── CartServiceInterface/     ICartService.py + CartDTO.py
│   ├── FavoriteServiceInterface/ IFavoriteService.py + FavoriteDTO.py
│   ├── AddressServiceInterface/  IAddressService.py + AddressDTO.py
│   ├── OrderServiceInterface/    IOrderService.py + OrderDTO.py (estados, línea de tiempo, acciones)
│   ├── ReviewServiceInterface/   IReviewService.py + ReviewDTO.py
│   └── ApiErrors.py              ← errores comunes del API (404, 403, 409, 400, no disponible)
├── Implementation/             ← LÓGICA y acceso a datos de cada servicio
│   ├── MainServiceImplementation/MainServiceImplementation.py
│   ├── AuthServiceImplementation/AuthServiceImplementation.py        ← RDS MySQL + PostgreSQL
│   ├── ProductServiceImplementation/ProductServiceImplementation.py  ← reglas del catálogo
│   │   └── ProductsApiClient.py  ← cliente del API Gateway (timeout, sin SSRF, token oculto)
│   ├── UserServiceImplementation/UserServiceImplementation.py        ← RDS MySQL
│   ├── AddressServiceImplementation/     ← RDS MySQL (siempre filtrando por el usuario en sesión)
│   ├── CartServiceImplementation/        ← API: /cart
│   ├── FavoriteServiceImplementation/    ← API: /favorites
│   ├── OrderServiceImplementation/       ← API: /orders y /sales
│   ├── ReviewServiceImplementation/      ← API: /products/{id}/reviews
│   └── SharedImplementation/     ApiGatewayClient.py (conexión común al API: token, timeout,
│                                 errores), ShopPaths.py (IDs con lista blanca), AccountQueries.py,
│                                 AuditLog.py (auth_events, admin_actions)
├── View/                       ← PRESENTACIÓN de cada módulo
│   ├── SharedViews/            ← lo común a todas las pantallas
│   │   ├── PY/SharedForms.py     ← validadores y piezas de formulario compartidas
│   │   ├── HTML/                 ← Base.html (cabecera, menú, íconos), Macros.html, Error.html
│   │   ├── CSS/                  ← Base.css + Fonts/ (Archivo, licencia OFL)
│   │   ├── JS/App.js             ← único JavaScript (sin inline, sin innerHTML ni eval)
│   │   └── Utils/                ← Assets.py (sirve CSS/JS con listas blancas),
│   │                               TemplateHelpers.py, Pagination.py
│   ├── MainViews/              ← HTML: Home, AdminDashboard, Profile · CSS: Main.css
│   ├── AuthViews/              ← PY: AuthForms · HTML: Login, Register, ChangePassword · CSS: Auth.css
│   ├── ProductViews/           ← PY: ProductForms · HTML: Catalog, ProductDetail, ProductForm,
│   │                             MyProducts, BlockProduct · CSS: Product.css · Utils: CatalogFilters
│   ├── UserViews/              ← PY: UserForms · HTML: UserList, UserDetail, UserForm · CSS: User.css
│   ├── CartViews/              ← PY: CartForms · HTML: Cart · CSS: Cart.css
│   ├── FavoriteViews/          ← PY: FavoriteForms · HTML: Favorites · CSS: Favorite.css
│   ├── AddressViews/           ← PY: AddressForms · HTML: Addresses, AddressForm · CSS: Address.css
│   ├── OrderViews/             ← PY: OrderForms · HTML: Checkout, Orders, OrderDetail · CSS: Order.css
│   └── ReviewViews/            ← PY: ReviewForms · HTML: Reviews (dentro de la ficha) · CSS: Review.css
│                                 (cada vista tiene sus carpetas PY, HTML, CSS, JS y Utils)
│
├── aws/
│   ├── dynamodb/crear_tablas_dynamodb.sh  ← crea las 4 tablas + índices + TTL + ítems (CloudShell)
│   ├── sql/00_mysql_schema.sql            ← esquema original Parte 5 (MySQL)
│   ├── sql/01_mysql_marketplace.sql       ← ajustes + usuario mkt_app (MySQL)
│   ├── sql/00_postgres_schema.sql         ← esquema original Parte 5 (PostgreSQL)
│   ├── sql/02_postgres_security.sql       ← usuario mkt_app (PostgreSQL)
│   ├── sql/03_mysql_addresses.sql         ← permisos de mkt_app sobre addresses (entrega 2)
│   ├── sql/04_mysql_sellers.sql           ← tabla sellers: perfil de la tienda del vendedor (2.1.0)
│   ├── lambdas/                           ← 19 archivos .py para pegar en la consola de Lambda
│   └── lambdas_src/                       ← fuente de las Lambdas: common.py + handlers/ (solo el
│                                            dueño las edita; tools/build_lambdas.py arma aws/lambdas/)
│
├── deploy/                   ← nginx.conf, política IAM mínima, política S3, IMDSv2
└── tests/                    ← pytest: Flask + Lambdas reales contra AWS simulado
```

**Cómo se conectan las capas** (ejemplo: ver el catálogo):

```
Navegador → Services/ProductService (ruta /items/)
              → valida el formulario de View/ProductViews/PY/ProductForms.py
              → pide IProductService (Interfaces/) a Core/ServiceRegistry
              → Implementation/ProductServiceImplementation aplica las reglas
                  → ProductsApiClient → API Gateway → Lambda → DynamoDB
            ← render de View/ProductViews/HTML/Catalog.html (+ Base.css + Product.css)
```

Las rutas (`Services/`) solo conocen las interfaces; la lógica vive una sola vez en
`Implementation/`. Las plantillas se buscan dentro de `View/` y el CSS/JS de cada vista se sirve
con una ruta que **solo** entrega archivos `.css`, `.js`, `.ttf` y `.svg` de las carpetas `CSS` y `JS`
(nunca el código Python que vive junto a ellos).

---

## 4. Inventario exacto de recursos

Usa **exactamente** estos nombres. Cada laboratorio es independiente, así que no hay conflictos
entre compañeros.

### 4.1 DynamoDB (todas en modo **Bajo demanda**, región **us-east-1**)

| Tabla | Clave de partición | Clave de ordenación | Índices (GSI) | TTL |
|---|---|---|---|---|
| `Products` | `product_id` (S) | — | `byCategoryPrice` (`listed_category` S / `price` N, Include) y `bySeller` (`seller_id` S / `product_id` S, Include) | — |
| `Orders` | `PK` (S) | `SK` (S) | `GSI1` (`GSI1PK`/`GSI1SK`, All) y `GSI2` (`GSI2PK`/`GSI2SK`, All) | — |
| `Marketplace` | `PK` (S) | `SK` (S) | ninguno | `expires_at` |
| `Community` | `PK` (S) | `SK` (S) | `GSI1` y `GSI2` (All) | `expires_at` |

Atributos proyectados con Include:
- **`byCategoryPrice`:** `name, search_name, category, stock, seller_id, condition, cover_image, rating_sum, rating_count`.
- **`bySeller`:** `name, price, stock, category, status, blocked_reason, prior_status, cover_image, sales_count, updated_at, version, seller_sku`.

Atributos de un ítem de `Products` que escribe la app: `product_id, name, search_name, description,
category, listed_category` (solo si está `ACTIVE`)`, price, stock, seller_id, condition, status`
(`ACTIVE | BLOCKED | DELISTED`)`, blocked_reason, prior_status, sales_count, version, created_at,
updated_at` y las calificaciones `rating_sum, rating_count, rating_1 … rating_5`.

Ítems de la tienda (entrega 2), mismos patrones de clave que la Parte 5:

| Tabla | `PK` | `SK` | Qué es | Índices que llena |
|---|---|---|---|---|
| `Marketplace` | `USER#<user_id>` | `CART#<product_id>` | renglón del carrito (`quantity`, `expires_at` = +30 días) | — |
| `Community` | `USER#<user_id>` | `FAV#<product_id>` | favorito | — |
| `Community` | `USER#<user_id>` | `PURCHASED#<product_id>` | compra entregada (habilita UNA reseña) | — |
| `Community` | `PRODUCT#<product_id>` | `REVIEW#<ulid>` | reseña (`rating` 1–5, `comment`, `author_name`) | `GSI1PK = USER#<user_id>` |
| `Orders` | `ORDER#<ulid>` | `ORDER` | encabezado (`buyer_id, seller_id, status, total, estimated_from/to`) | `GSI1PK = USER#<comprador>`, `GSI2PK = STATUS#<estado>` |
| `Orders` | `ORDER#<ulid>` | `ITEM#<product_id>` | renglón (precio de ese momento, cantidad) | `GSI1PK = SELLER#<vendedor>` |
| `Orders` | `ORDER#<ulid>` | `SHIPMENT` | copia de la dirección y fechas de envío/entrega | — |
| `Orders` | `ORDER#<ulid>` | `STATUS#<fecha>#<paso><ESTADO>` | historial de estados | — |

### 4.2 RDS

| | MySQL | PostgreSQL |
|---|---|---|
| Identificador | `rds-mkt-identity-db` | `rds-mkt-security-db` |
| Motor | MySQL **8.4.x** (nunca 8.0: cobra soporte extendido) | PostgreSQL, versión más reciente |
| Plantilla | Capa gratuita | Capa gratuita |
| Usuario maestro | `admin` (autoadministrado, sin Secrets Manager) | `postgres` (autoadministrado) |
| Clase / disco | `db.t4g.micro` (o `db.t3.micro`), gp2 20 GiB, sin autoescalado | igual |
| Acceso público | Sí, solo durante la sesión | igual |
| Grupo de seguridad | nuevo `mkt-sg-mysql`: 3306 desde **Mi IP** | nuevo `mkt-sg-postgres`: 5432 desde **Mi IP** |
| Supervisión | Database Insights estándar 7 días, monitoreo mejorado desactivado | igual |
| Copias / protección | Retención 1 día, sin protección contra eliminación | igual |
| Base | `marketplace` (la crea el script) | `security` (nombre de base inicial) |
| Tablas | `users, addresses, reports, admin_actions` | `login_attempts, auth_events` |
| Usuario de la app | `mkt_app` (SELECT/INSERT/UPDATE en `users` y `addresses`; SELECT/INSERT en `admin_actions`; SSL) | `mkt_app` (CRUD en `login_attempts`; SELECT/INSERT en `auth_events`) |

### 4.3 Lambda (Python 3.14, rol **LabRole**, región us-east-1)

Si tu consola no ofrece Python 3.14, usa Python 3.13: el código es compatible con ambos.
**Una Lambda por ruta** (regla del profesor). Cada archivo es independiente: se pega completo.

| # | Función | Archivo | Variable de entorno | Timeout | Tablas |
|---|---|---|---|---|---|
| 1 | `lambdaAuthorizer` | `aws/lambdas/lambdaAuthorizer.py` | `API_TOKEN` = token secreto | 5 s | — |
| 2 | `lambdaListProducts` | `aws/lambdas/lambdaListProducts.py` | `TABLE_NAME` = `Products` | 10 s | Products |
| 3 | `lambdaGetProduct` | `aws/lambdas/lambdaGetProduct.py` | `TABLE_NAME` = `Products` | 10 s | Products |
| 4 | `lambdaCreateProduct` | `aws/lambdas/lambdaCreateProduct.py` | `TABLE_NAME` = `Products` | 10 s | Products |
| 5 | `lambdaUpdateProduct` | `aws/lambdas/lambdaUpdateProduct.py` | `TABLE_NAME` = `Products` | 10 s | Products |
| 6 | `lambdaDeleteProduct` | `aws/lambdas/lambdaDeleteProduct.py` | `TABLE_NAME` = `Products` | 10 s | Products |
| 7 | `lambdaGetCart` | `aws/lambdas/lambdaGetCart.py` | ninguna | 10 s | Marketplace, Products |
| 8 | `lambdaPutCartItem` | `aws/lambdas/lambdaPutCartItem.py` | ninguna | 10 s | Marketplace, Products |
| 9 | `lambdaDeleteCartItem` | `aws/lambdas/lambdaDeleteCartItem.py` | ninguna | 10 s | Marketplace |
| 10 | `lambdaListFavorites` | `aws/lambdas/lambdaListFavorites.py` | ninguna | 10 s | Community, Products |
| 11 | `lambdaAddFavorite` | `aws/lambdas/lambdaAddFavorite.py` | ninguna | 10 s | Community, Products |
| 12 | `lambdaDeleteFavorite` | `aws/lambdas/lambdaDeleteFavorite.py` | ninguna | 10 s | Community |
| 13 | `lambdaCreateOrder` | `aws/lambdas/lambdaCreateOrder.py` | ninguna | **15 s** | Orders, Marketplace, Products |
| 14 | `lambdaListOrders` | `aws/lambdas/lambdaListOrders.py` | ninguna | 10 s | Orders |
| 15 | `lambdaGetOrder` | `aws/lambdas/lambdaGetOrder.py` | ninguna | 10 s | Orders |
| 16 | `lambdaUpdateOrderStatus` | `aws/lambdas/lambdaUpdateOrderStatus.py` | ninguna | 10 s | Orders, Products, Community |
| 17 | `lambdaListSales` | `aws/lambdas/lambdaListSales.py` | ninguna | 10 s | Orders |
| 18 | `lambdaListReviews` | `aws/lambdas/lambdaListReviews.py` | ninguna | 10 s | Community |
| 19 | `lambdaCreateReview` | `aws/lambdas/lambdaCreateReview.py` | ninguna | 10 s | Community, Products |

Las funciones 7 a 19 no llevan variables: usan los nombres de tabla de la Parte 5 (`Products`,
`Orders`, `Marketplace`, `Community`). Eventos de prueba en la consola: `testFakeToken` (en
`lambdaAuthorizer`) y `testGetProduct` (en `lambdaGetProduct`), detallados en la Fase 6.

### 4.4 API Gateway — API HTTP `apiGatewayMarketplace`, etapa `$default`, implementación **manual**

**Implementación automática siempre desactivada** (regla del profesor): después de cualquier
cambio se pulsa **Implementar** (Fase 7, paso 6). Todas las rutas llevan el autorizador.

| # | Método | Ruta | Integración |
|---|---|---|---|
| 1 | GET | `/products` | `lambdaListProducts` |
| 2 | POST | `/products` | `lambdaCreateProduct` |
| 3 | GET | `/products/{product_id}` | `lambdaGetProduct` |
| 4 | PUT | `/products/{product_id}` | `lambdaUpdateProduct` |
| 5 | DELETE | `/products/{product_id}` | `lambdaDeleteProduct` |
| 6 | GET | `/cart` | `lambdaGetCart` |
| 7 | PUT | `/cart/{product_id}` | `lambdaPutCartItem` |
| 8 | DELETE | `/cart/{product_id}` | `lambdaDeleteCartItem` |
| 9 | GET | `/favorites` | `lambdaListFavorites` |
| 10 | PUT | `/favorites/{product_id}` | `lambdaAddFavorite` |
| 11 | DELETE | `/favorites/{product_id}` | `lambdaDeleteFavorite` |
| 12 | POST | `/orders` | `lambdaCreateOrder` |
| 13 | GET | `/orders` | `lambdaListOrders` |
| 14 | GET | `/orders/{order_id}` | `lambdaGetOrder` |
| 15 | PUT | `/orders/{order_id}` | `lambdaUpdateOrderStatus` |
| 16 | GET | `/sales` | `lambdaListSales` |
| 17 | GET | `/products/{product_id}/reviews` | `lambdaListReviews` |
| 18 | POST | `/products/{product_id}/reviews` | `lambdaCreateReview` |

- **Autorizador `mktTokenAuthorizer`** en las 18 rutas: tipo Lambda (`lambdaAuthorizer`),
  payload 2.0, respuesta Simple, origen de identidad `$request.header.x-mkt-token`, caché
  desactivada (TTL 0).
- **Throttling** de la etapa `$default`: ráfaga 20, velocidad 10.
- **CORS:** no se configura.

**Contrato del API** (lo usa `Implementation/SharedImplementation/ApiGatewayClient.py`):

| Cabecera | Valor |
|---|---|
| `x-mkt-token` | secreto (≥32 caracteres), igual a `API_TOKEN` del autorizador y a `PRODUCTS_API_TOKEN` del `.env` |
| `x-mkt-actor-role` | `user` o `admin` (en escrituras y en todo lo de la tienda) |
| `x-mkt-actor-seller` | `seller_id` del usuario en sesión (`SEL-######`) o vacío si es admin |
| `x-mkt-actor-user` | UUID del usuario en sesión (carrito, favoritos, pedidos, reseñas) |

Flask llena las tres cabeceras `x-mkt-actor-*` con los datos de la **sesión**; el navegador nunca
llama al API (el token solo lo conoce el servidor).

| Ruta | Cuerpo | Respuesta |
|---|---|---|
| `PUT /products/{id}` | dueño: `{"action": "update", "expected_version": N, name, description, category, price, stock, condition}`; admin: `{"action": "block", "reason": "…"}`, `{"action": "unblock"}`, `{"action": "delist"}` | `{"producto": {...}}` |
| `GET /cart` | — | `{"lineas": [{product_id, quantity, available, reason, producto}], "total": "0.00"}` |
| `PUT /cart/{id}` | `{"quantity": 1..10, "mode": "add" \| "set"}` | `{"mensaje", "product_id", "quantity"}` |
| `GET /favorites` | — | `{"favoritos": [{product_id, added_at, producto}]}` |
| `POST /orders` | `{"address": {recipient_name, phone, line1, line2, city, state, postal_code}}` | **201** `{"pedidos": [...]}` (uno por vendedor) |
| `GET /orders` · `GET /sales` | — | `{"pedidos": [...]}` · `{"ventas": [...]}` |
| `GET /orders/{id}` | — | `{"pedido": {..., items, shipment, history, viewer}}` |
| `PUT /orders/{id}` | `{"action": "prepare" \| "ship" \| "deliver" \| "cancel", "reason": "opcional"}` | `{"pedido": {...}}` |
| `GET /products/{id}/reviews` | — | `{"resenas": [...], "puede_opinar": true/false}` |
| `POST /products/{id}/reviews` | `{"rating": 1..5, "comment": "10 a 1000", "author_name": "Ana P."}` | **201** `{"review_id"}` |

Los errores `400/403/404/409` traen `{"mensaje": "..."}` y, si aplica, `{"errores": [...]}`.
Un pedido ajeno responde **404** (no se revela que existe).

### 4.5 Variables del `.env`

| Variable | Valor |
|---|---|
| `APP_ENV` | `development` |
| `SECRET_KEY` | aleatoria, ≥32 caracteres (comando en la Fase 1) |
| `DATABASE_URL` | `mysql+pymysql://mkt_app:CLAVE@ENDPOINT-MYSQL:3306/marketplace?charset=utf8mb4&ssl_ca=certs/global-bundle.pem&connect_timeout=10` |
| `SECURITY_DATABASE_URL` | `postgresql+psycopg://mkt_app:CLAVE@ENDPOINT-POSTGRES:5432/security?sslmode=verify-full&sslrootcert=certs/global-bundle.pem&connect_timeout=10` |
| `PRODUCTS_API_URL` | URL de invocación de `$default`, sin `/` final |
| `PRODUCTS_API_TOKEN` | el token secreto |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | `admin@marketplace.mx` / *(define una contraseña fuerte en tu `.env`)* |
| `SEED_USER_EMAIL` / `SEED_USER_PASSWORD` | `vendedor@marketplace.mx` / *(define una contraseña fuerte en tu `.env`)* |

---

## 5. Plan de inicio a fin

Cada fase termina con un **punto de control**. No pases a la siguiente hasta cumplirlo.
Los comandos son para **Windows PowerShell** (terminal de VS Code); en Mac o Linux, cambia
`.venv\Scripts\Activate.ps1` por `source .venv/bin/activate` y `copy` por `cp`.

### Fase 0 — Requisitos

- **Python 3.13** exactamente (cualquier 3.13.x), que es la versión con la que se validó. Al
  instalarlo marca *Add Python to PATH*. Si ya tienes otra versión, instala 3.13 además de la
  tuya; en Windows el lanzador `py` permite elegirla (`py -3.13`).
- **Visual Studio Code** con Claude Code.
- **DataGrip** o **MySQL Workbench** (MySQL) y DataGrip o pgAdmin (PostgreSQL).
- **Postman.**
- Acceso a **AWS Academy** (Learner Lab).

✅ **Punto de control:** `py -3.13 --version` (Windows) o `python3.13 --version` (Mac/Linux) muestra 3.13.x.

### Fase 1 — Proyecto local

1. Recibe el proyecto del dueño (`marketplace-flask.zip`) y descomprímelo **fuera de OneDrive**,
   por ejemplo en `C:\proyectos\marketplace`. OneDrive bloquea archivos de `.venv`.
2. Abre la carpeta en VS Code (**Archivo → Abrir carpeta**) y una terminal (**Terminal → Nueva terminal**).
3. **Verifica que tu copia es idéntica:**
   ```powershell
   py -3.13 tools\verificar_integridad.py
   ```
   Debe decir `Copia idéntica (... archivos, versión X)`, con la misma versión que te indicó el
   dueño. Si no, vuelve a descargar el zip. Ojo: si descargas varias veces, Windows nombra los
   archivos `marketplace-flask (1).zip`, `(2)`…; usa el más reciente (columna *Fecha de
   modificación* en Descargas).
4. Crea el entorno **con Python 3.13** e instala:
   ```powershell
   py -3.13 -m venv .venv
   .venv\Scripts\Activate.ps1
   python --version
   pip install -r requirements-dev.txt
   ```
   `python --version` debe mostrar 3.13.x dentro del entorno. En Mac/Linux usa `python3.13 -m venv .venv`.
   Si PowerShell bloquea la activación, ejecuta una vez
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
5. Crea el `.env` y escribe la `SECRET_KEY` automáticamente, sin copiar y pegar:
   ```powershell
   copy .env.example .env
   python -c "import secrets,re; p='.env'; s=open(p,encoding='utf-8').read(); s=re.sub(r'(?m)^SECRET_KEY=.*', 'SECRET_KEY='+secrets.token_urlsafe(64), s); open(p,'w',encoding='utf-8').write(s); print('Listo')"
   Select-String SECRET_KEY .env
   ```
6. Corre las pruebas; no requieren AWS:
   ```powershell
   pytest
   ```

✅ **Punto de control:** copia idéntica, `pip install` sin errores, `SECRET_KEY` con una cadena
aleatoria y `pytest` con **347 passed**.

### Fase 2 — DynamoDB (4 tablas)

1. AWS Academy → **Start Lab** → indicador verde → abre la consola en **us-east-1**.
2. Abre **CloudShell** (icono `>_` de la barra superior de la consola, o el botón *CloudShell* de
   la barra inferior) → **Acciones → Cargar archivo** →
   `aws/dynamodb/crear_tablas_dynamodb.sh` → ejecuta:
   ```bash
   bash crear_tablas_dynamodb.sh
   ```
   *Alternativa manual:* crear las tablas en la consola según la sección 4.1 (como en la
   Parte 5, A.1–A.6), creando **un índice a la vez** por tabla.

✅ **Punto de control:** en DynamoDB → Tablas hay 4 tablas **Activas**, en Bajo demanda, con 2, 2,
0 y 2 índices, y `Products` contiene `PROD-00001` (Wireless Mouse).

### Fase 3 — RDS MySQL (`rds-mkt-identity-db`)

> **¿Ya tienes las RDS de la Parte 5?** Solo enciéndelas (**RDS → Bases de datos →** selecciona
> la instancia **→ Acciones → Iniciar**), actualiza la regla del grupo de seguridad a **Mi IP**
> (paso 2) y salta al paso 4. **No ejecutes** `00_mysql_schema.sql`: tus tablas ya existen.

1. **Crear la instancia.** **RDS → Crear base de datos → Creación estándar (Completa) → MySQL
   8.4.x**, con la configuración de la sección 4.2. Anota la contraseña de `admin` en un Bloc de
   notas **fuera del proyecto** (por ejemplo `Documentos\claves-marketplace.txt`). Tarda de 10 a
   20 minutos en quedar **Disponible**.
2. **Abrir el puerto solo a tu IP.** Clic en la instancia → pestaña **Conectividad y seguridad**
   → clic en el grupo de seguridad → **Editar reglas de entrada** → regla **MYSQL/Aurora**,
   origen **Mi IP** → **Guardar reglas**. **Nunca** `0.0.0.0/0`.
3. **Probar la red.** Copia el **Punto de enlace** de la misma pestaña y, en PowerShell:
   ```powershell
   Test-NetConnection PUNTO-DE-ENLACE-MYSQL -Port 3306
   ```
   Debe mostrar `TcpTestSucceeded : True`.
4. **Conectar en DataGrip como `admin`.** Panel **Database Explorer → + → Data Source → MySQL**:
   - **Host:** el punto de enlace
   - **Port:** `3306`
   - **User:** `admin`
   - **Password:** la contraseña maestra

   Si aparece *Download missing driver files*, haz clic. Luego **Test Connection** (debe decir
   *Succeeded*) **→ OK**. Si sale *Public Key Retrieval is not allowed*, en la pestaña
   **Advanced** pon `allowPublicKeyRetrieval=true`.
5. **(Solo réplica desde cero)** Clic derecho en la conexión **→ New → Query Console**. Copia
   **todo** `aws/sql/00_mysql_schema.sql` desde VS Code (`Ctrl+A`, `Ctrl+C`), pégalo en la
   consola y ejecútalo completo: `Ctrl+A` y luego `Ctrl+Enter`.
6. **Contraseña para `mkt_app`.** En la terminal de VS Code (PowerShell, con `(.venv)` activo):
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(24))"
   ```
   Pégala en tu Bloc de notas como `MKT_APP MySQL: …`.
7. **Ejecutar el script 01.** Abre una **Query Console nueva** de la conexión MySQL:
   - En VS Code abre **`aws/sql/01_mysql_marketplace.sql`**. Revisa bien el nombre: empieza con
     **01** y dice *mysql*. Copia todo y pégalo en la consola.
   - **Solo en DataGrip** (nunca en el archivo) reemplaza `CAMBIA_ESTA_CLAVE` por la contraseña
     del paso 6, dejando las comillas `' '`.
   - Ejecuta todo: `Ctrl+A` y luego `Ctrl+Enter`.

   Si cambias las contraseñas en los archivos del proyecto, rompes la verificación de integridad y
   podrías compartirlas por error.
8. **Ejecutar el script 03 (direcciones).** Otra **Query Console nueva** de la conexión MySQL →
   copia todo **`aws/sql/03_mysql_addresses.sql`** (no tiene contraseñas que cambiar) → `Ctrl+A`
   y `Ctrl+Enter`.
9. **Ejecutar el script 04 (tienda del vendedor).** Otra **Query Console nueva** → copia todo
   **`aws/sql/04_mysql_sellers.sql`** (se ejecuta después del 03; no tiene contraseñas) → `Ctrl+A` y
   `Ctrl+Enter`. Es seguro repetirlo (`CREATE TABLE IF NOT EXISTS`).

✅ **Punto de control (pestañas de resultado):**
- Script 04: `SHOW COLUMNS FROM sellers` lista 6 columnas y `SHOW GRANTS FOR 'mkt_app'@'%'` muestra
  además `SELECT, INSERT, UPDATE ON marketplace.sellers` (5 filas en total).
- `SHOW GRANTS` (del script 03) muestra 4 filas: `USAGE ON *.*`, `SELECT, INSERT ON
  marketplace.admin_actions`, `SELECT, INSERT, UPDATE ON marketplace.addresses` y
  `SELECT, INSERT, UPDATE ON marketplace.users`.
- `SHOW COLUMNS` muestra `session_nonce | varchar(64) | NO` (script 01) y `default_owner`
  con `STORED GENERATED` (script 03).
- `SHOW INDEX` muestra `uq_one_default`.

### Fase 4 — RDS PostgreSQL (`rds-mkt-security-db`)

> **¿Ya la tienes de la Parte 5?** Enciéndela, pon **Mi IP** (paso 2) y salta al paso 4. **No
> ejecutes** `00_postgres_schema.sql`.

1. **Crear la instancia.** **Crear base de datos → PostgreSQL** (versión más reciente):
   - Identificador: `rds-mkt-security-db`
   - Usuario maestro: `postgres`
   - En **Configuración adicional**, **Nombre de base de datos inicial: `security`**
   - Grupo de seguridad nuevo: `mkt-sg-postgres`
   - El resto igual que MySQL.
2. Regla de entrada **PostgreSQL → Mi IP** y prueba la red:
   ```powershell
   Test-NetConnection PUNTO-DE-ENLACE-POSTGRES -Port 5432
   ```
3. **Conectar en DataGrip como `postgres`.** **+ → Data Source → PostgreSQL**:
   - Host: el punto de enlace
   - Port: `5432`
   - User: `postgres`
   - **Database: `security`** (no `postgres`)

   Si la base `security` no existe, conéctate a `postgres`, ejecuta solo
   `CREATE DATABASE security;` y cambia **Database** a `security`.
4. **(Solo réplica desde cero)** Ejecuta `aws/sql/00_postgres_schema.sql` en una Query Console.
5. Genera **otra** contraseña con el mismo comando de la Fase 3.6 y anótala como
   `MKT_APP PostgreSQL: …`.
6. **Ejecutar el script 02.**
   - Abre una **Query Console** de la conexión PostgreSQL. Arriba a la derecha, el selector
     debe decir **`security.public`**; si no, cámbialo.
   - En VS Code abre **`aws/sql/02_postgres_security.sql`** (empieza con **02** y dice
     *postgres*). Cópialo y pégalo en la consola.
   - Reemplaza ahí `CAMBIA_ESTA_CLAVE` por la contraseña de PostgreSQL.
   - Ejecuta con `Ctrl+A` y `Ctrl+Enter`.

   Si sale `syntax error at or near "USE"`, pegaste por error el script de MySQL. No se cambió
   nada; vacía la consola y pega el 02.

✅ **Punto de control:** la consulta final muestra **6 filas** para `mkt_app`:
- `auth_events`: INSERT, SELECT
- `login_attempts`: DELETE, INSERT, SELECT, UPDATE

### Fase 5 — Token secreto del API

Este comando genera el token, **lo escribe directamente en tu `.env`** (como `PRODUCTS_API_TOKEN`)
y lo muestra **una sola vez** para que lo pegues en la Lambda. Ejecútalo **una vez**; si lo
repites, genera otro token y el válido es siempre el último.

```powershell
python -c "import secrets,re; p='.env'; t=secrets.token_urlsafe(48); s=open(p,encoding='utf-8').read(); s=re.sub(r'(?m)^PRODUCTS_API_TOKEN=.*', 'PRODUCTS_API_TOKEN='+t, s); open(p,'w',encoding='utf-8').write(s); print(t)"
```

Copia el token que aparece y pégalo en tu Bloc de notas como `TOKEN API: …`. No lo pongas en
capturas, código ni repositorios. Para verificar sin mostrarlo:

```powershell
python -c "import re; s=open('.env',encoding='utf-8').read(); m=re.search(r'(?m)^PRODUCTS_API_TOKEN=(.*)$', s); print('Token en .env:', len(m.group(1).strip()), 'caracteres')"
```

✅ **Punto de control:** `Token en .env: 64 caracteres`.

### Fase 6 — Las 19 funciones Lambda

Usa la tabla de la sección 4.3. **El nombre de cada función es igual al nombre de su archivo**
(sin `.py`). Hazlas en el orden de la tabla y marca cada una en tu Bloc de notas al terminarla.
Para **cada** función:

1. **Crear.** Consola de AWS → busca `Lambda` → **Funciones → Crear función → Crear desde cero**:
   - **Nombre de la función:** el de la tabla, por ejemplo `lambdaListProducts`.
   - **Tiempo de ejecución:** Python 3.14 (o 3.13 si no aparece).
   - **Permisos:** despliega **Cambiar el rol de ejecución predeterminado → Usar un rol
     existente → LabRole**. No elijas "Crear un rol nuevo": el laboratorio no lo permite.
   - Pulsa **Crear función**.
2. **Pegar el código.**
   - En VS Code: panel **Explorer → aws → lambdas** → abre el archivo `.py` con el **ícono de
     Python**. **No abras la carpeta `__pycache__`**: sus archivos `.pyc` son binarios y no
     sirven. **No uses `aws/lambdas_src/`**: esos archivos no están completos por sí solos.
   - `Ctrl+A`, `Ctrl+C`.
   - En la consola, pestaña **Código** → abre `lambda_function.py` → `Ctrl+A`, `Supr`, `Ctrl+V`
     → **Deploy**. Espera el mensaje verde.
   - La primera línea pegada debe ser `"""Lambda <nombre de la función>: …`.
3. **Variable de entorno** (solo las funciones 1 a 6). Pestaña **Configuración → Variables de
   entorno → Editar → Agregar variable de entorno → Guardar**:

   | Función | Clave | Valor |
   |---|---|---|
   | `lambdaAuthorizer` | `API_TOKEN` | tu token de la Fase 5 |
   | `lambdaListProducts`, `lambdaGetProduct`, `lambdaCreateProduct`, `lambdaUpdateProduct`, `lambdaDeleteProduct` | `TABLE_NAME` | `Products` |

   La **Clave** es literalmente `TABLE_NAME` (o `API_TOKEN`), no el nombre de la función. Las
   funciones 7 a 19 **no llevan variables**.
4. **Tiempo de espera.** **Configuración → Configuración general → Editar → Tiempo de espera**:
   `0 min 5 s` para `lambdaAuthorizer`, `0 min 15 s` para `lambdaCreateOrder` y `0 min 10 s` para
   las demás **→ Guardar**.

**Pruebas** (pestaña **Probar → Crear nuevo evento**, escribe el nombre, pega el JSON y pulsa
**Guardar → Probar**):

| Función | Nombre del evento | JSON | Resultado esperado |
|---|---|---|---|
| `lambdaAuthorizer` | `testFakeToken` | `{ "headers": { "x-mkt-token": "hola" } }` | `{"isAuthorized": false}` |
| `lambdaGetProduct` | `testGetProduct` | `{ "pathParameters": { "product_id": "PROD-00001" } }` | `"statusCode": 200` con el producto |
| `lambdaGetCart` | `testCartNoActor` | `{ "headers": {} }` | `"statusCode": 403` y `Actor no válido` |

En `testGetProduct` usa un `product_id` que exista en tu tabla (**DynamoDB → Explorar elementos →
`Products`**). **Nunca** crees un evento de prueba con el token real: los eventos se guardan en
la consola.

✅ **Punto de control:**
- **Lambda → Funciones** muestra las 19 funciones `lambda…` (busca `lambda` en el filtro).
- `testFakeToken` devuelve `false`, `testGetProduct` devuelve `200` y `testCartNoActor` `403`.

### Fase 7 — API Gateway `apiGatewayMarketplace`

Método del profesor: **primero todas las rutas, una por una; después la integración de cada
ruta; implementación automática desactivada** y se implementa a mano al final.

1. **Crear el API vacío.** Consola → busca `API Gateway` → **Crear API** → en **API HTTP** pulsa
   **Compilar** (o **Crear**).
   - **Paso 1:** **Nombre de la API: `apiGatewayMarketplace`**. **No** agregues integraciones →
     **Siguiente**.
   - **Paso 2 – Configurar rutas:** no agregues ninguna → **Siguiente**.
   - **Paso 3 – Etapas:** nombre `$default` y **desactiva Implementación automática** →
     **Siguiente**.
   - **Paso 4:** **Crear**. Si aparece *Unable to deploy… no valid routes*, ignóralo: todavía no
     hay rutas.
2. **Crear las 18 rutas, una por una.** Menú izquierdo **Desarrollar → Rutas → Crear**:
   - Elige el **método** y escribe la **ruta** exactamente como en la tabla de la sección 4.4
     (con `{product_id}` y `{order_id}` entre llaves) → **Crear**.
   - Repite hasta tener las 18. Ojo: `GET /orders` y `POST /orders` son dos rutas distintas, igual
     que `GET` y `POST` de `/products/{product_id}/reviews`.
3. **Integración de cada ruta.** **Desarrollar → Integraciones** → pestaña **Asociar
   integraciones a rutas**. Para **cada** ruta:
   - Clic en el método de la ruta → **Crear y asociar una integración**.
   - **Tipo de integración:** Función Lambda. **Región:** us-east-1. **Función Lambda:**
     **elígela de la lista** escribiendo su nombre (por ejemplo `lambdaGetCart`); no pegues el ARN
     a mano. Deja activado **Conceder permiso a API Gateway para invocar la función**.
   - **Crear**. La ruta debe mostrar *AWS Lambda* y el nombre correcto.
   Revisa con la tabla 4.4: cada ruta con **su** función (una Lambda por ruta).
4. **Autorizador.** Menú **Desarrollar → Autorización**.
   - Clic en **GET** bajo `/products` → **Crear y asociar un autorizador** (solo la primera vez):
     - Tipo **Lambda**
     - Nombre **`mktTokenAuthorizer`**
     - Función **`lambdaAuthorizer`**
     - Versión de formato de carga **2.0**
     - Modo de respuesta **Simple**
     - Origen de identidad: borra el ejemplo y escribe `$request.header.x-mkt-token`
     - Caché **desactivada**
     - Deja activado **Crear automáticamente un permiso**

     Pulsa **Crear y asociar**.
   - En las otras **17 rutas**: clic en la ruta → **Seleccionar autorizador existente →
     `mktTokenAuthorizer` → Asociar autorizador**.

   Las **18** rutas deben mostrar el autorizador. Una ruta sin autorizador queda abierta a cualquiera.
5. **Throttling.** **Proteger → Limitación** → etapa `$default` **→ Editar**: ráfaga `20`,
   velocidad `10` → **Guardar**.
6. **Implementar (a mano).** Botón **Implementar** (arriba a la derecha) → etapa **`$default`** →
   **Implementar**. **Cada vez** que cambies una ruta, integración o autorizador, vuelve a
   implementar; si no, el API sigue con la versión anterior (por ejemplo, responde
   "Hello from Lambda" o 404).
7. **CORS:** no lo toques. El navegador nunca llama a este API; solo lo llama Flask.
8. **URL.** **Implementar → Etapas → `$default` → URL de invocación** (por ejemplo
   `https://abc123xyz.execute-api.us-east-1.amazonaws.com`). Cópiala al Bloc de notas **sin la
   `/` final**.

✅ **Punto de control:**
- **Rutas** muestra las 18 rutas.
- **Integraciones** muestra *AWS Lambda* en las 18, cada una con su función.
- **Autorización** muestra `mktTokenAuthorizer` en las 18.
- **Etapas → `$default`**: *Implementación automática* desactivada y una implementación reciente.

### Fase 8 — Pruebas con Postman

Crea la colección **`Marketplace - Protected API`**. En la pestaña **Variables** de la colección
crea `URL` (la URL de invocación) y `token` (tu token; **no** marques *Sensitive* ni lo guardes en
el *vault*). Usa `{{URL}}` y `{{token}}` en las peticiones.

| # | Petición | Cabeceras / body | Esperado |
|---|---|---|---|
| 1 | `GET {{URL}}/products` | ninguna | **401** `Unauthorized` |
| 2 | `GET {{URL}}/products` | `x-mkt-token: hola` | **403** `Forbidden` |
| 3 | `GET {{URL}}/products` | `x-mkt-token: {{token}}` | **200** con la lista de productos |
| 4 | `DELETE {{URL}}/products/PROD-00001` | `x-mkt-token: {{token}}` (sin actor) | **403** `Actor no válido` |
| 5 | `POST {{URL}}/products` | token, `x-mkt-actor-role: user`, `x-mkt-actor-seller: SEL-001`; body raw JSON `{"name":"Prueba","category":"audio","price":"10","stock":1,"seller_id":"SEL-999"}` | **400** `Campos no permitidos` |
| 6 | `GET {{URL}}/cart` | token, `x-mkt-actor-role: user`, `x-mkt-actor-seller: SEL-000001`, `x-mkt-actor-user: 00000000-0000-4000-8000-000000000000` | **200** `{"lineas": [], "total": "0.00"}` |
| 7 | `GET {{URL}}/cart` | solo el token (sin `x-mkt-actor-user`) | **403** `Actor no válido` |
| 8 | `GET {{URL}}/orders/01ARZ3NDEKTSV4RRFFQ69G5FAV` | las 4 cabeceras de la petición 6 | **404** `Pedido no encontrado` |
| 9 | `PUT {{URL}}/cart/PROD-00001` | las 4 cabeceras de la 6; body `{"quantity": 50}` | **400** `Datos inválidos` |
| 10 | `GET {{URL}}/products/PROD-00001/reviews` | solo el token | **200** `{"resenas": [], "puede_opinar": false}` |

Si muestras capturas de Postman, oculta el valor del token.

✅ **Punto de control:** las 10 respuestas coinciden.

### Fase 9 — Conectar Flask a AWS

1. **Certificado de RDS** (desde la carpeta del proyecto):
   ```powershell
   mkdir certs
   Invoke-WebRequest -Uri https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -OutFile certs\global-bundle.pem
   ```
2. **Completa el `.env`** (`code .env`). Reemplaza en estas líneas los valores en mayúsculas por
   los de tu Bloc de notas:
   ```
   DATABASE_URL=mysql+pymysql://mkt_app:CLAVE_MYSQL@PUNTO-DE-ENLACE-MYSQL:3306/marketplace?charset=utf8mb4&ssl_ca=certs/global-bundle.pem&connect_timeout=10
   SECURITY_DATABASE_URL=postgresql+psycopg://mkt_app:CLAVE_POSTGRES@PUNTO-DE-ENLACE-POSTGRES:5432/security?sslmode=verify-full&sslrootcert=certs/global-bundle.pem&connect_timeout=10
   PRODUCTS_API_URL=https://XXXXXXXXXX.execute-api.us-east-1.amazonaws.com
   ```
   `PRODUCTS_API_TOKEN` ya quedó escrito en la Fase 5. Guarda con `Ctrl+S`. Usa siempre
   `mkt_app`, nunca `admin` ni `postgres`.
3. **Comprueba las conexiones:**
   ```powershell
   flask --app wsgi check-aws
   ```
   Debe mostrar `MySQL (users): OK`, `PostgreSQL (login_attempts): OK` y `API de productos: OK`.
4. **Carga los datos de demostración** (admin y vendedor en MySQL, 8 productos en DynamoDB a
   través del API):
   ```powershell
   flask --app wsgi seed-demo
   ```
   **No uses `init-db`** con RDS: las tablas ya existen.
5. **Arranca la app:**
   ```powershell
   python run.py
   ```
   Abre **http://localhost:5000**. Usa `localhost`, no `127.0.0.1`.

✅ **Punto de control:** inicias sesión con los usuarios de la sección 6 y el catálogo muestra
los productos de demostración.

### Fase 10 — Verificación final

1. Las pruebas y los análisis deben quedar limpios:
   ```powershell
   pytest                          # 347 passed
   bandit -r .                     # "No issues identified."
   pip-audit -r requirements.txt   # "No known vulnerabilities found"
   ```
   Si `pip-audit` reporta una vulnerabilidad nueva (aparecen con el tiempo), **no actualices por
   tu cuenta**: avisa al dueño para que actualice la versión para todos (sección 12).
2. Comprueba que todo pasa por AWS:

   | Acción en la app | Dónde verlo |
   |---|---|
   | Publicar un producto con `vendedor@marketplace.mx` | DynamoDB → `Products` → **Explorar elementos** |
   | Editar el precio | El mismo ítem con `version` incrementada |
   | Registrar un usuario | DataGrip (MySQL): `SELECT email, role, LEFT(password_hash,30) FROM users;` → `$argon2id$…` |
   | Fallar el login 5 veces | DataGrip (PostgreSQL): `SELECT * FROM login_attempts;` y `SELECT event, created_at FROM auth_events ORDER BY id DESC;` |
   | Bloquear un producto como admin | DynamoDB: `status = BLOCKED`; MySQL: fila nueva en `admin_actions` |
   | Agregar una dirección (con una cuenta compradora) | DataGrip (MySQL): `SELECT label, city, is_default, default_owner FROM addresses;` |
   | Agregar al carrito | DynamoDB → `Marketplace`: `PK = USER#<uuid>`, `SK = CART#PROD-…` con `expires_at` |
   | Guardar en favoritos | DynamoDB → `Community`: `SK = FAV#PROD-…` |
   | Confirmar la compra | DynamoDB → `Orders`: `ORDER#…` con `ORDER`, `ITEM#…`, `SHIPMENT` y `STATUS#…`; en `Products`, `stock` bajó y `sales_count` subió; el carrito quedó vacío |
   | Preparar y enviar (vendedor) y "Ya lo recibí" (comprador) | El encabezado `ORDER` cambia de `status` y aparece una fila `STATUS#…` por paso; en `Community`, `PURCHASED#PROD-…` |
   | Publicar una reseña | `Community`: `PRODUCT#…` / `REVIEW#…`; `Products`: `rating_sum`, `rating_count` y `rating_N` |
   | Cualquier llamada | CloudWatch → Grupos de registros → `/aws/lambda/<función>` |
3. **Autoauditoría como atacante:**
   - Cambiar IDs en la URL.
   - Enviar campos extra (`role=admin`, `seller_id`).
   - Usar GET en rutas de borrado.
   - Quitar el token CSRF.
   - Reutilizar la cookie después del logout.
   - Payloads de SQLi, XSS y `{{7*7}}` en la búsqueda.
   - Fuerza bruta en el login (debe dar 429).
   - Llamar al API sin token.
   - Tienda: abrir `/orders/<id>` de otra persona (404), editar `/addresses/<id>/edit` ajeno (404),
     agregar al carrito con cantidad `0`, `11` o `-1`, enviar un campo `price` al carrito (se
     ignora), comprar tu propio producto (se rechaza), opinar sin haber recibido el producto
     (se rechaza), saltarse estados (preparar → entregado) y poner `<script>` en una reseña
     (se muestra escapado).

✅ **Punto de control:** todo en verde y la autoauditoría sin hallazgos.

### Fase 11 — Apagar y retomar

**Al terminar cada sesión** (las RDS son lo único que gasta créditos de forma apreciable):
1. **RDS → Bases de datos** → selecciona cada instancia **→ Acciones → Detener temporalmente**.
   AWS las vuelve a encender sola a los 7 días.
2. En AWS Academy pulsa **End Lab**.

Las Lambdas, el API y DynamoDB bajo demanda no cobran mientras no se usan.

**Al retomar:**
1. Pulsa **Start Lab** y espera el indicador verde.
2. **RDS → Acciones → Iniciar** en las dos instancias; espera a que digan **Disponible**.
3. Si tu red cambió, vuelve a poner **Mi IP** en los dos grupos de seguridad.
4. Activa el entorno (`.venv\Scripts\Activate.ps1`) y ejecuta `flask --app wsgi check-aws`.

### Actualizar desde la entrega 1 (si ya terminaste las Fases 1 a 9 con la versión 1.x)

No repitas lo que ya funciona. Solo haz esto, en orden:

1. **Archivos.** Descomprime el zip nuevo **sobre** tu carpeta del proyecto (conserva `.env`,
   `.venv` y `certs/`) y ejecuta `python tools/verificar_integridad.py` → "Copia idéntica". Si
   dice `Sobran:`, borra esos archivos y vuelve a verificar.
2. **Dependencias y pruebas:** `pip install -r requirements.txt` (no cambian) y `pytest`.
3. **RDS MySQL:** enciende la instancia y ejecuta solo el paso 8 de la Fase 3 (script 03).
4. **Lambdas que ya tenías (2 a 6):** vuelve a pegar el código de `lambdaListProducts`,
   `lambdaGetProduct`, `lambdaCreateProduct`, `lambdaUpdateProduct` y `lambdaDeleteProduct`
   (ahora guardan la descripción y devuelven las estrellas) → **Deploy** en cada una.
   `lambdaAuthorizer` no cambia.
5. **Lambdas nuevas (7 a 19):** créalas con la Fase 6 (sin variables de entorno; 15 s para
   `lambdaCreateOrder`).
6. **API Gateway:** en `apiGatewayMarketplace` agrega **las rutas 6 a 18** de la sección 4.4 una
   por una (Fase 7, paso 2), su integración (paso 3) y el autorizador `mktTokenAuthorizer`
   (paso 4, "Seleccionar autorizador existente"); después **Implementar** (paso 6).
7. **Postman:** peticiones 6 a 10 de la Fase 8.
8. **Flask:** `flask --app wsgi check-aws` debe mostrar `OK` en `GET /cart`, `GET /favorites`,
   `GET /orders`, `GET /sales` y `GET /products/{id}/reviews`. Si una dice `FALLA`, revisa esa
   ruta, su integración y su autorizador, y vuelve a implementar.
9. **Descripciones de los productos de demostración:** `flask --app wsgi seed-descriptions`.
10. Para comprar necesitas **una segunda cuenta** (nadie compra sus propios productos):
    regístrala en la app (sección 6).

---

## 6. Usuarios de prueba

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | `admin@marketplace.mx` | La que definas en `SEED_ADMIN_PASSWORD` (`.env`) |
| Vendedor (dueño de los 8 productos) | `vendedor@marketplace.mx` | La que definas en `SEED_USER_PASSWORD` (`.env`) |
| Comprador (lo creas tú en **Crear cuenta**) | `comprador@marketplace.mx` | La que elijas al registrarte |

Una sola cuenta compra y vende, pero nadie compra sus propios productos: con el comprador agrega
al carrito un producto del vendedor, registra una dirección y confirma la compra. Luego entra
como vendedor (**Mis ventas**) para prepararlo y enviarlo, y de nuevo como comprador para
marcarlo como recibido y opinar. Para probar IDOR, intenta editar un producto del vendedor con
el comprador: debe dar **403**.

---

## 7. Funcionalidad y rutas

| Ruta | Método | Acceso |
|---|---|---|
| `/` | GET | **público**: portada con buscador, departamentos y lo más reciente |
| `/auth/login`, `/auth/register` | GET, POST | público (con rate limit) |
| `/auth/logout` | POST | sesión |
| `/auth/password` | GET, POST | sesión |
| `/dashboard`, `/profile` | GET | sesión (inicio personal con tu tienda; para admin, el panel de administración) |
| `/items/?q=&department=&category=&availability=&sort=` | GET | **público**: catálogo, búsqueda, filtros y orden (todos con lista blanca; 60 por minuto por IP) |
| `/items/<id>` | GET | **público** si está activo (bloqueados: solo dueño o admin) |
| `/items/mine`, `/items/new`, `/items/<id>/edit` | GET, POST | rol `user`, solo productos propios |
| `/items/<id>/delete` | POST | dueño o admin |
| `/items/<id>/block`, `/items/<id>/unblock` | GET/POST, POST | admin |
| `/users/` (listar y buscar), `/users/new`, `/users/<uuid>`, `/users/<uuid>/edit`, `/users/<uuid>/delete` | GET, POST | admin |
| `/cart/` | GET | rol `user`: carrito con precios y existencias actuales |
| `/cart/add/<id>`, `/cart/buy/<id>`, `/cart/update/<id>`, `/cart/remove/<id>` | POST | rol `user` (CSRF; 30 por minuto) |
| `/favorites/` · `/favorites/add/<id>`, `/favorites/remove/<id>` | GET · POST | rol `user` |
| `/addresses/`, `/addresses/new`, `/addresses/<n>/edit` · `/addresses/<n>/default`, `/addresses/<n>/delete` | GET, POST · POST | rol `user`, solo direcciones propias (ajena = 404) |
| `/checkout` | GET, POST | rol `user` (10 por minuto) |
| `/orders/` · `/sales/` | GET | rol `user`: Mis compras · Mis ventas |
| `/orders/<id>` · `/orders/<id>/status` | GET · POST | comprador, vendedor o admin del pedido (ajeno = 404) |
| `/items/<id>/reviews` | POST | rol `user` con el producto recibido (5 por minuto) |
| `/assets/<Vista>/<CSS\|JS>/<archivo>` | GET | público: solo `.css`, `.js`, `.ttf` y `.svg` de las vistas en lista blanca |

Comandos de CLI: `flask --app wsgi check-aws | seed-demo | seed-descriptions | create-admin | init-db`
(`init-db` solo para SQLite local).

---

## 8. Seguridad

Matriz completa en [SECURITY.md](SECURITY.md). Resumen:

- **Contraseñas y sesión:** Argon2id; política de 12+ caracteres con 3 de 4 clases; login con
  mensaje genérico; rate limit (10/min por IP) y bloqueo de 15 min tras 5 fallos; regeneración
  de sesión; cookies `HttpOnly`, `Secure` y `SameSite=Strict`; invalidación en el servidor.
- **Autorización:** control en cada ruta y en cada blueprint; anti-IDOR en Flask y otra vez en
  DynamoDB (`ConditionExpression`); sin mass assignment.
- **Inyecciones:** ORM parametrizado (SQL); parámetros de expresión (DynamoDB); autoescape sin
  `|safe`; sin `render_template_string`; CSRF global; `next` validado contra open redirect.
- **Cabeceras:** CSP sin inline, HSTS, `X-Frame-Options: DENY`, `nosniff`, Referrer-Policy,
  Permissions-Policy, `no-store` y `TRUSTED_HOSTS`.
- **Tienda:** el precio, las existencias y el dueño los decide la Lambda, no el navegador; la
  compra es una transacción todo-o-nada; la dirección y el pedido se buscan siempre con el
  usuario de la sesión (anti-IDOR; lo ajeno responde 404); los estados solo avanzan por las
  transiciones permitidas y con condición sobre el estado leído; una reseña por compra entregada.
- **AWS:** API con autorizador en las 18 rutas y throttling; RDS con TLS, usuario de mínimo
  privilegio y acceso limitado a tu IP; errores sin detalles internos.

---

## 9. Problemas conocidos y soluciones

| Síntoma | Solución |
|---|---|
| `No matching distribution found for psycopg-binary==…` | Estás usando otra versión de Python: crea el `.venv` con `py -3.13` (Fase 1.4). Si persiste con 3.13, avisa al dueño del proyecto |
| `Contraseña de … no cumple la política: No debe contener tu correo` | La contraseña contiene la parte local del correo; usa las de la sección 6 |
| `notepad <clave>` abre "¿crear archivo nuevo?" | Se escribió la clave en lugar del nombre; usa el comando automático de la Fase 1.5 |
| `Select-String SECRET_KEY .env` sigue mostrando "cambia-esto" | El cambio no se guardó; usa el comando automático |
| Activación del venv bloqueada | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Errores raros de acceso a archivos | El proyecto está en OneDrive; muévelo a `C:\proyectos` |
| Inicias sesión y vuelves al login | Usa `localhost`; o `SESSION_COOKIE_SECURE=false` solo en local |
| Error 400 al enviar un formulario | El token CSRF expiró o abriste con `127.0.0.1`; recarga en `localhost` |
| Error 503 en el catálogo | URL o token del API mal copiados; prueba con Postman (Fase 8) |
| `check-aws` se queda colgado | RDS detenida o tu IP cambió: inicia la instancia y vuelve a poner **Mi IP** |
| `Subscriber limit exceeded` al crear índices | Solo un índice a la vez por tabla; espera a que esté Activo |
| `verificar_integridad.py` dice "NO es idéntica" | Archivos modificados o incompletos: vuelve a descomprimir el zip original del dueño |
| `py -3.13` no existe | Instala Python 3.13 desde python.org (puede convivir con otras versiones) |
| CloudShell no aparece o no está permitido en el laboratorio | Crea las tablas a mano en la consola (Fase 2, alternativa manual) |
| VS Code dice *"The file is not displayed… binary"* | Abriste un `.pyc` de `__pycache__`; abre el `.py` con ícono de Python (Fase 6.2) |
| `syntax error at or near "USE"` en PostgreSQL | Pegaste el script de MySQL; usa `02_postgres_security.sql` (Fase 4.6) |
| `Operation CREATE USER failed for 'mkt_app'` / `role "mkt_app" already exists` | El usuario ya existía; cambia su contraseña con `ALTER USER 'mkt_app'@'%' IDENTIFIED BY '…';` (MySQL) o `ALTER ROLE mkt_app PASSWORD '…';` (PostgreSQL) |
| `Duplicate column name 'session_nonce'` | El script 01 ya se había ejecutado; esa parte está hecha |
| Una Lambda responde 500 o no encuentra la tabla | En sus variables, la clave debe ser `TABLE_NAME` (valor `Products`), no el nombre de la función |
| `API respondió 500` al editar un producto, bloquearlo o con `seed-descriptions` | Tienes `lambdaUpdateProduct` anterior a la 2.0.1: vuelve a pegar `aws/lambdas/lambdaUpdateProduct.py` y pulsa **Deploy** |
| `check-aws` dice `GET /cart: FALLA` (o otra ruta de la tienda) | Falta la ruta, su integración o su autorizador, o no se implementó: Fase 7, pasos 2 a 6 |
| Postman responde `Hello from Lambda` o 404 en una ruta nueva | Se pegó el código pero falta **Deploy** en la Lambda, o falta **Implementar** en el API |
| `Error 503 · La tienda no está disponible` al abrir el carrito o los pedidos | Igual que el caso anterior; mira el log de la Lambda en CloudWatch |
| `SELECT command denied … table 'addresses'` | Falta el script 03 (Fase 3, paso 8) |
| "No puedes comprar tus propios productos" | Es correcto: compra con otra cuenta (sección 6) |
| No aparece "Publicar opinión" | Solo aparece cuando el pedido está **Entregado** y todavía no opinaste |
| Creaste una Lambda con otro nombre | Las Lambdas no se pueden renombrar: crea la correcta y borra la otra (**Acciones → Eliminar**) |
| Postman con token correcto da **403** | El `API_TOKEN` de `lambdaAuthorizer` es distinto o tiene espacios; vuelve a copiarlo |
| `Access denied for user 'mkt_app'` / `password authentication failed` | Contraseña distinta en `.env`, o el script 01/02 no se ejecutó completo |
| `permission denied for table login_attempts` | El script 02 se ejecutó en la base `postgres`; ejecútalo con `security.public` seleccionado |
| `certificate verify failed` | Falta `certs\global-bundle.pem` o ejecutas Flask desde otra carpeta (Fase 9.1) |
| Más casos | [GUIA_AWS.md, Problemas frecuentes](GUIA_AWS.md#problemas-frecuentes) |

---

## 10. Costos y apagado

- **RDS micro:** unos 0.05 USD por hora las dos encendidas; detenidas solo cobran el disco
  (alrededor de 0.15 USD al día entre las dos).
- **DynamoDB, Lambda y API Gateway:** sin costo apreciable con este uso.
- Al terminar cada sesión: detener las dos RDS (Fase 11).

---

## 11. Estado de verificación

Validado por el dueño del proyecto antes de distribuirlo (Linux, Python 3.13, con las versiones
exactas de `requirements.txt`):

| Componente | Estado | Cómo |
|---|---|---|
| Suite completa (app Flask + Lambdas + cliente del API) | ✅ **347 pruebas pasan** | `pytest` |
| Código de las 19 Lambdas | ✅ incluidas en la suite | `tests/test_lambdas.py` y `tests/test_lambdas_shop.py` contra las 4 tablas simuladas (incluye transacciones) |
| Flujos de compra en Flask | ✅ | `tests/test_shop.py`: carrito, favoritos, direcciones, compra, estados, reseñas y ataques (IDOR, CSRF, precio, XSS, open redirect) |
| Análisis estático | ✅ sin hallazgos | `bandit` |
| Cadenas de conexión a RDS (TLS) | ✅ revisadas | SQLAlchemy traduce `ssl_ca` y `sslmode=verify-full` correctamente |
| Script de DynamoDB | ✅ sintaxis y JSON válidos | falta ejecutarlo en CloudShell |
| `pip-audit` | ⏳ se ejecuta en la Fase 10 | requiere internet hacia PyPI |
| Windows 11 + Python 3.13 | ✅ 210 pruebas en la 1.2.0; la 2.0.0 se valida al instalarla | réplica del dueño |
| RDS: scripts 01 y 02 | ✅ ejecutados en el laboratorio del dueño | `SHOW GRANTS` y permisos de PostgreSQL |
| Entrega 1 en AWS (6 Lambdas, 5 rutas, Postman, Flask) | ✅ en el laboratorio del dueño | Fases 6 a 9 |
| Entrega 2 en AWS (13 Lambdas y 13 rutas nuevas, script 03) | ⏳ pendiente en el laboratorio del dueño | "Actualizar desde la entrega 1" |

Si algo falla en una fase, **no improvises un cambio de diseño**: anota el error exacto y
corrígelo de forma que el proyecto siga siendo igual para todos (ver `AGENTS.md`).

---

## 12. Actualizaciones del proyecto (solo el dueño)

Cuando el dueño corrige algo (por un error reportado por una réplica, o una vulnerabilidad de `pip-audit`):

1. Hace el cambio y vuelve a correr `pytest`, `bandit -r .` y `pip-audit -r requirements.txt`.
2. Sube la versión en `VERSION` (por ejemplo `1.0.0` → `1.0.1`) y anota el cambio en la tabla de abajo.
3. Regenera la huella: `python tools/verificar_integridad.py --generar`.
4. Vuelve a comprimir y comparte el zip. Cada réplica reemplaza sus archivos (conservando su
   `.env`, `.venv` y `certs/`) y vuelve a verificar la integridad.

**Si la verificación dice `Sobran:`** con archivos de una versión anterior (por ejemplo, la
carpeta `app/` de la 1.2.0, reemplazada en la 1.3.0 por `Core/`, `Services/`, `Interfaces/`,
`Implementation/` y `View/`), bórralos y vuelve a verificar.

**Si ya habías creado Lambdas con los nombres de la versión 1.1.0** (`autorizadorMarketplace`,
`listarProductos`, `obtenerProducto`, `crearProducto`, `modificarProducto`, `eliminarProducto`):
crea las 6 nuevas con los nombres de la sección 4.3 (Fase 6) y después elimina las anteriores
(**Lambda → Funciones →** selecciónala **→ Acciones → Eliminar**). El código es el mismo; solo
cambia el nombre.

| Versión | Cambio |
|---|---|
| 1.0.0 | Versión inicial: Flask + RDS MySQL/PostgreSQL + API Gateway/Lambda/DynamoDB |
| 1.1.0 | Rediseño estilo marketplace: portada con buscador, catálogo con filtros (departamento, categoría, disponibilidad) y orden, ficha con productos relacionados, nombre público del vendedor, fuente autoalojada e íconos propios. 210 pruebas. |
| 1.2.0 | Nombres de AWS en inglés: Lambdas con prefijo `lambda` (`lambdaAuthorizer`, `lambdaListProducts`, `lambdaGetProduct`, `lambdaCreateProduct`, `lambdaUpdateProduct`, `lambdaDeleteProduct`; archivos renombrados igual) y API `apiGatewayMarketplace`. README con pasos clic por clic (DataGrip, Lambdas, API Gateway, apagar y retomar) y problemas encontrados en la réplica. El código de las funciones no cambia. 210 pruebas. |
| 2.1.0 | Cambios de esta entrega: pago simulado registrado en el pedido (entidad Pagos); catálogo paginado y carga masiva de 17,000 productos (`tools/load_products.py`); tienda del vendedor (tabla `sellers`, script 04); checkout con flujos GET y POST separados y confirmación de pago; textos y pantallas según las observaciones; integración continua, `/docs` y `/database`. Hay que volver a pegar las Lambdas de pedidos y `lambdaListProducts`, y ejecutar `04_mysql_sellers.sql`. |
| 2.0.1 | Corrige `lambdaUpdateProduct`: enviaba a DynamoDB nombres de atributo sin usar (`#st` al editar; `#n` y `#cond` al moderar) y el DynamoDB real respondía `ValidationException` (500 al editar, bloquear o `seed-descriptions`). Ahora solo envía los que usa. El simulador de las pruebas rechaza lo mismo que AWS. Solo hay que volver a pegar `lambdaUpdateProduct`. 346 pruebas. |
| 2.0.0 | **Entrega 2: tienda completa.** Una cuenta compra y vende. Productos con descripción. Carrito (`Marketplace`, TTL 30 días), favoritos (`Community`), direcciones de envío (RDS `addresses`, script 03), compra en una transacción con un pedido por vendedor, fecha y entrega estimada de 3 a 7 días, estados Confirmado → En preparación → Enviado → Entregado / Cancelado (devuelve existencias), Mis compras y Mis ventas (`Orders`, `GSI1`), reseñas de 1 a 5 estrellas solo de compras entregadas con promedio e histograma. 13 Lambdas y 13 rutas nuevas (una Lambda por ruta) y las 5 de productos actualizadas. API Gateway con implementación manual (regla del profesor). Rediseño visual estilo "Stuffus Shop". Pago fuera del alcance. 346 pruebas. |
| 1.3.0 | Estructura de carpetas del profesor: `Services/` (rutas), `Interfaces/` (contratos y DTO), `Implementation/` (lógica y datos) y `View/` por módulo (PY, HTML, CSS, JS, Utils), más `Core/`, `Models/` y `Security/`. Catálogo público (portada, catálogo, búsqueda y ficha sin cuenta) con caché de 10 s; reglas del profesor para el agente en el README. Sin cambios en AWS. 238 pruebas. |
