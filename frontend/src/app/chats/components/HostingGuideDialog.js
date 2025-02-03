import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ExternalLink } from 'lucide-react';

export function HostingGuideDialog({
  open,
  onOpenChange,
  repoName,
  onSendMessage,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Deploy Your Project</DialogTitle>
        </DialogHeader>
        <Tabs defaultValue="netlify" className="w-full">
          <TabsList className="grid w-full grid-cols-1">
            <TabsTrigger value="netlify">Netlify</TabsTrigger>
          </TabsList>
          <TabsContent value="netlify" className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Follow these steps to deploy your project on Netlify:
            </p>
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-sm font-medium">
                  Step 1: Connect to Netlify
                </h3>
                <p className="text-sm text-muted-foreground">
                  Go to{' '}
                  <a
                    href="https://app.netlify.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    Netlify <ExternalLink className="inline h-3 w-3" />
                  </a>{' '}
                  and sign up or log in.
                </p>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium">
                  Step 2: Import from GitHub
                </h3>
                <p className="text-sm text-muted-foreground">
                  Click "Add new site" → "Import an existing project" → "Deploy
                  with GitHub" and select your repository ({repoName}).
                </p>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium">
                  Step 3: Configure Build Settings
                </h3>
                <p className="text-sm text-muted-foreground">
                  Use these build settings:
                </p>
                <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                  <li>
                    Base directory:{' '}
                    <code className="bg-muted px-1 rounded">frontend</code>
                  </li>
                  <li>
                    Build command:{' '}
                    <code className="bg-muted px-1 rounded">npm run build</code>
                  </li>
                  <li>
                    Publish directory:{' '}
                    <code className="bg-muted px-1 rounded">
                      frontend/.next
                    </code>
                  </li>
                  <li>
                    Environment variables:{' '}
                    <code className="bg-muted px-1 rounded">
                      NPM_FLAGS = --force
                    </code>
                  </li>
                </ul>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium">
                  Step 4: Add Netlify Configuration File
                </h3>
                <p className="text-sm text-muted-foreground">
                  Update your project to support Netlify.
                </p>
                <pre
                  className="bg-muted p-2 rounded text-sm cursor-pointer border-2 border-muted-foreground/20 hover:border-primary/50 hover:bg-muted/80 transition-all flex flex-col group"
                  onClick={() =>
                    onSendMessage({
                      content: `If this is a NextJS project (ignore if not), please create (or update) /app/frontend/netlify.toml with:

[[plugins]]
package = "@netlify/plugin-nextjs"`,
                      images: [],
                    })
                  }
                >
                  <code>
                    {`Setup netlify.toml:

[[plugins]]
package = "@netlify/plugin-nextjs"`}
                  </code>
                  <span className="text-muted-foreground group-hover:text-primary transition-colors text-right mt-2">
                    Click to run
                  </span>
                </pre>
                <p className="text-sm text-muted-foreground">
                  This configures Netlify to properly handle Next.js
                  deployments.
                </p>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium">Step 5: Deploy</h3>
                <p className="text-sm text-muted-foreground">
                  Click "Deploy site". Netlify will build and deploy your site.
                  Once complete, you'll get a unique URL where your site is
                  live.
                </p>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium">Optional: Custom Domain</h3>
                <p className="text-sm text-muted-foreground">
                  Go to "Site settings" → "Domain management" to set up a custom
                  domain for your site.
                </p>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
