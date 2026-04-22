import { useState, useRef, useEffect, useLayoutEffect } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Checkbox } from "@/components/ui/checkbox";
import { modelGroups, getGroupByModelId } from "@/lib/models";

interface ModelSelectorProps {
  selectedModel: string;
  selectedModels: string[];
  onModelSelect: (modelId: string) => void;
  onModelsSelect: (modelIds: string[]) => void;
  isMultimodal: boolean;
}

export function ModelSelector({
  selectedModel,
  selectedModels,
  onModelSelect,
  onModelsSelect,
  isMultimodal,
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedGroupId, setExpandedGroupId] = useState<string | null>(null);
  const [expandedGroupPosition, setExpandedGroupPosition] = useState<{
    top: number;
    left: number;
  } | null>(null);

  const [dropdownHeight, setDropdownHeight] = useState<number | "auto">("auto");
  const [modelsDropdownHeight, setModelsDropdownHeight] = useState<
    number | "auto"
  >("auto");

  const [isMobile, setIsMobile] = useState(false);

  const dropdownRef = useRef<HTMLDivElement>(null);
  const groupsDropdownRef = useRef<HTMLDivElement>(null);
  const modelsDropdownRef = useRef<HTMLDivElement>(null);
  const dropdownContentRef = useRef<HTMLDivElement>(null);
  const groupItemRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // detect mobile
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  // main dropdown height
  useLayoutEffect(() => {
    if (isOpen && dropdownContentRef.current) {
      const contentHeight = dropdownContentRef.current.scrollHeight;
      const maxHeight = Math.min(contentHeight, window.innerHeight * 0.6);
      setDropdownHeight(maxHeight);
    }
  }, [isOpen]);

  // models dropdown height
  useLayoutEffect(() => {
    if (expandedGroupId && modelsDropdownRef.current) {
      const contentHeight = modelsDropdownRef.current.scrollHeight;
      const maxHeight = Math.min(contentHeight, window.innerHeight * 0.6);
      setModelsDropdownHeight(maxHeight);
    }
  }, [expandedGroupId]);

  // position submenu ONLY desktop
  useLayoutEffect(() => {
    if (isMobile) return;

    if (!isOpen || !expandedGroupId) {
      setExpandedGroupPosition(null);
      return;
    }

    if (groupsDropdownRef.current) {
      const groupElement = groupItemRefs.current.get(expandedGroupId);
      if (groupElement) {
        const groupRect = groupElement.getBoundingClientRect();
        const groupsRect = groupsDropdownRef.current.getBoundingClientRect();

        const gap = 8;
        const top = groupRect.top;
        const left = groupsRect.right + gap;

        setExpandedGroupPosition({ top, left });
      }
    }
  }, [expandedGroupId, isOpen, isMobile]);

  // resize / scroll reposition desktop only
  useEffect(() => {
    if (!isOpen || isMobile) return;
    const handler = () => setExpandedGroupId((prev) => prev);
    window.addEventListener("resize", handler);
    window.addEventListener("scroll", handler, true);
    return () => {
      window.removeEventListener("resize", handler);
      window.removeEventListener("scroll", handler, true);
    };
  }, [isOpen, isMobile]);

  // click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setExpandedGroupId(null);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () =>
        document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  // open selected model group
  useEffect(() => {
    const modelToCheck =
      isMultimodal && selectedModels.length > 0
        ? selectedModels[0]
        : selectedModel;
    const group = getGroupByModelId(modelToCheck);
    if (group && isOpen) setExpandedGroupId(group.id);
  }, [selectedModel, selectedModels, isOpen, isMultimodal]);

  const toggleGroup = (groupId: string) => {
    setExpandedGroupId((prev) => (prev === groupId ? null : groupId));
  };

  const handleModelClick = (modelId: string) => {
    if (isMultimodal) {
      // Multi-select mode
      const newSelectedModels = selectedModels.includes(modelId)
        ? selectedModels.filter((id) => id !== modelId)
        : [...selectedModels, modelId];
      onModelsSelect(newSelectedModels);
      // Don't close dropdown in multimodal mode to allow multiple selections
    } else {
      // Single-select mode
      onModelSelect(modelId);
      setIsOpen(false);
      setExpandedGroupId(null);
    }
  };

  const isModelSelected = (modelId: string) => {
    if (isMultimodal) {
      return selectedModels.includes(modelId);
    }
    return selectedModel === modelId;
  };

  const getDisplayText = () => {
    if (isMultimodal) {
      if (selectedModels.length === 0) return "Select models";
      if (selectedModels.length === 1) return selectedModels[0];
      return `${selectedModels.length} models`;
    }
    return selectedModel;
  };

  const getExpandedGroup = () =>
    modelGroups.find((g) => g.id === expandedGroupId);

  const expandedGroup = getExpandedGroup();

  const renderIcon = (icon: string, className = "w-5 h-5") => {
    if (icon.includes("/") || icon.includes(".")) {
      return <img src={icon} className={cn("object-contain", className)} />;
    }
    return <span className={className}>{icon}</span>;
  };

  const isGroupSelected = (groupId: string) => {
    const group = modelGroups.find((g) => g.id === groupId);
    if (isMultimodal) {
      return group?.models.some((m) => selectedModels.includes(m.id));
    }
    return group?.models.some((m) => m.id === selectedModel);
  };

  return (
    <div className="relative z-[40]" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 bg-card border border-border rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors min-w-[140px] justify-between"
      >
        <span>{getDisplayText()}</span>
        <ChevronDown className={cn("w-4 h-4", isOpen && "rotate-180")} />
      </button>

      {isOpen && (
        <>
          {/* GROUPS */}
          <div
            ref={groupsDropdownRef}
            className="absolute bottom-full left-0 mb-2 w-[280px] bg-card border border-border rounded-lg shadow-lg overflow-hidden"
          >
            <div ref={dropdownContentRef} className="overflow-y-auto">
              {modelGroups.map((group) => {
                const isExpanded = expandedGroupId === group.id;
                const isSelected = isGroupSelected(group.id);

                return (
                  <div
                    key={group.id}
                    ref={(el) => el && groupItemRefs.current.set(group.id, el)}
                  >
                    <div
                      onClick={() => toggleGroup(group.id)}
                      className={cn(
                        "flex items-center gap-3 px-4 py-2.5 text-sm cursor-pointer",
                        isSelected ? "bg-muted/30" : "hover:bg-muted/30",
                      )}
                    >
                      <Checkbox checked={isSelected} />
                      {renderIcon(group.icon, "w-4 h-4")}
                      <span className="flex-1">{group.name}</span>
                      <ChevronRight
                        className={cn("w-4 h-4", isExpanded && "rotate-90")}
                      />
                    </div>

                    {/* MOBILE ACCORDION */}
                    {isMobile && isExpanded && (
                      <div className="ml-6">
                        {group.models.map((model) => (
                          <div
                            key={model.id}
                            onClick={() => handleModelClick(model.id)}
                            className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-muted/30"
                          >
                            <Checkbox checked={isModelSelected(model.id)} />
                            {model.name}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* DESKTOP FLOATING MODELS */}
          {!isMobile && expandedGroup && expandedGroupPosition && (
            <div
              ref={modelsDropdownRef}
              className="fixed bg-card border border-border rounded-lg shadow-lg overflow-hidden z-[70]"
              style={{
                top: expandedGroupPosition.top,
                left: expandedGroupPosition.left,
                width: "250px",
                maxHeight: "60vh",
              }}
            >
              <div className="overflow-y-auto">
                {expandedGroup.models.map((model) => (
                  <div
                    key={model.id}
                    onClick={() => handleModelClick(model.id)}
                    className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-muted/30"
                  >
                    <Checkbox checked={isModelSelected(model.id)} />
                    {model.name}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
