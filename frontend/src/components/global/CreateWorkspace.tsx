import { useState } from "react";
import { ChevronDown, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getAllModels } from "@/lib/models";
import { createWorkspace } from "@/lib/api";
import { useNavigate } from "react-router-dom";

interface CreateWorkspaceComponentProps {
  onClose?: () => void;
  onSuccess?: () => void;
}

// Get all models from shared configuration
const aiModels = getAllModels();

export function CreateWorkspaceComponent({
  onClose,
  onSuccess,
}: CreateWorkspaceComponentProps) {
  const [workspaceName, setWorkspaceName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedModel, setSelectedModel] = useState("gpt-4.1");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleCreate = async () => {
    if (!workspaceName.trim()) return;

    setIsLoading(true);
    setError("");

    try {
      await createWorkspace({
        name: workspaceName.trim(),
        description: description.trim() || undefined,
      });
      setWorkspaceName("");
      setDescription("");
      onSuccess?.();
      onClose?.();
      navigate("/workspace");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create workspace",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleCreate();
    }
  };

  return (
    <div className="w-full max-w-[600px] mt-2 md:mt-5 mx-auto bg-card border border-border rounded-lg shadow-lg">
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-foreground">
            Create Your Workspace
          </h2>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 hover:bg-muted rounded-md transition-colors"
              aria-label="Close"
            >
              <span className="sr-only">Close</span>
              <svg
                className="w-5 h-5 text-muted-foreground"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}
        </div>

        <div className="space-y-6">
          {/* Error Message */}
          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive text-sm">
              {error}
            </div>
          )}

          {/* Workspace Name */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Workspace Name
            </label>
            <Input
              value={workspaceName}
              onChange={(e) => setWorkspaceName(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g: Saifai Studio"
              className="h-11 bg-background border-border text-foreground placeholder:text-muted-foreground text-base"
              autoFocus
              disabled={isLoading}
            />
          </div>

          {/* Description */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Description (Optional)
            </label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="short summary........"
              className="min-h-[80px] bg-background border-border text-foreground placeholder:text-muted-foreground resize-none text-base"
              disabled={isLoading}
            />
          </div>

          {/* AI Model Selector */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Select AI Model
            </label>
            <Select
              value={selectedModel}
              onValueChange={setSelectedModel}
              disabled={isLoading}
            >
              <SelectTrigger className="h-11 bg-background border-border text-foreground text-base">
                <SelectValue />
                <ChevronDown className="h-4 w-4 opacity-50" />
              </SelectTrigger>
              <SelectContent className="bg-card border-border max-h-[300px]">
                {aiModels.map((model) => (
                  <SelectItem
                    key={model.id}
                    value={model.id}
                    className="text-foreground hover:bg-muted text-base"
                  >
                    {model.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Create Button */}
          <div className="flex justify-center pt-2">
            <Button
              onClick={handleCreate}
              disabled={!workspaceName.trim() || isLoading}
              className="bg-primary text-primary-foreground hover:brightness-110 px-10 py-2.5 h-auto text-base"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create Workspace"
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
