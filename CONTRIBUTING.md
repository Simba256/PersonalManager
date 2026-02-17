# Contributing to Personal Manager

Thank you for considering contributing to Personal Manager! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect differing opinions and experiences

## How to Contribute

### Reporting Bugs

Before creating a bug report, please check existing issues to avoid duplicates.

**When filing a bug report, include**:
- Clear, descriptive title
- Steps to reproduce the issue
- Expected behavior vs actual behavior
- System information (OS, Python version)
- Relevant logs or error messages
- Screenshots if applicable

**Bug report template**:
```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**
 - OS: [e.g. Ubuntu 22.04]
 - Python Version: [e.g. 3.11.5]
 - Personal Manager Version: [e.g. 0.1.0]

**Additional context**
Any other context about the problem.
```

### Suggesting Features

Feature suggestions are welcome! Please:
- Check existing feature requests first
- Provide clear use cases
- Explain why this feature would be useful
- Consider implementation complexity

**Feature request template**:
```markdown
**Is your feature request related to a problem?**
A clear description of what the problem is.

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Other solutions or features you've considered.

**Additional context**
Any other context or screenshots about the feature.
```

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
   - Follow the code style (see below)
   - Add tests for new functionality
   - Update documentation as needed
4. **Commit your changes**
   ```bash
   git commit -m "feat: add amazing feature"
   ```
5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```
6. **Open a Pull Request**

**PR Guidelines**:
- Clear title following commit message format
- Description of changes and motivation
- Link to related issues
- All tests passing
- Code coverage maintained or improved
- Documentation updated

## Development Setup

### Prerequisites

- Python 3.11+
- Git
- SQLite 3
- Google Calendar API credentials

### Setup Steps

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/PersonalManager.git
cd PersonalManager

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL_OWNER/PersonalManager.git

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Copy configuration
cp config.example.yaml config.yaml
cp .env.example .env

# Edit with your settings
nano config.yaml
nano .env

# Initialize database
alembic upgrade head

# Run tests
pytest
```

## Code Style

### Python Style

We follow PEP 8 with these modifications:
- Line length: 100 characters
- Use type hints
- Use f-strings for formatting
- Docstrings for all public functions

### Formatting

```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Lint
ruff check app/ tests/

# Type check
mypy app/
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, no logic change)
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples**:
```
feat(calendar): add CalDAV support

Implemented CalDAV client for generic calendar integration.
Tested with NextCloud and Fastmail.

Closes #42
```

```
fix(scheduler): handle timezone edge case

Tasks scheduled near daylight saving time changes
were incorrectly scheduled. Added timezone-aware
datetime handling.

Fixes #56
```

## Testing

### Writing Tests

- Write tests for all new features
- Aim for 80%+ code coverage
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)

**Test naming**:
```python
def test_<function_name>_<scenario>_<expected_result>():
    # Example
    def test_create_task_with_valid_data_returns_task():
        pass

    def test_create_task_with_invalid_data_raises_error():
        pass
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific tests
pytest tests/unit/test_models.py

# Run fast tests only
pytest -m "not integration"

# Watch mode (auto-run on changes)
pytest-watch
```

### Test Categories

Use markers to categorize tests:

```python
import pytest

@pytest.mark.unit
def test_task_model():
    pass

@pytest.mark.integration
def test_calendar_sync():
    pass

@pytest.mark.slow
def test_full_workflow():
    pass
```

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def create_task(title: str, priority: str = "medium") -> Task:
    """Create a new task.

    Args:
        title: The task title
        priority: Task priority (low, medium, high, critical)

    Returns:
        The created Task object

    Raises:
        ValidationError: If title is empty or priority invalid

    Example:
        >>> task = create_task("Write docs", priority="high")
        >>> task.title
        'Write docs'
    """
    pass
```

### API Documentation

Document all API endpoints:

```python
@router.post("/api/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db)
) -> TaskResponse:
    """Create a new task.

    Create a new task with the provided data. The task will be
    automatically scheduled based on priority and due date.

    **Request Body:**
    - title: Task title (required, 1-500 chars)
    - priority: low|medium|high|critical (default: medium)
    - due_date: ISO 8601 datetime (optional)

    **Returns:**
    - 201: Task created successfully
    - 400: Invalid request data
    - 500: Server error

    **Example:**
    ```json
    {
      "title": "Review pull request",
      "priority": "high",
      "due_date": "2026-02-25T17:00:00Z"
    }
    ```
    """
    pass
```

### Updating Documentation

When making changes:
- Update relevant documentation files
- Update code comments
- Update API documentation
- Update README if needed
- Add examples for new features

## Project Structure

When adding new files, follow this structure:

```
app/
├── calendar/       # Calendar integration modules
├── agent/          # LangGraph agent workflows
├── integrations/   # External service integrations
├── llm/            # LLM client implementations
├── services/       # Business logic services
├── web/            # Web UI and API routes
├── models.py       # Database models
├── schemas.py      # Pydantic schemas
└── utils.py        # Utility functions
```

## Review Process

### For Contributors

1. Submit PR with clear description
2. Respond to review comments
3. Update based on feedback
4. Wait for approval from maintainer
5. PR will be merged by maintainer

### For Reviewers

Check for:
- [ ] Code follows style guide
- [ ] Tests pass and coverage maintained
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] No breaking changes (or documented)
- [ ] Security considerations addressed
- [ ] Performance impact acceptable

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create release branch
4. Run full test suite
5. Tag release: `git tag -a v0.2.0 -m "Release v0.2.0"`
6. Push tag: `git push origin v0.2.0`
7. Create GitHub release with notes

## Getting Help

- Check documentation in `docs/`
- Search existing issues
- Ask in discussions
- Contact maintainers

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in documentation (for significant contributions)

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to Personal Manager! 🎉
