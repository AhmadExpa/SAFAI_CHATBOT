import { API_BASE_URL } from "@/config/environment";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    full_name: string;
  };
}

export interface SignupResponse {
  user_id: string;
  email: string;
  full_name: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
}

// Generic fetch wrapper with auth header
async function fetchWithAuth(
  endpoint: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });
}

// Register a new user
export async function registerUser(
  email: string,
  password: string,
  full_name: string,
): Promise<SignupResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
      full_name,
    }),
  });

  if (!response.ok) {
    let errorMessage = "Registration failed";
    try {
      const error = await response.json();
      console.error("Backend Error:", error);
      errorMessage = error.detail || error.message || errorMessage;
    } catch (e) {
      console.error("Failed to parse error response");
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

// Login user
export async function loginUser(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
    }),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Login failed" }));
    throw new Error(error.detail || "Login failed");
  }

  return response.json();
}

// Get current user (optional - for validating token)
export async function getCurrentUser(token: string): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch user");
  }

  return response.json();
}

// Generic API call helper method
export async function apiCall(
  endpoint: string,
  options: RequestInit = {},
): Promise<Response> {
  return fetchWithAuth(endpoint, options);
}

// Set authorization header for all requests
export function setAuthToken(token: string) {
  localStorage.setItem("auth_token", token);
}

// Get authorization token
export function getAuthToken(): string | null {
  return localStorage.getItem("auth_token");
}

// Clear authorization token
export function clearAuthToken() {
  localStorage.removeItem("auth_token");
}

// Chat message type
export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  project_id?: string;
  conversation_id?: string;
  personality_id?: string;
}

export interface MultiModelChatRequest {
  models: string[];
  messages: ChatMessage[];
  project_id?: string;
  conversation_id?: string;
  personality_id?: string;
}

// Map frontend model IDs to backend endpoint paths
function getModelEndpoint(modelId: string): string {
  const modelEndpointMap: Record<string, string> = {
    "gpt-4.1": "/openai/gpt4-1/chat",
    "gpt-4": "/openai/gpt-4/chat",
    "gpt-4.1-mini": "/openai/gpt-4-1-mini/chat",
    "gpt-4.1-nano": "/openai/gpt-4-1-nano/chat",
    "gpt-4o": "/openai/gpt-4o/chat",
    "o4-mini": "/openai/o4-mini/chat",
    "o3-mini": "/openai/o3-mini/chat",
    "gpt-image-1": "/openai/gpt-image-1/chat",
    "deepseek-v3": "/openai/deepseek-v3/chat",
    "deepseek-r1": "/openai/deepseek-r1/chat",
    "grok-2": "/openai/grok-3/chat",
    "grok-3": "/openai/grok-3/chat",
    "grok-4": "/openai/grok-4/chat",
    "qwen-72b": "/openai/qwen1/chat",
    "qwen-max": "/openai/qwen2/chat",
    "k-1": "/moonshot/k1/chat",
  };
  return modelEndpointMap[modelId] || `/openai/${modelId}/chat`;
}

// Single model chat - returns SSE stream
export async function sendChatMessage(
  modelName: string,
  request: ChatRequest,
): Promise<Response> {
  const token = getAuthToken();
  const endpoint = getModelEndpoint(modelName);

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Chat request failed" }));
    throw new Error(error.detail || "Chat request failed");
  }

  return response;
}

