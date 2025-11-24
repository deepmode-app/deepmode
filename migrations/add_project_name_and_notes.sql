-- Migration: Add project_name and notes columns to sessions table
-- Run this migration for both PostgreSQL and SQLite

-- ============================================
-- PostgreSQL Migration
-- ============================================
-- Run this if DB_BACKEND=postgres

ALTER TABLE sessions 
ADD COLUMN IF NOT EXISTS project_name VARCHAR(255);

ALTER TABLE sessions 
ADD COLUMN IF NOT EXISTS notes TEXT;

-- ============================================
-- SQLite Migration  
-- ============================================
-- Run this if DB_BACKEND=sqlite
-- Note: SQLite doesn't support IF NOT EXISTS in ALTER TABLE
-- So check if columns exist first, or handle errors

-- For SQLite, you can run:
-- ALTER TABLE sessions ADD COLUMN project_name TEXT;
-- ALTER TABLE sessions ADD COLUMN notes TEXT;

-- If columns already exist, SQLite will throw an error.
-- You can check first with:
-- PRAGMA table_info(sessions);

