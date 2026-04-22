-- Migration: Make message_id nullable in model_responses for backward compatibility
-- This allows comments to work even when responses aren't properly stored in the database

ALTER TABLE model_responses 
ALTER COLUMN message_id DROP NOT NULL;

-- Add comment explaining this design decision
COMMENT ON COLUMN model_responses.message_id IS 'References messages table. Nullable for backward compatibility with legacy chat responses.';

