/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'prompt-stack.sshh.io',
        pathname: '/api/mocks/images/**',
      },
      {
        protocol: 'https',
        hostname: 'sparkstack.app',
        pathname: '/api/mocks/images/**',
      },
      {
        protocol: 'https',
        hostname: 'picsum.photos',
      },
      {
        protocol: 'https',
        hostname: 'placehold.co',
      },
      {
        protocol: 'https',
        hostname: 'avatars.githubusercontent.com',
      },
      {
        protocol: 'https',
        hostname: 'ui-avatars.com',
      },
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
      },
      {
        protocol: 'https',
        hostname: '*.cloudinary.com',
      },
      {
        protocol: 'https',
        hostname: '*.imgur.com',
      },
    ],
  },

  typescript: {
    ignoreBuildErrors: process.env.NODE_ENV === 'development',
  },

  eslint: {
    ignoreDuringBuilds: process.env.NODE_ENV === 'development',
  },

  reactStrictMode: process.env.NODE_ENV === 'development' ? false : true,

  experimental: {
    largePageDataBytes: 128 * 100000,
  },

  async headers() {
    return process.env.NODE_ENV === 'development' 
      ? [
          {
            source: '/api/:path*',
            headers: [
              { key: 'Access-Control-Allow-Origin', value: '*' },
              { key: 'Access-Control-Allow-Methods', value: 'GET,POST,PUT,DELETE,OPTIONS' },
              { key: 'Access-Control-Allow-Headers', value: '*' },
            ],
          },
        ]
      : []
  },

  webpack: (config, { dev, isServer }) => {
    if (dev) {
      config.performance = {
        hints: false,
        maxEntrypointSize: 512000,
        maxAssetSize: 512000
      }
    }
    
    return config
  },
}

export default nextConfig
