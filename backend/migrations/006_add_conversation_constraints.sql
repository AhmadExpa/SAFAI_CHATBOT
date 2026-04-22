-- Add additional constraints and improvements to conversation structure
-- This migration adds constraints to ensure data integrity and proper conversation flow

-- Add comment to conversations table
COMMENT ON TABLE conversations IS 'Conversations represent single chat sessions with multiple request-response pairs';

-- Add comment to bubbles table  
COMMENT ON TABLE bubbles IS 'Bubbles represent request-response pairs within conversations, supporting modifications';

-- Add comment to messages table
COMMENT ON TABLE messages IS 'Messages within bubbles, supporting ChatGPT-like conversation structure';

-- Add comments to specific columns
COMMENT ON COLUMN conversations.title IS 'Title of the conversation, typically from first user message';
COMMENT ON COLUMN conversations.updated_at IS 'Last updated timestamp, updated when new bubbles are added';
COMMENT ON COLUMN bubbles.bubble_index IS 'Order of bubble within conversation (0, 1, 2, ...)';
COMMENT ON COLUMN messages.message_index IS 'Index of the bubble within conversation (same for user and assistant in bubble)';
COMMENT ON COLUMN messages.role IS 'Role of message: user, assistant, system, or function';
COMMENT ON COLUMN messages.model_used IS 'AI model used for generating the assistant response';

-- Create index for efficient querying of conversations by user
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);

-- Create index for efficient querying of bubbles by conversation
CREATE INDEX IF NOT EXISTS idx_bubbles_conversation_id ON bubbles(conversation_id);

-- Create index for efficient querying of messages by bubble
CREATE INDEX IF NOT EXISTS idx_messages_bubble_id ON messages(bubble_id);

-- Create composite index for efficient ordering of bubbles within conversations
CREATE INDEX IF NOT EXISTS idx_bubbles_conversation_bubble_index ON bubbles(conversation_id, bubble_index);

-- Create composite index for efficient ordering of messages within bubbles
CREATE INDEX IF NOT EXISTS idx_messages_bubble_message_index ON messages(bubble_id, message_index); 