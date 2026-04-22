import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import companyLogo from '@/assets/2.png';
import {
  Plus,
  MessageSquare,
  Users,
  Search,
  Library,
  Grid3X3,
  Compass,
  FileText,
  ChevronRight,
  ChevronDown,
  Folder,
  LogOut,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { SearchChatDialog } from '@/components/dialogs/SearchChatDialog';
import MultiModelModal from '@/components/chat/MultiModelMode';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { useIsMobile } from '@/hooks/use-mobile';
import { listConversations, listProjects, getAuthToken, Conversation, Project } from '@/lib/api';

interface SidebarItemProps {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  variant?: 'primary' | 'secondary' | 'default';
  badge?: string;
  onClick?: () => void;
}

const SidebarItem = ({ icon, label, active, variant = 'default', badge, onClick }: SidebarItemProps) => {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
        variant === 'primary' && 'bg-primary dark:text-black hover:brightness-110 text-xs',
        variant === 'secondary' && 'bg-[#E9E9E9] dark:bg-card border border-border text-foreground hover:border-blue-200 text-xs',
        variant === 'default' && 'text-muted-foreground hover:bg-sidebar-hover hover:text-foreground text-xs',
        active && variant === 'default' && 'bg-sidebar-active text-primary text-xs'
      )}
    >
      {icon}
      <span className="flex-1 text-left">{label}</span>
      {badge && <span className="text-xs text-muted-foreground">{badge}</span>}
    </button>
  );
};

interface CollapsibleSectionProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
  active?: boolean;
}

const CollapsibleSection = ({ title, icon, children, defaultOpen = false, active }: CollapsibleSectionProps) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="space-y-0">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg font-medium transition-all duration-200 text-xs',
          'text-muted-foreground hover:bg-sidebar-hover hover:text-foreground',
          active && 'text-primary'
        )}
      >
        {icon}
        <span className="flex-1 text-left">{title}</span>
        {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
      </button>
      {isOpen && (
        <div className="pl-6 space-y-0.5 animate-fade-in">
          {children}
        </div>
      )}
    </div>
  );
};

// Helper to format relative time
function formatRelativeTime(dateString?: string): string {
  if (!dateString) return '';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return '1 day ago';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  return `${Math.floor(diffDays / 30)} months ago`;
}

interface SidebarProps {
  activePage?: 'home' | 'library' | 'explore' | 'codex' | 'chat';
  onLogout?: () => void;
  isOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}

