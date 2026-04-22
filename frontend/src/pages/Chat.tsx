import { useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";
import bgTheme from "../assets/8.png";
import MultiModelMode from "@/components/chat/MultiModelMode";
import { useTheme } from "@/hooks/useTheme";
import { Skeleton } from "@/components/ui/skeleton";

interface Message {
  id: string;
  type: "user" | "assistant";
  content: string;
  hasImage?: boolean;
  hasCode?: boolean;
  codeContent?: string;
}

const sampleMessages: Message[] = [
  {
    id: "1",
    type: "user",
    content:
      "Give me some codes related to it: Lorem ipsum dolor sit amet consectetur. Pretium ac mattis pellentesque.",
  },
  {
    id: "2",
    type: "assistant",
    content:
      "Note: Need a remark about missing or uncertain statistics — check tables 2 & 4 for nulls and inconsistent units.",
    hasCode: true,
    codeContent: `function calculateTotal(items) {
  let total = 0;
  items.forEach(item => {
    total += item.price;
  });
  return total;
}

console.log(calculateTotal([{price: 10}, {price: 15}]));`,
  },
  {
    id: "3",
    type: "user",
    content:
      "Hi, I'm working on a project called Project Chimera. Can you explain its purpose in simple terms?",
  },
  {
    id: "4",
    type: "assistant",
    content:
      "Sure! Project Chimera appears to be a system that combines different AI models to analyze data, generate responses, and help with maintenance or reporting tasks.\n\nIt's like having multiple smart assistants collaborating to give you better insights.",
  },
  {
    id: "5",
    type: "assistant",
    content:
      "Absolutely. Project Chimera is a multi-AI workflow tool designed to merge different AI strengths into one workspace.\n\nIt can analyze documents, generate explanations, run code, and help track important metrics.\n\nIn simple terms: it's a hub where several AIs solve the same problem together, giving you richer answers.",
  },
];

const Chat = ({ onLogout }: { onLogout: () => void }) => {
  const { theme } = useTheme();
  const [messages] = useState<Message[]>(sampleMessages);
  const [isMultiMode] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen  overflow-hidden main-bg">
      <Sidebar
        activePage="chat"
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
        <Header title="Chat" onMenuClick={() => setSidebarOpen(true)} />

        <main className="flex-1 overflow-y-auto px-3 md:px-6 py-4 relative z-20">
          {isMultiMode ? (
            <MultiModelMode isOpen={true} onClose={() => {}} />
          ) : (
            <div className="max-w-4xl mx-auto">
              {/* File Upload Indicator */}
              <div className="flex justify-end mb-4">
                <div className="bg-card border border-border rounded-xl p-3 flex items-center gap-3 max-w-xs">
                  <div className="w-10 h-10 bg-destructive/10 rounded-lg flex items-center justify-center">
                    <span className="text-destructive text-xs font-bold">
                      PDF
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      Uploading Q3 report pdf summary...
                    </p>
                    <p className="text-xs text-muted-foreground">PDF</p>
                  </div>
                </div>
              </div>

              {/* User context message */}
              <div className="flex justify-end mb-4">
                <div className="chat-bubble-user-themed rounded-2xl rounded-br-sm px-4 py-3 max-w-[70%]">
                  <p className="text-sm">
                    The document discusses performance trends, missing data
                    points, and suggests improvements for the final report.
                  </p>
                </div>
              </div>

              {/* Assistant response with images */}
              <div className="flex gap-3 mb-4">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-accent flex-shrink-0 flex items-center justify-center">
                  <span className="text-primary-foreground text-sm font-medium">
                    AI
                  </span>
                </div>
                <div className="max-w-[70%] chat-bubble-assistant-themed border border-border rounded-2xl rounded-bl-sm px-4 py-3">
                  <p className="text-sm mb-3">
                    I've reviewed your file and created a corner remark about
                    missing statistics and section gaps that need expansion.
                    Below are the synthesized outputs — an image summary, a code
                    diagnostic, and model comparison notes.
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <Skeleton className="aspect-video rounded-lg bg-muted" />
                    <Skeleton className="aspect-video rounded-lg bg-muted" />
                  </div>
                </div>
              </div>

              {/* Chat Messages */}
              {messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  type={message.type}
                  content={message.content}
                  hasImage={message.hasImage}
                  hasCode={message.hasCode}
                  codeContent={message.codeContent}
                />
              ))}
            </div>
          )}
        </main>

        <div className="md:pb-2">
          <ChatInput />
        </div>
      </div>
    </div>
  );
};

export default Chat;
