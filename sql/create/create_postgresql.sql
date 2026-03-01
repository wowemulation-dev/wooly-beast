-- PostgreSQL equivalent of create_mysql.sql for Cataclysm Classic
-- Creates the trinity user and all four databases

-- Create user (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'trinity') THEN
        CREATE ROLE trinity WITH LOGIN PASSWORD 'trinity';
    END IF;
END
$$;

-- Create databases
CREATE DATABASE world OWNER trinity;
CREATE DATABASE characters OWNER trinity;
CREATE DATABASE auth OWNER trinity;
CREATE DATABASE hotfixes OWNER trinity;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE world TO trinity;
GRANT ALL PRIVILEGES ON DATABASE characters TO trinity;
GRANT ALL PRIVILEGES ON DATABASE auth TO trinity;
GRANT ALL PRIVILEGES ON DATABASE hotfixes TO trinity;
