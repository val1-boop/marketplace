-- Ejecutar en rds-mkt-identity-db (MySQL 8.4) conectado como admin.
-- Entidad "Vendedores": perfil público de la tienda de cada vendedor (nombre y descripción).
USE marketplace;

CREATE TABLE IF NOT EXISTS sellers (
  seller_id VARCHAR(20) NOT NULL PRIMARY KEY,
  user_id CHAR(36) CHARACTER SET ascii NOT NULL,
  store_name VARCHAR(80) NOT NULL,
  description VARCHAR(300) NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uq_seller_user (user_id),
  CONSTRAINT fk_seller_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Sin DELETE: mkt_app solo puede leer, crear y actualizar.
GRANT SELECT, INSERT, UPDATE ON marketplace.sellers TO 'mkt_app'@'%';

-- Verificación: la tabla debe tener 6 columnas y mkt_app debe mostrar 5 permisos en total.
SHOW COLUMNS FROM sellers;
SHOW GRANTS FOR 'mkt_app'@'%';
