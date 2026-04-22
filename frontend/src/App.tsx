import React from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { ThemeProvider } from "@/hooks/useTheme";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import Signup from "./pages/Signup";
import Login from "./pages/Login";
import Index from "./pages/Index";
import Library from "./pages/Library";
import Explore from "./pages/Explore";
import Codex from "./pages/Codex";
import Chat from "./pages/Chat";
import Templates from "./pages/Templates";
import Workspace from "./pages/Workspace";
import CreateProject from "./pages/createProject";
import CreateWorkspace from "./pages/createWorkspace";
import ProjectDetail from "@/pages/ProjectDetail";
import ChatDetail from "@/pages/ChatDetail";

const queryClient = new QueryClient();

// Wrapper component to handle logout with navigation
const PageWrapper = ({
  Component,
}: {
  Component: React.ComponentType<{ onLogout: () => void }>;
}) => {
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return <Component onLogout={handleLogout} />;
};

const AppRoutes = () => (
  <Routes>
    <Route path="/signup" element={<Signup />} />
    <Route path="/login" element={<Login />} />
    <Route
      path="/"
      element={
        <ProtectedRoute>
          <PageWrapper Component={Index} />
        </ProtectedRoute>
      }
    />
    <Route
      path="/library"
      element={
        <ProtectedRoute>
          <PageWrapper Component={Library} />
        </ProtectedRoute>
      }
    />
    <Route
      path="/explore"
      element={
        <ProtectedRoute>
          <PageWrapper Component={Explore} />
        </ProtectedRoute>
      }
    />
    <Route
      path="/codex"
      element={
        <ProtectedRoute>
          <PageWrapper Component={Codex} />
        </ProtectedRoute>
      }
    />
    <Route
      path="/chat"
      element={
        <ProtectedRoute>
          <PageWrapper Component={Chat} />
        </ProtectedRoute>
      }
    />
    <Route
      path="/templates"
      element={
        <ProtectedRoute>
          <PageWrapper Component={Templates} />
        </ProtectedRoute>
      }
    />
    <Route
      path="/workspace"
      element={
        <ProtectedRoute>
          <PageWrapper Component={Workspace} />
        </ProtectedRoute>
      }
    />
    <Route
      path="/createProject"
      element={
        <ProtectedRoute>
          <PageWrapper Component={CreateProject} />
        </ProtectedRoute>
      }
    />
    <Route
      path="/createWorkspace"
      element={
        <ProtectedRoute>
          <PageWrapper Component={CreateWorkspace} />
        </ProtectedRoute>
      }
    />
    <Route
      path="/project/:projectId"
      element={
        <ProtectedRoute>
          <PageWrapper Component={ProjectDetail} />
        </ProtectedRoute>
      }
    />
    <Route
      path="/chat/:conversationId"
      element={
        <ProtectedRoute>
          <PageWrapper Component={ChatDetail} />
        </ProtectedRoute>
      }
    />
  </Routes>
);

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <AuthProvider>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </TooltipProvider>
      </AuthProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
