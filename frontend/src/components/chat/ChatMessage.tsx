import { ThumbsUp, ThumbsDown, Copy, Download, Plus, RefreshCw, Edit2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';

interface ChatMessageProps {
  type: 'user' | 'assistant';
  content: string;
  avatar?: string;
  hasImage?: boolean;
  hasCode?: boolean;
  codeContent?: string;
}

export function ChatMessage({ type, content, avatar, hasImage, hasCode, codeContent }: ChatMessageProps) {
  const isUser = type === 'user';

  return (
    <div className={cn("flex gap-3 mb-4", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div className={cn(
        "w-8 h-8 rounded-full overflow-hidden flex-shrink-0",
        isUser ? "bg-primary" : "bg-gradient-to-br from-primary to-accent"
      )}>
        {avatar ? (
          <img src={avatar} alt="Avatar" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-primary-foreground text-sm font-medium">
            {isUser ? 'U' : 'AI'}
          </div>
        )}
      </div>

      {/* Message Content */}
      <div className={cn(
        "max-w-[70%] rounded-2xl px-4 py-3",
        isUser
          ? "chat-bubble-user-themed rounded-br-sm"
          : "chat-bubble-assistant-themed border border-border rounded-bl-sm"
      )}>
        {/* Text Content */}
        <p className="text-sm whitespace-pre-wrap">{content}</p>

        {/* Image Placeholder */}
        {hasImage && (
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Skeleton className="aspect-video rounded-lg bg-muted" />
            <Skeleton className="aspect-video rounded-lg bg-muted" />
          </div>
        )}

        {/* Code Block */}
        {hasCode && codeContent && (
          <div className="mt-3 bg-background/50 rounded-lg p-3 font-mono text-xs overflow-x-auto border border-border">
            <pre className="text-foreground">{codeContent}</pre>
          </div>
        )}

        {/* Actions (for assistant messages) */}
        {!isUser && (
          <div className="flex items-center gap-1 mt-3 pt-2 border-t border-border/50">
            <button className="p-1.5 rounded hover:bg-muted transition-colors" aria-label="Like">
              <ThumbsUp className="w-4 h-4 text-muted-foreground hover:text-foreground" />
            </button>
            <button className="p-1.5 rounded hover:bg-muted transition-colors" aria-label="Dislike">
              <ThumbsDown className="w-4 h-4 text-muted-foreground hover:text-foreground" />
            </button>
            <button className="p-1.5 rounded hover:bg-muted transition-colors" aria-label="Copy">
              <Copy className="w-4 h-4 text-muted-foreground hover:text-foreground" />
            </button>
            <button className="p-1.5 rounded hover:bg-muted transition-colors" aria-label="Download">
              <Download className="w-4 h-4 text-muted-foreground hover:text-foreground" />
            </button>
            <button className="p-1.5 rounded hover:bg-muted transition-colors" aria-label="Add">
              <Plus className="w-4 h-4 text-muted-foreground hover:text-foreground" />
            </button>
          </div>
        )}

        {/* Actions (for user messages) */}
        {isUser && (
          <div className="flex items-center gap-1 mt-2 justify-end">
            <button className="p-1 rounded hover:bg-primary-foreground/20 transition-colors" aria-label="Copy">
              <Copy className="w-3.5 h-3.5 text-primary-foreground/70" />
            </button>
            <button className="p-1 rounded hover:bg-primary-foreground/20 transition-colors" aria-label="Edit">
              <Edit2 className="w-3.5 h-3.5 text-primary-foreground/70" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