// Multi-model chat - returns SSE stream with interleaved responses
export async function sendMultiModelChat(
  request: MultiModelChatRequest,
): Promise<Response> {
  const token = getAuthToken();

  const response = await fetch(`${API_BASE_URL}/api/multi-model/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Multi-model chat failed" }));
    throw new Error(error.detail || "Multi-model chat failed");
  }

  return response;
}

// Parse SSE stream and handle chunks
export async function* parseSSEStream(
  response: Response,
): AsyncGenerator<{ model?: string; content: string; done?: boolean }> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let streamMode: "unknown" | "sse" | "plain" = "unknown";

  const stripConversationMetadata = (text: string) => {
    const metadataIndex = text.indexOf("<!--CONVERSATION_ID:");
    return metadataIndex >= 0 ? text.slice(0, metadataIndex) : text;
  };

  const parseDataLine = (
    line: string,
  ): { model?: string; content: string; done?: boolean } | null => {
    const data = line.slice(6).trim();
    if (data === "[DONE]") {
      return { content: "", done: true };
    }
    try {
      const parsed = JSON.parse(data);
      return {
        model: parsed.model,
        content: parsed.content || parsed.choices?.[0]?.delta?.content || "",
        done: parsed.done || false,
      };
    } catch {
      return data ? { content: data, done: false } : null;
    }
  };

  const resolveStreamMode = (text: string) => {
    if (streamMode !== "unknown") return;

    const trimmed = text.trimStart();
    if (!trimmed) return;

    const ssePrefixes = ["data:", "event:", "id:", "retry:", ":"];
    const couldBecomeSse = ssePrefixes.some(
      (prefix) => prefix.startsWith(trimmed) || trimmed.startsWith(prefix),
    );

    if (trimmed.startsWith("data:")) {
      streamMode = "sse";
    } else if (!couldBecomeSse || trimmed.length >= 6 || trimmed.includes("\n")) {
      streamMode = "plain";
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const decoded = decoder.decode(value, { stream: true });
    buffer += decoded;
    resolveStreamMode(buffer);

    if (streamMode === "plain") {
      const content = stripConversationMetadata(decoded);
      if (content) {
        yield { content, done: false };
      }
      continue;
    }

    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const parsedLine = parseDataLine(line);
        if (!parsedLine) continue;
        yield parsedLine;
        if (parsedLine.done) {
          return;
        }
      } else if (streamMode === "unknown" && line.trim()) {
        streamMode = "plain";
        const content = stripConversationMetadata(line);
        if (content) yield { content, done: false };
      }
    }
  }

  const remaining = stripConversationMetadata(buffer.trimEnd());
  if (remaining) {
    if (remaining.startsWith("data: ")) {
      const parsedLine = parseDataLine(remaining);
      if (parsedLine) yield parsedLine;
    } else {
      yield { content: remaining, done: false };
    }
  }
}

// ============ PROJECTS API ============

export interface Project {
  project_id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateProjectRequest {
  name: string;
  description?: string;
}

export interface UpdateProjectRequest {
  name?: string;
  description?: string;
}

// List all projects
export async function listProjects(): Promise<Project[]> {
  const response = await fetchWithAuth("/api/projects");
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch projects" }));
    throw new Error(error.detail || "Failed to fetch projects");
  }
  return response.json();
}

// Create a new project
export async function createProject(
  data: CreateProjectRequest,
): Promise<Project> {
  const response = await fetchWithAuth("/api/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to create project" }));
    throw new Error(error.detail || "Failed to create project");
  }
  return response.json();
}

// Get a single project
export async function getProject(projectId: string): Promise<Project> {
  const response = await fetchWithAuth(`/api/projects/${projectId}`);
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch project" }));
    throw new Error(error.detail || "Failed to fetch project");
  }
  return response.json();
}

// Update a project
export async function updateProject(
  projectId: string,
  data: UpdateProjectRequest,
): Promise<Project> {
  const response = await fetchWithAuth(`/api/projects/${projectId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to update project" }));
    throw new Error(error.detail || "Failed to update project");
  }
  return response.json();
}

// Delete a project
export async function deleteProject(projectId: string): Promise<void> {
  const response = await fetchWithAuth(`/api/projects/${projectId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to delete project" }));
    throw new Error(error.detail || "Failed to delete project");
  }
}

// ============ ENHANCED PROJECTS API ============

export interface ProjectContext {
  context?: string;
  goals?: string;
  decisions?: string;
  preferences?: string;
}

export interface ToolConfig {
  tool_name: string;
  tool_config: string;
  is_enabled: boolean;
}

// Get project context
export async function getProjectContext(
  projectId: string,
): Promise<ProjectContext> {
  const response = await fetchWithAuth(
    `/api/enhanced-projects/projects/${projectId}/context`,
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch project context" }));
    throw new Error(error.detail || "Failed to fetch project context");
  }
  return response.json();
}

// Update project context
export async function updateProjectContext(
  projectId: string,
  data: ProjectContext,
): Promise<ProjectContext> {
  const response = await fetchWithAuth(
    `/api/enhanced-projects/projects/${projectId}/context`,
    {
      method: "PUT",
      body: JSON.stringify(data),
    },
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to update project context" }));
    throw new Error(error.detail || "Failed to update project context");
  }
  return response.json();
}

// Configure tool for project
export async function configureProjectTool(
  projectId: string,
  config: ToolConfig,
): Promise<void> {
  const response = await fetchWithAuth(
    `/api/enhanced-projects/projects/${projectId}/tools`,
    {
      method: "POST",
      body: JSON.stringify(config),
    },
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to configure tool" }));
    throw new Error(error.detail || "Failed to configure tool");
  }
}

// ============ PROJECT FILES API ============

export interface ProjectFile {
  file_id: string;
  project_id?: string;
  filename: string;
  original_filename?: string;
  file_type?: string;
  file_size?: number;
  upload_order?: number;
  created_at?: string;
  file_content?: string | null;
  message?: string;
}

// List project files
export async function listProjectFiles(
  projectId: string,
): Promise<ProjectFile[]> {
  const response = await fetchWithAuth(`/api/projects/${projectId}/files`);
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch files" }));
    throw new Error(error.detail || "Failed to fetch files");
  }
  return response.json();
}

// Upload file to project
export async function uploadProjectFile(
  projectId: string,
  file: File,
): Promise<ProjectFile> {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/files`,
    {
      method: "POST",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: formData,
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to upload file" }));
    throw new Error(error.detail || "Failed to upload file");
  }
  return response.json();
}

// Get file content
export async function getFileContent(
  projectId: string,
  fileId: string,
): Promise<string> {
  const response = await fetchWithAuth(
    `/api/projects/${projectId}/files/${fileId}/content`,
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch file content" }));
    throw new Error(error.detail || "Failed to fetch file content");
  }
  return response.text();
}

// Delete project file
export async function deleteProjectFile(
  projectId: string,
  fileId: string,
): Promise<void> {
  const response = await fetchWithAuth(
    `/api/projects/${projectId}/files/${fileId}`,
    {
      method: "DELETE",
    },
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to delete file" }));
    throw new Error(error.detail || "Failed to delete file");
  }
}

// ============ CONVERSATIONS API ============

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Bubble {
  bubble_id: string;
  messages: ConversationMessage[];
}

export interface Conversation {
  conversation_id: string;
  title: string;
  created_at?: string;
  updated_at?: string;
  model_used?: string;
}

export interface ConversationDetail extends Conversation {
  bubbles: Bubble[];
}

export interface LibraryImage {
  image_url: string;
  conversation_id: string;
  created_at: string;
}

// List all conversations
export async function listConversations(): Promise<Conversation[]> {
  const response = await fetchWithAuth("/api/conversations");
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch conversations" }));
    throw new Error(error.detail || "Failed to fetch conversations");
  }
  return response.json();
}

// Get conversation with full history
export async function getConversation(
  conversationId: string,
): Promise<ConversationDetail> {
  const response = await fetchWithAuth(`/api/conversations/${conversationId}`);
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch conversation" }));
    throw new Error(error.detail || "Failed to fetch conversation");
  }
  return response.json();
}

