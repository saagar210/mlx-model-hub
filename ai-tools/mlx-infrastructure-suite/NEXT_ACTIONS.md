# MLX Infrastructure Suite - Next Actions

**Date:** January 12, 2026
**Priority:** Critical → High → Medium → Low
**Estimated Total Time:** 6-10 hours to be ready for development

---

## 🔴 CRITICAL: Resolve Blockers (Required Before Starting)

### 1. Install Xcode (30-60 minutes)

**Why:** Required to build MLXDash (Swift menu bar app)

**Options:**

**Option A: App Store (Recommended)**
1. Open App Store
2. Search for "Xcode"
3. Click "Get" or "Install"
4. Wait for download (~15GB, 30-60 min depending on connection)

**Option B: Command Line Tools**
```bash
xcode-select --install
```

**Verify Installation:**
```bash
xcodebuild -version
# Expected output: Xcode 16.x, Build version XXX

swift --version
# Expected: Swift 5.9+
```

**Status:** ❌ Not installed

---

### 2. Install Missing Tools (5 minutes)

```bash
brew install create-dmg xcbeautify
```

**Why:**
- `create-dmg`: Package MLXDash for distribution
- `xcbeautify`: Pretty-print Xcode build output

**Verify:**
```bash
which create-dmg xcbeautify
```

**Status:** ❌ Not installed

---

### 3. Obtain Developer ID Certificate (OPTIONAL - Can defer)

**Why:** Required to sign and notarize MLXDash for public distribution

**Note:** NOT required for development/testing. Can be obtained later before v1.0 release.

**Steps (if doing now):**
1. Go to https://developer.apple.com
2. Sign in with Apple ID
3. Navigate to: Account → Certificates, Identifiers & Profiles
4. Click "Certificates" → Create new
5. Select "Developer ID Application"
6. Follow prompts to download certificate
7. Double-click .cer file to install in Keychain

**Verify:**
```bash
security find-identity -v -p codesigning
# Should show: "Developer ID Application: Your Name (TEAM_ID)"
```

**Status:** ❌ Not obtained (but can defer)

---

## 🟠 HIGH PRIORITY: Repository Setup (2-3 hours)

### 4. Choose Repository Structure

**Option A: Monorepo (Recommended)**
- Single repository: `mlx-infrastructure-suite`
- Contains: `mlxdash/`, `mlx-cache/`, `swiftmlx/`
- Benefits: Easier coordination, shared CI/CD, atomic releases
- Tools: Turborepo or simple structure

**Option B: Multi-repo**
- Three repositories: `mlxdash`, `mlx-cache`, `swiftmlx`
- Benefits: Independent versioning, smaller repos
- Drawbacks: Coordination overhead

**Recommendation:** Monorepo for MVP, can split later if needed

---

### 5. Create GitHub Repository

```bash
# Create directory
cd /Users/d/claude-code/ai-tools/mlx-infrastructure-suite

# Initialize git (if not already)
git init

# Create .gitignore
cat > .gitignore << 'EOF'
# macOS
.DS_Store
*.swp

# Xcode
*.xcuserstate
*.xcworkspace
xcuserdata/
DerivedData/
.build/

# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
*.egg-info/
dist/
build/
.pytest_cache/
.coverage
.mypy_cache/
.ruff_cache/

# UV
uv.lock

# Environment
.env
.env.local

# IDEs
.vscode/
.idea/
*.sublime-*

# Testing
.taskmaster/
EOF

# Create README
cat > README.md << 'EOF'
# MLX Infrastructure Suite

The "plumbing" that every MLX developer needs. Three tools that make local ML on Mac seamless.

## The Suite

- **MLXDash** - Menu bar monitor for ML workloads
- **MLXCache** - Shared model weight cache with deduplication
- **SwiftMLX** - Xcode templates for MLX apps

## Status

🚧 Under development - See [ROADMAP_2026.md](./ROADMAP_2026.md)

## Documentation

- [Audit Report](./AUDIT_REPORT_2026-01-12.md) - Comprehensive project audit
- [Roadmap](./ROADMAP_2026.md) - Implementation and growth plan
- [Executive Summary](./EXECUTIVE_SUMMARY.md) - Quick overview
- [Strategy](./STRATEGY.md) - Business strategy
- [Implementation Plan](./IMPLEMENTATION_PLAN_V2.md) - Technical specifications

## Quick Start

Documentation for usage will be added once tools are implemented.

## License

MIT
EOF

# Create LICENSE
cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2026 [Your Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

# Create remote repository on GitHub
gh repo create mlx-infrastructure-suite --public --source=. --remote=origin

# Initial commit
git add .
git commit -m "Initial commit: Planning documents and project structure"
git push -u origin main
```

