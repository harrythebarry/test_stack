import { Inter } from 'next/font/google';
import './globals.css';
import { UserProvider } from '@/context/user-context';
import { ThemeProvider } from '@/context/theme-context';
import { Toaster } from '@/components/ui/toaster';

const inter = Inter({ subsets: ['latin'] });

export const viewport = {
  themeColor: '#000000',
  viewport: 'width=device-width, initial-scale=1, maximum-scale=1',
};

export const metadata = {
  title: 'Spark Stack - AI-Powered App and Game Builder',
  description:
    'Build full stack apps and games in seconds using AI. Subscriptionless alternative to v0.dev and bolt.new.',
  manifest: '/manifest.json',
  keywords: [
    'bolt.new alternative',
    'v0.dev alternative',
    'AI app generator',
    'AI game builder',
    'claude sonnet app builder',
  ],
  openGraph: {
    title: 'Spark Stack',
    description:
      'Build full stack apps and games in seconds using AI. Subscriptionless alternative to v0.dev and bolt.new.',
    url: 'https://sparkstack.app',
    siteName: 'Spark Stack',
    images: [],
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Spark Stack',
    description:
      'Build full stack apps and games in seconds using AI. Subscriptionless alternative to v0.dev and bolt.new.',
    images: [],
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <meta name="theme-color" content="#000000" />
        <link rel="manifest" href="/manifest.json" />
      </head>
      <body className={inter.className}>
        <ThemeProvider>
          <UserProvider>
            {children}
            <Toaster />
          </UserProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
