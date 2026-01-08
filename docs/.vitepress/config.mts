import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "Google Workspace Secretary MCP",
  description: "AI-native secretary for Gmail and Google Calendar via MCP",
  base: process.env.VITEPRESS_BASE || "/Google-Workspace-Secretary-MCP/",
  
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    logo: '/logo.svg',
    
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Getting Started', link: '/getting-started' },
      { text: 'Guide', link: '/guide/' },
      { text: 'API Reference', link: '/api/' },
      {
        text: 'v1.1.0',
        items: [
          { text: 'Changelog', link: 'https://github.com/johnneerdael/Google-Workspace-Secretary-MCP/releases' },
          { text: 'Contributing', link: 'https://github.com/johnneerdael/Google-Workspace-Secretary-MCP' }
        ]
      }
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Guide',
          items: [
            { text: 'Introduction', link: '/guide/' },
            { text: 'Configuration', link: '/guide/configuration' },
            { text: 'OAuth Workaround', link: '/guide/oauth_workaround' },
            { text: 'Docker Deployment', link: '/guide/docker' },
            { text: 'Agent Patterns', link: '/guide/agents' },
            { text: 'Use Cases', link: '/guide/use-cases' },
            { text: 'OpenCode Integration', link: '/guide/opencode' }
          ]
        }
      ],
      '/api/': [
        {
          text: 'API Reference',
          items: [
            { text: 'Overview', link: '/api/' },
            { text: 'Email Tools', link: '/api/email' },
            { text: 'Calendar Tools', link: '/api/calendar' },
            { text: 'Intelligence Tools', link: '/api/intelligence' }
          ]
        }
      ]
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/johnneerdael/Google-Workspace-Secretary-MCP' }
    ],

    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2024-present John Neerdael'
    },

    search: {
      provider: 'local'
    },

    editLink: {
      pattern: 'https://github.com/johnneerdael/Google-Workspace-Secretary-MCP/edit/main/docs/:path',
      text: 'Edit this page on GitHub'
    }
  }
})
