'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Settings2, Trash2, Loader2, Eye, EyeOff } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { api } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

export function EnvVarsDialog({ project, team }) {
  const [envVars, setEnvVars] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isOpen, setIsOpen] = useState(false);
  const [hiddenVars, setHiddenVars] = useState({});
  const [editingVars, setEditingVars] = useState({});
  const { toast } = useToast();

  useEffect(() => {
    if (isOpen) {
      loadEnvVars();
    }
  }, [isOpen]);

  const loadEnvVars = async () => {
    try {
      const response = await api.getProjectEnvVars(team.id, project.id);
      setEnvVars(response.env_vars);
      // Initialize all variables as hidden
      const hidden = Object.keys(response.env_vars).reduce((acc, key) => {
        acc[key] = true;
        return acc;
      }, {});
      setHiddenVars(hidden);
    } catch (error) {
      console.error('Failed to load env vars:', error);
      toast({
        title: 'Error',
        description: 'Failed to load environment variables',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddVar = () => {
    setEnvVars({ ...envVars, '': '' });
    setHiddenVars({ ...hiddenVars, '': true });
  };

  const handleUpdateVar = (oldKey, newKey, value) => {
    setEditingVars((prev) => ({
      ...prev,
      [oldKey]: { key: newKey, value },
    }));
  };

  const handleBlur = (oldKey) => {
    const edit = editingVars[oldKey];
    if (!edit) return;

    const newEnvVars = { ...envVars };
    if (oldKey in newEnvVars) {
      delete newEnvVars[oldKey];
    }
    newEnvVars[edit.key] = edit.value;
    setEnvVars(newEnvVars);

    // Update hidden state for the new key
    const newHiddenVars = { ...hiddenVars };
    if (oldKey in newHiddenVars) {
      delete newHiddenVars[oldKey];
    }
    newHiddenVars[edit.key] = hiddenVars[oldKey] ?? true;
    setHiddenVars(newHiddenVars);

    // Clear the editing state for this key
    const newEditingVars = { ...editingVars };
    delete newEditingVars[oldKey];
    setEditingVars(newEditingVars);
  };

  const handleDeleteVar = (key) => {
    const newEnvVars = { ...envVars };
    delete newEnvVars[key];
    setEnvVars(newEnvVars);

    const newHiddenVars = { ...hiddenVars };
    delete newHiddenVars[key];
    setHiddenVars(newHiddenVars);
  };

  const toggleVisibility = (key) => {
    setHiddenVars({
      ...hiddenVars,
      [key]: !hiddenVars[key],
    });
  };

  const handleSave = async () => {
    try {
      await api.updateProjectEnvVars(team.id, project.id, {
        env_vars: envVars,
      });
      toast({
        title: 'Success',
        description:
          'Environment variables updated. Restart the project for changes to take effect.',
      });
      setIsOpen(false);
    } catch (error) {
      console.error('Failed to update env vars:', error);
      toast({
        title: 'Error',
        description: 'Failed to update environment variables',
        variant: 'destructive',
      });
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="ml-2">
          <Settings2 className="h-4 w-4 mr-2" />
          Edit
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Environment Variables</DialogTitle>
          <DialogDescription>
            Add or modify environment variables for your project. Changes will
            take effect after restarting the project.
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(envVars).map(([key, value]) => (
                <div key={key} className="flex gap-2">
                  <Input
                    placeholder="Key"
                    value={editingVars[key]?.key ?? key}
                    onChange={(e) =>
                      handleUpdateVar(
                        key,
                        e.target.value,
                        editingVars[key]?.value ?? value
                      )
                    }
                    onBlur={() => handleBlur(key)}
                    className="flex-1"
                  />
                  <div className="flex-1 relative">
                    <Input
                      placeholder="Value"
                      type={hiddenVars[key] ? 'password' : 'text'}
                      value={editingVars[key]?.value ?? value}
                      onChange={(e) =>
                        handleUpdateVar(
                          key,
                          editingVars[key]?.key ?? key,
                          e.target.value
                        )
                      }
                      onBlur={() => handleBlur(key)}
                      className="w-full pr-10"
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      className="absolute right-0 top-0 h-full"
                      onClick={() => toggleVisibility(key)}
                    >
                      {hiddenVars[key] ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDeleteVar(key)}
                    className="h-10 w-10 text-destructive hover:text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              <Button
                variant="outline"
                onClick={handleAddVar}
                className="w-full"
              >
                Add Variable
              </Button>
            </div>
          )}
        </div>
        <div className="flex justify-end space-x-2">
          <Button variant="outline" onClick={() => setIsOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save Changes</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
