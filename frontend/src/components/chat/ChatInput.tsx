import { useState } from "react";
import {
  Plus,
  Globe,
  Paperclip,
  Scissors,
  Image,
  Mic,
  PenTool,
  Sparkles,
  Smile,
  Send,
  Loader2,
} from "lucide-react";
import { ModelSelector } from "./ModelSelector";
import { PersonalitySelector } from "./PersonalitySelector";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";

interface ChatInputProps {
  onSendMessage?: (
    message: string,
    model: string,
    isMultimodal: boolean,
    personalityId?: string | null,
    selectedModels?: string[],
  ) => Promise<void>;
  isLoading?: boolean;
  disabled?: boolean;
  initialModel?: string;
}

export function ChatInput({
  onSendMessage,
  isLoading = false,
  disabled = false,
  initialModel,
}: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [selectedModel, setSelectedModel] = useState(initialModel || "gpt-4.1");
  const [selectedModels, setSelectedModels] = useState<string[]>([
    initialModel || "gpt-4.1",
  ]);
  const [isMultimodal, setIsMultimodal] = useState(true);
  const [selectedPersonality, setSelectedPersonality] = useState<string | null>(
    null,
  );
  const navigate = useNavigate();

  // Sync selectedModels with selectedModel when multimodal is toggled off
  const handleMultimodalToggle = () => {
    if (isMultimodal) {
      // Switching to single mode - use first selected model or default
      if (selectedModels.length > 0) {
        setSelectedModel(selectedModels[0]);
      }
    } else {
      // Switching to multimodal - initialize with current single selection
      setSelectedModels([selectedModel]);
    }
    setIsMultimodal(!isMultimodal);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const hasModelSelected = isMultimodal
      ? selectedModels.length > 0
      : !!selectedModel;
    if (message.trim() && !isLoading && !disabled && hasModelSelected) {
      const currentMessage = message;
      setMessage("");
      if (onSendMessage) {
        await onSendMessage(
          currentMessage,
          isMultimodal ? selectedModels[0] : selectedModel,
          isMultimodal,
          selectedPersonality,
          isMultimodal ? selectedModels : [selectedModel],
        );
      } else {
        // Navigate to home page with initial message
        navigate("/", {
          state: {
            initialMessage: currentMessage,
            model: isMultimodal ? selectedModels[0] : selectedModel,
            isMultimodal,
            personalityId: selectedPersonality,
            selectedModels: isMultimodal ? selectedModels : [selectedModel],
          },
        });
      }
    }
  };

  const toolbarIcons = [
    { icon: Globe, label: "Web search" },
    { icon: Paperclip, label: "Attach file" },
    { icon: Scissors, label: "Cut" },
    { icon: Image, label: "Image" },
    { icon: Mic, label: "Voice" },
    { icon: PenTool, label: "Draw" },
    { icon: Sparkles, label: "Effects" },
    { icon: Smile, label: "Emoji" },
  ];

  return (
    <div className="w-full max-w-5xl mx-auto md:mb-2 bg-card/50 z-15 relative rounded-md py-3 md:py-4 px-3 md:px-8">
      <form onSubmit={handleSubmit} className="space-y-2 md:space-y-3">
        {/* Input Field */}
        <div className="relative bg-card border border-border rounded-xl md:rounded-2xl shadow-card overflow-hidden">
          <div className="flex items-center gap-2 md:gap-6  pl-2 md:pl-4">
            <button
              type="button"
              className="p-1 md:p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors flex-shrink-0"
              aria-label="Add attachment"
            >
              <Plus className="w-4 md:w-5 h-4 md:h-5" />
            </button>
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Ask me anything..."
              className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none text-sm min-w-0"
            />
            <button
              type="submit"
              disabled={isLoading || disabled || !message.trim()}
              className={cn(
                "p-2  md:px-3 px-3  bg-primary transition-all flex-shrink-0 ",

                "bg-primary text-primary hover:brightness-110",
                (isLoading || disabled || !message.trim()) &&
                  "opacity-50 cursor-not-allowed",
              )}
              aria-label="Send message"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 text-black animate-spin" />
              ) : (
                <Send className="w-4 h-4 text-black " />
              )}
            </button>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center justify-center gap-1 md:gap-2 flex-wrap">
          {/* Multimodal Toggle */}
          <div className="flex items-center gap-1 md:gap-2 mr-1 md:mr-2">
            <button
              type="button"
              onClick={handleMultimodalToggle}
              className={cn(
                "relative w-9 md:w-10 h-4 md:h-5 rounded-full transition-colors flex-shrink-0",
                isMultimodal ? "bg-primary" : "bg-muted",
              )}
              role="switch"
              aria-checked={isMultimodal}
              aria-label="Toggle multimodal"
            >
              <span
                className={cn(
                  "absolute top-0.5 left-0.5 w-3 md:w-4 h-3 md:h-4 rounded-full bg-white transition-transform shadow-sm",
                  isMultimodal && "translate-x-[18px] md:translate-x-5",
                )}
              />
            </button>
            <span className="text-[10px] md:text-xs text-muted-foreground font-medium hidden sm:inline">
              Multimodal
            </span>
          </div>

          {/* Model Selector */}
          <ModelSelector
            selectedModel={selectedModel}
            selectedModels={selectedModels}
            onModelSelect={setSelectedModel}
            onModelsSelect={setSelectedModels}
            isMultimodal={isMultimodal}
          />

          {/* Personality Selector */}
          <PersonalitySelector
            selectedPersonality={selectedPersonality}
            onPersonalitySelect={setSelectedPersonality}
          />

          {/* Toolbar Icons */}
          <div className="flex items-center gap-0.5 md:gap-1 ml-1 md:ml-2 overflow-x-auto">
            {toolbarIcons.map(({ icon: Icon, label }) => (
              <button
                key={label}
                type="button"
                className="p-1.5 md:p-2 rounded-lg text-foreground hover:bg-card transition-colors flex-shrink-0"
                aria-label={label}
              >
                <Icon className="w-3.5 md:w-4 h-3.5 md:h-4" />
              </button>
            ))}
          </div>
        </div>
      </form>
    </div>
  );
}
