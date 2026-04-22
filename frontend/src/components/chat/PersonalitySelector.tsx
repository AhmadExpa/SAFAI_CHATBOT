import { useState, useEffect } from "react";
import { listPersonalities, Personality } from "@/lib/api";
import { Bot, ChevronDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

interface PersonalitySelectorProps {
  selectedPersonality: string | null;
  onPersonalitySelect: (personalityId: string | null) => void;
}

export function PersonalitySelector({
  selectedPersonality,
  onPersonalitySelect,
}: PersonalitySelectorProps) {
  const [personalities, setPersonalities] = useState<Personality[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadPersonalities = async () => {
      try {
        const data = await listPersonalities(true);
        setPersonalities(data);
      } catch (error) {
        console.error("Failed to load personalities:", error);
      } finally {
        setLoading(false);
      }
    };
    loadPersonalities();
  }, []);

  const selected = personalities.find((p) => p.id === selectedPersonality);

  if (loading) {
    return (
      <div className="flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground">
        <Bot className="w-3 h-3" />
        Loading...
      </div>
    );
  }

  if (personalities.length === 0) {
    return null; // Don't show if no personalities available
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            "flex items-center gap-1 px-2 py-1 rounded-lg text-xs",
            "bg-muted hover:bg-muted/80 transition-colors",
            selectedPersonality && "bg-primary/10 text-primary"
          )}
        >
          <span className="text-base">{selected?.avatar_emoji || "🤖"}</span>
          <span className="hidden sm:inline max-w-[80px] truncate">
            {selected?.name || "Default"}
          </span>
          <ChevronDown className="w-3 h-3" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-48">
        <DropdownMenuItem
          onClick={() => onPersonalitySelect(null)}
          className={cn(!selectedPersonality && "bg-accent")}
        >
          <span className="mr-2">🤖</span>
          <span>Default</span>
        </DropdownMenuItem>
        {personalities.map((personality) => (
          <DropdownMenuItem
            key={personality.id}
            onClick={() => onPersonalitySelect(personality.id)}
            className={cn(selectedPersonality === personality.id && "bg-accent")}
          >
            <span className="mr-2">{personality.avatar_emoji || "🤖"}</span>
            <div className="flex flex-col">
              <span className="font-medium">{personality.name}</span>
              {personality.description && (
                <span className="text-xs text-muted-foreground truncate max-w-[140px]">
                  {personality.description}
                </span>
              )}
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
