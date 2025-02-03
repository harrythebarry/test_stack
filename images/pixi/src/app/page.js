'use client';

import { useEffect } from 'react';

export default function Home() {
  useEffect(() => {
    (async () => {
      await import('./pixi/app');
    })();
  }, []);
  return <div></div>;
}
