import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'CodexA',
  description: 'Developer Intelligence Engine — semantic code search, AI-assisted understanding, and workspace tooling',

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' }],
  ],

  themeConfig: {
    nav: [
      { text: 'Guide', link: '/guide/introduction' },
      { text: 'Features', link: '/features/semantic-search' },
      { text: 'Reference', link: '/reference/cli' },
      { text: 'GitHub', link: 'https://github.com/M9nx/CodexA' },
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Guide',
          items: [
            { text: 'Introduction', link: '/guide/introduction' },
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Quick Start', link: '/guide/quickstart' },
            { text: 'AI Agent Setup', link: '/guide/ai-agent-setup' },
            { text: 'Configuration', link: '/guide/configuration' },
            { text: 'Contributing', link: '/guide/contributing' },
            { text: 'Roadmap', link: '/guide/roadmap' },
          ],
        },
      ],
      '/features/': [
        {
          text: 'Features',
          items: [
            { text: 'Semantic Search', link: '/features/semantic-search' },
            { text: 'Quality Analysis', link: '/features/quality-analysis' },
            { text: 'AI Tools Protocol', link: '/features/ai-tools' },
            { text: 'Plugin System', link: '/features/plugin-system' },
            { text: 'MCP Integration', link: '/features/mcp-integration' },
            { text: 'Web Interface', link: '/features/web-interface' },
            { text: 'Workflow Intelligence', link: '/features/workflow-intelligence' },
            { text: 'Evolution Engine', link: '/features/evolution-engine' },
          ],
        },
      ],
      '/reference/': [
        {
          text: 'Reference',
          items: [
            { text: 'CLI Commands', link: '/reference/cli' },
            { text: 'Modules', link: '/reference/modules' },
            { text: 'API', link: '/reference/api' },
            { text: 'Bridge Protocol', link: '/reference/bridge' },
            { text: 'Architecture', link: '/reference/architecture' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/M9nx/CodexA' },
    ],

    editLink: {
      pattern: 'https://github.com/M9nx/CodexA/edit/main/docs/:path',
    },

    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2025 M9nx',
    },

    search: {
      provider: 'local',
    },
  },

  markdown: {
    lineNumbers: true,
  },
})
