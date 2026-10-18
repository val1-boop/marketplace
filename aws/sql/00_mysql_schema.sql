-- Esquema ORIGINAL de la Parte 5 (sección B.4), sin cambios.
-- Ejecutar en rds-mkt-identity-db (MySQL 8.4) conectado como admin, el script completo a la vez
-- (MySQL Workbench: Ctrl+Shift+Enter). Después ejecutar 01_mysql_marketplace.sql.
CREATE DATABASE IF NOT EXISTS marketplace;
USE marketplace;

CREATE TABLE users (
  id CHAR(36) CHARACTER SET ascii PRIMARY KEY,
  email VARCHAR(254) NOT NULL,
  email_normalized VARCHAR(254) COLLATE utf8mb4_0900_bin NOT NULL UNIQUE,
  first_name VARCHAR(60) NOT NULL,
  last_name VARCHAR(80) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('user','admin','super_admin') NOT NULL DEFAULT 'user',
  status ENUM('active','suspended','banned','deleted') NOT NULL DEFAULT 'active',
  status_reason VARCHAR(500) NULL,
  seller_id VARCHAR(20) NULL UNIQUE,
  email_verified_at DATETIME(3) NULL,
  terms_version VARCHAR(10) NOT NULL,
  privacy_version VARCHAR(10) NOT NULL,
  terms_accepted_at DATETIME(3) NOT NULL,
  last_login_at DATETIME(3) NULL,
  password_changed_at DATETIME(3) NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted_at DATETIME(3) NULL,
  INDEX idx_role_status (role, status),
  CONSTRAINT chk_staff_no_store CHECK (role = 'user' OR seller_id IS NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE addresses (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id CHAR(36) CHARACTER SET ascii NOT NULL,
  label VARCHAR(40) NOT NULL,
  recipient_name VARCHAR(120) NOT NULL,
  phone VARCHAR(20) NOT NULL,
  line1 VARCHAR(120) NOT NULL,
  line2 VARCHAR(120) NULL,
  city VARCHAR(80) NOT NULL,
  state VARCHAR(80) NOT NULL,
  postal_code CHAR(5) NOT NULL,
  country CHAR(2) NOT NULL DEFAULT 'MX',
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  default_owner CHAR(36) CHARACTER SET ascii
    AS (IF(is_default AND is_active, user_id, NULL)) STORED,
  UNIQUE KEY uq_one_default (default_owner),
  INDEX idx_user (user_id, is_active),
  CONSTRAINT fk_addr_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE reports (
  id CHAR(26) CHARACTER SET ascii PRIMARY KEY,
  reporter_id CHAR(36) CHARACTER SET ascii NOT NULL,
  target_type ENUM('product','review','question','store','user') NOT NULL,
  target_id VARCHAR(80) NOT NULL,
  reason ENUM('prohibited_item','counterfeit','ip_infringement','misleading',
              'fraud','offensive','spam','wrong_category','contact_info',
              'review_request','other') NOT NULL,
  details VARCHAR(500) NULL,
  status ENUM('open','dismissed','actioned') NOT NULL DEFAULT 'open',
  resolved_by CHAR(36) CHARACTER SET ascii NULL,
  resolved_at DATETIME(3) NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  open_key VARCHAR(160) AS (IF(status = 'open',
    CONCAT_WS('|', reporter_id, target_type, target_id), NULL)) STORED,
  UNIQUE KEY uq_one_open (open_key),
  INDEX idx_queue (status, created_at),
  INDEX idx_target (target_type, target_id),
  CONSTRAINT fk_report_reporter FOREIGN KEY (reporter_id) REFERENCES users(id),
  CONSTRAINT fk_report_resolver FOREIGN KEY (resolved_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE admin_actions (
  id CHAR(26) CHARACTER SET ascii PRIMARY KEY,
  admin_id CHAR(36) CHARACTER SET ascii NOT NULL,
  action ENUM('block_product','unblock_product','remove_image','restore_image',
              'hide_review','unhide_review','hide_question','unhide_question',
              'suspend_store','reactivate_store','suspend_user','ban_user',
              'reactivate_user','grant_admin','revoke_admin','dismiss_report') NOT NULL,
  target_type ENUM('product','image','review','question','store','user','report') NOT NULL,
  target_id VARCHAR(80) NOT NULL,
  report_id CHAR(26) CHARACTER SET ascii NULL,
  reason VARCHAR(500) NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  INDEX idx_admin_time (admin_id, created_at),
  INDEX idx_target (target_type, target_id, created_at),
  CONSTRAINT fk_action_admin FOREIGN KEY (admin_id) REFERENCES users(id),
  CONSTRAINT fk_action_report FOREIGN KEY (report_id) REFERENCES reports(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
