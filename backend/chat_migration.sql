-- SmartInterview — Chat Feature Migration
-- Safe, non-destructive. Run AFTER the base database is set up.
-- Run with: mysql -u root -proot smartinterview < backend/chat_migration.sql

USE smartinterview;

-- ── 1. chat_groups ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `chat_groups` (
  `id`          INT NOT NULL AUTO_INCREMENT,
  `name`        VARCHAR(150) NOT NULL,
  `description` VARCHAR(500) DEFAULT NULL,
  `avatar_url`  VARCHAR(500) DEFAULT NULL,
  `created_by`  INT DEFAULT NULL,
  `created_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_active`   TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `fk_cg_created_by` (`created_by`),
  CONSTRAINT `fk_cg_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ── 2. chat_messages (before chat_group_members so FK to messages works) ───
CREATE TABLE IF NOT EXISTS `chat_messages` (
  `id`                    INT NOT NULL AUTO_INCREMENT,
  `group_id`              INT NOT NULL,
  `sender_id`             INT DEFAULT NULL,
  `message_type`          ENUM('TEXT','SYSTEM','INTERVIEW','INTERVIEW_RESULT') NOT NULL DEFAULT 'TEXT',
  `content`               JSON NOT NULL,
  `reply_to_message_id`   INT DEFAULT NULL,
  `client_message_id`     VARCHAR(100) DEFAULT NULL,
  `created_at`            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `edited_at`             DATETIME DEFAULT NULL,
  `deleted_at`            DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_msg_sender_client_id` (`sender_id`, `client_message_id`),
  KEY `idx_cm_group_created` (`group_id`, `created_at`),
  KEY `idx_cm_group_id` (`group_id`, `id`),
  KEY `idx_cm_sender_created` (`sender_id`, `created_at`),
  KEY `fk_cm_reply` (`reply_to_message_id`),
  CONSTRAINT `fk_cm_group` FOREIGN KEY (`group_id`) REFERENCES `chat_groups` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cm_sender` FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_cm_reply` FOREIGN KEY (`reply_to_message_id`) REFERENCES `chat_messages` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ── 3. chat_group_members ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `chat_group_members` (
  `id`                    INT NOT NULL AUTO_INCREMENT,
  `group_id`              INT NOT NULL,
  `user_id`               INT NOT NULL,
  `role`                  ENUM('ADMIN','MEMBER') NOT NULL DEFAULT 'MEMBER',
  `joined_at`             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `left_at`               DATETIME DEFAULT NULL,
  `is_active`             TINYINT(1) NOT NULL DEFAULT 1,
  `last_read_message_id`  INT DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_chat_group_member` (`group_id`, `user_id`),
  KEY `idx_cgm_group_user` (`group_id`, `user_id`),
  KEY `idx_cgm_user_group` (`user_id`, `group_id`),
  KEY `fk_cgm_last_read` (`last_read_message_id`),
  CONSTRAINT `fk_cgm_group` FOREIGN KEY (`group_id`) REFERENCES `chat_groups` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cgm_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cgm_last_read` FOREIGN KEY (`last_read_message_id`) REFERENCES `chat_messages` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ── 4. group_interview_shares ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `group_interview_shares` (
  `id`                    INT NOT NULL AUTO_INCREMENT,
  `group_id`              INT NOT NULL,
  `interview_session_id`  INT NOT NULL,
  `posted_by`             INT DEFAULT NULL,
  `message_id`            INT DEFAULT NULL,
  `created_at`            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `is_active`             TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `idx_gis_group_created` (`group_id`, `created_at`),
  KEY `fk_gis_session` (`interview_session_id`),
  KEY `fk_gis_poster` (`posted_by`),
  KEY `fk_gis_message` (`message_id`),
  CONSTRAINT `fk_gis_group` FOREIGN KEY (`group_id`) REFERENCES `chat_groups` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_gis_session` FOREIGN KEY (`interview_session_id`) REFERENCES `interview_sessions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_gis_poster` FOREIGN KEY (`posted_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_gis_message` FOREIGN KEY (`message_id`) REFERENCES `chat_messages` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ── 5. group_interview_attempts ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `group_interview_attempts` (
  `id`                    INT NOT NULL AUTO_INCREMENT,
  `share_id`              INT NOT NULL,
  `user_id`               INT NOT NULL,
  `interview_session_id`  INT DEFAULT NULL,
  `status`                ENUM('NOT_STARTED','IN_PROGRESS','COMPLETED') NOT NULL DEFAULT 'NOT_STARTED',
  `attempted_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_gia_share_user` (`share_id`, `user_id`),
  KEY `idx_gia_share` (`share_id`),
  KEY `idx_gia_user` (`user_id`),
  KEY `fk_gia_session` (`interview_session_id`),
  CONSTRAINT `fk_gia_share` FOREIGN KEY (`share_id`) REFERENCES `group_interview_shares` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_gia_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_gia_session` FOREIGN KEY (`interview_session_id`) REFERENCES `interview_sessions` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
