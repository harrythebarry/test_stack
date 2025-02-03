'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { GitBranch, Loader2, Globe } from 'lucide-react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useToast } from '@/hooks/use-toast';
import { HostingGuideDialog } from './HostingGuideDialog';

export function DeployTab({ project, team, onSendMessage }) {
  const [status, setStatus] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isPushing, setIsPushing] = useState(false);
  const [message, setMessage] = useState(null);
  const [githubToken, setGithubToken] = useState('');
  const [showHostingGuide, setShowHostingGuide] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    const fetchGithubDeployStatus = async () => {
      const status = await api.deployStatusGithub(team.id, project.id);
      setStatus(status);
    };
    fetchGithubDeployStatus();
  }, [project, team]);

  const handleGithubCreateDeploy = async () => {
    if (!githubToken) {
      toast({
        title: 'GitHub Token Required',
        description: 'Please enter your GitHub token to continue.',
        variant: 'destructive',
      });
      return;
    }
    setIsCreating(true);
    setMessage('Deploying...');
    try {
      await api.deployCreateGithub(
        team.id,
        project.id,
        {
          githubToken,
        },
        (message) => {
          try {
            const data = JSON.parse(message);
            if (data.message) {
              setMessage(data.message);
            }
            if (data.done) {
              api.deployStatusGithub(team.id, project.id).then((status) => {
                setStatus(status);
                toast({
                  title: 'Integration Complete',
                  description: 'Your project has been integrated with GitHub.',
                });
                setIsCreating(false);
              });
            }
          } catch (e) {
            console.error('Failed to parse deploy status:', e);
          }
        }
      );
    } catch (error) {
      console.error('Failed to deploy:', error);
      toast({
        title: 'Integration Failed',
        description: 'There was an error integrating with GitHub.',
        variant: 'destructive',
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleGithubPushDeploy = async () => {
    setIsPushing(true);
    setMessage('Pushing...');
    try {
      await api.deployPushGithub(team.id, project.id);
      toast({
        title: 'Push Complete',
        description: 'Your project has been pushed to GitHub.',
      });
    } catch (error) {
      console.error('Failed to push:', error);
      toast({
        title: 'Push Failed',
        description: 'There was an error pushing to GitHub.',
        variant: 'destructive',
      });
    } finally {
      setIsPushing(false);
    }
  };

  if (status?.created) {
    return (
      <>
        <Card className="p-4">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-medium">GitHub</h3>
                <a
                  href={`https://github.com/${status.repo_name}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  {status.repo_name}
                </a>
              </div>
              <Button onClick={handleGithubPushDeploy} disabled={isPushing}>
                {isPushing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {message}
                  </>
                ) : (
                  <>
                    <GitBranch className="mr-2 h-4 w-4" />
                    Push Changes
                  </>
                )}
              </Button>
            </div>
          </div>
        </Card>
        <Button
          variant="outline"
          className="w-full mt-4"
          onClick={() => setShowHostingGuide(true)}
        >
          <Globe className="mr-2 h-4 w-4" />
          How do I host this as a website for free?
        </Button>

        <HostingGuideDialog
          open={showHostingGuide}
          onOpenChange={setShowHostingGuide}
          repoName={status.repo_name}
          onSendMessage={onSendMessage}
        />
      </>
    );
  } else if (status && !status.created) {
    return (
      <Card className="p-4">
        <div className="space-y-4">
          <div className="text-sm text-muted-foreground">
            <p>
              For long-term hosting and CI/CD deployments, we support syncing
              with GitHub.
            </p>
            <ul className="list-disc list-inside mt-2">
              <li>24/7 uptime</li>
              <li>Custom domains</li>
              <li>Free hosting with tools like Netlify, Vercel, and more</li>
            </ul>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <h3 className="text-sm font-medium">Step 1: GitHub Token</h3>
              <p className="text-sm text-muted-foreground">
                Create a GitHub token with <b>repo</b> access at{' '}
                <a
                  href="https://github.com/settings/tokens/new"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  github.com/settings/tokens/new
                </a>
              </p>
              <Input
                type="password"
                placeholder="Enter your GitHub token"
                value={githubToken}
                onChange={(e) => setGithubToken(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-medium">Step 2: Create Repository</h3>
              <p className="text-sm text-muted-foreground">
                Create a new GitHub repository to host your project.
              </p>
              <Button onClick={handleGithubCreateDeploy} className="w-full">
                {isCreating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {message}
                  </>
                ) : (
                  <>
                    <GitBranch className="mr-2 h-4 w-4" />
                    Create Repository
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </Card>
    );
  } else {
    return (
      <Card className="flex items-center justify-center p-4">
        <Loader2 className="h-4 w-4 animate-spin" />
      </Card>
    );
  }
}
