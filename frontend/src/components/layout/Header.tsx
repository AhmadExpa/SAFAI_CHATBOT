import { Sun, Moon, Users, MessageSquare, Menu, User, Settings, LogOut, UserPlus, Users2, Bell, Mail, CheckCircle } from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import { useIsMobile } from '@/hooks/use-mobile';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface HeaderProps {
  title?: string;
  onMenuClick?: () => void;
}

export function Header({ title, onMenuClick }: HeaderProps) {
  const { theme, toggleTheme, setTheme } = useTheme();
  const isMobile = useIsMobile();

  return (
    <>
      <header className="h-16 mt-2 md:mt-4 rounded-md mr-2 md:mr-4 flex items-center justify-between px-3 md:px-6 gap-2 md:gap-4 bg-card/50 border-b border-border relative z-20">
        {/* Left: Menu Button (mobile) + Title */}
        <div className="flex items-center gap-3">
          {isMobile && (
            <button
              onClick={onMenuClick}
              className="p-2 rounded-lg text-foreground hover:bg-muted transition-colors"
              aria-label="Open menu"
            >
              <Menu className="w-5 h-5" />
            </button>
          )}
          {title && (
            <h2 className="text-base md:text-lg font-semibold text-foreground truncate">{title}</h2>
          )}
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-1 md:gap-2">
          {/* Theme Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="p-2 md:p-2.5 rounded-lg hover:bg-muted transition-colors"
                aria-label="Theme options"
              >
                {theme === 'light' ? (
                  <Sun className="w-4 md:w-5 h-4 md:h-5 text-muted-foreground hover:text-foreground transition-colors" />
                ) : (
                  <Moon className="w-4 md:w-5 h-4 md:h-5 text-muted-foreground hover:text-foreground transition-colors" />
                )}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48 bg-card border-border">
              <DropdownMenuItem onClick={() => setTheme('light')} className="cursor-pointer">
                <Sun className="w-4 h-4 mr-2" />
                <span>Light Mode</span>
                {theme === 'light' && <CheckCircle className="w-4 h-4 ml-auto text-primary" />}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('dark')} className="cursor-pointer">
                <Moon className="w-4 h-4 mr-2" />
                <span>Dark Mode</span>
                {theme === 'dark' && <CheckCircle className="w-4 h-4 ml-auto text-primary" />}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Users/Team Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="hidden sm:block p-2.5 rounded-lg hover:bg-muted transition-colors" aria-label="Team">
                <Users className="w-5 h-5 text-muted-foreground hover:text-foreground transition-colors" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48 bg-card border-border">
              <DropdownMenuItem className="cursor-pointer">
                <Users2 className="w-4 h-4 mr-2" />
                <span>Team Members</span>
              </DropdownMenuItem>
              <DropdownMenuItem className="cursor-pointer">
                <UserPlus className="w-4 h-4 mr-2" />
                <span>Invite Users</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="cursor-pointer">
                <Settings className="w-4 h-4 mr-2" />
                <span>Manage Team</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Messages Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="hidden sm:block p-2.5 rounded-lg hover:bg-muted transition-colors" aria-label="Messages">
                <MessageSquare className="w-5 h-5 text-muted-foreground hover:text-foreground transition-colors" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48 bg-card border-border">
              <DropdownMenuItem className="cursor-pointer">
                <Mail className="w-4 h-4 mr-2" />
                <span>All Messages</span>
              </DropdownMenuItem>
              <DropdownMenuItem className="cursor-pointer">
                <Bell className="w-4 h-4 mr-2" />
                <span>Notifications</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="cursor-pointer">
                <CheckCircle className="w-4 h-4 mr-2" />
                <span>Mark All Read</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* User Profile Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="w-8 h-8 md:w-9 md:h-9 rounded-full overflow-hidden border-2 border-primary/30 hover:border-primary transition-colors">
                <img
                  src="https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face"
                  alt="User avatar"
                  className="w-full h-full object-cover"
                />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48 bg-card border-border">
              <DropdownMenuItem className="cursor-pointer">
                <User className="w-4 h-4 mr-2" />
                <span>Account</span>
              </DropdownMenuItem>
              <DropdownMenuItem className="cursor-pointer">
                <Settings className="w-4 h-4 mr-2" />
                <span>Settings</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="cursor-pointer text-destructive focus:text-destructive">
                <LogOut className="w-4 h-4 mr-2" />
                <span>Log Out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
    </>
  );
}
