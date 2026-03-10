# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.4.x   | :white_check_mark: |
| < 0.4   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in CodexA, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Email the maintainers or use GitHub's private vulnerability reporting feature.
3. Include a description of the vulnerability, steps to reproduce, and potential impact.

We will acknowledge reports within 48 hours and work toward a fix promptly.

## Security Architecture

CodexA includes a built-in `SafetyValidator` with detection patterns for:

- SQL injection
- Command injection
- Path traversal
- Hardcoded secrets
- XSS risks
- Insecure cryptography
- Insecure HTTP usage
- SSL verification bypass
- `eval()` / `exec()` usage
- Deserialization risks

The safety pipeline runs automatically on code review and validation operations. Plugins can extend validation via the `CUSTOM_VALIDATION` hook.
