import { useState } from "react";
import { Folder, LightbulbIcon, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { createProject } from "@/lib/api";
import { useNavigate } from "react-router-dom";

interface CreateProjectComponentProps {
  onClose?: () => void;
  onSuccess?: () => void;
}

export function CreateProjectComponent({
  onClose,
  onSuccess,
}: CreateProjectComponentProps) {
  const [projectName, setProjectName] = useState("");
  const [description, setDescription] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleCreate = async () => {
    if (!projectName.trim()) return;

    setIsLoading(true);
    setError("");

    try {
      await createProject({
        name: projectName.trim(),
        description: description.trim() || undefined,
      });
      setProjectName("");
      setDescription("");
      onSuccess?.();
      onClose?.();
      navigate("/library");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
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
    <div className="w-full max-w-[1000px] md:mt-10 mt-6 mx-auto bg-card border border-border rounded-lg shadow-lg">
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-foreground">
            Create Project
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

          {/* Name Input */}
          <div className="relative">
            <Folder className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter Project Name...."
              className="pl-10 h-11 bg-background border-border text-foreground placeholder:text-muted-foreground text-base"
              autoFocus
              disabled={isLoading}
            />
          </div>

          {/* Description Input */}
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Project description (optional)"
            className="bg-background border-border text-foreground placeholder:text-muted-foreground text-base min-h-[80px]"
            disabled={isLoading}
          />

          {/* Description */}
          <div className="flex items-start gap-4 p-5 bg-muted/30 rounded-lg">
            <LightbulbIcon className="w-5 h-5 text-muted-foreground mt-0.5 flex-shrink-0" />
            <p className="text-sm text-muted-foreground leading-relaxed">
              Projects keep chats, files, and custom instructions in one place.
              Use them for ongoing work, or just to keep things tidy.
            </p>
          </div>

          {/* Create Button */}
          <div className="flex justify-center pt-2">
            <Button
              onClick={handleCreate}
              disabled={!projectName.trim() || isLoading}
              className="bg-primary text-primary-foreground hover:brightness-110 px-10 py-2.5 h-auto text-base rounded-xl"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create Project"
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
