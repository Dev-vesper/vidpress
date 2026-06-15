# Contributing to vidpress

Thank you for your interest in contributing to vidpress! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and constructive environment for everyone.

## How Can I Contribute?

### Reporting Bugs

Before submitting a bug report:
- Check the issue tracker for similar issues
- Ensure you're using the latest version
- Verify the issue is not already fixed

**When submitting a bug report, include:**
- Your operating system and Python version
- The exact command that caused the issue
- Complete error output
- Steps to reproduce the problem

### Suggesting Enhancements

Open an issue with the "enhancement" label and include:
- A clear description of the feature
- Why this would be useful
- Any potential implementation ideas

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Install development dependencies**:
   ```bash
   pip install -e ".[dev]"
   pre-commit install