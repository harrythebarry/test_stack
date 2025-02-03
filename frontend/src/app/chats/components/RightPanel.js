'use client';

import { useState, useEffect } from 'react';


import { Button } from '@/components/ui/button';
import { PreviewTab } from './PreviewTab';
import { FilesTab } from './FilesTab';
import { ProjectTab } from './ProjectTab';
import { PanelRightIcon } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'; // Ensure you are importing from your UI components, not Radix raw

export function RightPanel({
  projectPreviewUrl,
  projectPreviewPath,
  setProjectPreviewPath,
  projectPreviewHash,
  backendFileTree,
  frontendFileTree,
  onSendMessage,
  project,
  chatId,
  status,
  isOpen,
  onClose,
}) {
  
  const [selectedTab, setSelectedTab] = useState('preview');

  return (
    <div className="flex flex-col w-full h-full md:pt-0 pt-14">
      <div className="sticky top-0 bg-background border-b">
        <div className="px-4 py-2 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Button
              variant={selectedTab === 'preview' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setSelectedTab('preview')}
            >
              Preview
            </Button>
            <Button
              variant={selectedTab === 'files' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setSelectedTab('files')}
            >
              Files
            </Button>
            <Button
              variant={selectedTab === 'project' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setSelectedTab('project')}
            >
              Project
            </Button>
          </div>
          {isOpen && (
            <div className="md:hidden">
              <Button variant="outline" size="sm" onClick={onClose}>
                <PanelRightIcon className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        {selectedTab === 'preview' && (
          <PreviewTab
            projectPreviewUrl={projectPreviewUrl}
            projectPreviewHash={projectPreviewHash}
            projectPreviewPath={projectPreviewPath}
            setProjectPreviewPath={setProjectPreviewPath}
            status={status}
          />
        )}
        {selectedTab === 'files' && (
          <div className="h-full">
            <Tabs defaultValue="backend" className="w-full h-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="backend">Backend Files</TabsTrigger>
                <TabsTrigger value="frontend">Frontend Files</TabsTrigger>
              </TabsList>
              <TabsContent value="backend" className="mt-4 h-full">
                <FilesTab fileTree={backendFileTree} project={project} />
              </TabsContent>
              <TabsContent value="frontend" className="mt-4 h-full">
                <FilesTab fileTree={frontendFileTree} project={project} />
              </TabsContent>
            </Tabs>
          </div>
        )}
        {selectedTab === 'project' && (
          <ProjectTab project={project} onSendMessage={onSendMessage} />
        )}
      </div>
    </div>
  );
}
