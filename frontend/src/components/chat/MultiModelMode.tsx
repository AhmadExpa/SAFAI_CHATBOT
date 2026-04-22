import { useState, useEffect, useMemo } from "react";
import { X, ChevronDown, ChevronRight, Search, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { searchConversations, Conversation } from "@/lib/api";
import { useNavigate } from "react-router-dom";

interface SearchChatsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SearchChatsModal = ({
  isOpen,
  onClose,
}: SearchChatsModalProps) => {
  const [expandedModels, setExpandedModels] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const navigate = useNavigate();

  // Debounced search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setConversations([]);
      setHasSearched(false);
      return;
    }

    const timeoutId = setTimeout(async () => {
      setIsLoading(true);
      setHasSearched(true);
      try {
        const results = await searchConversations(searchQuery);
        setConversations(results);
      } catch (error) {
        console.error("Failed to search conversations:", error);
        setConversations([]);
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [searchQuery]);

  // Group conversations by model
  const groupedByModel = useMemo(() => {
    const groups: Record<string, Conversation[]> = {};

    conversations.forEach((conv) => {
      const model = conv.model_used || "Unknown Model";
      if (!groups[model]) {
        groups[model] = [];
      }
      groups[model].push(conv);
    });

    return groups;
  }, [conversations]);

  const toggleModel = (model: string) => {
    setExpandedModels((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(model)) {
        newSet.delete(model);
      } else {
        newSet.add(model);
      }
      return newSet;
    });
  };

  const handleConversationClick = (conversationId: string) => {
    onClose();
    navigate(`/chat/${conversationId}`);
  };

  const getModelColor = (model: string) => {
    const colors: Record<string, string> = {
      "gpt-4.1": "bg-cyan-500",
      "gpt-4": "bg-cyan-400",
      "gpt-3.5": "bg-cyan-300",
      claude: "bg-orange-500",
      k2: "bg-emerald-500",
      grok: "bg-purple-500",
      gemini: "bg-blue-500",
    };
    const lowerModel = model.toLowerCase();
    for (const [key, color] of Object.entries(colors)) {
      if (lowerModel.includes(key)) return color;
    }
    return "bg-gray-500";
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-2xl mx-2 md:mx-4 bg-card border border-border rounded-xl md:rounded-2xl shadow-2xl overflow-hidden max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-3 md:px-6 py-2 md:py-4 border-b border-border bg-muted/30">
          <div className="flex items-center gap-2 md:gap-3">
            <Search className="w-4 h-4 md:w-5 md:h-5 text-muted-foreground" />
            <span className="text-sm md:text-lg font-semibold text-foreground">
              Search Chats
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 md:p-2 rounded-lg hover:bg-muted transition-colors"
          >
            <X className="w-4 h-4 md:w-5 md:h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Search Input */}
        <div className="px-3 md:px-6 py-3 md:py-4 border-b border-border">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search your chats..."
            autoFocus
            className="w-full px-3 md:px-4 py-2 md:py-3 text-sm md:text-base bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>

        {/* Results Area */}
        <div className="flex-1 overflow-y-auto p-3 md:p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          ) : !hasSearched ? (
            <div className="text-center py-8 text-muted-foreground">
              <Search className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p className="text-sm">Type to search your conversations</p>
            </div>
          ) : Object.keys(groupedByModel).length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p className="text-sm">No chats found for "{searchQuery}"</p>
            </div>
          ) : (
            <div className="space-y-2 md:space-y-3">
              {Object.entries(groupedByModel).map(([model, chats]) => {
                const isExpanded = expandedModels.has(model);

                return (
                  <div
                    key={model}
                    className={cn(
                      "rounded-lg md:rounded-xl border transition-all duration-200",
                      isExpanded
                        ? "border-primary/50 bg-primary/5"
                        : "border-border bg-card hover:border-primary/30",
                    )}
                  >
                    {/* Model Header */}
                    <button
                      onClick={() => toggleModel(model)}
                      className="w-full flex items-center justify-between px-3 md:px-4 py-2 md:py-3"
                    >
                      <div className="flex items-center gap-2 md:gap-3">
                        {isExpanded ? (
                          <ChevronDown className="w-3.5 h-3.5 md:w-4 md:h-4 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="w-3.5 h-3.5 md:w-4 md:h-4 text-muted-foreground" />
                        )}
                        <div
                          className={cn(
                            "w-2.5 h-2.5 md:w-3 md:h-3 rounded-sm",
                            getModelColor(model),
                          )}
                        />
                        <span className="text-sm md:text-base font-medium text-foreground">
                          {model}
                        </span>
                      </div>
                      <span className="text-[11px] md:text-sm text-muted-foreground">
                        {chats.length} {chats.length === 1 ? "chat" : "chats"}
                      </span>
                    </button>

                    {/* Expanded Conversations */}
                    {isExpanded && (
                      <div className="px-3 md:px-4 pb-3 md:pb-4 space-y-1.5 md:space-y-2">
                        {chats.map((chat) => (
                          <div
                            key={chat.conversation_id}
                            onClick={() =>
                              handleConversationClick(chat.conversation_id)
                            }
                            className="px-3 py-2 rounded-lg bg-muted/50 hover:bg-muted cursor-pointer transition-colors"
                          >
                            <p className="text-sm font-medium text-foreground truncate">
                              {chat.title}
                            </p>
                            {chat.updated_at && (
                              <p className="text-xs text-muted-foreground mt-0.5">
                                {new Date(chat.updated_at).toLocaleDateString()}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SearchChatsModal;
