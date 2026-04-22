// Shared models configuration for frontend and backend consistency

import chatGPT from "../assets/chatgpt.png";
import deepseek from "../assets/deepseek.png";
import qwen from "../assets/qwen.png";
import grok from "../assets/grok.png";

export interface Model {
  id: string;
  name: string;
  icon?: string;
  multimodal: boolean; // 🔥 IMPORTANT
}

export interface ModelGroup {
  id: string;
  name: string;
  icon: string;
  models: Model[];
}

export const modelGroups: ModelGroup[] = [
  {
    id: "gpt",
    name: "GPT",
    icon: chatGPT,
    models: [
      { id: "gpt-4.1", name: "GPT - 4.1", multimodal: true },
      { id: "gpt-4", name: "GPT - 4", multimodal: false },
      { id: "gpt-4.1-mini", name: "GPT - 4.1 mini", multimodal: false },
      { id: "gpt-4.1-nano", name: "GPT - 4.1 nano", multimodal: false },
      { id: "gpt-4o", name: "GPT - 4.0", multimodal: true },
      { id: "o4-mini", name: "04 - mini", multimodal: false },
      { id: "o3-mini", name: "03 - mini", multimodal: false },
      { id: "gpt-image-1", name: "GPT - image 1", multimodal: true },
    ],
  },

  {
    id: "grok",
    name: "Grok",
    icon: grok,
    models: [
      { id: "grok-2", name: "Grok 2", multimodal: false },
      { id: "grok-3", name: "Grok 3", multimodal: true },
    ],
  },

  {
    id: "deepseek",
    name: "Deepseek",
    icon: deepseek,
    models: [
      { id: "deepseek-v3", name: "Deepseek V3", multimodal: false },
      { id: "deepseek-r1", name: "Deepseek R1", multimodal: false },
    ],
  },

  {
    id: "qwen",
    name: "Qwen",
    icon: qwen,
    models: [
      { id: "qwen-72b", name: "Qwen 72B", multimodal: false },
      { id: "qwen-max", name: "Qwen Max", multimodal: true },
    ],
  },

  {
    id: "k",
    name: "K",
    icon: "⚡",
    models: [
      { id: "k-1", name: "K-1", multimodal: false },
    ],
  },
];

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */

// Get model by ID
export function getModelById(modelId: string): Model | undefined {
  for (const group of modelGroups) {
    const model = group.models.find((m) => m.id === modelId);
    if (model) return model;
  }
  return undefined;
}

// Get model group by model ID
export function getGroupByModelId(modelId: string): ModelGroup | undefined {
  return modelGroups.find((group) =>
    group.models.some((m) => m.id === modelId)
  );
}

// Get all models (flat)
export function getAllModels(): Model[] {
  return modelGroups.flatMap((group) => group.models);
}

// 🔥 Optional helper (VERY useful)
export function isModelMultimodal(modelId: string): boolean {
  return getModelById(modelId)?.multimodal ?? false;
}
