# CodexA Eclipse Plugin

Stub for Eclipse IDE integration via the CodexA bridge server.

## Architecture

The Eclipse plugin communicates with CodexA through the HTTP bridge:

```
Eclipse Plugin (Java) → HTTP → codexa serve (port 24842)
```

## Building

1. Import as an Eclipse Plugin project
2. The `plugin.xml` defines commands and menu contributions
3. `CodexaSearchHandler` demonstrates the bridge HTTP integration

## Development

This is a minimal starter. To extend:

1. Add proper Eclipse preferences page for bridge URL configuration
2. Add an Eclipse view for persistent search results
3. Integrate with the Eclipse Search framework
