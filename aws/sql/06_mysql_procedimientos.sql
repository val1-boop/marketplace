-- Ejecutar en rds-mkt-identity-db (MySQL 8.4) conectado como admin, DESPUES de 04_mysql_sellers.sql.
-- Procedimientos almacenados (Stored Procedures) de la base marketplace:
--   1) sp_guardar_tienda   -> crea o actualiza la tienda de un vendedor en una sola operacion atomica.
--   2) sp_resumen_cuentas  -> consulta consolidada de cuentas y tiendas para el panel del administrador.
-- Los dos usan SQL SECURITY INVOKER: se ejecutan con los permisos de quien los llama (mkt_app), asi que
-- no le dan ningun permiso extra. mkt_app solo recibe EXECUTE sobre ellos. No contiene contrasenas.
-- Es seguro repetirlo: DROP PROCEDURE IF EXISTS + CREATE PROCEDURE.
-- En DataGrip: Ctrl + A y Ctrl + Enter ejecuta todo el script (cada procedimiento termina en "END;").
USE marketplace;

-- ---------------------------------------------------------------------------------------------
-- 1) sp_guardar_tienda
--    La app la llama al guardar "Datos de mi tienda". Valida los datos, comprueba que la cuenta sea
--    duena de ese codigo de vendedor y hace INSERT ... ON DUPLICATE KEY UPDATE: dos guardados casi
--    simultaneos no pueden chocar ni crear tiendas repetidas (seller_id y user_id son unicos).
-- ---------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_guardar_tienda;

CREATE PROCEDURE sp_guardar_tienda(
  IN p_seller_id VARCHAR(20),
  IN p_user_id CHAR(36),
  IN p_store_name VARCHAR(200),
  IN p_description VARCHAR(1000)
)
MODIFIES SQL DATA
SQL SECURITY INVOKER
COMMENT 'Crea o actualiza la tienda de un vendedor (atomico y validado)'
BEGIN
  DECLARE v_name VARCHAR(200);
  DECLARE v_description VARCHAR(1000);

  SET v_name = TRIM(p_store_name);
  SET v_description = NULLIF(TRIM(p_description), '');

  IF p_seller_id IS NULL OR p_seller_id NOT REGEXP '^SEL-[0-9]{3,8}$' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El codigo de vendedor no es valido';
  END IF;
  IF v_name IS NULL OR CHAR_LENGTH(v_name) < 3 OR CHAR_LENGTH(v_name) > 80 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El nombre de la tienda debe tener de 3 a 80 caracteres';
  END IF;
  IF v_description IS NOT NULL AND CHAR_LENGTH(v_description) > 300 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La descripcion admite hasta 300 caracteres';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM users
                 WHERE id = p_user_id AND seller_id = p_seller_id AND status = 'active') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La cuenta activa no tiene ese codigo de vendedor';
  END IF;

  INSERT INTO sellers (seller_id, user_id, store_name, description)
  VALUES (p_seller_id, p_user_id, v_name, v_description) AS nueva
  ON DUPLICATE KEY UPDATE store_name = nueva.store_name, description = nueva.description;
END;

-- ---------------------------------------------------------------------------------------------
-- 2) sp_resumen_cuentas
--    Devuelve UNA fila con el resumen consolidado de cuentas y tiendas (sin contar cuentas eliminadas).
--    Solo lee: la app la llama al abrir el panel del administrador.
-- ---------------------------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_resumen_cuentas;

CREATE PROCEDURE sp_resumen_cuentas()
READS SQL DATA
SQL SECURITY INVOKER
COMMENT 'Resumen consolidado de cuentas y tiendas para el panel del administrador'
BEGIN
  SELECT
    COUNT(*) AS usuarios,
    CAST(COALESCE(SUM(status = 'active'), 0) AS SIGNED) AS activos,
    CAST(COALESCE(SUM(status = 'suspended'), 0) AS SIGNED) AS suspendidos,
    CAST(COALESCE(SUM(status = 'banned'), 0) AS SIGNED) AS bloqueados,
    CAST(COALESCE(SUM(role IN ('admin', 'super_admin')), 0) AS SIGNED) AS administradores,
    (SELECT COUNT(*) FROM sellers) AS tiendas
  FROM users
  WHERE status <> 'deleted';
END;

-- ---------------------------------------------------------------------------------------------
-- Permisos: mkt_app solo puede ejecutarlos (sigue sin poder borrar ni crear tablas).
-- ---------------------------------------------------------------------------------------------
GRANT EXECUTE ON PROCEDURE marketplace.sp_guardar_tienda TO 'mkt_app'@'%';
GRANT EXECUTE ON PROCEDURE marketplace.sp_resumen_cuentas TO 'mkt_app'@'%';

-- Verificacion: deben aparecer los 2 procedimientos y mkt_app debe tener 2 permisos EXECUTE mas.
SHOW PROCEDURE STATUS WHERE Db = 'marketplace';
SHOW GRANTS FOR 'mkt_app'@'%';
