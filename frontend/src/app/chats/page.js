'use client';

import { useEffect, useState, useRef } from 'react';
import { useUser } from '@/context/user-context';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { ProjectWebSocketService } from '@/lib/project-websocket';
import { api } from '@/lib/api';
import { Chat } from './components/Chat';
import { RightPanel } from './components/RightPanel';
import { useToast } from '@/hooks/use-toast';
import Splitter from '@/components/ui/splitter';

export default function WorkspacePage({ chatId }) {
  const { addChat, team, projects, chats, refreshProjects } = useUser();
  const router = useRouter();
  const [projectId, setProjectId] = useState(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [chatTitle, setChatTitle] = useState('New Chat');
  const [projectPreviewUrl, setProjectPreviewUrl] = useState(null);
  const [projectPreviewPath, setProjectPreviewPath] = useState('/');
  const [backendFileTree, setBackendFileTree] = useState([]);
  const [frontendFileTree, setFrontendFileTree] = useState([]);
  const [projectStackPackId, setProjectStackPackId] = useState(null);
  const [suggestedFollowUps, setSuggestedFollowUps] = useState([]);
  const [previewHash, setPreviewHash] = useState(1);
  const [status, setStatus] = useState('NEW_CHAT');
  const webSocketRef = useRef(null);
  const { toast } = useToast();
  const [isMobile, setIsMobile] = useState(false);
  const chat = chats?.find((c) => c.id === +chatId);

  useEffect(() => {
    if (!localStorage.getItem('token')) {
      router.push('/');
    }
    if (!chatId) {
      router.push('/chats/new');
    }
  }, [chatId]);

  const initializeWebSocket = async (wsProjectId) => {
    if (webSocketRef.current) {
      webSocketRef.current.disconnect();
    }
    const ws = new ProjectWebSocketService(wsProjectId);
    webSocketRef.current = ws;

    const connectWS = async () => {
      try {
        await new Promise((resolve, reject) => {
          ws.connect();
          ws.ws.onopen = () => resolve();
          ws.ws.onerror = (error) => reject(error);
          ws.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleSocketMessage(data);
          };
          ws.ws.onclose = (e) => {
            setStatus('DISCONNECTED');
            console.log('WebSocket connection closed', e.code, e.reason);
            if ([1002, 1003].includes(e.code)) {
              initializeWebSocket(chatId);
            }
          };
          setTimeout(
            () => reject(new Error('WebSocket connection timeout')),
            5000
          );
        });

        const handleSocketMessage = (data) => {
          console.log('handleMessage', data);
          if (data.for_type === 'status') {
            handleStatus(data);
          } else if (data.for_type === 'chat_update') {
            handleChatUpdate(data);
          } else if (data.for_type === 'chat_chunk') {
            handleChatChunk(data);
          }
        };

        // In the handleStatus callback, update to process new fields:
        const handleStatus = (data) => {
          // (Assuming data.sandbox_statuses may be an object – you might choose the primary status from the backend service)
          // For preview URL, use the dedicated frontend_tunnel if provided:
          if (data.frontend_tunnel) {
            setProjectPreviewUrl(data.frontend_tunnel);
          } else if (data.tunnels) {
            const keys = Object.keys(data.tunnels);
            if (keys.length > 0) {
              setProjectPreviewUrl(data.tunnels[keys[0]]);
            } else {
              setProjectPreviewUrl(null);
            }
          }
          if (data.backend_file_paths) {
            setBackendFileTree(data.backend_file_paths);
          }
          if (data.frontend_file_paths) {
            setFrontendFileTree(data.frontend_file_paths);
          }
          // Optionally update overall status – for simplicity, pick the backend status (if available)
          if (data.sandbox_statuses && Object.values(data.sandbox_statuses).length > 0) {
            // For example, pick the backend service status:
            const backendStatus = data.sandbox_statuses[
              Object.keys(data.sandbox_statuses)[0]
            ];
            setStatus(backendStatus);
          }
        };

        const handleChatUpdate = (data) => {
          setMessages((prev) => {
            const existingMessageIndex = prev.findIndex(
              (m) => m.id === data.message.id
            );
            if (existingMessageIndex >= 0) {
              return [
                ...prev.slice(0, existingMessageIndex),
                data.message,
                ...prev.slice(existingMessageIndex + 1),
              ];
            }
            const lastMessage = prev[prev.length - 1];
            if (
              lastMessage?.role === 'assistant' &&
              data.message.role === 'assistant'
            ) {
              return [
                ...prev.slice(0, -1),
                { ...lastMessage, content: data.message.content },
              ];
            }
            return [...prev, data.message];
          });
          if (data.follow_ups) {
            setSuggestedFollowUps(data.follow_ups);
          }
          if (data.navigate_to) {
            setProjectPreviewPath(data.navigate_to);
          }
          setPreviewHash((prev) => prev + 1);
        };

        const handleChatChunk = (data) => {
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage?.role === 'assistant') {
              return [
                ...prev.slice(0, -1),
                {
                  ...lastMessage,
                  content: lastMessage.content + data.content,
                  thinking_content:
                    (lastMessage?.thinking_content || '') +
                    data.thinking_content,
                },
              ];
            }
            return [
              ...prev,
              {
                role: 'assistant',
                content: data.content,
                thinking_content: data.thinking_content,
              },
            ];
          });
        };

        return ws;
      } catch (error) {
        setStatus('DISCONNECTED');
      }
    };

    await connectWS();
    return { ws };
  };

  useEffect(() => {
    if (chatId !== 'new') {
      initializeWebSocket(chatId).catch((error) => {
        console.error('Failed to initialize WebSocket:', error);
      });
    }
    return () => {
      if (webSocketRef.current) {
        webSocketRef.current.disconnect();
      }
    };
  }, [chatId]);

  const handleStackPackSelect = (stackPackId) => {
    setProjectStackPackId(stackPackId);
  };

  const handleProjectSelect = (projectId) => {
    setProjectId(projectId);
  };

  const handleSendMessage = async (message) => {
    if (!message.content.trim() && message.images.length === 0) return;

    const userMessage = {
      role: 'user',
      content: message.content,
      images: message.images || [],
    };
    if (chatId === 'new') {
      try {
        const chat = await api.createChat({
          name: message.content,
          stack_id: projectStackPackId,
          project_id: projectId,
          team_id: team.id,
          seed_prompt: message.content,
        });
        toast({
          title: 'Chat created',
          description: 'Setting things up...',
        });
        await refreshProjects();
        addChat(chat);
        router.push(
          `/chats/${chat.id}?message=${encodeURIComponent(
            JSON.stringify(userMessage)
          )}`
        );
      } catch (error) {
        toast({
          title: 'Error',
          description: error.message,
          variant: 'destructive',
        });
        if (error.message.includes('credits')) {
          router.push('/settings?buy=true');
        }
      }
    } else {
      setStatus('WORKING');
      webSocketRef.current.sendMessage(userMessage);
    }
  };

  useEffect(() => {
    (async () => {
      if (chatId !== 'new') {
        setStatus('DISCONNECTED');
        const chat = await api.getChat(chatId);
        setChatTitle(chat.name);
        const existingMessages =
          chat?.messages.map((m) => ({
            role: m.role,
            content: m.content,
          })) || [];
        setMessages(existingMessages);
        setProjectId(chat.project.id);
      } else {
        setChatTitle('New Chat');
        setMessages([]);
        setProjectPreviewUrl(null);
        setBackendFileTree([]);
        setFrontendFileTree([]);
        setStatus('NEW_CHAT');
      }
    })();
  }, [chatId]);

  useEffect(() => {
    (async () => {
      if (status === 'READY') {
        const params = new URLSearchParams(window.location.search);
        const messageParam = params.get('message');
        if (messageParam) {
          try {
            const message = JSON.parse(decodeURIComponent(messageParam));
            const searchParams = new URLSearchParams(window.location.search);
            searchParams.delete('message');
            router.replace(
              `${window.location.pathname}?${searchParams.toString()}`,
              {
                scroll: false,
              }
            );
            await webSocketRef.current.sendMessage(message);
          } catch (error) {
            console.error('Failed to process message parameter:', error);
          }
        }
      }
    })();
  }, [chatId, status]);

  const handleReconnect = async () => {
    if (chatId !== 'new') {
      try {
        setStatus('CONNECTING');
        await initializeWebSocket(chatId);
      } catch (error) {
        console.error('Failed to reconnect:', error);
        setStatus('DISCONNECTED');
      }
    }
  };

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  return (
    <div className="flex h-screen bg-background">
      <div className="flex-1 flex flex-col">
        {!isPreviewOpen && (
          <div className="md:hidden fixed top-4 right-4 z-40">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsPreviewOpen(!isPreviewOpen)}
            >
              View
            </Button>
          </div>
        )}

        {isMobile ? (
          // Mobile Layout: Stack vertically and show/hide based on isPreviewOpen
          <div className="flex-1">
            <div className={`h-full ${isPreviewOpen ? 'hidden' : 'block'}`}>
              <Chat
                chat={chat}
                connected={!!webSocketRef.current}
                messages={messages}
                onSendMessage={handleSendMessage}
                projectTitle={chatTitle}
                status={status}
                onProjectSelect={handleProjectSelect}
                onStackSelect={handleStackPackSelect}
                showStackPacks={chatId === 'new'}
                suggestedFollowUps={suggestedFollowUps}
                onReconnect={handleReconnect}
              />
            </div>
            <div className={`h-full ${isPreviewOpen ? 'block' : 'hidden'}`}>
              <RightPanel
                onSendMessage={handleSendMessage}
                isOpen={isPreviewOpen}
                onClose={() => setIsPreviewOpen(false)}
                projectPreviewUrl={projectPreviewUrl}
                projectPreviewPath={projectPreviewPath}
                setProjectPreviewPath={setProjectPreviewPath}
                projectPreviewHash={previewHash}
                backendFileTree={backendFileTree}
                frontendFileTree={frontendFileTree}
                project={projects.find((p) => +p.id === +projectId)}
                chatId={chatId}
                status={status}
              />
            </div>
          </div>
        ) : (
          // Desktop Layout: Use Splitter
          <Splitter
            defaultLeftWidth="60%"
            minLeftWidth={400}
            minRightWidth={400}
            className="h-full"
          >
            <Chat
              chat={chat}
              connected={!!webSocketRef.current}
              messages={messages}
              onSendMessage={handleSendMessage}
              projectTitle={chatTitle}
              status={status}
              onProjectSelect={handleProjectSelect}
              onStackSelect={handleStackPackSelect}
              showStackPacks={chatId === 'new'}
              suggestedFollowUps={suggestedFollowUps}
              onReconnect={handleReconnect}
            />
            <RightPanel
              onSendMessage={handleSendMessage}
              isOpen={isPreviewOpen}
              onClose={() => setIsPreviewOpen(false)}
              projectPreviewUrl={projectPreviewUrl}
              projectPreviewPath={projectPreviewPath}
              setProjectPreviewPath={setProjectPreviewPath}
              projectPreviewHash={previewHash}
              backendFileTree={backendFileTree}  
              frontendFileTree={frontendFileTree} 
              project={projects.find((p) => +p.id === +projectId)}
              chatId={chatId}
              status={status}
            />

          </Splitter>
        )}
      </div>
    </div>
  );
}
