'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { components } from '@/app/chats/components/MarkdownComponents';
import { fixCodeBlocks } from '@/lib/code';
import { Button } from '@/components/ui/button';
import { ExternalLink, RotateCw } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { useDebounce } from '@/lib/hooks/useDebounce';

export default function PublicChatPage() {
  const { shareId } = useParams();
  const [chat, setChat] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [projectPreviewPath, setProjectPreviewPath] = useState('/');
  const [projectPreviewUrl, setProjectPreviewUrl] = useState(null);
  const [isIframeLoading, setIsIframeLoading] = useState(true);
  const debouncedPath = useDebounce(projectPreviewPath, 500);

  useEffect(() => {
    const fetchChat = async () => {
      setIsLoading(true);
      try {
        const response = await api.getPublicChat(shareId);
        if (!response || !response.id) {
          throw new Error('Invalid chat data received');
        }
        setChat(response);
      } catch (err) {
        console.error('Error fetching chat:', err);
        setError('This chat is not available or has been removed');
      } finally {
        setIsLoading(false);
      }
    };
    fetchChat();
  }, [shareId]);

  useEffect(() => {
    const fetchPreview = async () => {
      if (!chat?.project) return;

      setIsPreviewLoading(true);
      try {
        const previewResponse = await api.getPublicChatPreviewUrl(shareId);
        setProjectPreviewUrl(previewResponse.preview_url);
      } catch (previewErr) {
        console.error('Error fetching preview URL:', previewErr);
      } finally {
        setIsPreviewLoading(false);
      }
    };
    fetchPreview();
  }, [chat, shareId]);

  const handleIframeLoad = () => {
    setIsIframeLoading(false);
  };

  const handleRefresh = () => {
    const iframe = document.querySelector('iframe');
    if (iframe) {
      setIsIframeLoading(true);
      iframe.src = iframe.src;
    }
  };

  if (error) {
    return (
      <div className="container mx-auto p-4">
        <Card className="p-6">
          <h1 className="text-2xl font-bold text-red-500 mb-2">Error</h1>
          <p>{error}</p>
        </Card>
      </div>
    );
  }

  if (isLoading || !chat) {
    return (
      <div className="container mx-auto p-4 space-y-4">
        <Card className="p-6">
          <div className="space-y-4">
            <div className="h-8 w-48 bg-muted animate-pulse rounded-md" />
            <div className="h-4 w-32 bg-muted/60 animate-pulse rounded-md" />
            <div className="space-y-4 mt-8">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex items-start gap-4">
                  <div className="w-8 h-8 rounded bg-muted/60 animate-pulse" />
                  <div className="space-y-2 flex-1">
                    <div className="h-4 w-3/4 bg-muted animate-pulse rounded-md" />
                    <div className="h-4 w-1/2 bg-muted animate-pulse rounded-md" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4 space-y-4">
      <Card className="p-6">
        <h1 className="text-2xl font-bold mb-2">{chat.project?.name}</h1>
        <div className="text-sm text-muted-foreground mb-4">
          Chat: {chat.name}
        </div>
        <ScrollArea className="h-[400px] pr-4">
          <div className="space-y-4">
            {chat.messages?.map((message, index) => (
              <div key={index} className="flex items-start gap-4">
                <div
                  className={`w-8 h-8 rounded ${
                    message.role === 'user' ? 'bg-blue-500/10' : 'bg-primary/10'
                  } flex-shrink-0 flex items-center justify-center text-sm font-medium ${
                    message.role === 'user' ? 'text-blue-500' : 'text-primary'
                  }`}
                >
                  {message.role === 'user' ? 'H' : 'AI'}
                </div>
                <div className="flex-1">
                  <div className="mt-1 prose prose-sm max-w-[80%]">
                    {message.images && message.images.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-4">
                        {message.images.map((img, imgIndex) => (
                          <img
                            key={imgIndex}
                            src={img}
                            alt={`Message attachment ${imgIndex + 1}`}
                            className="max-h-48 max-w-[300px] object-contain rounded-lg"
                          />
                        ))}
                      </div>
                    )}
                    {!message.content && message.thinking_content && (
                      <div className="prose prose-sm max-w-none">
                        <div className="inline-block px-2 py-1 mb-2 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-md animate-pulse">
                          {[
                            ...message.thinking_content.matchAll(
                              /### ([\s\S]+?)\n/g
                            ),
                          ].at(-1)?.[1] || 'Thinking...'}
                        </div>
                      </div>
                    )}
                    <ReactMarkdown
                      components={components}
                      rehypePlugins={[rehypeRaw]}
                      remarkPlugins={[remarkGfm]}
                      className="max-w-[80%]"
                    >
                      {fixCodeBlocks(message.content, false)}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </Card>

      {projectPreviewUrl && (
        <Card className="p-6">
          <div className="flex flex-col space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Input
                  value={projectPreviewPath}
                  onChange={(e) => setProjectPreviewPath(e.target.value)}
                  className="w-[200px]"
                  placeholder="Path (e.g. /)"
                />
              </div>
              <div className="flex gap-2">
                {isPreviewLoading ? (
                  <Button variant="ghost" size="icon" disabled>
                    <RotateCw className="h-4 w-4 animate-spin" />
                  </Button>
                ) : (
                  <>
                    <Button variant="ghost" size="icon" onClick={handleRefresh}>
                      <RotateCw
                        className={`h-4 w-4 ${
                          isIframeLoading ? 'animate-spin' : ''
                        }`}
                      />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => window.open(projectPreviewUrl, '_blank')}
                    >
                      <ExternalLink className="h-4 w-4" />
                    </Button>
                  </>
                )}
              </div>
            </div>
            <div className="w-full h-[600px] bg-muted/10 overflow-auto relative">
              {isIframeLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-background/80">
                  <div className="flex flex-col items-center gap-2">
                    <RotateCw className="h-8 w-8 animate-spin" />
                    <p className="text-sm text-muted-foreground">
                      Loading preview...
                    </p>
                  </div>
                </div>
              )}
              <div className="w-full h-full flex items-start justify-center p-4">
                <iframe
                  src={`${projectPreviewUrl}${debouncedPath}`}
                  className="w-full h-full border shadow-sm bg-white"
                  title="Project Preview"
                  onLoad={handleIframeLoad}
                />
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
