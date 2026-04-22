import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";
import bgTheme from "@/assets/8.png";
import {
  getConversation,
  sendChatMessage,
  sendMultiModelChat,
  parseSSEStream,
  ChatMessage as ApiChatMessage,
  ConversationDetail,
} from "@/lib/api";
import { Loader2 } from "lucide-react";

interface Message {
  type: "user" | "assistant";
  content: string;
}

interface ChatDetailProps {
  onLogout: () => void;
}

const ChatDetail = ({ onLogout }: ChatDetailProps) => {
  const { conversationId } = useParams<{ conversationId: string }>();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [conversation, setConversation] = useState<ConversationDetail | null>(
    null,
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    if (mainRef.current) {
      mainRef.current.scrollTop = mainRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load conversation history
  useEffect(() => {
    if (!conversationId) return;

    const loadConversation = async () => {
      setLoadingHistory(true);
      try {
        const convo = await getConversation(conversationId);
        setConversation(convo);

        // Convert bubbles to flat messages
        const flatMessages: Message[] = [];
        for (const bubble of convo.bubbles || []) {
          for (const msg of bubble.messages || []) {
            flatMessages.push({
              type: msg.role === "user" ? "user" : "assistant",
              content: msg.content,
            });
          }
        }
        setMessages(flatMessages);
      } catch (error) {
        console.error("Failed to load conversation:", error);
      } finally {
        setLoadingHistory(false);
      }
    };

    loadConversation();
  }, [conversationId]);

  const handleSendMessage = async (
    content: string,
    model: string,
    isMultimodal: boolean,
    personalityId?: string | null,
    selectedModels?: string[],
  ) => {
    setMessages((prev) => [...prev, { type: "user", content }]);
    setIsLoading(true);

    try {
      const apiMessages: ApiChatMessage[] = [
        ...messages.map(
          (m): ApiChatMessage => ({
            role: m.type === "user" ? "user" : "assistant",
            content: m.content,
          }),
        ),
        { role: "user", content },
      ];

      // Determine which models to query
      const modelsToQuery =
        isMultimodal && selectedModels && selectedModels.length > 0
          ? selectedModels
          : [model];

      if (isMultimodal && modelsToQuery.length > 1) {
        const modelContents = Object.fromEntries(
          modelsToQuery.map((modelId) => [modelId, `**[${modelId}]**\n`]),
        );

        setMessages((prev) => [
          ...prev,
          ...modelsToQuery.map((modelId) => ({
            type: "assistant" as const,
            content: modelContents[modelId],
          })),
        ]);

        const response = await sendMultiModelChat({
          models: modelsToQuery,
          messages: apiMessages,
          conversation_id: conversationId,
          personality_id: personalityId || undefined,
        });

        for await (const chunk of parseSSEStream(response)) {
          if (chunk.done) break;
          if (!chunk.model || !chunk.content || !(chunk.model in modelContents)) {
            continue;
          }

          modelContents[chunk.model] += chunk.content;
          const modelLabel = `**[${chunk.model}]**\n`;
          setMessages((prev) => {
            const next = [...prev];
            let index = -1;
            for (let i = next.length - 1; i >= 0; i -= 1) {
              if (
                next[i].type === "assistant" &&
                next[i].content.startsWith(modelLabel)
              ) {
                index = i;
                break;
              }
            }
            if (index >= 0) {
              next[index] = {
                ...next[index],
                content: modelContents[chunk.model as string],
              };
            }
            return next;
          });
        }

        return;
      }

      // For each model, send the message and collect responses
      for (const currentModel of modelsToQuery) {
        // Add empty assistant message with model label for this model
        const modelLabel =
          modelsToQuery.length > 1 ? `**[${currentModel}]**\n` : "";
        setMessages((prev) => [
          ...prev,
          { type: "assistant", content: modelLabel },
        ]);

        const response = await sendChatMessage(currentModel, {
          messages: apiMessages,
          conversation_id: conversationId,
          personality_id: personalityId || undefined,
        });

        let fullContent = modelLabel;
        for await (const chunk of parseSSEStream(response)) {
          if (chunk.done) break;
          fullContent += chunk.content;
          setMessages((prev) => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage.type === "assistant") {
              lastMessage.content = fullContent;
            }
            return newMessages;
          });
        }
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => [
        ...prev,
        {
          type: "assistant",
          content: `Error: ${error instanceof Error ? error.message : "Failed to send message"}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  if (loadingHistory) {
    return (
      <div className="flex items-center justify-center h-screen main-bg">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex overflow-hidden h-screen md:h-[100vh] main-bg">
      <Sidebar
        activePage="chat"
        onLogout={onLogout}
        isOpen={sidebarOpen}
        onOpenChange={setSidebarOpen}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header onMenuClick={() => setSidebarOpen(true)} />

        <main ref={mainRef} className="flex-1 overflow-y-auto relative">
          <div
            className="absolute top-80 dark:top-0 flex items-center justify-center w-full inset-0 z-0"
            style={{ pointerEvents: "none" }}
          >
            <img
              src={bgTheme}
              alt="Background"
              className="dark:w-[70%] w-[80%] mx-auto object-stretch dark:invert opacity-50 dark:opacity-20"
            />
          </div>

          <div className="relative z-10 max-w-4xl mx-auto px-4 py-6">
            {/* Conversation title */}
            {conversation?.title && (
              <h1 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                {conversation.title}
              </h1>
            )}

            {/* Messages */}
            <div className="space-y-6">
              {messages.map((message, index) => (
                <ChatMessage
                  key={index}
                  type={message.type}
                  content={message.content}
                />
              ))}
              {isLoading &&
                messages[messages.length - 1]?.type !== "assistant" && (
                  <div className="flex items-center gap-2 text-gray-500">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">Thinking...</span>
                  </div>
                )}
            </div>
            <div ref={messagesEndRef} />
          </div>
        </main>

        <ChatInput onSendMessage={handleSendMessage} disabled={isLoading} />
      </div>
    </div>
  );
};

export default ChatDetail;
