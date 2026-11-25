# Guía: conectar el marketplace a tu laboratorio de AWS

> **El plan maestro es el [GUIA_REPLICA.md](GUIA_REPLICA.md)** (Fases 0 a 11, con todos los pasos clic por clic).
> Esta guía es un resumen para quien ya tiene los recursos de la Parte 5. Si algo aquí y en el
> GUIA_REPLICA.md no coincide, manda el GUIA_REPLICA.md.
>
> **Nombres en inglés:** las Lambdas empiezan con `lambda` y el API se llama `apiGatewayMarketplace`.

Esta guía parte de lo que ya tienes de la **Parte 5**:

- **DynamoDB:** `Products` (con `byCategoryPrice` y `bySeller`), `Orders`, `Marketplace` y `Community`.
- **RDS MySQL** `rds-mkt-identity-db`, base `marketplace`, con `users`, `addresses`, `reports` y `admin_actions`.
- **RDS PostgreSQL** `rds-mkt-security-db`, base `security`, con `login_attempts` y `auth_events`.

Al final tendrás la misma arquitectura de la Parte 4, pero protegida:

```
Navegador ──► Flask en tu computadora (login, roles, CSRF, validación)
                ├──► RDS MySQL      users, admin_actions
                ├──► RDS PostgreSQL login_attempts, auth_events
                └──► API Gateway apiGatewayMarketplace
                       │  autorizador: sin el token secreto de Flask → 401/403
                       ▼
                    19 Lambdas ──► DynamoDB Products
```

Todo el código que vas a pegar en AWS está en la carpeta `aws/` del proyecto. Ábrela en **Visual Studio Code** (`Archivo → Abrir carpeta…` → la carpeta `marketplace`).

| Archivo en VS Code | Para qué |
|---|---|
| `aws/lambdas/lambdaAuthorizer.py` | Lambda que valida el token secreto |
| `aws/lambdas/lambdaListProducts.py` | `GET /products` |
| `aws/lambdas/lambdaGetProduct.py` | `GET /products/{product_id}` |
| `aws/lambdas/lambdaCreateProduct.py` | `POST /products` |
| `aws/lambdas/lambdaUpdateProduct.py` | `PUT /products/{product_id}` |
| `aws/lambdas/lambdaDeleteProduct.py` | `DELETE /products/{product_id}` |
| `aws/sql/01_mysql_marketplace.sql` | Ajustes en MySQL y usuario de la app |
| `aws/sql/02_postgres_security.sql` | Usuario de la app en PostgreSQL |

---

## Fase 0. Preparar el laboratorio

1. En AWS Academy pulsa **Start Lab** y espera a que el indicador se ponga en verde. Abre la consola y verifica la región **Norte de Virginia (us-east-1)**.
2. **Enciende las dos RDS** (en la Parte 5 quedaron detenidas): **RDS → Bases de datos**, selecciona `rds-mkt-identity-db` → **Acciones → Iniciar**. Repite con `rds-mkt-security-db`. Espera a que ambas digan **Disponible** (5–10 min).
3. **Actualiza tu IP en los grupos de seguridad**, porque puede haber cambiado desde la Parte 5. En cada instancia: **Conectividad y seguridad** → clic en el grupo (`VPC-mkt-sg-mysql` o `VPC-mkt-sg-postgres`) → **Editar reglas de entrada** → en la regla existente vuelve a elegir **Mi IP** → **Guardar reglas**.
4. Comprueba el camino de red desde PowerShell, con los puntos de conexión reales de cada instancia:
   ```powershell
   Test-NetConnection PUNTO-DE-CONEXION-MYSQL -Port 3306
   Test-NetConnection PUNTO-DE-CONEXION-POSTGRES -Port 5432
   ```
   Ambos deben decir `TcpTestSucceeded : True`.

## Fase 1. Ajustes en las bases RDS (DataGrip o MySQL Workbench)

