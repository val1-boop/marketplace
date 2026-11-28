-- Ejecutar en rds-mkt-identity-db (MySQL 8.4) conectado como admin, DESPUES de 04_mysql_sellers.sql.
-- Datos iniciales (DML) de la entidad "Vendedores": crea un perfil de tienda para cada cuenta que
-- ya tiene codigo de vendedor y todavia no configuro el suyo. Cada persona puede cambiarlo luego
-- en la pantalla "Datos de mi tienda". No contiene contrasenas ni datos personales nuevos.
-- Es seguro repetirlo: INSERT IGNORE omite a quien ya tiene tienda (seller_id y user_id son unicos).
USE marketplace;

INSERT IGNORE INTO sellers (seller_id, user_id, store_name)
SELECT u.seller_id, u.id, LEFT(CONCAT('Tienda de ', u.first_name), 80)
FROM users AS u
WHERE u.seller_id IS NOT NULL;

-- Verificacion: debe haber una tienda por cada cuenta con codigo de vendedor.
SELECT
  (SELECT COUNT(*) FROM users WHERE seller_id IS NOT NULL) AS cuentas_con_vendedor,
  (SELECT COUNT(*) FROM sellers) AS tiendas;
SELECT seller_id, store_name FROM sellers ORDER BY seller_id;
