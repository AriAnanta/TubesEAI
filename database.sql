-- Membuat database untuk Production Management Service
CREATE DATABASE IF NOT EXISTS manufacturing_production_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Membuat database untuk Production Planning Service
CREATE DATABASE IF NOT EXISTS manufacturing_production_planning CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Membuat database untuk Machine Queue Service
CREATE DATABASE IF NOT EXISTS manufacturing_machine_queue CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Membuat database untuk Material Inventory Service
CREATE DATABASE IF NOT EXISTS manufacturing_material_inventory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Membuat database untuk Production Feedback Service
CREATE DATABASE IF NOT EXISTS manufacturing_production_feedback CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE manufacturing_material_inventory;

-- Tabel suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100),
    email VARCHAR(100),
    phone VARCHAR(20),
    address VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabel materials
CREATE TABLE IF NOT EXISTS materials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    sku VARCHAR(50) UNIQUE,
    unit VARCHAR(20),
    quantity FLOAT DEFAULT 0,
    min_stock_level FLOAT DEFAULT 0,
    supplier_id INT,
    cost_per_unit FLOAT,
    location VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- Tabel material_transactions
CREATE TABLE IF NOT EXISTS material_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    material_id INT,
    transaction_type VARCHAR(20),
    quantity FLOAT NOT NULL,
    reference VARCHAR(100),
    notes VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES materials(id)
);

USE manufacturing_production_planning;

-- Tabel machines
CREATE TABLE IF NOT EXISTS machines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    machine_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'available',
    capacity_per_hour FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabel production_plans
CREATE TABLE IF NOT EXISTS production_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    product_id INT,
    quantity INT NOT NULL,
    priority INT DEFAULT 1,
    status VARCHAR(20) DEFAULT 'draft',
    start_date DATETIME,
    end_date DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabel machine_slots
CREATE TABLE IF NOT EXISTS machine_slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    machine_id INT,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    status VARCHAR(20) DEFAULT 'available',
    production_plan_id INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES machines(id),
    FOREIGN KEY (production_plan_id) REFERENCES production_plans(id)
);

-- Tabel capacity_plans
CREATE TABLE IF NOT EXISTS capacity_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    period_start DATETIME NOT NULL,
    period_end DATETIME NOT NULL,
    total_capacity_hours FLOAT,
    allocated_capacity_hours FLOAT DEFAULT 0,
    notes VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabel plan_materials (many-to-many)
CREATE TABLE IF NOT EXISTS plan_materials (
    plan_id INT,
    material_id INT,
    quantity_required FLOAT NOT NULL,
    PRIMARY KEY (plan_id, material_id),
    FOREIGN KEY (plan_id) REFERENCES production_plans(id)
);

USE manufacturing_production_management;

-- Tabel production_batches
CREATE TABLE IF NOT EXISTS production_batches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_number VARCHAR(50) UNIQUE NOT NULL,
    order_id VARCHAR(50),
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    priority INT DEFAULT 1,
    status VARCHAR(20) DEFAULT 'pending',
    production_plan_id INT,
    scheduled_start DATETIME,
    scheduled_end DATETIME,
    actual_start DATETIME,
    actual_end DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabel production_steps
CREATE TABLE IF NOT EXISTS production_steps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id INT,
    step_number INT,
    name VARCHAR(100) NOT NULL,
    machine_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    duration_minutes INT,
    start_time DATETIME,
    end_time DATETIME,
    machine_queue_id INT,
    notes VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES production_batches(id)
);

-- Tabel step_materials
CREATE TABLE IF NOT EXISTS step_materials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    step_id INT,
    material_id INT NOT NULL,
    quantity_required FLOAT NOT NULL,
    is_consumed BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (step_id) REFERENCES production_steps(id)
);

-- Tabel product_definitions
CREATE TABLE IF NOT EXISTS product_definitions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    production_workflow JSON,
    standard_batch_size INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

USE manufacturing_machine_queue;

-- Tabel machines
CREATE TABLE IF NOT EXISTS machines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    machine_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'available',
    current_queue_item_id INT,
    last_maintenance DATETIME,
    next_maintenance DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabel machine_queue_items
CREATE TABLE IF NOT EXISTS machine_queue_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    machine_id INT,
    production_step_id INT NOT NULL,
    batch_id INT NOT NULL,
    position INT NOT NULL,
    priority INT DEFAULT 1,
    status VARCHAR(20) DEFAULT 'queued',
    estimated_start_time DATETIME,
    estimated_end_time DATETIME,
    actual_start_time DATETIME,
    actual_end_time DATETIME,
    setup_time_minutes INT DEFAULT 0,
    processing_time_minutes INT NOT NULL,
    materials_ready BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES machines(id)
);

-- Tabel queue_item_materials
CREATE TABLE IF NOT EXISTS queue_item_materials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    queue_item_id INT,
    material_id INT NOT NULL,
    quantity_required FLOAT NOT NULL,
    is_available BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (queue_item_id) REFERENCES machine_queue_items(id)
);

-- Tabel operation_logs
CREATE TABLE IF NOT EXISTS operation_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    machine_id INT,
    queue_item_id INT,
    operation_type VARCHAR(50),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    operator VARCHAR(100),
    notes VARCHAR(255),
    error_details VARCHAR(255),
    FOREIGN KEY (machine_id) REFERENCES machines(id),
    FOREIGN KEY (queue_item_id) REFERENCES machine_queue_items(id)
);
USE manufacturing_production_feedback;

-- Tabel production_feedbacks
CREATE TABLE IF NOT EXISTS production_feedbacks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id INT NOT NULL,
    step_id INT,
    status VARCHAR(20) NOT NULL,
    completion_percentage FLOAT DEFAULT 0,
    quality_score FLOAT,
    quality_data JSON,
    issues TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabel production_histories
CREATE TABLE IF NOT EXISTS production_histories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id INT NOT NULL,
    batch_number VARCHAR(50),
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    start_time DATETIME,
    end_time DATETIME,
    duration_minutes INT,
    status VARCHAR(20) NOT NULL,
    marketplace_order_id VARCHAR(50),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tabel quality_checks
CREATE TABLE IF NOT EXISTS quality_checks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id INT NOT NULL,
    step_id INT,
    check_type VARCHAR(50) NOT NULL,
    parameter_name VARCHAR(100) NOT NULL,
    expected_value VARCHAR(100),
    actual_value VARCHAR(100),
    passed BOOLEAN NOT NULL,
    severity INT,
    notes TEXT,
    checked_by VARCHAR(100),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tabel marketplace_notifications
CREATE TABLE IF NOT EXISTS marketplace_notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id INT NOT NULL,
    marketplace_order_id VARCHAR(50) NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    sent BOOLEAN DEFAULT FALSE,
    sent_at DATETIME,
    success BOOLEAN,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);