---

### 6. Create Directory Structure

```bash
cd /Users/d/claude-code/ai-tools/mlx-infrastructure-suite

# Create directories
mkdir -p mlxdash/{MLXDash/{App,Views,Services,Database,Models,Resources},MLXDashTests}
mkdir -p mlx-cache/{src/mlx_cache/{sources,__pycache__},tests}
mkdir -p swiftmlx/{Sources/{SwiftMLX,SwiftMLXUI},Tests/SwiftMLXTests,Templates,Examples}
mkdir -p .github/workflows
mkdir -p shared/{config,assets}
mkdir -p scripts
mkdir -p docs

echo "✅ Directory structure created"
```

---

## 🟡 MEDIUM PRIORITY: CI/CD Setup (2-3 hours)

### 7. Create GitHub Actions Workflows

**MLXCache CI:**
```bash
cat > .github/workflows/mlxcache-ci.yml << 'EOF'
name: MLXCache CI

on:
  push:
    branches: [ main ]
    paths:
      - 'mlx-cache/**'
  pull_request:
    branches: [ main ]
    paths:
      - 'mlx-cache/**'

jobs:
  test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install UV
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install dependencies
        working-directory: mlx-cache
        run: uv sync

      - name: Run tests
        working-directory: mlx-cache
        run: uv run pytest --cov=mlx_cache --cov-report=term-missing

      - name: Lint with ruff
        working-directory: mlx-cache
        run: uv run ruff check .

      - name: Type check with mypy
        working-directory: mlx-cache
        run: uv run mypy src/mlx_cache
EOF
```

**MLXDash CI:**
```bash
cat > .github/workflows/mlxdash-ci.yml << 'EOF'
name: MLXDash CI

on:
  push:
    branches: [ main ]
    paths:
      - 'mlxdash/**'
  pull_request:
    branches: [ main ]
    paths:
      - 'mlxdash/**'

jobs:
  build:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Select Xcode
        run: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer

      - name: Build
        working-directory: mlxdash
        run: swift build

      - name: Run tests
        working-directory: mlxdash
        run: swift test

      - name: Lint (if swiftlint configured)
        working-directory: mlxdash
        run: |
          if command -v swiftlint &> /dev/null; then
            swiftlint
          fi
EOF
```

**SwiftMLX CI:**
```bash
cat > .github/workflows/swiftmlx-ci.yml << 'EOF'
name: SwiftMLX CI

on:
  push:
    branches: [ main ]
    paths:
      - 'swiftmlx/**'
  pull_request:
    branches: [ main ]
    paths:
      - 'swiftmlx/**'

jobs:
  build:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Select Xcode
        run: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer

      - name: Build
        working-directory: swiftmlx
        run: swift build

      - name: Run tests
        working-directory: swiftmlx
        run: swift test
EOF
```

---

### 8. Create Issue Templates

```bash
mkdir -p .github/ISSUE_TEMPLATE

cat > .github/ISSUE_TEMPLATE/bug_report.yml << 'EOF'
name: Bug Report
description: File a bug report
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to fill out this bug report!

  - type: dropdown
    id: component
    attributes:
      label: Component
      options:
        - MLXDash
        - MLXCache
        - SwiftMLX
    validations:
      required: true

  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: Describe the bug
    validations:
      required: true

  - type: textarea
    id: steps
    attributes:
      label: Steps to reproduce
      description: How can we reproduce this?
    validations:
      required: true

  - type: textarea
    id: expected
    attributes:
      label: Expected behavior
    validations:
      required: true

  - type: textarea
    id: environment
    attributes:
      label: Environment
      description: |
        - macOS version
        - Xcode version (if MLXDash/SwiftMLX)
        - Python version (if MLXCache)
      value: |
        - macOS:
        - Xcode:
        - Python:
    validations:
      required: true
EOF

cat > .github/ISSUE_TEMPLATE/feature_request.yml << 'EOF'
name: Feature Request
description: Suggest a new feature
labels: ["enhancement"]
body:
  - type: dropdown
    id: component
    attributes:
      label: Component
      options:
        - MLXDash
        - MLXCache
        - SwiftMLX
    validations:
      required: true

  - type: textarea
    id: description
    attributes:
      label: Feature description
    validations:
      required: true

  - type: textarea
    id: use-case
    attributes:
      label: Use case
      description: Why is this feature needed?
    validations:
      required: true

  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives considered
EOF
```

