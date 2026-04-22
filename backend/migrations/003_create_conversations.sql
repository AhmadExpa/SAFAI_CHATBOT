-- Create conversations table
-- Conversations represent a single chat session
-- Conversation Structure:
-- - One conversation per chat session (created when user clicks "New Chat")
-- - Contains multiple bubbles (request-response pairs)
-- - Each bubble represents one user request and its corresponding assistant response
-- - Bubbles can contain multiple request-response pairs (when user modifies and resends)
-- This implements ChatGPT-like conversation management

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    project_id UUID,
    title TEXT NOT NULL, -- Title of the conversation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP, -- Last updated timestamp
    CONSTRAINT fk_user FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_project FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE SET NULL
); 