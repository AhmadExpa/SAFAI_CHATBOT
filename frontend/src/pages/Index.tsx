import { useState, useRef, useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatInput } from "@/components/chat/ChatInput";
import { WelcomeCard } from "@/components/welcome/WelcomeCard";
import { ChatMessage } from "@/components/chat/ChatMessage";
import bgTheme from "../assets/8.png";
import { useTheme } from "@/hooks/useTheme";
import welcomeText from "../assets/3.png";
import workspaceText from "../assets/4.png";
import {
  sendChatMessage,
  sendMultiModelChat,
  parseSSEStream,
  ChatMessage as ApiChatMessage,
} from "@/lib/api";
import { useLocation } from "react-router-dom";

interface Message {
  type: "user" | "assistant";
  content: string;
}

interface IndexProps {
  onLogout: () => void;
}

const Index = ({ onLogout }: IndexProps) => {
  useTheme();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);
  const initialMessageProcessed = useRef(false);

  const scrollToBottom = () => {
    if (mainRef.current) {
      mainRef.current.scrollTop = mainRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Handle initial message from navigation (e.g., from Library, Workspace pages)
  useEffect(() => {
    const state = location.state as {
      initialMessage?: string;
      model?: string;
      isMultimodal?: boolean;
      personalityId?: string | null;
      selectedModels?: string[];
    } | null;
    if (state?.initialMessage && !initialMessageProcessed.current) {
      initialMessageProcessed.current = true;
      handleSendMessage(
        state.initialMessage,
        state.model || "gpt-4.1",
        state.isMultimodal ?? true,
        state.personalityId,
        state.selectedModels || [state.model || "gpt-4.1"],
      );
      // Clear the state to prevent re-sending on refresh
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  const handleSendMessage = async (
    content: string,
    model: string,
    isMultimodal: boolean,
    personalityId?: string | null,
    selectedModels?: string[],
  ) => {
    // Add user message
    setMessages((prev) => [...prev, { type: "user", content }]);
    setIsLoading(true);

    try {
      // Build messages array for API
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

        // Send to API
        const response = await sendChatMessage(currentModel, {
          messages: apiMessages,
          personality_id: personalityId || undefined,
        });

        // Parse SSE stream
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

  const hasMessages = messages.length > 0;

  return (
    <div className="flex overflow-hidden h-screen md:h-[100vh] main-bg">
      {/* Sidebar */}
      <Sidebar
        activePage="home"
        onLogout={onLogout}
        isOpen={sidebarOpen}
        onOpenChange={setSidebarOpen}
      />

      <div className="flex-1 flex flex-col relative min-w-0">
        <div className="absolute -top-40 md:top-56 flex items-center justify-center w-full inset-0 z-0 pointer-events-none">
          <img
            src={bgTheme}
            alt="Background"
            className="md:w-[90%] object-cover opacity-60 dark:opacity-5 translate-y-10"
          />
        </div>
        <Header onMenuClick={() => setSidebarOpen(true)} />

        <main
          ref={mainRef}
          className={`flex-1 overflow-y-auto flex flex-col items-center px-3 md:px-6 pb-4 md:pb-8 relative z-10 ${hasMessages ? "pt-4" : "py-28 md:py-auto"}`}
        >
          {hasMessages ? (
            <div className="w-full max-w-4xl flex flex-col gap-4 py-4">
              {messages.map((msg, index) => (
                <ChatMessage
                  key={index}
                  type={msg.type}
                  content={msg.content}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          ) : (
            <>
              <div className="text-center mb-4 md:mb-8 relative z-10">
                <img
                  src={welcomeText}
                  alt="Welcome to SaiFai AI"
                  className="mb-3 w-auto max-w-full dark:invert"
                />

                <img
                  src={workspaceText}
                  alt="Your Intelligence Workspace"
                  className="translate-x-0 md:translate-x-16 w-auto max-w-full dark:invert"
                />
              </div>

              <WelcomeCard />
            </>
          )}
        </main>

        {/* Chat Input */}
        <div className="md:pb-2">
          <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
        </div>
      </div>
    </div>
  );
};

export default Index;
