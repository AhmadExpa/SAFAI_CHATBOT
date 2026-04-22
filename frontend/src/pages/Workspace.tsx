import { useState, useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatInput } from "@/components/chat/ChatInput";
import bgTheme from "../assets/8.png";
import { useTheme } from "@/hooks/useTheme";
import {
  listWorkspaces,
  deleteWorkspace,
  Workspace as WorkspaceType,
} from "@/lib/api";
import { Plus, Briefcase, Trash2, Loader2, Calendar } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface PageProps {
  onLogout: () => void;
}

const Workspace = ({ onLogout }: PageProps) => {
  const { theme } = useTheme();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [workspaces, setWorkspaces] = useState<WorkspaceType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const fetchWorkspaces = async () => {
    try {
      setIsLoading(true);
      const data = await listWorkspaces();
      setWorkspaces(data);
      setError("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch workspaces",
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const handleDeleteWorkspace = async (
    workspaceId: string,
    e: React.MouseEvent,
  ) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this workspace?")) return;

    try {
      await deleteWorkspace(workspaceId);
      setWorkspaces((prev) =>
        prev.filter((w) => w.workspace_id !== workspaceId),
      );
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete workspace");
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
        <Header title="Workspace" onMenuClick={() => setSidebarOpen(true)} />

        <main className="flex-1 overflow-y-auto px-3 md:px-6 py-4 relative z-20">
          {/* Header with New Workspace button */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-foreground">
              Workspaces
            </h2>
            <button
              onClick={() => navigate("/createWorkspace")}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:brightness-110 transition-all"
            >
              <Plus className="w-4 h-4" />
              New Workspace
            </button>
          </div>

          {/* Workspaces List */}
          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="text-center py-20">
              <p className="text-destructive mb-4">{error}</p>
              <button
                onClick={fetchWorkspaces}
                className="text-primary hover:underline"
              >
                Try again
              </button>
            </div>
          ) : workspaces.length === 0 ? (
            <div className="text-center py-20">
              <Briefcase className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground mb-4">No workspaces yet</p>
              <button
                onClick={() => navigate("/createWorkspace")}
                className="flex items-center gap-2 mx-auto px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:brightness-110"
              >
                <Plus className="w-4 h-4" />
                Create your first workspace
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {workspaces.map((workspace) => (
                <div
                  key={workspace.workspace_id}
                  className="bg-card border border-border rounded-xl p-5 hover:shadow-lg transition-all cursor-pointer group"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                        <Briefcase className="w-5 h-5 text-primary" />
                      </div>
                      <h3 className="font-semibold text-foreground truncate max-w-[180px]">
                        {workspace.name}
                      </h3>
                    </div>
                    <button
                      onClick={(e) =>
                        handleDeleteWorkspace(workspace.workspace_id, e)
                      }
                      className="p-2 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  {workspace.description && (
                    <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                      {workspace.description}
                    </p>
                  )}
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Calendar className="w-3 h-3" />
                    {formatDate(workspace.created_at)}
                  </div>
                </div>
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

export default Workspace;
