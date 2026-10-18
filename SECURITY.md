# SECURITY.md — Controles de seguridad

Referencias: OWASP Top 10 (2021) y OWASP ASVS 4.0 nivel 2.

## 1. Vulnerabilidades cubiertas

| Riesgo | Mitigación | Archivo(s) | Prueba |
|---|---|---|---|
| **SQL Injection** (login, búsqueda, IDs) | Solo ORM SQLAlchemy con parámetros; ningún `text()` ni concatenación. IDs validados con regex antes de consultar | `Services/ProductService`, `Services/UserService`, `Implementation/AuthServiceImplementation` | `test_search_sql_injection`, `test_login_sqli_payload…`, `test_admin_user_search…` |
| **Comodines LIKE** (`%`, `_`, `\`) | Usuarios: `escape_like()` + `ESCAPE '\'`. Productos: búsqueda literal por subcadena (sin LIKE ni expresiones). Longitud máx. 64 | `Security/SecurityUtils.py`, `Implementation/UserServiceImplementation`, `Implementation/ProductServiceImplementation` | `test_search_like_wildcards_are_literal` |
| **XSS almacenado / reflejado** | Autoescape de Jinja2; prohibido `|safe`, `Markup()`; CSP sin `unsafe-inline` | `View/*/HTML/`, `Core/AppFactory.py` (CSP) | `test_stored_xss_is_escaped`, `test_reflected_xss…` |
| **XSS DOM** | Un solo JS externo sin `innerHTML`/`eval`; sin handlers inline | `View/SharedViews/JS/App.js` | `test_no_inline_scripts_in_pages` |
| **SSTI** | No se usa `render_template_string`; las plantillas son archivos fijos | `View/*/HTML/` | `test_ssti_payload_is_not_evaluated` |
| **CSRF** | `CSRFProtect` global; `SameSite=Strict`; verificación de Referer en HTTPS; logout y borrados solo por POST | `Core/Extensions.py`, `Core/Config.py` | `test_login_without_csrf…`, `test_post_with_forged…`, `test_cross_site_referer…` |
| **Fuerza bruta** | Flask-Limiter: login 10/min y 50/h por IP; bloqueo de cuenta 15 min tras 5 fallos (HMAC del correo, exista o no) | `Services/AuthService`, `Implementation/AuthServiceImplementation` | `test_bruteforce_is_rate_limited_with_429`, `test_lockout…` |
| **Enumeración de usuarios** | Mensaje único "Credenciales inválidas"; hash ficticio si el usuario no existe; registro duplicado con el mismo mensaje | `Implementation/AuthServiceImplementation`, `Services/AuthService` | `test_login_wrong_password_and_unknown…`, `test_register_duplicate…` |
| **Almacenamiento de contraseñas** | Argon2id (argon2-cffi), rehash automático si cambian los parámetros | `Security/SecurityUtils.py` | `test_register_creates…` (`$argon2id$`) |
| **Contraseñas débiles** | 12–128 caracteres, 3 de 4 clases, lista de comunes, no contener el correo | `Security/SecurityUtils.py`, `View/SharedViews/PY/SharedForms.py` | `test_register_rejects_weak_password`, `test_admin_resets_password…` |
| **Fijación / secuestro de sesión** | `session.clear()` antes de `login_user`; `session_protection="strong"`; cookie `HttpOnly`, `Secure`, `SameSite=Strict`, prefijo `__Host-` en producción | `Services/AuthService`, `Core/Config.py` | `test_session_is_regenerated_on_login`, `test_session_cookie_flags` |
| **Reutilización de cookie tras logout** | `users.session_nonce` dentro del ID de sesión; se rota en logout, cambio de contraseña, de rol, de estado o de correo | `Models/IdentityModels.py`, `Implementation/AuthServiceImplementation`, `Implementation/UserServiceImplementation` | `test_logout_invalidates_old_cookie…`, `test_change_password_logs_out…`, `test_admin_suspends_user…` |
| **Expiración de sesión** | 30 min de inactividad (validado por la firma de la cookie) y 8 h absolutas | `Core/Config.py`, `Core/AppFactory.py` | — |
| **Control de acceso roto** | `login_required` en cada blueprint (`before_request`) y en cada vista; `role_required`; 403 en el servidor | `Security/SecurityUtils.py`, `Services/*` | `test_protected_get_without_session…` (14 rutas), `test_protected_post…` (9 rutas) |
| **IDOR** | Se compara `product.seller_id` con el de la sesión antes de editar/eliminar; usuarios solo vía admin | `Implementation/ProductServiceImplementation` (`get_owned_product`) | `test_idor_edit_…`, `test_idor_delete_…` |
| **Escalada de privilegios** | Blueprint `users` solo admin; admin no puede cambiar su propio rol/estado; siempre queda ≥1 admin | `Services/UserService` (`require_admin`), `Implementation/UserServiceImplementation` | `test_regular_user_cannot_escalate_own_role`, `test_admin_cannot_demote_or_suspend_self` |
| **Mass assignment** | Solo se leen campos declarados en WTForms y se asignan uno por uno; `role`, `status`, `seller_id`, `product_id` nunca vienen del cliente | `View/*/PY/*Forms.py` (`to_dto`), DTO de `Interfaces/` | `test_register_ignores_mass_assignment_fields`, `test_cannot_steal_product…` |
| **Validación de entradas** | WTForms con listas blancas (categoría, condición, rol, estado), longitudes, rangos, decimales finitos y ≤2 decimales, rechazo de caracteres de control; atributos HTML (`required`, `maxlength`, `min`, `max`) como apoyo en cliente | `forms.py`, `catalog.py` | `test_create_product_rejects_invalid_input` (20 casos) |
| **Path traversal** | IDs con regex/UUID; los CSS/JS se sirven con listas blancas (vista, carpeta y extensión) y `send_from_directory`; no hay subida de archivos | `View/SharedViews/Utils/Assets.py`, `Implementation/ProductServiceImplementation` | `test_path_traversal_returns_404` |
| **Open redirect** | `next` solo acepta rutas relativas (`/…`), sin `//`, `\`, esquema ni host | `Security/SecurityUtils.py` | `test_open_redirect_is_blocked` |
| **Header / CRLF injection** | Werkzeug rechaza saltos de línea en cabeceras; la entrada nunca se copia a cabeceras; logs escapados | `Security/SecurityUtils.py` (`_clean`) | `test_create_product…` (`\r\n`) |
| **Log injection** | Los valores se escapan con `unicode_escape`; nunca se registran contraseñas ni tokens (solo prefijo del HMAC del correo) | `Security/SecurityUtils.py` | — |
| **Host header injection** | `TRUSTED_HOSTS` (Flask 3.1) obligatorio en producción | `Core/Config.py`, `Core/AppFactory.py` | `test_untrusted_host_header_rejected` |
| **Clickjacking** | `X-Frame-Options: DENY` y `frame-ancestors 'none'` | `Core/AppFactory.py` | `test_security_headers_present` |
| **Cabeceras de seguridad** | Talisman: CSP, HSTS (1 año), `nosniff`, Referrer-Policy, Permissions-Policy; además COOP, CORP y `Cache-Control: no-store` | `Core/AppFactory.py` | `test_security_headers_present` |
| **Exposición de información** | Páginas de error propias (400, 401, 403, 404, 405, 413, 429, 500) sin trazas; `debug` siempre apagado; cabecera `Server` oculta (Gunicorn/Nginx) | `Core/AppFactory.py`, `run.py`, `gunicorn.conf.py` | `test_500_page_hides_internals`, `test_debug_is_off` |
| **DoS básico** | `MAX_CONTENT_LENGTH` 256 KB, `MAX_FORM_MEMORY_SIZE` 64 KB, rate limit global 300/min, límites HTTP en Gunicorn y Nginx | `Core/Config.py`, `gunicorn.conf.py`, `deploy/nginx.conf` | `test_request_too_large_returns_413` |
| **Catálogo público (sin sesión)** | Lo público solo lee; toda escritura exige sesión y rol. Productos bloqueados ocultos al público; del vendedor solo "Nombre A."; rate limit de búsqueda 60/min por IP; caché de 10 s del listado (menos llamadas a Lambda/DynamoDB ante muchas visitas) que se vacía al escribir; usuario anónimo con atributos seguros (`AnonymousUser`) | `Services/ProductService`, `Services/MainService`, `Models/IdentityModels.py` | `tests/test_public.py` |
| **Exposición de código por archivos estáticos** | No hay carpeta static global; una ruta sirve solo `.css`, `.js` y `.ttf` de las carpetas `CSS`/`JS` de vistas en lista blanca, nunca `PY`, `HTML` ni `Utils` | `View/SharedViews/Utils/Assets.py` | `test_view_assets_never_expose_code_or_other_files` |
| **CORS** | No se habilita CORS (no hay `Access-Control-Allow-Origin`) | — | `test_no_cors_headers` |
| **Command injection / deserialización / XXE / SSRF** | No se usa `os.system`, `subprocess`, `eval`, `exec`, `pickle`, ni XML, ni peticiones salientes a URLs del usuario | todo el código | revisión + `bandit` |
| **Condiciones de carrera al editar** | Bloqueo optimista: `version` en DynamoDB + `ConditionExpression #ver = :v` y versión oculta en el formulario | `lambdaUpdateProduct.py`, `Services/ProductService` | `test_edit_with_stale_version_is_rejected` |
| **Secretos** | Solo variables de entorno; `.env` en `.gitignore`; `SECRET_KEY` ≥32 caracteres o la app no arranca | `Core/Config.py`, `Core/AppFactory.py` | `test_secret_key_required` |
| **Tienda: IDOR de direcciones** | Toda consulta de `addresses` filtra por `user_id` de la sesión; la ajena responde 404; en la compra, el `RadioField` solo acepta las direcciones del usuario y el servicio la vuelve a buscar con su `user_id` | `Implementation/AddressServiceImplementation`, `View/OrderViews/PY/OrderForms.py` | `test_address_idor_is_404`, `test_checkout_with_someone_elses_address_fails` |
| **Tienda: manipulación de precio y cantidades** | El formulario solo envía producto (en la URL, con regex) y cantidad 1–10; el precio se lee de `Products` en la Lambda al mostrar y al comprar | `View/CartViews/PY/CartForms.py`, `lambdaGetCart`, `lambdaCreateOrder` | `test_cart_ignores_price_sent_by_browser`, `test_cart_rejects_bad_quantities` |
| **Tienda: pedido ajeno y saltos de estado** | El pedido se pide con el actor de la sesión y la Lambda responde 404 si no es comprador, vendedor o admin; las transiciones permitidas dependen del papel y del estado, y la escritura es condicional al estado leído | `Services/OrderService`, `lambdaGetOrder`, `lambdaUpdateOrderStatus` | `test_order_of_someone_else_is_404`, `test_full_status_flow_and_permissions` |
| **Tienda: reseñas falsas o repetidas** | Solo con `PURCHASED#producto` (se escribe al confirmar la entrega); la reseña lo marca como usado en la misma transacción; el nombre público lo arma el servidor; texto escapado | `Services/ReviewService`, `lambdaCreateReview` | `test_review_requires_delivered_purchase`, `test_review_after_delivery_updates_average`, `test_review_text_is_escaped`, `test_review_author_name_comes_from_session` |
| **Tienda: open redirect en `next`** | `safe_next()` solo acepta rutas relativas del propio sitio (`is_safe_redirect`) | `View/SharedViews/PY/SafeNext.py` | `test_cart_next_is_not_an_open_redirect` |
| **Auditoría** | `auth_events` (login, fallo, bloqueo, logout, cambio de contraseña) y `admin_actions` (toda acción de admin); log `marketplace.security` | `Implementation/SharedImplementation/AuditLog.py` | `test_lockout…`, `test_admin_can_block…` |

## 1b. Capa AWS (API Gateway → Lambda → DynamoDB)

| Riesgo | Mitigación | Archivo(s) | Prueba |
|---|---|---|---|
| **API expuesto** (la URL del API de la Parte 3 aparece en el PDF y sus rutas no tenían autorización) | Autorizador Lambda en las 18 rutas: exige `x-mkt-token` con un secreto de ≥32 caracteres que solo conoce Flask; comparación en tiempo constante; si falta la variable, niega todo | `aws/lambdas/lambdaAuthorizer.py` | `test_authorizer_*`, `test_products_api_requires_token…` |
| **IDOR directo contra el API** | `UpdateItem`/`DeleteItem` con `ConditionExpression seller_id = :sid`: DynamoDB solo modifica si el producto es del vendedor | `lambdaUpdateProduct.py`, `lambdaDeleteProduct.py` | `test_idor_update_by_other_seller_is_403`, `test_idor_delete_by_other_seller_is_403` |
| **Mass assignment en el API** | Lista blanca de campos de entrada (cualquier otro → 400) y de salida (`public()`); `product_id`, `seller_id`, `status` y `version` los pone el servidor | Lambdas | `test_create_rejects_invalid_or_extra_fields`, `test_update_cannot_change_owner_or_status` |
| **Validación en la segunda capa** | Las Lambdas repiten las reglas de Flask (longitudes, categorías, precio finito ≤2 decimales, stock entero, sin caracteres de control) | Lambdas | 20 casos en `test_create_rejects…` |
| **Concurrencia** | `version` + `ConditionExpression #ver = :v` (bloqueo optimista atómico) | `lambdaUpdateProduct.py` | `test_stale_version_is_409` |
| **Inyección NoSQL** | Solo `ExpressionAttributeValues` (parámetros); IDs con regex antes de usarlos | Lambdas | `test_get_unknown_or_malformed_id_is_404`, `test_list_rejects_bad_seller_filter` |
| **Fuga de información** | Errores 500 genéricos con `request_id`; detalle solo en CloudWatch; sin `Access-Control-Allow-Origin: *` | Lambdas | `test_internal_errors_hide_details`, `test_responses_have_no_cors_wildcard` |
| **SSRF / token en el navegador** | URL del API solo desde configuración (`https://` obligatorio), IDs validados antes de armar la ruta, timeout, sin redirecciones; el token nunca se envía al navegador ni aparece en `repr` | `Implementation/ProductServiceImplementation/ProductsApiClient.py` | `test_ids_are_validated_before_building_urls`, `test_api_token_never_reaches_the_browser` |
| **Compras concurrentes (última pieza)** | `TransactWriteItems`: pedidos + descuento condicional de existencias (`stock >= :q`, activo y no propio) + vaciar carrito, todo o nada | `lambdaCreateOrder.py` | `test_transaction_race_is_reported_as_conflict` |
| **Actor de la tienda** | `x-mkt-actor-user` (UUID) solo lo pone Flask desde la sesión; la Lambda exige el formato y nunca acepta un usuario en el cuerpo | `ApiGatewayClient.py`, `common.get_actor` | `test_lambdas_shop.py` |
| **DoS / costos** | Throttling en la etapa `$default` (ráfaga 20, 10 req/s) + rate limit de Flask; cuerpo máx. 8 KB en Lambda | GUIA_AWS.md 4.4 | — |
| **Mínimo privilegio en BD** | La app usa `mkt_app` (sin DDL ni DELETE en `users` ni en `addresses`) en lugar de `admin`/`postgres`; TLS obligatorio (`REQUIRE SSL`, `sslmode=verify-full`) | `aws/sql/` | — |

## 2. Checklist AWS

- [ ] **IAM mínimo privilegio:** rol de instancia (EC2) o de tarea con solo `deploy/iam-policy-app.json`; nunca claves en el código ni el usuario root.
- [ ] **Secretos** (`SECRET_KEY`, `DATABASE_URL`) en Secrets Manager o SSM Parameter Store (SecureString), inyectados como variables de entorno al arrancar.
- [ ] **RDS PostgreSQL** en subred privada, *Public access: No*, cifrado en reposo, `sslmode=require`, Security Group que solo acepte 5432 desde el SG de la app. (En la Parte 5 el acceso público se abrió solo para la práctica con DataGrip; para la app debe cerrarse).
- [ ] **Usuario de BD de la app** distinto del maestro, con permisos solo sobre su base.
- [ ] **HTTPS obligatorio:** certificado de ACM en el ALB o CloudFront; HTTP → 301 a HTTPS.
- [ ] **AWS WAF** en el ALB con `AWSManagedRulesCommonRuleSet`, `AWSManagedRulesSQLiRuleSet`, `AWSManagedRulesKnownBadInputsRuleSet` y una regla *rate-based* (p. ej. 300 peticiones/5 min por IP en `/auth/login`).
- [ ] **EC2 con IMDSv2 obligatorio** (`deploy/ec2-imdsv2.sh`), hop limit 1.
- [ ] **Security Groups:** la app solo acepta tráfico del ALB; SSH cerrado (usar Session Manager).
- [ ] **S3** (si se agregan imágenes): bucket privado, Block Public Access activado, cifrado SSE, `deploy/s3-bucket-policy.json` (solo HTTPS), acceso por URLs prefirmadas de corta duración.
- [ ] **Rate limit compartido:** ElastiCache Redis para `RATELIMIT_STORAGE_URI` con más de un worker o instancia.
- [ ] **CloudTrail** activo en todas las regiones; **CloudWatch Logs** para el log de la app y alarmas sobre `event=login_lockout` y picos de 403/429.
- [ ] **ProxyFix** con `TRUSTED_PROXY_COUNT` igual al número real de proxies.
- [ ] **Copias de seguridad** de RDS y protección contra eliminación en producción.

## 3. Riesgos residuales conocidos

1. **Bloqueo de cuentas como DoS:** un atacante que conozca un correo puede bloquearlo 15 min con 5 intentos. Se acepta a cambio de frenar la fuerza bruta distribuida; el rate limit por IP lo acota.
2. **Rate limit en memoria** en local: con varios workers no se comparte (usar Redis en producción).
3. **Sin verificación de correo ni MFA:** cualquiera puede registrarse con un correo ajeno. Fuera del alcance del laboratorio.
4. **Sesión en cookie firmada:** el contenido de la sesión es legible (no cifrado) aunque no modificable. No se guarda información sensible en ella.
5. **Lista de contraseñas comunes reducida;** en producción conviene comprobar contra *Have I Been Pwned* (k-anonimato).
6. **Logout cierra todas las sesiones del usuario,** porque el nonce es único por usuario.
7. **LabRole es amplio:** AWS Academy no permite crear roles propios, así que las Lambdas usan `LabRole`. En una cuenta real tendrían un rol con solo `dynamodb:GetItem/PutItem/UpdateItem/DeleteItem/Scan/Query` sobre `Products` y su índice.
8. **RDS con acceso público durante la práctica:** limitado a tu IP por Security Group y con TLS, pero en producción la app correría en la misma VPC y RDS sería privada.
9. **Cabeceras de actor confiadas:** las Lambdas confían en `x-mkt-actor-*` porque solo Flask tiene el token. Si el token se filtra, hay que rotarlo (cambiarlo en la Lambda y en `.env`).
10. **Verificación:** la suite completa (238 pruebas) y `bandit` pasan con las versiones exactas de `requirements.txt` en Python 3.13. `pip-audit` debe ejecutarse en cada instalación, porque aparecen vulnerabilidades nuevas con el tiempo; si reporta algo, el dueño actualiza la versión para todas las réplicas.
8. **Sin pagos reales:** el pedido nace "Confirmado" sin cobro (pendiente de definir con el profesor). Un sistema real integraría una pasarela con webhooks firmados antes de descontar existencias.
9. **Contadores de la cabecera en la sesión:** el número de piezas del carrito y los favoritos se copian en la cookie de sesión solo para pintar la interfaz; nunca se usan para autorizar ni para calcular precios.
10. **Reseñas sin moderación todavía:** se publican al instante (escapadas). El esquema ya tiene `status` (`VISIBLE`) para ocultarlas desde administración en una entrega futura.
