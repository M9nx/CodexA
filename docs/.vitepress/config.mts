import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'CodexA',
  description: 'Developer Intelligence Engine — semantic code search, AI-assisted understanding, and workspace tooling',

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' }],
    ['meta', { name: 'theme-color', content: '#3eaf7c' }],
    ['meta', { name: 'og:type', content: 'website' }],
    ['meta', { name: 'og:title', content: 'CodexA — Developer Intelligence Engine' }],
    ['meta', { name: 'og:description', content: 'Semantic code search, AI-assisted understanding, and workspace tooling for developers and AI agents.' }],
  ],

  cleanUrls: true,
  lastUpdated: true,

  themeConfig: {
    logo: '/logo.svg',
    siteTitle: 'CodexA',

    nav: [
      {
        text: 'Documentation',
        items: [
          { text: 'Introduction', link: '/guide/introduction' },
          { text: 'Installation', link: '/guide/installation' },
          { text: 'Quick Start', link: '/guide/quickstart' },
          { text: 'Configuration', link: '/guide/configuration' },
        ],
      },
      {
        text: 'Features',
        items: [
          { text: 'Semantic Search', link: '/features/semantic-search' },
          { text: 'AI Tools Protocol', link: '/features/ai-tools' },
          { text: 'Quality Analysis', link: '/features/quality-analysis' },
          { text: 'Plugin System', link: '/features/plugin-system' },
          { text: 'MCP Integration', link: '/features/mcp-integration' },
          { text: 'Evolution Engine', link: '/features/evolution-engine' },
        ],
      },
      { text: 'API Reference', link: '/reference/cli' },
      {
        text: 'v0.5.0',
        items: [
          {
            text: 'Release Info',
            items: [
              { text: 'Changelog', link: 'https://github.com/M9nx/CodexA/blob/main/CHANGELOG.md' },
              { text: 'Release Notes', link: 'https://github.com/M9nx/CodexA/blob/main/RELEASE_NOTES.md' },
              { text: 'Upgrade Guide', link: '/guide/upgrade' },
              { text: 'Roadmap', link: '/guide/roadmap' },
            ],
          },
          {
            text: 'Previous Versions',
            items: [
              { text: 'v0.4.5', link: 'https://pypi.org/project/codexa/0.4.5/' },
              { text: 'v0.4.4', link: 'https://pypi.org/project/codexa/0.4.4/' },
              { text: 'v0.4.3', link: 'https://pypi.org/project/codexa/0.4.3/' },
              { text: 'v0.4.2', link: 'https://pypi.org/project/codexa/0.4.2/' },
              { text: 'v0.4.1', link: 'https://pypi.org/project/codexa/0.4.1/' },
              { text: 'v0.4.0', link: 'https://pypi.org/project/codexa/0.4.0/' },
            ],
          },
        ],
      },
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Getting Started',
          collapsed: false,
          items: [
            { text: 'Introduction', link: '/guide/introduction' },
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Quick Start', link: '/guide/quickstart' },
          ],
        },
        {
          text: 'Essentials',
          collapsed: false,
          items: [
            { text: 'Configuration', link: '/guide/configuration' },
            { text: 'AI Agent Setup', link: '/guide/ai-agent-setup' },
          ],
        },
        {
          text: 'Community',
          collapsed: false,
          items: [
            { text: 'Contributing', link: '/guide/contributing' },
            { text: 'Roadmap', link: '/guide/roadmap' },
            { text: 'Upgrade Guide', link: '/guide/upgrade' },
          ],
        },
      ],
      '/features/': [
        {
          text: 'Core',
          collapsed: false,
          items: [
            { text: 'Semantic Search', link: '/features/semantic-search' },
            { text: 'Quality Analysis', link: '/features/quality-analysis' },
            { text: 'AI Tools Protocol', link: '/features/ai-tools' },
          ],
        },
        {
          text: 'Integrations',
          collapsed: false,
          items: [
            { text: 'Plugin System', link: '/features/plugin-system' },
            { text: 'MCP Integration', link: '/features/mcp-integration' },
            { text: 'Web Interface', link: '/features/web-interface' },
          ],
        },
        {
          text: 'Advanced',
          collapsed: false,
          items: [
            { text: 'Workflow Intelligence', link: '/features/workflow-intelligence' },
            { text: 'Evolution Engine', link: '/features/evolution-engine' },
          ],
        },
      ],
      '/reference/': [
        {
          text: 'API Reference',
          collapsed: false,
          items: [
            { text: 'CLI Commands', link: '/reference/cli' },
            { text: 'Modules', link: '/reference/modules' },
            { text: 'REST API', link: '/reference/api' },
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
      text: 'Edit this page on GitHub',
    },

    footer: {
      message: 'Released under the <a href="https://github.com/M9nx/CodexA/blob/main/LICENSE">MIT License</a>.',
      copyright: 'Copyright © 2025 <a href="https://github.com/M9nx">M9nx</a> · v0.4.5',
    },

    search: {
      provider: 'local',
    },

    outline: {
      level: [2, 3],
      label: 'On this page',
    },

    lastUpdated: {
      text: 'Last updated',
    },

    docFooter: {
      prev: 'Previous',
      next: 'Next',
    },

    returnToTopLabel: 'Back to top',
    darkModeSwitchLabel: 'Appearance',
    sidebarMenuLabel: 'Menu',
  },

  markdown: {
    lineNumbers: true,
  },
})
