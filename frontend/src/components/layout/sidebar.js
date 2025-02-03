'use client';

import React from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import {
  PlusIcon,
  MenuIcon,
  XIcon,
  MoreVertical,
  Pencil,
  Trash2,
  MessageCircle,
  BookOpen,
  Share2,
  Link,
  Loader2,
} from 'lucide-react';
import { useUser } from '@/context/user-context';
import { useRouter } from 'next/navigation';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { api } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { useShareChat } from '@/hooks/use-share-chat';

export const Sidebar = () => {
  const [isMobileOpen, setIsMobileOpen] = React.useState(false);
  const { user, chats, refreshChats, refreshProjects, team, projects } =
    useUser();
  const router = useRouter();
  const [editingChatId, setEditingChatId] = React.useState(null);
  const [editingName, setEditingName] = React.useState('');
  const { toast } = useToast();
  const { sharingChatId, handleShare } = useShareChat();

  const handleChatClick = (chatId) => {
    router.push(`/chats/${chatId}`);
    setIsMobileOpen(false);
  };

  const handleNewChat = () => {
    router.push('/chats/new');
    setIsMobileOpen(false);
  };

  const handleRename = (chatId, e) => {
    e.stopPropagation();
    const chat = chats.find((c) => c.id === chatId);
    setEditingChatId(chatId);
    setEditingName(chat.name);
  };

  const handleRenameSubmit = async (chatId, e) => {
    e.preventDefault();
    e.stopPropagation();

    if (!editingName.trim()) return;

    try {
      await api.updateChat(chatId, { name: editingName.trim() });
      await refreshChats();
      setEditingChatId(null);
    } catch (error) {
      console.error('Failed to rename chat:', error);
      // Add proper error handling here
    }
  };

  const handleDelete = async (chatId, e) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this chat?')) {
      try {
        const { message } = await api.deleteChat(chatId);
        toast({
          title: 'Deleted',
          description: message,
        });
        await refreshChats();
        await refreshProjects();
        if (window.location.pathname.includes(`/chats/${chatId}`)) {
          router.push('/chats/new');
        }
      } catch (error) {
        console.error('Failed to delete chat:', error);
      }
    }
  };

  const handleShareClick = (chatId, e) => {
    e.stopPropagation();
    const chat = chats.find((c) => c.id === chatId);
    handleShare(chat);
  };

  const toggleButton = (
    <Button
      variant="ghost"
      size="sm"
      className="fixed top-4 left-4 z-50 md:hidden"
      onClick={() => setIsMobileOpen(!isMobileOpen)}
    >
      {isMobileOpen ? (
        <XIcon className="h-4 w-4" />
      ) : (
        <MenuIcon className="h-4 w-4" />
      )}
    </Button>
  );

  const projectIdToChats = chats
    .filter(
      (chat) => chat.project && projects.some((p) => p.id === chat.project.id)
    )
    .reduce((acc, chat) => {
      const projectId = chat.project.id;
      if (!acc[projectId]) {
        acc[projectId] = [];
      }
      acc[projectId].push(chat);
      return acc;
    }, {});
  const sortedProjectIdToChats = Object.entries(projectIdToChats).sort(
    ([projectIdA], [projectIdB]) => {
      return (
        new Date(projects.find((p) => +p.id === +projectIdB)?.created_at) -
        new Date(projects.find((p) => +p.id === +projectIdA)?.created_at)
      );
    }
  );

  return (
    <>
      {toggleButton}
      <div
        className={`${
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        } md:translate-x-0 fixed md:static w-48 h-screen bg-background border-r transition-transform duration-200 ease-in-out z-40`}
      >
        <div className="flex flex-col h-full">
          <div className="p-3 border-b md:pl-3 pl-16">
            <Button
              variant="outline"
              className="w-full justify-start"
              size="sm"
              onClick={handleNewChat}
            >
              <PlusIcon className="mr-2 h-4 w-4" />
              New Chat
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start mt-2"
              size="sm"
              onClick={() =>
                window.open('https://forms.gle/VHkpxFnQXVxTqhaJ7', '_blank')
              }
            >
              <MessageCircle className="mr-2 h-4 w-4" />
              Feedback
            </Button>
            {process.env.NEXT_PUBLIC_HIDE_BLOG_BUTTON !== 'true' && (
              <Button
                variant="outline"
                className="w-full justify-start mt-2"
                size="sm"
                onClick={() =>
                  window.open(
                    'https://blog.sshh.io/p/building-v0-in-a-weekend',
                    '_blank'
                  )
                }
              >
                <BookOpen className="mr-2 h-4 w-4" />
                Dev Blog
              </Button>
            )}
          </div>
          <div className="flex-1 overflow-y-auto p-3">
            <div className="space-y-4">
              {sortedProjectIdToChats.map(([projectId, projectChats]) => (
                <div key={projectId}>
                  <div className="text-sm text-muted-foreground font-medium px-2 mb-2">
                    {projects.find((p) => p.id === +projectId)?.name}
                  </div>
                  <div className="space-y-1">
                    {projectChats.map((chat) => (
                      <div
                        key={chat.id}
                        className="py-1 px-2 hover:bg-accent rounded-md cursor-pointer group relative"
                        onClick={() => handleChatClick(chat.id)}
                      >
                        <div className="flex justify-between items-center">
                          {editingChatId === chat.id ? (
                            <form
                              onSubmit={(e) => handleRenameSubmit(chat.id, e)}
                              className="flex-1 mr-2"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <input
                                type="text"
                                value={editingName}
                                onChange={(e) => setEditingName(e.target.value)}
                                className="w-full px-1 py-0.5 text-sm bg-background border rounded"
                                autoFocus
                                onBlur={(e) => handleRenameSubmit(chat.id, e)}
                              />
                            </form>
                          ) : (
                            <span className="truncate pr-2 text-sm">
                              {chat.name}
                            </span>
                          )}
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="opacity-0 group-hover:opacity-100 h-6 w-6 p-0"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent>
                              <DropdownMenuItem
                                onClick={(e) => handleShareClick(chat.id, e)}
                                disabled={sharingChatId === chat.id}
                              >
                                {sharingChatId === chat.id ? (
                                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                ) : chat.is_public ? (
                                  <Link className="mr-2 h-4 w-4" />
                                ) : (
                                  <Share2 className="mr-2 h-4 w-4" />
                                )}
                                {chat.is_public ? 'Unshare' : 'Share'}
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={(e) => handleRename(chat.id, e)}
                              >
                                <Pencil className="mr-2 h-4 w-4" />
                                Rename
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={(e) => handleDelete(chat.id, e)}
                                className="text-red-600 focus:text-red-600 focus:bg-red-100"
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="p-2 border-t">
            <div
              className="flex items-center justify-between hover:bg-accent rounded-md p-1.5 cursor-pointer"
              onClick={() => router.push('/settings')}
            >
              <div className="flex flex-col gap-0.5 min-w-0">
                <div className="flex items-center space-x-3 min-w-0">
                  <Avatar>
                    <AvatarImage src="" />
                    <AvatarFallback>{user.username[0]}</AvatarFallback>
                  </Avatar>
                  <span className="font-medium truncate">{user.username}</span>
                </div>
                {team && (
                  <span className="text-sm text-muted-foreground ml-[3.25rem] truncate">
                    {team.name}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-30 md:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}
    </>
  );
};
