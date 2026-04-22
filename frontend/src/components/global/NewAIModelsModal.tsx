import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Music } from 'lucide-react';
import { cn } from '@/lib/utils';
import { modelGroups } from '@/lib/models';

interface NewAIModelsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Get GPT models from shared configuration
const aiModels = modelGroups.find((g) => g.id === 'gpt')?.models || [];

export function NewAIModelsModal({ open, onOpenChange }: NewAIModelsModalProps) {
  const [selectedModel, setSelectedModel] = useState('gpt-4.1-mini');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          // Main fixes here
          'max-h-[90dvh] overflow-y-auto',
          // Optional: better padding and rounded corners consistency
          'p-6 sm:max-w-[500px] bg-card border-border',
          // Helps on very small screens
          'max-w-[95vw] sm:max-w-[500px]'
        )}
      >
        <DialogHeader className="pb-4">
          <DialogTitle className="flex items-center gap-2 text-xl font-semibold text-foreground">
            <Music className="w-5 h-5 text-primary" />
            New AI Models
          </DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            Discover Complete New AI Systems Designed For Your Workspace
          </DialogDescription>
        </DialogHeader>

        {/* Scrollable content area */}
        <div className="py-2">
          <RadioGroup
            value={selectedModel}
            onValueChange={setSelectedModel}
            className="space-y-3"
          >
            {aiModels.map((model) => (
              <div
                key={model.id}
                className={cn(
                  'flex items-center space-x-3 p-3 rounded-lg border transition-colors cursor-pointer',
                  selectedModel === model.id
                    ? 'bg-primary/10 border-primary/30'
                    : 'bg-background border-border hover:bg-muted/50'
                )}
                onClick={() => setSelectedModel(model.id)}
              >
                <RadioGroupItem value={model.id} id={model.id} />
                <Label
                  htmlFor={model.id}
                  className={cn(
                    'flex-1 cursor-pointer font-medium text-sm',
                    selectedModel === model.id ? 'text-primary' : 'text-foreground'
                  )}
                >
                  {model.name}
                </Label>
              </div>
            ))}
          </RadioGroup>
        </div>

        {/* Optional: if you want to add a footer later (e.g. buttons) */}
        {/* <div className="pt-6 border-t mt-4">
          <Button>Confirm Selection</Button>
        </div> */}
      </DialogContent>
    </Dialog>
  );
}