// Delete a conversation
export async function deleteConversation(
  conversationId: string,
): Promise<void> {
  const response = await fetchWithAuth(`/api/conversations/${conversationId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to delete conversation" }));
    throw new Error(error.detail || "Failed to delete conversation");
  }
}

// Search conversations
export async function searchConversations(
  query: string,
): Promise<Conversation[]> {
  const response = await fetchWithAuth(
    `/api/conversations/search?q=${encodeURIComponent(query)}`,
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to search conversations" }));
    throw new Error(error.detail || "Failed to search conversations");
  }
  return response.json();
}

// Get library images
export async function getLibraryImages(): Promise<LibraryImage[]> {
  const response = await fetchWithAuth("/api/library/images");
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch library images" }));
    throw new Error(error.detail || "Failed to fetch library images");
  }
  return response.json();
}

// ============ WORKSPACES API ============

export interface Workspace {
  workspace_id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at?: string;
}

export interface CreateWorkspaceRequest {
  name: string;
  description?: string;
}

// List all workspaces
export async function listWorkspaces(): Promise<Workspace[]> {
  const response = await fetchWithAuth("/api/workspaces");
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch workspaces" }));
    throw new Error(error.detail || "Failed to fetch workspaces");
  }
  return response.json();
}

// Create a new workspace
export async function createWorkspace(
  data: CreateWorkspaceRequest,
): Promise<Workspace> {
  const response = await fetchWithAuth("/api/workspaces", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to create workspace" }));
    throw new Error(error.detail || "Failed to create workspace");
  }
  return response.json();
}

// Get a single workspace
export async function getWorkspace(workspaceId: string): Promise<Workspace> {
  const response = await fetchWithAuth(`/api/workspaces/${workspaceId}`);
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch workspace" }));
    throw new Error(error.detail || "Failed to fetch workspace");
  }
  return response.json();
}

// Delete a workspace
export async function deleteWorkspace(workspaceId: string): Promise<void> {
  const response = await fetchWithAuth(`/api/workspaces/${workspaceId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to delete workspace" }));
    throw new Error(error.detail || "Failed to delete workspace");
  }
}

// ============ GOOGLE OAUTH ============

// Get Google OAuth URL - redirects to Google login
export function getGoogleOAuthUrl(): string {
  return `${API_BASE_URL}/auth/google/login`;
}

// ============ AI PERSONALITIES API ============

export interface Personality {
  id: string;
  name: string;
  description?: string;
  system_prompt?: string;
  avatar_emoji?: string;
  is_active?: boolean;
}

export interface CreatePersonalityRequest {
  name: string;
  description?: string;
  system_prompt: string;
  avatar_emoji?: string;
}

// List all personalities
export async function listPersonalities(
  activeOnly: boolean = true,
): Promise<Personality[]> {
  const response = await fetchWithAuth(
    `/api/personalities/?active_only=${activeOnly}`,
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch personalities" }));
    throw new Error(error.detail || "Failed to fetch personalities");
  }
  return response.json();
}

// Get a single personality
export async function getPersonality(id: string): Promise<Personality> {
  const response = await fetchWithAuth(`/api/personalities/${id}`);
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch personality" }));
    throw new Error(error.detail || "Failed to fetch personality");
  }
  return response.json();
}

