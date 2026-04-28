-- Add soft delete fields to project table
-- Migration: Add is_deleted and deleted_at columns to Project model
-- Date: 2026-01-19

-- Add is_deleted column (boolean, defaults to false)
ALTER TABLE project ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE NOT NULL;

-- Add deleted_at column (timestamp, nullable)
ALTER TABLE project ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP NULL;

-- Add index on is_deleted for better query performance
CREATE INDEX IF NOT EXISTS ix_project_is_deleted ON project (is_deleted);

-- Add comment for documentation
COMMENT ON COLUMN project.is_deleted IS 'Soft delete flag: true if project is deleted';
COMMENT ON COLUMN project.deleted_at IS 'Timestamp when project was soft-deleted';
