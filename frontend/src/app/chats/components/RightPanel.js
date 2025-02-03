'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { PreviewTab } from './PreviewTab';
import { FilesTab } from './FilesTab';
import { ProjectTab } from './ProjectTab';
import { PanelRightIcon } from 'lucide-react';

export function RightPanel({
  projectPreviewUrl,
  projectPreviewHash,
  projectFileTree,
  project,
  projectPreviewPath,
  setProjectPreviewPath,
  onSendMessage,
  status,
  isOpen,
  onClose,
}) {
  const [selectedTab, setSelectedTab] = useState('preview');

  return (
    <div className="flex flex-col w-full h-full md:pt-0 pt-14">
      <div className="border-b bg-background">
        <div className="flex items-center justify-between px-4 py-2">
          <div className="flex items-center space-x-4">
            <Button
              variant={selectedTab === 'preview' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setSelectedTab('preview')}
            >
              Preview
            </Button>
            <Button
              variant={selectedTab === 'editor' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setSelectedTab('editor')}
            >
              Files
            </Button>
            <Button
              variant={selectedTab === 'info' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setSelectedTab('info')}
            >
              Project
            </Button>
          </div>
          {isOpen && (
            <div className="md:hidden">
              <Button variant="outline" size="sm" onClick={() => onClose()}>
                <PanelRightIcon className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        {selectedTab === 'preview' ? (
          <PreviewTab
            projectPreviewUrl={projectPreviewUrl}
            projectPreviewHash={projectPreviewHash}
            projectPreviewPath={projectPreviewPath}
            setProjectPreviewPath={setProjectPreviewPath}
            status={status}
          />
        ) : selectedTab === 'editor' ? (
          <FilesTab projectFileTree={projectFileTree} project={project} />
        ) : (
          <ProjectTab project={project} onSendMessage={onSendMessage} />
        )}
      </div>
    </div>
  );
}
