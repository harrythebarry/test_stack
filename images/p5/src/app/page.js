'use client';

import { useEffect } from 'react';

export default function Home() {
  useEffect(() => {
    // Only run p5 initialization on the client side
    if (typeof window !== 'undefined') {
      new window.p5();
    }

    // Cleanup function
    return () => {
      if (typeof window !== 'undefined' && window.p5) {
        // Remove the canvas when component unmounts
        document.querySelector('canvas')?.remove();
      }
    };
  }, []); // Empty dependency array means this runs once on mount

  return <main>{/* p5.js will create and inject the canvas here */}</main>;
}
