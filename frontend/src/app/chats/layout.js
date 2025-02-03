'use client';

import { useUser } from '@/context/user-context';
import { MainLayout } from '@/components/layout/main-layout';

export default function WorkspaceLayout({ children }) {
  const { user } = useUser();

  if (!user) return null;

  return <MainLayout>{children}</MainLayout>;
}
