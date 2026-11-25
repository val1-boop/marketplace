-- Ejecutar en la instancia rds-mkt-security-db (PostgreSQL), conectado como postgres
-- y con la base `security` seleccionada (no la base postgres).

-- Usuario de la aplicación con mínimo privilegio. Cambia la contraseña
-- (solo letras, números, guion y guion bajo).
CREATE ROLE mkt_app LOGIN PASSWORD 'CAMBIA_ESTA_CLAVE';
GRANT CONNECT ON DATABASE security TO mkt_app;
GRANT USAGE ON SCHEMA public TO mkt_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON login_attempts TO mkt_app;
GRANT SELECT, INSERT ON auth_events TO mkt_app;
GRANT USAGE ON SEQUENCE auth_events_id_seq TO mkt_app;

-- Verificación
SELECT grantee, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'mkt_app'
ORDER BY table_name, privilege_type;
