import { useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatInput } from "@/components/chat/ChatInput";
import bgTheme from "../assets/8.png";
import { useTheme } from "@/hooks/useTheme";

interface PageProps {
  onLogout: () => void;
}

const Templates = ({ onLogout }: PageProps) => {
  const { theme } = useTheme();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen  overflow-hidden">
      <Sidebar
        activePage="library"
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
        <Header title="Templates" onMenuClick={() => setSidebarOpen(true)} />

        <main className="flex-1 overflow-y-auto px-3 md:px-6 py-4 relative z-20">
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm md:text-base">
            Templates Page - Coming Soon
          </div>
        </main>

        <div className="md:pb-2">
          <ChatInput />
        </div>
      </div>
    </div>
  );
};

export default Templates;
