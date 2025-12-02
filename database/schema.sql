-- ===================================
-- Tạo cơ sở dữ liệu (nếu cần)
-- ===================================
CREATE DATABASE IF NOT EXISTS discord_bot;
USE discord_bot;

-- ===================================
-- Bảng 1: Users
-- Quản lý thông tin người dùng
-- ===================================
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,        -- ID người dùng Discord
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Thời gian thêm vào
    INDEX idx_user_id (user_id)        -- Tăng tốc truy vấn theo ID người dùng
);

-- ===================================
-- Bảng 2: Servers
-- Quản lý thông tin máy chủ
-- ===================================
CREATE TABLE IF NOT EXISTS servers (
    server_id BIGINT PRIMARY KEY,      -- ID máy chủ Discord
    prefix VARCHAR(10) DEFAULT '!',   -- Prefix của bot trong server
    mod_role BIGINT DEFAULT NULL,     -- Vai trò moderator (nếu có)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Thời gian thêm vào
    INDEX idx_server_id (server_id)    -- Tăng tốc truy vấn theo ID máy chủ
);

-- ===================================
-- Bảng 3: User_Server_Relation
-- Quản lý người dùng trong từng máy chủ
-- ===================================
CREATE TABLE IF NOT EXISTS user_server_relation (
    user_id BIGINT,                   -- ID người dùng
    server_id BIGINT,                 -- ID máy chủ
    warn_count INT DEFAULT 0,        -- Số lần bị cảnh cáo
    PRIMARY KEY (user_id, server_id), -- Khoá chính kết hợp
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (server_id) REFERENCES servers(server_id) ON DELETE CASCADE,
    INDEX idx_user_server (user_id, server_id) -- Tăng tốc truy vấn kết hợp
);


-- ===================================
-- Bảng 4: Command_Logs
-- Lịch sử sử dụng lệnh
-- ===================================
CREATE TABLE IF NOT EXISTS command_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,    -- ID log
    user_id BIGINT NOT NULL,                  -- ID người dùng thực thi lệnh
    server_id BIGINT NOT NULL,                -- ID máy chủ
    command_name VARCHAR(50) NOT NULL,        -- Tên lệnh
    command_args TEXT DEFAULT NULL,           -- Đối số lệnh
    executed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Thời gian thực thi
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (server_id) REFERENCES servers(server_id) ON DELETE CASCADE,
    INDEX idx_user_command (user_id, command_name), -- Truy vấn theo user + lệnh
    INDEX idx_executed_at (executed_at)       -- Tăng tốc truy vấn theo thời gian
);

-- ===================================
-- Bảng 5: Wallets
-- Quản lý số dư của từng người dùng trong từng máy chủ
-- ===================================
CREATE TABLE IF NOT EXISTS wallets (
    wallet_id INT AUTO_INCREMENT PRIMARY KEY,  -- ID ví tiền
    user_id BIGINT NOT NULL,                   -- ID người dùng
    server_id BIGINT NOT NULL,                 -- ID máy chủ
    balance DECIMAL(10,2) DEFAULT 0.00 CHECK (balance >= 0.00), -- Số dư hiện tại
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (server_id) REFERENCES servers(server_id) ON DELETE CASCADE,
    INDEX idx_user_server (user_id, server_id) -- Tăng tốc truy vấn kết hợp
);

-- ===================================
-- Bảng 6: Transactions
-- Lịch sử giao dịch của người dùng
-- ===================================
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY, -- ID giao dịch
    wallet_id INT NOT NULL,                        -- ID ví tiền
    amount DECIMAL(10,2) NOT NULL,                 -- Số tiền giao dịch
    transaction_type ENUM('earn', 'spend', 'tax', 'gift') NOT NULL, -- Loại giao dịch
    description TEXT DEFAULT NULL,                -- Mô tả giao dịch
    transaction_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Thời gian giao dịch
    FOREIGN KEY (wallet_id) REFERENCES wallets(wallet_id) ON DELETE CASCADE,
    INDEX idx_wallet_date (wallet_id, transaction_at) -- Truy vấn theo ví + thời gian
);
