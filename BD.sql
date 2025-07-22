
CREATE TABLE telegram_bindings (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    telegram_id  BIGINT      NOT NULL,   
    user_id      INT         DEFAULT NULL, 
    binding_code VARCHAR(6)  NOT NULL,  
    code_expires TIMESTAMP   NOT NULL,  
    is_bound     TINYINT(1)  DEFAULT 0,
    KEY idx_telegram_id (telegram_id),
    KEY idx_user_id      (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE telegram_notifications (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    telegram_id  BIGINT     NOT NULL,   
    message      TEXT       NOT NULL,   
    is_sent      TINYINT(1) DEFAULT 0,  
    created_at   TIMESTAMP  DEFAULT CURRENT_TIMESTAMP,
    KEY idx_telegram_id (telegram_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

