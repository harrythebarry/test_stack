import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import Image from 'next/image';

export function WhatIsThisModal({ isOpen, onClose }) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>About Spark Stack</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <p className="text-muted-foreground">
            Spark Stack is an tool for building web apps through an AI-powered
            chat interface. Create quick MVPs with simple prompts.
          </p>
          <div className="relative w-full h-[300px] rounded-lg overflow-hidden">
            <Image
              src="/screenshot.png" // Make sure to add your screenshot to the public folder
              alt="Spark Stack Screenshot"
              fill
              className="object-cover"
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
