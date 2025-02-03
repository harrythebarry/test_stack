'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button } from '@/components/ui/button';
import {
  SendIcon,
  Loader2,
  ImageIcon,
  X,
  Scan,
  RefreshCw,
  Pencil,
  Mic,
  MicOff,
  Share2,
  Link,
} from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';
import rehypeRaw from 'rehype-raw';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUser } from '@/context/user-context';
import { api, uploadImage } from '@/lib/api';
import { resizeImage, captureScreenshot } from '@/lib/image';
import { components } from '@/app/chats/components/MarkdownComponents';
import { fixCodeBlocks } from '@/lib/code';
import { SketchDialog } from './SketchDialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useToast } from '@/hooks/use-toast';
import { useShareChat } from '@/hooks/use-share-chat';
import { Progress } from '@/components/ui/progress';

// Example starter prompts
const STARTER_PROMPTS = [
  'Build a 90s themed cat facts app with catfact.ninja API',
  'Build a modern control panel for a spaceship',
  'Build a unique p5.js asteroid game',
];

//---------------------------------------------------------------------
// If user has zero messages and "showStackPacks === true", we show this
//   => user picks existing project or "New Project" (the rest is up to backend).
//---------------------------------------------------------------------
function EmptyState({ selectedProject, projects, onProjectSelect }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-0 h-full overflow-hidden">
      <div className="max-w-md w-full space-y-4 px-4 sm:px-6">
        <Select
          value={selectedProject}
          onValueChange={(value) => {
            onProjectSelect(value);
          }}
        >
          <SelectTrigger className="w-full py-10 md:py-12">
            <SelectValue placeholder="Select a Project" />
          </SelectTrigger>
          <SelectContent className="max-h-[40vh] w-full overflow-y-auto">
            {[
              {
                id: null,
                name: 'New Project',
                description:
                  'Start a new project from scratch (created after first chat).',
              },
            ]
              .concat(projects ?? [])
              .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
              .map((proj) => (
                <SelectItem key={proj.id} value={proj.id} className="py-2">
                  <div className="flex flex-col gap-1 max-w-full">
                    <span className="font-medium truncate">{proj.name}</span>
                    <p className="text-sm text-muted-foreground break-words">
                      {proj.description}
                    </p>
                  </div>
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

//------------------------------------------
// If the assistant is "thinking", we parse
// the last h3 heading for display
//------------------------------------------
const ThinkingContent = ({ thinkingContent }) => {
  const lastHeader = [...thinkingContent.matchAll(/### ([\s\S]+?)\n/g)].at(
    -1
  )?.[1];
  return (
    <div className="prose prose-sm max-w-none">
      <div className="inline-block px-2 py-1 mb-2 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-md animate-pulse">
        {lastHeader || 'Thinking...'}
      </div>
    </div>
  );
};

//------------------------------------------
// The main message list
//------------------------------------------
const MessageList = ({ messages, status }) => (
  <div className="space-y-4">
    {messages.map((msg, idx) => (
      <div key={idx} className="flex items-start gap-4">
        <div
          className={`w-8 h-8 rounded ${
            msg.role === 'user'
              ? 'bg-blue-500/10 text-blue-500'
              : 'bg-primary/10 text-primary'
          } flex-shrink-0 flex items-center justify-center text-sm font-medium`}
        >
          {msg.role === 'user' ? 'H' : 'AI'}
        </div>
        <div className="flex-1">
          <div className="mt-1 prose prose-sm max-w-[80%]">
            {/* If images exist, show them */}
            {msg.images && msg.images.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-4">
                {msg.images.map((img, imgIndex) => (
                  <img
                    key={imgIndex}
                    src={img}
                    alt={`Message attachment ${imgIndex + 1}`}
                    className="max-h-48 max-w-[300px] object-contain rounded-lg"
                  />
                ))}
              </div>
            )}
            {/* If we have no direct content, but "thinking_content" */}
            {!msg.content && msg.thinking_content && (
              <ThinkingContent thinkingContent={msg.thinking_content} />
            )}
            {/* Otherwise, we parse the markdown */}
            <ReactMarkdown
              components={components}
              rehypePlugins={[rehypeRaw]}
              remarkPlugins={[remarkGfm]}
              className="max-w-[80%]"
            >
              {fixCodeBlocks(msg.content, status === 'WORKING')}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    ))}
  </div>
);

//------------------------------------------
// Container for image attachments
//------------------------------------------
const ImageAttachments = ({ attachments, onRemove }) => (
  <div className="flex flex-wrap gap-2">
    {attachments.map((img, idx) => (
      <div key={idx} className="relative inline-block">
        <img
          src={img}
          alt={`attachment ${idx + 1}`}
          className="max-h-32 max-w-[200px] object-contain rounded-lg"
        />
        <Button
          type="button"
          size="icon"
          variant="secondary"
          className="absolute top-1 right-1 h-6 w-6"
          onClick={() => onRemove(idx)}
        >
          <X className="h-3 w-3" />
        </Button>
      </div>
    ))}
  </div>
);

//------------------------------------------
// ChatInput => the text area + image attach, etc.
//------------------------------------------
const ChatInput = ({
  disabled,
  message,
  setMessage,
  handleSubmit,
  handleKeyDown,
  handleChipClick,
  suggestedFollowUps,
  chatPlaceholder,
  onImageAttach,
  imageAttachments,
  onRemoveImage,
  onScreenshot,
  uploadingImages,
  status,
  onReconnect,
  onSketchSubmit,
  messages,
}) => {
  const [sketchOpen, setSketchOpen] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const recognition = useRef(null);

  useEffect(() => {
    // Setup speech recognition if available
    if (window.webkitSpeechRecognition) {
      recognition.current = new window.webkitSpeechRecognition();
      recognition.current.continuous = true;
      recognition.current.interimResults = true;

      recognition.current.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map((r) => r[0].transcript)
          .join('');
        setMessage(transcript);
      };

      recognition.current.onerror = (evt) => {
        console.error('Speech recognition error:', evt.error);
        setIsListening(false);
      };

      recognition.current.onend = () => {
        setIsListening(false);
      };
    }

    return () => {
      if (recognition.current) {
        recognition.current.stop();
      }
    };
  }, [setMessage]);

  const toggleListening = () => {
    if (!recognition.current) {
      alert('Speech recognition not supported in this browser.');
      return;
    }
    if (isListening) {
      recognition.current.stop();
      setIsListening(false);
    } else {
      recognition.current.start();
      setIsListening(true);
    }
  };

  const getDisabledReason = () => {
    if (uploadingImages) {
      return 'Uploading images...';
    }
    if (status === 'WORKING') {
      return 'Please wait for the AI to finish...';
    }
    if (status === 'WORKING_APPLYING') {
      return 'Please wait for the changes to be applied...';
    }
    if (disabled) {
      if (['BUILDING', 'BUILDING_WAITING'].includes(status)) {
        return 'Please wait while environment is set up...';
      }
      return 'Chat is temporarily unavailable';
    }
    return null;
  };

  const isLongConversation = messages.length > 40;

  return (
    <>
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        {/* If disabled, show reason. Otherwise show "chips" */}
        {disabled ||
        uploadingImages ||
        ['WORKING', 'WORKING_APPLYING'].includes(status) ? (
          <p className="text-sm text-muted-foreground">{getDisabledReason()}</p>
        ) : (
          <div className="flex flex-col md:flex-row flex-wrap gap-2">
            {suggestedFollowUps.map((prompt) => (
              <button
                key={prompt}
                type="button"
                disabled={disabled}
                onClick={() => handleChipClick(prompt)}
                className="w-10/12 md:w-auto px-3 py-1.5 text-sm rounded-full bg-secondary hover:bg-secondary/80 transition-colors text-left"
              >
                <span className="block truncate">{prompt}</span>
              </button>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-4">
          {/* If images were attached, show them */}
          {imageAttachments.length > 0 && (
            <ImageAttachments
              attachments={imageAttachments}
              onRemove={onRemoveImage}
            />
          )}
          <div className="flex gap-4">
            <Textarea
              placeholder={chatPlaceholder}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              className="flex-1 min-h-[40px] max-h-[200px] resize-none"
              rows={Math.min(message.split('\n').length, 5)}
            />
          </div>
        </div>

        <div className="flex justify-end gap-2">
          {/* Hidden file input for images */}
          <input
            type="file"
            id="imageInput"
            accept="image/*"
            multiple
            className="hidden"
            onChange={onImageAttach}
          />

          <TooltipProvider>
            {/* Screenshot button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon"
                  variant="outline"
                  disabled={disabled}
                  onClick={onScreenshot}
                >
                  <Scan className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Take screenshot</TooltipContent>
            </Tooltip>

            {/* Upload image button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon"
                  variant="outline"
                  disabled={disabled}
                  onClick={() => document.getElementById('imageInput').click()}
                >
                  <ImageIcon className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Upload image</TooltipContent>
            </Tooltip>

            {/* Sketch button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon"
                  variant="outline"
                  disabled={disabled}
                  onClick={() => setSketchOpen(true)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Draw sketch</TooltipContent>
            </Tooltip>

            {/* Speech-to-text button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon"
                  variant={isListening ? 'destructive' : 'outline'}
                  disabled={disabled}
                  onClick={toggleListening}
                >
                  {isListening ? (
                    <MicOff className="h-4 w-4" />
                  ) : (
                    <Mic className="h-4 w-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {isListening ? 'Stop recording' : 'Start recording'}
              </TooltipContent>
            </Tooltip>

            {/* Reconnect or Send Button */}
            {status === 'DISCONNECTED' ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    onClick={onReconnect}
                    variant="destructive"
                    className="flex items-center gap-2"
                  >
                    <span>Reconnect</span>
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Reconnect to server</TooltipContent>
              </Tooltip>
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="submit"
                    size="icon"
                    disabled={disabled || uploadingImages}
                    variant={isLongConversation ? 'destructive' : 'default'}
                  >
                    {uploadingImages ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <SendIcon className="h-4 w-4" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {isLongConversation
                    ? 'Warning: Very long conversations may degrade quality. Consider a new chat.'
                    : 'Send message'}
                </TooltipContent>
              </Tooltip>
            )}
          </TooltipProvider>
        </div>
      </form>

      {/* Sketch Dialog for drawing a quick image */}
      <SketchDialog
        open={sketchOpen}
        onOpenChange={setSketchOpen}
        onSave={onSketchSubmit}
      />
    </>
  );
};

//------------------------------------------
// A status map to show environment states
//------------------------------------------
const statusMap = {
  NEW_CHAT: { status: 'Ready', color: 'bg-gray-500', animate: false },
  DISCONNECTED: {
    status: 'Disconnected',
    color: 'bg-gray-500',
    animate: false,
  },
  OFFLINE: { status: 'Offline', color: 'bg-gray-500', animate: false },
  BUILDING: {
    status: 'Setting up (~1m)',
    color: 'bg-yellow-500',
    animate: true,
  },
  BUILDING_WAITING: {
    status: 'Setting up (~3m)',
    color: 'bg-yellow-500',
    animate: true,
  },
  READY: { status: 'Ready', color: 'bg-green-500', animate: false },
  WORKING: { status: 'Coding...', color: 'bg-green-500', animate: true },
  WORKING_APPLYING: {
    status: 'Applying...',
    color: 'bg-green-500',
    animate: true,
  },
  CONNECTING: {
    status: 'Connecting...',
    color: 'bg-yellow-500',
    animate: true,
  },
};

//------------------------------------------
// A small loading state if environment is building
//------------------------------------------
const LoadingState = () => {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const duration = 60000; // 1 minute in ms
    const interval = 100; // update every 100ms
    const increment = (interval / duration) * 100;

    const timer = setInterval(() => {
      setProgress((prev) => {
        const next = prev + increment;
        return next >= 100 ? 100 : next;
      });
    }, interval);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
      <p className="text-sm text-muted-foreground">
        Booting up your development environment...
      </p>
      <div className="w-64">
        <Progress value={progress} className="h-2" />
      </div>
    </div>
  );
};

//------------------------------------------
// MAIN Chat Component
//------------------------------------------
export function Chat({
  messages,
  onSendMessage,
  projectTitle,
  status,
  onProjectSelect,
  showStackPacks = false,
  suggestedFollowUps = [],
  onReconnect,
  chat,
}) {
  const { projects } = useUser();
  const [message, setMessage] = useState('');
  const [imageAttachments, setImageAttachments] = useState([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const messagesEndRef = useRef(null);
  const [selectedProject, setSelectedProject] = useState(null);
  const [uploadingImages, setUploadingImages] = useState(false);
  const { sharingChatId, handleShare: shareChat } = useShareChat();
  const { toast } = useToast();

  // If needed, fetch anything else from an API

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!message.trim() && imageAttachments.length === 0) return;

    onSendMessage({
      content: message,
      images: imageAttachments,
    });
    setMessage('');
    setImageAttachments([]);
  };

  const handleKeyDown = (e) => {
    // Plain Enter => submit
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const scrollToBottom = () => {
    if (autoScroll) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleScroll = (e) => {
    const el = e.target;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    setAutoScroll(nearBottom);
  };

  const handleChipClick = (prompt) => {
    onSendMessage({ content: prompt, images: imageAttachments });
  };

  const handleImageAttach = async (e) => {
    const files = Array.from(e.target.files);
    setUploadingImages(true);
    try {
      const processedImages = await Promise.all(
        files.map(async (file) => {
          const resizedImage = await resizeImage(file);
          return uploadImage(resizedImage.data, resizedImage.type);
        })
      );
      setImageAttachments((prev) => [...prev, ...processedImages]);
    } catch (err) {
      console.error('Error processing images:', err);
    } finally {
      setUploadingImages(false);
    }
  };

  const handleRemoveImage = (idx) => {
    setImageAttachments((prev) => prev.filter((_, i) => i !== idx));
    // Clear file input if empty
    if (imageAttachments.length === 1) {
      const fileInput = document.getElementById('imageInput');
      if (fileInput) fileInput.value = '';
    }
  };

  const handleScreenshot = async () => {
    setUploadingImages(true);
    try {
      const screenshot = await captureScreenshot();
      const url = await uploadImage(screenshot.data, screenshot.type);
      setImageAttachments((prev) => [...prev, url]);
    } catch (err) {
      console.error('Error with screenshot:', err);
    } finally {
      setUploadingImages(false);
    }
  };

  const handleSketchSubmit = async (sketchDataUrl) => {
    setUploadingImages(true);
    try {
      const url = await uploadImage(sketchDataUrl, 'image/png');
      setImageAttachments((prev) => [...prev, url]);
    } catch (err) {
      console.error('Error uploading sketch:', err);
    } finally {
      setUploadingImages(false);
    }
  };

  const handleShare = () => {
    if (chat) {
      shareChat(chat);
    }
  };

  return (
    <div className="flex-1 flex flex-col md:max-w-[80%] md:mx-auto w-full h-[100dvh]">
      {/* HEADER */}
      <div className="sticky top-0 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-10 border-b">
        <div className="px-8 py-2.5 pt-16 md:pt-2.5 flex items-center justify-between gap-4">
          <h1 className="text-base font-semibold truncate">{projectTitle}</h1>
          <div className="flex items-center gap-4 flex-shrink-0">
            {chat?.id && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={handleShare}
                      disabled={sharingChatId === chat.id}
                    >
                      {sharingChatId === chat.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : chat.is_public ? (
                        <Link className="h-4 w-4" />
                      ) : (
                        <Share2 className="h-4 w-4" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {chat.is_public ? 'Unshare chat' : 'Share chat'}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  statusMap[status]?.color || 'bg-gray-500'
                } ${statusMap[status]?.animate ? 'animate-pulse' : ''}`}
              />
              <span className="text-sm text-muted-foreground capitalize">
                {statusMap[status]?.status || status}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* BODY / MESSAGES */}
      <div
        className="flex-1 overflow-y-auto p-4 relative"
        onScroll={handleScroll}
      >
        {/* Possibly show environment building loader */}
        {!showStackPacks &&
          messages.length <= 1 &&
          ['BUILDING', 'OFFLINE', 'BUILDING_WAITING'].includes(status) && (
            <LoadingState />
          )}
        {/* If no messages & showStackPacks => show the empty state project picker */}
        {messages.length === 0 && showStackPacks ? (
          <EmptyState
            selectedProject={selectedProject}
            projects={projects}
            onProjectSelect={onProjectSelect}
          />
        ) : (
          <MessageList messages={messages} status={status} />
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* FOOTER / INPUT */}
      <div className="border-t p-4">
        <ChatInput
          disabled={!['NEW_CHAT', 'READY'].includes(status)}
          message={message}
          setMessage={setMessage}
          handleSubmit={handleSubmit}
          handleKeyDown={handleKeyDown}
          handleChipClick={handleChipClick}
          status={status}
          onReconnect={onReconnect}
          suggestedFollowUps={
            suggestedFollowUps?.length
              ? suggestedFollowUps
              : messages.length === 0
              ? STARTER_PROMPTS
              : []
          }
          chatPlaceholder={
            suggestedFollowUps?.length && messages.length > 0
              ? suggestedFollowUps[0]
              : 'What would you like to build?'
          }
          onImageAttach={handleImageAttach}
          imageAttachments={imageAttachments}
          onRemoveImage={handleRemoveImage}
          onScreenshot={handleScreenshot}
          uploadingImages={uploadingImages}
          onSketchSubmit={handleSketchSubmit}
          messages={messages}
        />
      </div>
    </div>
  );
}
