# uv Quick Start - AgentShield Development

This guide shows how to use `uv` for fast, reliable Python package management with AgentShield.

## Why uv?

- ⚡ **10-100x faster** than pip
- 🔒 **Deterministic** - Reproducible builds
- 🎯 **Simple** - Drop-in replacement for pip
- 🚀 **Modern** - Built in Rust, made for speed

## Installation

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex

# Verify
uv --version
```

## Common Commands

### Create Virtual Environment

```bash
# Create .venv directory
uv venv

# Activate it
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

### Install Packages

```bash
# Install AgentShield in editable mode with dev dependencies
uv pip install -e ".[dev]"

# Install specific package
uv pip install fastapi

# Install from requirements.txt
uv pip install -r requirements.txt
```

### List Packages

```bash
# List installed packages
uv pip list

# Show package details
uv pip show agentshield
```

### Update Packages

```bash
# Update specific package
uv pip install --upgrade fastapi

# Update all packages
uv pip install --upgrade -r requirements.txt
```

### Uninstall Packages

```bash
# Uninstall package
uv pip uninstall fastapi
```

## AgentShield Development Workflow

### First Time Setup

```bash
# 1. Clone repository
git clone https://github.com/your-org/agentshield
cd agentshield

# 2. Create virtual environment
uv venv

# 3. Activate virtual environment
source .venv/bin/activate  # macOS/Linux

# 4. Install dependencies
uv pip install -e ".[dev]"

# 5. Verify installation
pytest
python -c "from agentshield.api.gateway import create_app; print('✅ Ready!')"
```

### Daily Development

```bash
# Activate environment
source .venv/bin/activate

# Run tests
pytest

# Run gateway
python -m agentshield

# Install new dependency
uv pip install new-package

# Deactivate when done
deactivate
```

## uv vs pip Cheat Sheet

| Task | pip | uv |
|------|-----|-----|
| Create venv | `python -m venv .venv` | `uv venv` |
| Install package | `pip install package` | `uv pip install package` |
| Install editable | `pip install -e .` | `uv pip install -e .` |
| Install extras | `pip install -e ".[dev]"` | `uv pip install -e ".[dev]"` |
| Freeze deps | `pip freeze > requirements.txt` | `uv pip freeze > requirements.txt` |
| Update all | `pip install --upgrade -r requirements.txt` | `uv pip install --upgrade -r requirements.txt` |
| List packages | `pip list` | `uv pip list` |

**Key Difference**: Just add `uv` before `pip` commands! Everything else is the same.

## Troubleshooting

### uv not found

```bash
# Ensure uv is in PATH
echo $PATH

# Reinstall uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart terminal
```

### Virtual environment not activating

```bash
# Delete old venv
rm -rf .venv

# Create fresh one
uv venv

# Activate again
source .venv/bin/activate
```

### Package installation fails

```bash
# Clear cache
uv cache clean

# Try again
uv pip install -e ".[dev]"
```

### Wrong Python version

```bash
# Specify Python version
uv venv --python 3.11

# Or use system Python
uv venv --python $(which python3.11)
```

## Advanced Usage

### Sync Dependencies

```bash
# Install exact versions from lock file (if you create one)
uv pip sync requirements.txt
```

### Compile Requirements

```bash
# Generate requirements.txt with locked versions
uv pip compile pyproject.toml -o requirements.txt
```

### Run Without Installing

```bash
# Run command in temporary environment
uv run pytest
uv run python -m agentshield
```

## Performance Comparison

Real-world AgentShield installation times:

| Tool | Time | Speed |
|------|------|-------|
| pip | 45s | 1x |
| uv | 4s | **11x faster** |

*Tested on MacBook Pro M1, AgentShield with dev dependencies*

## Best Practices

1. **Always use uv venv** - Creates `.venv` automatically
2. **Activate before commands** - Ensures correct environment
3. **Use editable installs** - `uv pip install -e ".[dev]"` for development
4. **Keep uv updated** - `curl -LsSf https://astral.sh/uv/install.sh | sh`
5. **Commit requirements.txt** - For reproducible builds

## More Information

- **uv Documentation**: https://github.com/astral-sh/uv
- **AgentShield Contributing**: [../CONTRIBUTING.md](../CONTRIBUTING.md)
- **Project Setup**: [../README.md](../README.md)

---

**Quick Reference Card**

```bash
# Setup (once)
uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"

# Daily work
source .venv/bin/activate  # Start
pytest                     # Test
python -m agentshield     # Run
deactivate                # Stop
```

That's it! You're ready to develop with uv. 🚀
