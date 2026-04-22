import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatInput } from "@/components/chat/ChatInput";
import bgTheme from "@/assets/8.png";
import {
  getProject,
  getProjectContext,
  updateProjectContext,
  listProjectFiles,
  uploadProjectFile,
  deleteProjectFile,
  getFileContent,
  Project,
  ProjectContext,
  ProjectFile,
} from "@/lib/api";
import {
  FileText,
  Upload,
  Trash2,
  Save,
  ArrowLeft,
  Loader2,
  Eye,
} from "lucide-react";

interface ProjectDetailProps {
  onLogout: () => void;
}

const ProjectDetail = ({ onLogout }: ProjectDetailProps) => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [project, setProject] = useState<Project | null>(null);
  const [context, setContext] = useState<ProjectContext>({
    context: "",
    goals: "",
    decisions: "",
    preferences: "",
  });
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [activeTab, setActiveTab] = useState<"context" | "files">("context");
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<ProjectFile | null>(null);

  useEffect(() => {
    if (!projectId) return;
    loadProjectData();
  }, [projectId]);

  const loadProjectData = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [proj, ctx, fileList] = await Promise.all([
        getProject(projectId),
        getProjectContext(projectId).catch(() => ({
          context: "",
          goals: "",
          decisions: "",
          preferences: "",
        })),
        listProjectFiles(projectId).catch(() => []),
      ]);
      setProject(proj);
      setContext(ctx);
      setFiles(fileList);
    } catch (error) {
      console.error("Failed to load project:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveContext = async () => {
    if (!projectId) return;
    setSaving(true);
    try {
      await updateProjectContext(projectId, context);
    } catch (error) {
      console.error("Failed to save context:", error);
    } finally {
      setSaving(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!projectId || !e.target.files?.length) return;
    setUploading(true);
    try {
      const file = e.target.files[0];
      const uploaded = await uploadProjectFile(projectId, file);
      setFiles((prev) => [...prev, uploaded]);
    } catch (error) {
      console.error("Failed to upload file:", error);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    if (!projectId) return;
    try {
      await deleteProjectFile(projectId, fileId);
      setFiles((prev) => prev.filter((f) => f.file_id !== fileId));
      if (selectedFile?.file_id === fileId) {
        setSelectedFile(null);
        setFileContent(null);
      }
    } catch (error) {
      console.error("Failed to delete file:", error);
    }
  };

  const handleViewFile = async (file: ProjectFile) => {
    if (!projectId) return;
    try {
      const content = await getFileContent(projectId, file.file_id);
      setFileContent(content);
      setSelectedFile(file);
    } catch (error) {
      console.error("Failed to load file content:", error);
      setFileContent("Unable to display file content");
      setSelectedFile(file);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen main-bg">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex overflow-hidden h-screen md:h-[100vh] main-bg">
      <Sidebar
        activePage="library"
        onLogout={onLogout}
        isOpen={sidebarOpen}
        onOpenChange={setSidebarOpen}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          onMenuClick={() => setSidebarOpen(true)}
        />

        <main className="flex-1 overflow-y-auto relative">
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
            {/* Back button and title */}
            <div className="flex items-center gap-4 mb-6">
              <button
                onClick={() => navigate("/library")}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {project?.name || "Project"}
                </h1>
                {project?.description && (
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {project.description}
                  </p>
                )}
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mb-6">
              <button
                onClick={() => setActiveTab("context")}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                  activeTab === "context"
                    ? "bg-primary text-white"
                    : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                }`}
              >
                Context & Goals
              </button>
              <button
                onClick={() => setActiveTab("files")}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                  activeTab === "files"
                    ? "bg-primary text-white"
                    : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                }`}
              >
                Files ({files.length})
              </button>
            </div>

            {/* Context Tab */}
            {activeTab === "context" && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Project Context
                  </label>
                  <textarea
                    value={context.context || ""}
                    onChange={(e) =>
                      setContext((prev) => ({ ...prev, context: e.target.value }))
                    }
                    placeholder="Describe the main context of your project..."
                    className="w-full h-32 p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white resize-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Goals
                  </label>
                  <textarea
                    value={context.goals || ""}
                    onChange={(e) =>
                      setContext((prev) => ({ ...prev, goals: e.target.value }))
                    }
                    placeholder="What are the goals of this project?"
                    className="w-full h-24 p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white resize-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Key Decisions
                  </label>
                  <textarea
                    value={context.decisions || ""}
                    onChange={(e) =>
                      setContext((prev) => ({ ...prev, decisions: e.target.value }))
                    }
                    placeholder="Document important decisions made..."
                    className="w-full h-24 p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white resize-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Preferences
                  </label>
                  <textarea
                    value={context.preferences || ""}
                    onChange={(e) =>
                      setContext((prev) => ({
                        ...prev,
                        preferences: e.target.value,
                      }))
                    }
                    placeholder="User preferences and settings..."
                    className="w-full h-24 p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white resize-none"
                  />
                </div>

                <button
                  onClick={handleSaveContext}
                  disabled={saving}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:brightness-110 transition disabled:opacity-50"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  {saving ? "Saving..." : "Save Context"}
                </button>
              </div>
            )}

            {/* Files Tab */}
            {activeTab === "files" && (
              <div className="space-y-4">
                {/* Upload button */}
                <div className="flex items-center gap-2">
                  <label className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:brightness-110 transition cursor-pointer">
                    {uploading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Upload className="w-4 h-4" />
                    )}
                    {uploading ? "Uploading..." : "Upload File"}
                    <input
                      type="file"
                      onChange={handleFileUpload}
                      className="hidden"
                      disabled={uploading}
                    />
                  </label>
                </div>

                {/* Files list */}
                <div className="grid gap-2">
                  {files.length === 0 ? (
                    <p className="text-gray-500 dark:text-gray-400 text-sm py-4 text-center">
                      No files uploaded yet
                    </p>
                  ) : (
                    files.map((file) => (
                      <div
                        key={file.file_id}
                        className="flex items-center justify-between p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
                      >
                        <div className="flex items-center gap-3">
                          <FileText className="w-5 h-5 text-primary" />
                          <div>
                            <p className="text-sm font-medium text-gray-900 dark:text-white">
                              {file.original_filename || file.filename}
                            </p>
                            {file.file_size && (
                              <p className="text-xs text-gray-500">
                                {(file.file_size / 1024).toFixed(1)} KB
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleViewFile(file)}
                            className="p-2 text-gray-500 hover:text-primary transition"
                            title="View content"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteFile(file.file_id)}
                            className="p-2 text-gray-500 hover:text-red-500 transition"
                            title="Delete file"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* File content viewer */}
                {selectedFile && (
                  <div className="mt-4 p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                        {selectedFile.original_filename || selectedFile.filename}
                      </h3>
                      <button
                        onClick={() => {
                          setSelectedFile(null);
                          setFileContent(null);
                        }}
                        className="text-xs text-gray-500 hover:text-gray-700"
                      >
                        Close
                      </button>
                    </div>
                    <pre className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap max-h-64 overflow-y-auto bg-gray-50 dark:bg-gray-900 p-3 rounded">
                      {fileContent}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </main>

        <ChatInput />
      </div>
    </div>
  );
};

export default ProjectDetail;