const SidebarContent = ({
  activePage = 'home',
  onLogout,
  onItemClick,
}: {
  activePage?: 'home' | 'library' | 'explore' | 'codex' | 'chat';
  onLogout?: () => void;
  onItemClick?: () => void;
}) => {
  const navigate = useNavigate();
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);

  // Fetch conversations and projects from API (only if authenticated)
  useEffect(() => {
    const fetchData = async () => {
      // Only fetch if user is authenticated
      const token = getAuthToken();
      if (!token) return;
      
      try {
        const [convos, projs] = await Promise.all([
          listConversations().catch(() => []),
          listProjects().catch(() => []),
        ]);
        setConversations(convos.slice(0, 5)); // Show only 5 recent
        setProjects(projs.slice(0, 5)); // Show only 5 recent
      } catch (error) {
        console.error('Failed to fetch sidebar data:', error);
      }
    };
    fetchData();
  }, []);

  const isActive = (page: string) => {
    if (page === 'home') return location.pathname === '/';
    return activePage === page || location.pathname === `/${page}`;
  };

  const handleNavigation = (path: string) => {
    navigate(path);
    onItemClick?.();
  };

  return (
    <div className="flex flex-col h-full">
      {/* Logo - fixed */}
      <div className="p-4 pb-6 flex flex-col items-center flex-shrink-0">
        <img
          src={companyLogo}
          alt="SaiFai"
          className="w-16 h-16 rounded-full object-cover mb-2 border-2 border-primary/30"
        />
        <h1 className="text-lg font-semibold text-foreground">SaiFai</h1>
        <p className="text-[10px] text-muted-foreground italic">When One View Won't Do</p>
      </div>

      {/* Quick actions - fixed */}
      <div className="px-3 space-y-1.5 flex-shrink-0">
        <SidebarItem
          icon={<Plus className="w-4 h-4" />}
          label="New Chat"
          variant="primary"
          onClick={() => handleNavigation('/')}
        />
        <SidebarItem
          icon={<MessageSquare className="w-4 h-4" />}
          label="New Project"
          variant="secondary"
          onClick={() => handleNavigation('/createProject')}
        />
        <SidebarItem
          icon={<Users className="w-4 h-4" />}
          label="New Workspace"
          variant="secondary"
          onClick={() => handleNavigation('/createWorkspace')}
        />
        <SidebarItem
          icon={<Search className="w-4 h-4" />}
          label="Search Chat"
          variant="secondary"
          onClick={() => setIsSearchModalOpen(true)}
        />
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden px-3 min-h-0">
        {/* GPTs Section */}
        <div className="mt-6">
          <p className="text-xs font-semibold text-foreground mb-2 px-3">GPTs</p>
          <div className="space-y-0.5">
            <SidebarItem
              icon={<Library className="w-4 h-4" />}
              label="Library"
              active={isActive('library')}
              onClick={() => handleNavigation('/library')}
            />
            <SidebarItem
              icon={<Grid3X3 className="w-4 h-4" />}
              label="Explore"
              active={isActive('explore')}
              onClick={() => handleNavigation('/explore')}
            />
            <SidebarItem
              icon={<Compass className="w-4 h-4" />}
              label="Codex"
              active={isActive('codex')}
              onClick={() => handleNavigation('/codex')}
            />
          </div>
        </div>

        {/* My Space Section */}
        <div className="mt-6 pb-10">
          <p className="text-xs font-semibold text-foreground mb-2 px-3">My Space</p>
          <div className="space-y-0.5">
            <SidebarItem
              icon={<FileText className="w-4 h-4" />}
              label="Templates"
              onClick={() => handleNavigation('/templates')}
            />
            <SidebarItem
              icon={<Users className="w-4 h-4" />}
              label="Workspace"
              onClick={() => handleNavigation('/workspace')}
            />

            <CollapsibleSection
              title="Recent Chats"
              icon={<MessageSquare className="w-4 h-4" />}
              defaultOpen={true}
            >
              {conversations.length === 0 ? (
                <p className="text-xs text-muted-foreground px-3 py-2">No conversations yet</p>
              ) : (
                conversations.map((chat) => (
                  <button
                    key={chat.conversation_id}
                    onClick={() => handleNavigation(`/chat/${chat.conversation_id}`)}
                    className="w-full text-left text-xs px-3 py-2 text-muted-foreground hover:text-foreground hover:bg-sidebar-hover rounded-lg transition-colors"
                  >
                    <span className="block truncate">{chat.title || 'Untitled Chat'}</span>
                    <span className="text-[10px] text-muted-foreground/70">({formatRelativeTime(chat.created_at)})</span>
                  </button>
                ))
              )}
              {conversations.length > 0 && (
                <button 
                  onClick={() => handleNavigation('/library')}
                  className="w-full text-left px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
                >
                  See More...
                </button>
              )}
            </CollapsibleSection>

            <CollapsibleSection
              title="Projects"
              icon={<Folder className="w-4 h-4" />}
              defaultOpen={true}
            >
              {projects.length === 0 ? (
                <p className="text-xs text-muted-foreground px-3 py-2">No projects yet</p>
              ) : (
                projects.map((project) => (
                  <button
                    key={project.project_id}
                    onClick={() => handleNavigation(`/project/${project.project_id}`)}
                    className="w-full text-left px-3 py-2 text-xs text-muted-foreground hover:text-foreground hover:bg-sidebar-hover rounded-lg transition-colors flex items-center gap-2"
                  >
                    <Folder className="w-3.5 h-3.5" />
                    <span className="truncate">{project.name}</span>
                  </button>
                ))
              )}
              {projects.length > 0 && (
                <button 
                  onClick={() => handleNavigation('/library')}
                  className="w-full text-left px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
                >
                  See More...
                </button>
              )}
            </CollapsibleSection>
          </div>
        </div>

        {/* Extra padding at bottom to prevent content being hidden under edge */}
        <div className="h-16 md:h-0" />
      </div>

      {/* Logout - always at bottom */}
      <div className="p-3 flex-shrink-0 border-t border-sidebar-border mt-auto">
        <button
          onClick={() => {
            if (onLogout) {
              onLogout();
              onItemClick?.();
            }
          }}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[#D8F2F9] dark:bg-primary dark:text-black rounded-lg font-medium hover:brightness-110 transition-all"
        >
          <LogOut className="w-4 h-4" />
          <span>Logout</span>
        </button>
      </div>

      {/* Modals */}
      <MultiModelModal isOpen={isSearchModalOpen} onClose={() => setIsSearchModalOpen(false)} />
      <SearchChatDialog open={false} onOpenChange={() => {}} /> {/* Adjust if you use this */}
    </div>
  );
};

export function Sidebar({ activePage = 'home', onLogout, isOpen, onOpenChange }: SidebarProps) {
  const isMobile = useIsMobile();
  const [internalOpen, setInternalOpen] = useState(false);
  const open = isOpen !== undefined ? isOpen : internalOpen;
  const setOpen = onOpenChange || setInternalOpen;

  const sidebarContent = (
    <SidebarContent
      activePage={activePage}
      onLogout={onLogout}
      onItemClick={() => {
        if (isMobile) {
          setOpen(false);
        }
      }}
    />
  );

  if (isMobile) {
    return (
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          side="left"
          className="w-[280px] p-0 bg-sidebar border-sidebar-border flex flex-col h-full"
        >
          {sidebarContent}
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <aside className="hidden md:flex w-[220px] bg-sidebar border-r border-sidebar-border flex-col shadow-soft m-4 rounded-md overflow-hidden">
      {sidebarContent}
    </aside>
  );
}