// Create a new personality (Admin)
export async function createPersonality(
  data: CreatePersonalityRequest,
): Promise<Personality> {
  const response = await fetchWithAuth("/api/personalities/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to create personality" }));
    throw new Error(error.detail || "Failed to create personality");
  }
  return response.json();
}

// ============ RESPONSE COMMENTS API ============

export interface ResponseComment {
  comment_id: string;
  response_id: string;
  comment_text: string;
  created_at: string;
}

export interface AddCommentRequest {
  response_id: string;
  comment_text: string;
}

export interface CreateModelResponseRequest {
  message_id: string;
  model_name: string;
  content: string;
  response_order?: number;
}

export interface ModelResponse {
  response_id: string;
  message_id: string;
  model_name: string;
  content: string;
  response_order: number;
  created_at: string;
  comments?: ResponseComment[];
}

// Create a model response (to get a response_id for comments)
export async function createModelResponse(
  data: CreateModelResponseRequest,
): Promise<{ response_id: string; message: string }> {
  const response = await fetchWithAuth("/api/model-responses", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to create model response" }));
    throw new Error(error.detail || "Failed to create model response");
  }
  return response.json();
}

// Get model responses for a message (with comments)
export async function getModelResponses(
  messageId: string,
): Promise<ModelResponse[]> {
  const response = await fetchWithAuth(
    `/api/model-responses/message/${messageId}`,
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch model responses" }));
    throw new Error(error.detail || "Failed to fetch model responses");
  }
  return response.json();
}

// Add a comment to a response
export async function addResponseComment(
  data: AddCommentRequest,
): Promise<ResponseComment> {
  const response = await fetchWithAuth("/api/comments", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to add comment" }));
    throw new Error(error.detail || "Failed to add comment");
  }
  return response.json();
}

// Get comments for a response
export async function getResponseComments(
  responseId: string,
): Promise<ResponseComment[]> {
  const response = await fetchWithAuth(`/api/comments/response/${responseId}`);
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to fetch comments" }));
    throw new Error(error.detail || "Failed to fetch comments");
  }
  return response.json();
}