1. **MySQL.** Conéctate a `rds-mkt-identity-db` como `admin`, igual que en la sección B.3 del documento. Abre `aws/sql/01_mysql_marketplace.sql` en VS Code y genera una contraseña para el usuario de la app:
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(24))"
   ```
   Reemplaza `CAMBIA_ESTA_CLAVE` por esa contraseña y **anótala** (será `CLAVE_MYSQL`). Copia el script completo al cliente SQL y ejecútalo todo. Al final debe mostrar los permisos de `mkt_app` y la columna `session_nonce`.
2. **PostgreSQL.** Conéctate a `rds-mkt-security-db` con la base **`security`** seleccionada (no `postgres`). Genera otra contraseña, ponla en `aws/sql/02_postgres_security.sql` en lugar de `CAMBIA_ESTA_CLAVE`, **anótala** (será `CLAVE_POSTGRES`) y ejecuta el script. Debe listar los permisos de `mkt_app` sobre las dos tablas.

> **Por qué un usuario `mkt_app`:** si alguien lograra una inyección SQL o robara la cadena de conexión, este usuario solo puede leer, insertar y actualizar en sus tablas. No puede borrar tablas, crear usuarios, borrar filas ni leer `reports`. Sobre `addresses` solo tiene SELECT, INSERT y UPDATE (script `03_mysql_addresses.sql`, entrega 2).

## Fase 2. Token secreto del API

Genera el token que solo conocerán Flask y el autorizador:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Guárdalo en un lugar seguro y **no lo pongas en el código ni en capturas**. Lo usarás en la Fase 3 (variable `API_TOKEN`) y en la Fase 6 (`PRODUCTS_API_TOKEN`).

## Fase 3. Las 19 funciones Lambda

La lista exacta (nombre, archivo, variable, tiempo de espera y tablas) está en la **sección 4.3
del GUIA_REPLICA.md** y los pasos clic por clic en su **Fase 6**. Resumen:

1. **Lambda → Funciones → Crear función → Crear desde cero**, nombre igual al archivo, Python 3.14
   (o 3.13), rol existente **LabRole**.
2. Pega el archivo completo de `aws/lambdas/` en `lambda_function.py` → **Deploy**.
3. Variable de entorno solo en las funciones 1 a 6 (`API_TOKEN` en el autorizador, `TABLE_NAME =
   Products` en las de productos). Las 13 de la tienda no llevan variables.
4. Tiempo de espera: 5 s el autorizador, 15 s `lambdaCreateOrder`, 10 s las demás.

**Prueba rápida** en `lambdaGetProduct` (evento `testGetProduct`):

```json
{ "pathParameters": { "product_id": "PROD-00001" } }
```

Debe responder `statusCode 200` con el "Wireless Mouse" de ejemplo de la Parte 5 (sección A.6).

## Fase 4. API Gateway `apiGatewayMarketplace`

Las 18 rutas están en la **sección 4.4 del GUIA_REPLICA.md** y los pasos en su **Fase 7**. Reglas del
profesor que siempre se cumplen:

- **Una Lambda por ruta.**
- **Primero se crean todas las rutas, una por una** (**Desarrollar → Rutas → Crear**), y después
  **la integración de cada ruta** (**Desarrollar → Integraciones → Crear y asociar una
  integración**, eligiendo la función de la lista, no pegando el ARN).
- **Implementación automática desactivada** en la etapa `$default`: después de cualquier cambio
  se pulsa **Implementar → `$default`**.
- **Autorizador `mktTokenAuthorizer` en las 18 rutas** (Lambda `lambdaAuthorizer`, payload 2.0,
  respuesta Simple, identidad `$request.header.x-mkt-token`, sin caché).
- **Throttling** ráfaga 20 / velocidad 10. **Sin CORS.**
- La URL de invocación va en `.env` **sin la `/` final**.

## Fase 5. Probar el API con Postman

Crea la colección `Marketplace - Protected API`:

| Prueba | Petición | Esperado |
|---|---|---|
| Sin token | `GET {URL}/products` sin cabeceras | **401** `Unauthorized` |
| Token falso | `GET {URL}/products` con cabecera `x-mkt-token: hola` | **403** `Forbidden` |
| Token correcto | `GET {URL}/products` con tu token | **200** con `PROD-00001` |
| Borrar sin actor | `DELETE {URL}/products/PROD-00001` con tu token | **403** `Actor no válido` |
| Cambiar dueño | `POST {URL}/products` con token, `x-mkt-actor-role: user`, `x-mkt-actor-seller: SEL-001` y body `{"name":"Prueba","category":"audio","price":"10","stock":1,"seller_id":"SEL-999"}` | **400** `Campos no permitidos` |

Si las cinco dan lo esperado, el API está protegido y valida igual que la app. Las peticiones 6
a 10 de la tienda (carrito, pedido ajeno, cantidad inválida y reseñas) están en la **Fase 8 del
GUIA_REPLICA.md**.

## Fase 6. Configurar y arrancar Flask

1. **Descomprime el proyecto nuevo** en una carpeta fuera de OneDrive, por ejemplo `C:\proyectos\marketplace`. **Copia tu `.env` anterior** a esa carpeta y ábrela en VS Code.
2. En la terminal de VS Code (**Terminal → Nueva terminal**, que es PowerShell):
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   ```
3. **Certificado de RDS** (para conexiones cifradas, como en la Figura 100 del documento):
   ```powershell
   mkdir certs
   Invoke-WebRequest -Uri https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -OutFile certs\global-bundle.pem
   ```