---

## 🟢 LOW PRIORITY: Code Reuse (1-2 hours)

### 9. Copy HuggingFace Service from MLX Model Hub

```bash
# Create target directory
mkdir -p mlx-cache/src/mlx_cache/sources

# Copy service
cp /Users/d/claude-code/ai-tools/mlx-model-hub/backend/src/mlx_hub/services/huggingface.py \
   mlx-cache/src/mlx_cache/sources/huggingface_download.py

# Create __init__.py
touch mlx-cache/src/mlx_cache/sources/__init__.py

echo "✅ HuggingFace service copied - needs adaptation (remove FastAPI deps)"
```

**Adaptation needed:**
- Remove FastAPI dependencies
- Add CLI progress callbacks for Typer/Rich
- Add symlink creation methods
- Add registry integration

---

### 10. Create Shared Types (Optional)

If you want to share types between Python projects:

```bash
# Create shared package
mkdir -p shared/python/mlx_types
touch shared/python/mlx_types/__init__.py

cat > shared/python/mlx_types/models.py << 'EOF'
"""Shared data models for MLX Infrastructure Suite."""

from dataclasses import dataclass
from typing import Optional

@dataclass
class ModelInfo:
    """Information about an ML model."""
    id: str
    name: str
    size_bytes: int
    quantization: Optional[str] = None
    provider: str = "unknown"  # "ollama", "huggingface", "local"
EOF
```

---

## 🎯 RECOMMENDED FIRST ACTIONS (Today)

**Priority Order:**

1. ✅ Install Xcode (30-60 min) - **BLOCKING**
2. ✅ Install tools (5 min)
3. ✅ Create GitHub repository (30 min)
4. ✅ Create directory structure (10 min)
5. ✅ Copy HuggingFace service (10 min)
6. ✅ Create CI/CD workflows (1-2 hours)
7. ✅ Create issue templates (30 min)

**Total Time: 3-5 hours**

**Optional (can do later):**
- Obtain Developer ID certificate
- Create shared types package
- Set up project management tools

---

## 📋 Checklist

### Critical Blockers
- [ ] Xcode installed and verified
- [ ] create-dmg installed
- [ ] xcbeautify installed
- [ ] UV package manager working
- [ ] Ollama running locally

### Repository Setup
- [ ] GitHub repository created
- [ ] .gitignore configured
- [ ] README.md created
- [ ] LICENSE added (MIT)
- [ ] Directory structure created
- [ ] Initial commit pushed

### CI/CD
- [ ] MLXCache CI workflow
- [ ] MLXDash CI workflow
- [ ] SwiftMLX CI workflow
- [ ] Issue templates created
- [ ] PR template created

### Code Reuse
- [ ] HuggingFace service copied
- [ ] Adaptation plan documented
- [ ] Shared types created (optional)

### Optional (Defer)
- [ ] Developer ID certificate
- [ ] Pre-commit hooks
- [ ] Contributing guidelines
- [ ] Code of conduct

---

## 🚀 After Setup Complete

Once all critical and high-priority items are done:

1. **Review documents:**
   - Read [AUDIT_REPORT_2026-01-12.md](./AUDIT_REPORT_2026-01-12.md) in detail
   - Review [IMPLEMENTATION_PLAN_V2.md](./IMPLEMENTATION_PLAN_V2.md)
   - Familiarize with [ROADMAP_2026.md](./ROADMAP_2026.md)

2. **Start Phase 1: MLXCache MVP**
   - Create `mlx-cache/pyproject.toml`
   - Implement CLI scaffold with Typer
   - Set up SQLite registry
   - Begin core functionality

3. **Track Progress:**
   - Use GitHub Projects or Issues
   - Update ROADMAP with actual progress
   - Weekly reviews of timeline

---

## 📞 Questions or Issues?

If you encounter problems:

1. **Xcode issues:** Check System Requirements, ensure enough disk space (15GB+)
2. **UV issues:** Try `brew install uv` if script installation fails
3. **GitHub issues:** Ensure `gh` CLI is authenticated: `gh auth login`

---

**Ready to start? Let's resolve those blockers first! 🔧**

**Next command to run:**
```bash
xcode-select --install
```
