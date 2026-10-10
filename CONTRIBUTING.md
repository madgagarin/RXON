# Contributing to RXON

**EN** | [ES](https://github.com/madgagarin/rxon/blob/main/docs/es/CONTRIBUTING.md) | [RU](https://github.com/madgagarin/rxon/blob/main/docs/ru/CONTRIBUTING.md)

As the shared protocol layer, changes in this repository affect downstream libraries.

## Setup

1. Clone the repository and navigate to the project directory.
2. Install with development dependencies:
   ```bash
   pip install -e .[dev]
   ```

## Testing & Quality Checks

Run test suite and static analysis:

```bash
pytest tests/
ruff check .
mypy src tests
```

## Guidelines

- **Breaking Changes**: Changes to `rxon.models` may introduce breaking wire incompatibilities. Discuss proposed changes before submitting.
- **Dependencies**: Keep the core lightweight and avoid introducing heavy runtime dependencies.
- **Typing**: Strict static typing is required for all models and public functions.
