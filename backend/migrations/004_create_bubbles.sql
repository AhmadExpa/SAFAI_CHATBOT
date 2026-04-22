-- Create bubbles table
-- Bubbles represent a single request-response pair within a conversation
-- Bubble Structure:
-- - Each bubble represents one user request and its corresponding assistant response
-- - bubble_index represents the order of bubbles within a conversation
-- - A bubble can contain multiple request-response pairs (when user modifies and resends)
-- - Each request-response pair within a bubble has the same message_index
-- This implements ChatGPT-like conversation structure

CREATE TABLE IF NOT EXISTS bubbles (
    bubble_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL,
    bubble_index INTEGER NOT NULL, -- Order of bubble within conversation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_conversation FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    CONSTRAINT check_bubble_index_positive CHECK (bubble_index >= 0),
    CONSTRAINT check_bubble_index_reasonable CHECK (bubble_index <= 999999)
); 