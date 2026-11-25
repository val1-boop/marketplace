-- Esquema ORIGINAL de la Parte 5 (sección C.4), sin cambios.
-- Ejecutar en rds-mkt-security-db con la conexión apuntando a la base `security`
-- (NO a la base postgres). Si la base no existe: conectarse a `postgres` y ejecutar
-- solo `CREATE DATABASE security;` (modo de transacción Auto en DataGrip).
-- Después ejecutar 02_postgres_security.sql.
CREATE TABLE login_attempts (
  email_hmac BYTEA PRIMARY KEY,
  failures SMALLINT NOT NULL DEFAULT 0,
  locked_until TIMESTAMP(3) NULL,
  updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE auth_events (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event VARCHAR(32) NOT NULL,
  user_id CHAR(36) NULL,
  email_hmac BYTEA NULL,
  created_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_time ON auth_events (user_id, created_at);
CREATE INDEX idx_time ON auth_events (created_at);
