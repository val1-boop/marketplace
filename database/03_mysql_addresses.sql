-- Ejecutar en la instancia rds-mkt-identity-db (MySQL 8.4), conectado como admin.
-- Entrega 2: la app guarda las direcciones de envío en la tabla `addresses` de la Parte 5.
-- La tabla ya existe (00_mysql_schema.sql); aquí solo se dan los permisos mínimos a mkt_app.
-- Sin DELETE: las direcciones se "borran" con is_active = FALSE (los pedidos guardan su copia).
USE marketplace;

GRANT SELECT, INSERT, UPDATE ON marketplace.addresses TO 'mkt_app'@'%';

-- Verificación: deben aparecer 4 filas (USAGE, admin_actions, addresses y users).
SHOW GRANTS FOR 'mkt_app'@'%';
-- Debe existir la columna generada default_owner y el índice único uq_one_default.
SHOW COLUMNS FROM addresses LIKE 'default_owner';
SHOW INDEX FROM addresses WHERE Key_name = 'uq_one_default';
