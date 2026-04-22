import { useState } from 'react';
import { Music } from 'lucide-react';
import { NewAIModelsModal } from '@/components/global/NewAIModelsModal';
import { cn } from '@/lib/utils';

export function WelcomeCard() {
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <>
      <div className="model-card max-w-md mx-auto text-center ">
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center justify-center gap-2 mb-2 w-full"
        >
          <div className="bg-white/70 dark:bg-card rounded-lg px-6 py-4 shadow-md border border-border hover:bg-muted/50 transition-colors cursor-pointer w-full">
            <div className="flex items-center justify-center gap-2 mb-1">
              <Music className="w-5 h-5 text-primary" />
              <h3 className="text-lg font-semibold text-foreground">New AI Models</h3>
            </div>
            <p className="text-sm text-muted-foreground">Discover Complete New AI Systems Designed For Your Workspace</p>
          </div>
        </button>
      </div>
      
      <NewAIModelsModal open={isModalOpen} onOpenChange={setIsModalOpen} />
    </>
  );
}
