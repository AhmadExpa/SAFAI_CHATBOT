import { useState } from 'react';
import { Search, X, MessageSquare, Clock } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

interface SearchChatDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const recentSearches = [
  { id: 1, query: 'React hooks tutorial', time: '2 hours ago' },
  { id: 2, query: 'AI model comparison', time: '1 day ago' },
  { id: 3, query: 'Project setup guide', time: '3 days ago' },
];

const chatResults = [
  { id: 1, title: 'Hello World', preview: 'Getting started with the platform...', time: '1 day ago' },
  { id: 2, title: 'Create Illustration', preview: 'Designing beautiful graphics...', time: '8 days ago' },
  { id: 3, title: 'UI Design Project', preview: 'Building modern interfaces...', time: '9 days ago' },
];

export function SearchChatDialog({ open, onOpenChange }: SearchChatDialogProps) {
  const [searchQuery, setSearchQuery] = useState('');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] bg-card border-border p-0 overflow-hidden">
        {/* Search Header */}
        <div className="p-4 border-b border-border">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search chats, projects, files..."
              className="pl-10 pr-10 h-11 bg-background border-border text-foreground placeholder:text-muted-foreground"
              autoFocus
            />
            {searchQuery && (
              <button 
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-muted"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            )}
          </div>
        </div>

        {/* Results */}
        <div className="max-h-[400px] overflow-y-auto">
          {/* Recent Searches */}
          {!searchQuery && (
            <div className="p-4">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Recent Searches</h3>
              <div className="space-y-1">
                {recentSearches.map((search) => (
                  <button
                    key={search.id}
                    onClick={() => setSearchQuery(search.query)}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-muted transition-colors text-left"
                  >
                    <Clock className="w-4 h-4 text-muted-foreground" />
                    <span className="flex-1 text-sm text-foreground">{search.query}</span>
                    <span className="text-xs text-muted-foreground">{search.time}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Chat Results */}
          <div className="p-4 border-t border-border">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase mb-2">
              {searchQuery ? 'Results' : 'Recent Chats'}
            </h3>
            <div className="space-y-1">
              {chatResults.map((chat) => (
                <button
                  key={chat.id}
                  className="w-full flex items-start gap-3 px-3 py-3 rounded-lg hover:bg-muted transition-colors text-left"
                >
                  <MessageSquare className="w-5 h-5 text-primary mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground">{chat.title}</p>
                    <p className="text-xs text-muted-foreground truncate">{chat.preview}</p>
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">{chat.time}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