4. **Completa el `.env`** (`code .env` o `notepad .env`). Copia de `.env.example` las líneas nuevas y llénalas:
   ```
   DATABASE_URL=mysql+pymysql://mkt_app:CLAVE_MYSQL@rds-mkt-identity-db.xxxx.us-east-1.rds.amazonaws.com:3306/marketplace?charset=utf8mb4&ssl_ca=certs/global-bundle.pem&connect_timeout=10
   SECURITY_DATABASE_URL=postgresql+psycopg://mkt_app:CLAVE_POSTGRES@rds-mkt-security-db.xxxx.us-east-1.rds.amazonaws.com:5432/security?sslmode=verify-full&sslrootcert=certs/global-bundle.pem&connect_timeout=10
   PRODUCTS_API_URL=https://abc123xyz.execute-api.us-east-1.amazonaws.com
   PRODUCTS_API_TOKEN=el-token-de-la-fase-2
   SEED_ADMIN_PASSWORD=define-una-contraseña-fuerte
   SEED_USER_PASSWORD=define-una-contraseña-fuerte
   ```
5. **Comprueba las tres conexiones:**
   ```powershell
   flask --app wsgi check-aws
   ```
   Debe responder:
   ```
   MySQL (users): OK
   PostgreSQL (login_attempts): OK
   API de productos: OK (1 productos en DynamoDB)
   ```
6. **Carga los datos de demostración.** Crea el admin y el vendedor en MySQL y publica los 8 productos en DynamoDB a través del API:
   ```powershell
   flask --app wsgi seed-demo
   ```
   **No ejecutes `init-db`:** las tablas ya existen en RDS desde la Parte 5.
7. **Arranca:** `python run.py` y abre **http://localhost:5000**.

## Fase 7. Comprobar que todo pasa por AWS

| Acción en la app | Dónde verlo en AWS |
|---|---|
| Entrar con `vendedor@marketplace.mx` y publicar un producto | DynamoDB → `Products` → **Explorar elementos**: aparece con `seller_id` del vendedor |
| Editar el precio | El mismo ítem con `version` incrementada |
| Registrar un usuario nuevo | DataGrip, MySQL: `SELECT email, role, LEFT(password_hash,30) FROM users;` (hash `$argon2id$…`) |
| Fallar el login 5 veces | DataGrip, PostgreSQL: `SELECT * FROM login_attempts;` y `SELECT event, created_at FROM auth_events ORDER BY id DESC;` |
| Como admin, bloquear un producto | DynamoDB: `status = BLOCKED` y sin `listed_category`; MySQL: fila nueva en `admin_actions` |
| Cualquier llamada | CloudWatch → Grupos de registros → `/aws/lambda/<función>` |

Luego corre las pruebas (no tocan AWS; usan simulaciones):

```powershell
pytest
bandit -r .
pip-audit -r requirements.txt
```

## Fase 8. Al terminar la sesión

Igual que en la sección 7 del documento: **RDS → Acciones → Detener temporalmente** en las dos instancias. Las Lambdas, el API y DynamoDB bajo demanda no cobran mientras no se usan. Opcionalmente, quita tu IP de los grupos de seguridad.

---

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `check-aws` se queda colgado o dice *timed out* en MySQL o PostgreSQL | RDS detenida o tu IP cambió | Fase 0, pasos 2 y 3 |
| `Access denied for user 'mkt_app'` | Contraseña distinta o el script 01 no se ejecutó completo | Revisa `DATABASE_URL`; vuelve a ejecutar el `CREATE USER` |
| `password authentication failed for user "mkt_app"` | Lo mismo en PostgreSQL | Revisa `SECURITY_DATABASE_URL` y el script 02 |
| `permission denied for table login_attempts` | El script 02 se ejecutó en la base `postgres` | Conéctate a `security` y ejecútalo de nuevo |
| `Unknown column 'session_nonce'` | No se ejecutó el `ALTER TABLE users` | Script 01, paso 1 |
| `Data truncated for column 'action'` | No se ejecutó el `ALTER TABLE admin_actions` | Script 01, paso 2 |
| La app muestra **Error 503 · El catálogo no está disponible** | URL o token mal copiados, o falta una integración | Prueba con Postman (Fase 5); en `.env`, la URL va sin `/` final |
| Postman con token correcto da **403** | `API_TOKEN` del autorizador distinto o con espacios | Vuelve a copiarlo en la Lambda y en el `.env` |
| Postman con token correcto da **500** | Error en una Lambda | CloudWatch → registros de esa función; revisa `TABLE_NAME = Products` |
| `ssl` o `certificate verify failed` | Falta `certs\global-bundle.pem` o corres Flask desde otra carpeta | Fase 6, paso 3; ejecuta desde la carpeta del proyecto |
| La contraseña de la BD tiene `@`, `:` o `/` y falla la URL | Caracteres especiales en la URL | Usa contraseñas generadas con `token_urlsafe` |
