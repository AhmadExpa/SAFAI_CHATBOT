import { useState, useEffect } from "react";
import { Folder, FileText, BookOpen } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatInput } from "@/components/chat/ChatInput";
import { cn } from "@/lib/utils";
import bgTheme from "../assets/8.png";
import {
  listProjects,
  listProjectFiles,
  Project,
  ProjectFile,
} from "@/lib/api";

const Codex = ({ onLogout }: { onLogout: () => void }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState<"projects" | "files">("projects");
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);

  // Fetch projects on mount
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const data = await listProjects();
        setProjects(data);
        if (data.length > 0) {
          setSelectedProject(data[0].project_id);
        }
      } catch (error) {
        console.error("Failed to fetch projects:", error);
      } finally {
        setIsLoadingProjects(false);
      }
    };
    fetchProjects();
  }, []);

  // Fetch files when selected project changes
  useEffect(() => {
    if (!selectedProject) {
      setFiles([]);
      return;
    }

    const fetchFiles = async () => {
      setIsLoadingFiles(true);
      try {
        const data = await listProjectFiles(selectedProject);
        setFiles(data);
      } catch (error) {
        console.error("Failed to fetch files:", error);
        setFiles([]);
      } finally {
        setIsLoadingFiles(false);
      }
    };
    fetchFiles();
  }, [selectedProject]);

  return (
    <div className="flex h-screen  overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        activePage="codex"
        onLogout={onLogout}
        isOpen={sidebarOpen}
        onOpenChange={setSidebarOpen}
      />

      {/* Main */}
      <div className="flex-1 flex flex-col relative min-w-0">
        {/* Background */}
        <div className="absolute -top-40 md:top-56 flex items-center justify-center w-full inset-0 z-0 pointer-events-none">
          <img
            src={bgTheme}
            alt="Background"
            className="md:w-[90%] object-cover opacity-60 dark:opacity-5 translate-y-10"
          />
        </div>

        {/* Header */}
        <Header title="Codex" onMenuClick={() => setSidebarOpen(true)} />

        {/* Content */}
        <main className="flex-1 overflow-hidden px-3 md:px-6 py-3 md:py-4 relative z-20">
          {/* Codex Header */}
          <div className="flex items-center gap-2 mb-3 md:mb-6">
            <div className="w-7 h-7 md:w-10 md:h-10 rounded-lg bg-accent/10 flex items-center justify-center">
              <BookOpen className="w-4 h-4 md:w-5 md:h-5 text-accent" />
            </div>
            <h2 className="text-base md:text-xl font-semibold text-foreground">
              Codex Library
            </h2>
          </div>

          {/* 🔥 MOBILE TABS */}
          <div className="md:hidden flex bg-card border border-border rounded-xl p-1 mb-3">
            <button
              onClick={() => setMobileTab("projects")}
              className={cn(
                "flex-1 py-2 text-xs font-medium rounded-lg transition-all",
                mobileTab === "projects"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground",
              )}
            >
              Projects
            </button>
            <button
              onClick={() => setMobileTab("files")}
              className={cn(
                "flex-1 py-2 text-xs font-medium rounded-lg transition-all",
                mobileTab === "files"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground",
              )}
            >
              Files
            </button>
          </div>

          {/* Layout */}
          <div className="flex flex-col md:flex-row gap-2 md:gap-6 md:h-[calc(100%-3rem)]">
            {/* Projects */}
            <div
              className={cn(
                "w-full md:w-64 bg-card border border-border rounded-xl p-2 md:p-4 overflow-y-auto",
                "hidden md:block",
                mobileTab === "projects" && "block",
              )}
            >
              <h3 className="font-semibold text-sm md:text-base text-foreground mb-2 md:mb-4">
                Projects
              </h3>

              <div className="space-y-1">
                {isLoadingProjects ? (
                  <div className="text-xs text-muted-foreground py-2">
                    Loading...
                  </div>
                ) : projects.length === 0 ? (
                  <div className="text-xs text-muted-foreground py-2">
                    No projects found
                  </div>
                ) : (
                  projects.map((project) => (
                    <button
                      key={project.project_id}
                      onClick={() => setSelectedProject(project.project_id)}
                      className={cn(
                        "w-full flex items-center gap-2 md:gap-3 px-2 md:px-3 py-2 md:py-2.5 rounded-lg text-xs md:text-sm transition-colors text-left",
                        selectedProject === project.project_id
                          ? "bg-primary/10 text-primary"
                          : "text-foreground hover:bg-muted",
                      )}
                    >
                      <Folder
                        className={cn(
                          "w-4 h-4 md:w-5 md:h-5",
                          selectedProject === project.project_id
                            ? "text-primary"
                            : "text-muted-foreground",
                        )}
                      />
                      <span className="truncate">{project.name}</span>
                    </button>
                  ))
                )}
              </div>
            </div>

            {/* Files */}
            <div
              className={cn(
                "flex-1 bg-card border border-border rounded-xl p-2 md:p-4 overflow-y-auto",
                "hidden md:block",
                mobileTab === "files" && "block",
              )}
            >
              <h3 className="font-semibold text-sm md:text-base text-foreground mb-2 md:mb-4">
                Files
              </h3>

              <div className="space-y-1">
                {isLoadingFiles ? (
                  <div className="text-xs text-muted-foreground py-2">
                    Loading...
                  </div>
                ) : files.length === 0 ? (
                  <div className="text-xs text-muted-foreground py-2">
                    No files in this project
                  </div>
                ) : (
                  files.map((file) => (
                    <button
                      key={file.file_id}
                      className="w-full flex items-center gap-2 md:gap-3 px-2 md:px-3 py-2 md:py-2.5 rounded-lg text-xs md:text-sm text-foreground hover:bg-muted transition-colors text-left"
                    >
                      <FileText className="w-4 h-4 md:w-5 md:h-5 text-primary" />
                      <span className="truncate">
                        {file.original_filename || file.filename}
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>
        </main>

        {/* Chat Input */}
        <div className="md:pb-2">
          <ChatInput />
        </div>
      </div>
    </div>
  );
};

export default Codex;
