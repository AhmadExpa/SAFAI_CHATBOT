-- Create messages table
-- Messages represent individual messages within a bubble
-- Message Index Logic:
-- - message_index represents the position of the bubble within the conversation
-- - Both user request and assistant response have the same message_index
-- - message_index 0: First request-response pair (bubble 0)
-- - message_index 1: Second request-response pair (bubble 1)
-- - message_index 2: Third request-response pair (bubble 2)
-- - This implements ChatGPT-like conversation structure

CREATE TABLE IF NOT EXISTS messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bubble_id UUID NOT NULL,
    message_index INTEGER NOT NULL, -- Index of the bubble within conversation (same for user and assistant in bubble)
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    model_used VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bubble FOREIGN KEY(bubble_id) REFERENCES bubbles(bubble_id) ON DELETE CASCADE,
    CONSTRAINT valid_role CHECK (role IN ('user', 'assistant', 'system', 'function')),
    CONSTRAINT check_message_index_positive CHECK (message_index >= 0),
    CONSTRAINT check_message_index_reasonable CHECK (message_index >= 0 AND message_index <= 999999)
); 