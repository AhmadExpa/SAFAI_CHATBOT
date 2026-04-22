-- Migration 009: Redesign for Multi-Model Support with Comments
-- This migration creates a better structure for handling multi-model responses

-- Create model_responses table
-- This table stores individual model responses, allowing multiple models to respond to one user message
CREATE TABLE IF NOT EXISTS model_responses (
    response_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,  -- Reference to the user's message that triggered this response
    model_name VARCHAR(100) NOT NULL,  -- The model that generated this response (e.g., 'GPT-4o', 'Claude-3')
    content TEXT NOT NULL,  -- The actual response content
    response_order INTEGER NOT NULL DEFAULT 0,  -- Order of this response (for display purposes)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_message FOREIGN KEY(message_id) REFERENCES messages(message_id) ON DELETE CASCADE,
    CONSTRAINT check_response_order_positive CHECK (response_order >= 0)
);

-- Create response_comments table
-- This table stores comments attached to specific model responses
CREATE TABLE IF NOT EXISTS response_comments (
    comment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    response_id UUID NOT NULL,  -- Reference to the model response this comment is attached to
    user_id UUID NOT NULL,  -- User who created the comment
    comment_text TEXT NOT NULL,  -- The comment content
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_response FOREIGN KEY(response_id) REFERENCES model_responses(response_id) ON DELETE CASCADE,
    CONSTRAINT fk_user FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT check_comment_not_empty CHECK (LENGTH(TRIM(comment_text)) > 0)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_model_responses_message_id ON model_responses(message_id);
CREATE INDEX IF NOT EXISTS idx_model_responses_created_at ON model_responses(created_at);
CREATE INDEX IF NOT EXISTS idx_response_comments_response_id ON response_comments(response_id);
CREATE INDEX IF NOT EXISTS idx_response_comments_user_id ON response_comments(user_id);
CREATE INDEX IF NOT EXISTS idx_response_comments_created_at ON response_comments(created_at);

-- Add comment to explain the new structure
COMMENT ON TABLE model_responses IS 'Stores individual model responses, supporting multi-model chat where multiple models can respond to a single user message';
COMMENT ON TABLE response_comments IS 'Stores user comments attached to specific model responses for annotation and feedback';
COMMENT ON COLUMN model_responses.response_order IS 'Order in which responses should be displayed (0-indexed)';
COMMENT ON COLUMN model_responses.model_name IS 'Name of the AI model that generated this response (e.g., GPT-4o, Claude-3, Gemini-Pro)';

