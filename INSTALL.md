<!--
topmark:header:start

  file         : INSTALL.md
  file_relpath : INSTALL.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Installation Instructions

These steps will set up the development environment for the `topmark` project.

## Requirements

- Python 3.10 or newer
- Git (for cloning and pre-commit hooks)

## Step-by-step Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-org/topmark.git
cd topmark
```

### 2. Create and activate a virtual environment

```bash
make venv
```

Then activate it:

- On macOS/Linux:

  ```bash
  source .venv/bin/activate
  ```

- On Windows:

  ```bash
  .venv\Scripts\activate
  ```

### 3. Set up the development environment

```bash
make setup
```

This will:

- Install `pip-tools`
- Compile both runtime and development dependencies
- Install them into the virtualenv

### 4. Install pre-commit hooks

```bash
make pre-commit-install
```

To ensure hooks stay up to date:

```bash
make pre-commit-autoupdate
```

This sets up automatic linting and formatting checks before each commit.

## Optional: Run all pre-commit hooks manually

```bash
make pre-commit-run
```

## Installing the tool in edit mode

Run the following command from the root directory (where the `pyproject.toml` file is located):

```bash
source .venv/bin/activate
pip install -e .
```

## Running the tool

Use the CLI:

```bash
topmark [path(s)] [--options]
```

See `topmark --help` for available arguments.
