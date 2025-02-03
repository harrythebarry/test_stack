'use client';

import { useParams } from 'next/navigation';
import WorkspacePage from '../page';

export default function ProjectWorkspace() {
  const params = useParams();

  return <WorkspacePage chatId={params.chatId} />;
}
