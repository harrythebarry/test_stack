'use client';

import React from 'react';
import { Sidebar } from './sidebar';

export const MainLayout = ({ children }) => {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
};
