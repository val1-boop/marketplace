-- Ejecutar en la instancia rds-mkt-identity-db (MySQL 8.4), conectado como admin.
-- Ajusta el esquema de la Parte 5 a lo que necesita la aplicación Flask.
USE marketplace;

-- 1) Nonce de sesión: rotarlo invalida en el servidor las cookies de sesión emitidas
--    (logout, cambio de contraseña, de rol o de estado).
ALTER TABLE users
  ADD COLUMN session_nonce VARCHAR(64) CHARACTER SET ascii NOT NULL AFTER deleted_at;

-- 2) Acciones administrativas que registra la app y que no estaban en el ENUM original.
ALTER TABLE admin_actions MODIFY action ENUM(
  'block_product','unblock_product','remove_image','restore_image',
  'hide_review','unhide_review','hide_question','unhide_question',
  'suspend_store','reactivate_store','suspend_user','ban_user',
  'reactivate_user','grant_admin','revoke_admin','dismiss_report',
  'delete_product','create_user','update_user','delete_user'
) NOT NULL;

-- 3) Usuario de la aplicación con mínimo privilegio (la app NO usa el usuario admin).
--    Cambia la contraseña: usa solo letras, números, guion y guion bajo
--    (por ejemplo, la salida de: python -c "import secrets; print(secrets.token_urlsafe(24))").
CREATE USER 'mkt_app'@'%' IDENTIFIED BY 'CAMBIA_ESTA_CLAVE' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE ON marketplace.users TO 'mkt_app'@'%';
GRANT SELECT, INSERT ON marketplace.admin_actions TO 'mkt_app'@'%';

-- Verificación
SHOW GRANTS FOR 'mkt_app'@'%';
SHOW COLUMNS FROM users LIKE 'session_nonce';
