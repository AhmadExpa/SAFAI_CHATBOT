import { useState, useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatInput } from "@/components/chat/ChatInput";
import bgTheme from "../assets/8.png";
import { listProjects, deleteProject, Project } from "@/lib/api";
import { Plus, Folder, Trash2, Loader2, Calendar } from "lucide-react";
import { useNavigate } from "react-router-dom";

import img14 from "../assets/14.png";
import img20 from "../assets/20.png";
import img19 from "../assets/19.png";
import img17 from "../assets/17.png";
import img11 from "../assets/11.png";
import img15 from "../assets/15.png";
import img10 from "../assets/10.png";
import img18 from "../assets/18.png";
import img12 from "../assets/12.png";
import img21 from "../assets/21.png";
import img13 from "../assets/13.png";
import img16 from "../assets/16.png";

const libraryImages = [
  { id: 1, src: img14 },
  { id: 2, src: img20 },
  { id: 3, src: img19 },
  { id: 4, src: img17 },
  { id: 5, src: img11 },
  { id: 6, src: img15 },
  { id: 7, src: img10 },
  { id: 8, src: img18 },
  { id: 9, src: img12 },
  { id: 10, src: img21 },
  { id: 11, src: img13 },
  { id: 12, src: img16 },
];

interface LibraryProps {
  onLogout: () => void;
}

const Library = ({ onLogout }: LibraryProps) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"projects" | "images">("projects");
  const navigate = useNavigate();

  const fetchProjects = async () => {
    try {
      setIsLoading(true);
      const data = await listProjects();
      setProjects(data);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch projects");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleDeleteProject = async (
    projectId: string,
    e: React.MouseEvent,
  ) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this project?")) return;

    try {
      await deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.project_id !== projectId));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete project");
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div className="flex h-screen overflow-hidden">
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
        <Header title="Library" onMenuClick={() => setSidebarOpen(true)} />

        <main className="flex-1 overflow-y-auto px-3 md:px-6 py-4 relative z-20">
          {/* Tabs */}
          <div className="flex items-center gap-4 mb-6">
            <button
              onClick={() => setActiveTab("projects")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === "projects"
                  ? "bg-primary text-primary-foreground"
                  : "bg-card text-muted-foreground hover:text-foreground"
              }`}
            >
              Projects
            </button>
            <button
              onClick={() => setActiveTab("images")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === "images"
                  ? "bg-primary text-primary-foreground"
                  : "bg-card text-muted-foreground hover:text-foreground"
              }`}
            >
              Images
            </button>
            {activeTab === "projects" && (
              <button
                onClick={() => navigate("/createProject")}
                className="ml-auto flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:brightness-110 transition-all"
              >
                <Plus className="w-4 h-4" />
                New Project
              </button>
            )}
          </div>

          {/* Projects Tab */}
          {activeTab === "projects" && (
            <>
              {isLoading ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                </div>
              ) : error ? (
                <div className="text-center py-20">
                  <p className="text-destructive mb-4">{error}</p>
                  <button
                    onClick={fetchProjects}
                    className="text-primary hover:underline"
                  >
                    Try again
                  </button>
                </div>
              ) : projects.length === 0 ? (
                <div className="text-center py-20">
                  <Folder className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
                  <p className="text-muted-foreground mb-4">No projects yet</p>
                  <button
                    onClick={() => navigate("/createProject")}
                    className="flex items-center gap-2 mx-auto px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:brightness-110"
                  >
                    <Plus className="w-4 h-4" />
                    Create your first project
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {projects.map((project) => (
                    <div
                      key={project.project_id}
                      className="bg-card border border-border rounded-xl p-5 hover:shadow-lg transition-all cursor-pointer group"
                      onClick={() =>
                        navigate(`/workspace?project=${project.project_id}`)
                      }
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                            <Folder className="w-5 h-5 text-primary" />
                          </div>
                          <h3 className="font-semibold text-foreground truncate max-w-[180px]">
                            {project.name}
                          </h3>
                        </div>
                        <button
                          onClick={(e) =>
                            handleDeleteProject(project.project_id, e)
                          }
                          className="p-2 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-all"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                      {project.description && (
                        <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                          {project.description}
                        </p>
                      )}
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Calendar className="w-3 h-3" />
                        {formatDate(project.created_at)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* Images Tab */}
          {activeTab === "images" && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 md:gap-4">
              {libraryImages.map((image) => (
                <div
                  key={image.id}
                  className="aspect-square rounded-xl overflow-hidden bg-card border border-border shadow-card hover:shadow-soft transition-all duration-200 hover:scale-[1.02] cursor-pointer group relative"
                >
                  <img
                    src={image.src}
                    alt={`Library item ${image.id}`}
                    className="w-full h-full object-cover"
                  />
                  {/* Hover overlay */}
                  <div className="absolute inset-0 bg-foreground/0 group-hover:bg-foreground/10 transition-colors" />
                </div>
              ))}
            </div>
          )}
        </main>

        <div className=" md:pb-2">
          <ChatInput />
        </div>
      </div>
    </div>
  );
};

export default Library;
