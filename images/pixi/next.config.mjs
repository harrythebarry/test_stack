/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'pixijs.com',
        pathname: '/assets/**',
      },
    ],
  },
};

export default nextConfig;
