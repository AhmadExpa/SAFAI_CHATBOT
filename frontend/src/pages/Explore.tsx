import { useState, useEffect, useMemo } from "react";
import { Search, Folder, FileText, MessageCircle } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatInput } from "@/components/chat/ChatInput";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import bgTheme from "../assets/8.png";
import { listProjects, Project } from "@/lib/api";
import { getAllModels, Model } from "@/lib/models";

const categories = ["All", "AI Models", "Projects"];

interface ExploreItem {
  id: string;
  title: string;
  description: string;
  type: "AI Model" | "Projects";
  icon: "ai" | "folder" | "file" | "chat";
}

const Explore = ({ onLogout }: { onLogout: () => void }) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("All");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState<string | undefined>(
    undefined,
  );

  // Fetch projects on mount
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const data = await listProjects();
        setProjects(data);
      } catch (error) {
        console.error("Failed to fetch projects:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchProjects();
  }, []);

  // Get all AI models
  const aiModels = getAllModels();

  // Build explore items from real data
  const exploreItems = useMemo((): ExploreItem[] => {
    const modelItems: ExploreItem[] = aiModels.map((model: Model) => ({
      id: `model-${model.id}`,
      title: model.name,
      description: model.multimodal
        ? "Multimodal AI model with vision capabilities"
        : "Text-based AI model for conversations",
      type: "AI Model" as const,
      icon: "ai" as const,
    }));

    const projectItems: ExploreItem[] = projects.map((project: Project) => ({
      id: `project-${project.project_id}`,
      title: project.name,
      description: project.description || "Your project workspace",
      type: "Projects" as const,
      icon: "folder" as const,
    }));

    return [...modelItems, ...projectItems];
  }, [aiModels, projects]);

  // Filter items based on category and search
  const filteredItems = useMemo(() => {
    return exploreItems.filter((item) => {
      const matchesCategory =
        activeCategory === "All" || item.type === activeCategory;
      const matchesSearch =
        searchQuery === "" ||
        item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.description.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [exploreItems, activeCategory, searchQuery]);

  const getIcon = (iconType: string) => {
    switch (iconType) {
      case "ai":
        return (
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <span className="text-xl">🤖</span>
          </div>
        );
      case "folder":
        return (
          <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
            <Folder className="w-5 h-5 text-accent" />
          </div>
        );
      case "file":
        return (
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <FileText className="w-5 h-5 text-primary" />
          </div>
        );
      case "chat":
        return (
          <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
            <MessageCircle className="w-5 h-5 text-muted-foreground" />
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        activePage="explore"
        onLogout={onLogout}
        isOpen={sidebarOpen}
        onOpenChange={setSidebarOpen}
      />

      <div className="flex-1 flex flex-col relative">
        <div className="absolute -top-40 md:top-56 flex items-center justify-center w-full inset-0 z-0 pointer-events-none">
          <img
            src={bgTheme}
            alt="Background"
            className="md:w-[90%] object-cover opacity-60 dark:opacity-5 translate-y-10"
          />
        </div>
        <Header title="Explore" onMenuClick={() => setSidebarOpen(true)} />

        <main className="flex-1 overflow-y-auto px-3 md:px-6 py-4 relative z-20">
          {/* Hero Section */}
          <div className="text-center mb-4 md:mb-8">
            <h1 className="text-3xl md:text-4xl lg:text-5xl font-display italic text-foreground mb-3">
              SaiFai
            </h1>
            <p className="text-sm md:text-base text-muted-foreground max-w-xl mx-auto px-4">
              Discover and create custom versions of SaiFai that combine
              instructions, extra knowledge, and any combination of skills.
            </p>
          </div>

          {/* Search Bar */}
          <div className="max-w-2xl mx-auto mb-4 md:mb-6 px-3 md:px-0">
            <div className="relative">
              <Search className="absolute left-3 md:left-4 top-1/2 -translate-y-1/2 w-4 md:w-5 h-4 md:h-5 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search SaiFai"
                className="pl-10 md:pl-12 h-10 md:h-12 bg-card border-border text-foreground placeholder:text-muted-foreground rounded-xl text-sm md:text-base"
              />
            </div>
          </div>

          {/* Category Tabs */}
          <div className="flex items-center justify-center gap-1 md:gap-2 mb-4 md:mb-8 flex-wrap px-3 md:px-0">
            {categories.map((category) => (
              <button
                key={category}
                onClick={() => setActiveCategory(category)}
                className={cn(
                  "px-3 md:px-4 py-1.5 md:py-2 rounded-full text-xs md:text-sm font-medium transition-all",
                  activeCategory === category
                    ? "bg-primary text-primary-foreground"
                    : "bg-card border border-border text-foreground hover:bg-muted",
                )}
              >
                {category}
              </button>
            ))}
          </div>

          {/* Results Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 md:gap-4 max-w-6xl mx-auto px-3 md:px-0">
            {isLoading ? (
              <div className="col-span-full text-center py-8 text-muted-foreground">
                Loading...
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="col-span-full text-center py-8 text-muted-foreground">
                No items found
              </div>
            ) : (
              filteredItems.map((item) => {
                const handleItemClick = () => {
                  if (item.type === "AI Model") {
                    // Extract model ID from the item id (remove 'model-' prefix)
                    const modelId = item.id.replace("model-", "");
                    setSelectedModel(modelId);
                  }
                };
                return (
                  <div
                    key={item.id}
                    onClick={handleItemClick}
                    className={cn(
                      "bg-card border border-border rounded-xl p-4 hover:shadow-soft transition-all duration-200 cursor-pointer hover:border-primary/30",
                      item.type === "AI Model" &&
                        selectedModel === item.id.replace("model-", "") &&
                        "border-primary ring-2 ring-primary/20",
                    )}
                  >
                    <div className="mb-3">{getIcon(item.icon)}</div>
                    <h3 className="font-semibold text-foreground mb-1">
                      {item.title}
                    </h3>
                    <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                      {item.description}
                    </p>
                    <span className="inline-block px-3 py-1 rounded-full text-xs font-medium bg-primary text-primary-foreground">
                      {item.type}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </main>

        <div className="md:pb-2">
          <ChatInput key={selectedModel} initialModel={selectedModel} />
        </div>
      </div>
    </div>
  );
};

export default Explore;
