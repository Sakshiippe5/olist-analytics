-- Rebuilds the schema from scratch so the ETL is re-runnable (idempotent).
DROP SCHEMA IF EXISTS olist CASCADE;
CREATE SCHEMA olist;
SET search_path TO olist;

CREATE TABLE customers (
    customer_id               VARCHAR(32) PRIMARY KEY,
    customer_unique_id        VARCHAR(32) NOT NULL,
    customer_zip_code_prefix  CHAR(5),
    customer_city             VARCHAR(100),
    customer_state            CHAR(2)
);

CREATE TABLE sellers (
    seller_id                 VARCHAR(32) PRIMARY KEY,
    seller_zip_code_prefix    CHAR(5),
    seller_city               VARCHAR(100),
    seller_state              CHAR(2)
);

CREATE TABLE products (
    product_id                  VARCHAR(32) PRIMARY KEY,
    product_category_name       VARCHAR(100),
    category_english            VARCHAR(100),
    product_name_length         INT,
    product_description_length  INT,
    product_photos_qty          INT,
    product_weight_g            NUMERIC(10,2),
    product_length_cm           NUMERIC(10,2),
    product_height_cm           NUMERIC(10,2),
    product_width_cm            NUMERIC(10,2)
);

CREATE TABLE orders (
    order_id                       VARCHAR(32) PRIMARY KEY,
    customer_id                    VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    order_status                   VARCHAR(20) NOT NULL,
    order_purchase_timestamp       TIMESTAMP NOT NULL,
    order_approved_at              TIMESTAMP,
    order_delivered_carrier_date   TIMESTAMP,
    order_delivered_customer_date  TIMESTAMP,
    order_estimated_delivery_date  TIMESTAMP,
    delivery_days                  NUMERIC(8,2),
    delivery_delay_days            NUMERIC(8,2),
    is_late                        BOOLEAN
);

CREATE TABLE order_items (
    order_id             VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    order_item_id        INT NOT NULL,
    product_id           VARCHAR(32) NOT NULL REFERENCES products(product_id),
    seller_id            VARCHAR(32) NOT NULL REFERENCES sellers(seller_id),
    shipping_limit_date  TIMESTAMP,
    price                NUMERIC(10,2) NOT NULL,
    freight_value        NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE order_payments (
    order_id              VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    payment_sequential    INT NOT NULL,
    payment_type          VARCHAR(30),
    payment_installments  INT,
    payment_value         NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE order_reviews (
    order_id                 VARCHAR(32) PRIMARY KEY REFERENCES orders(order_id),
    review_id                VARCHAR(32),
    review_score             INT CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title     TEXT,
    review_comment_message   TEXT,
    review_creation_date     TIMESTAMP,
    review_answer_timestamp  TIMESTAMP
);

CREATE INDEX idx_orders_customer   ON orders(customer_id);
CREATE INDEX idx_orders_purchase   ON orders(order_purchase_timestamp);
CREATE INDEX idx_orders_status     ON orders(order_status);
CREATE INDEX idx_items_product     ON order_items(product_id);
CREATE INDEX idx_items_seller      ON order_items(seller_id);
CREATE INDEX idx_customers_unique  ON customers(customer_unique_id);
