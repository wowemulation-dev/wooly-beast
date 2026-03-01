-- PostgreSQL equivalent of drop_mysql.sql for Cataclysm Classic
-- Drops all four databases and the trinity user

DROP DATABASE IF EXISTS world;
DROP DATABASE IF EXISTS characters;
DROP DATABASE IF EXISTS auth;
DROP DATABASE IF EXISTS hotfixes;
DROP ROLE IF EXISTS trinity;
