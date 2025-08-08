# Shepherd AI - Backend Development Guide

## Table of Contents
1. [Project Structure](#project-structure)
2. [Code Style & Best Practices](#code-style--best-practices)
3. [API Design](#api-design)
4. [Database Layer](#database-layer)
5. [Authentication & Authorization](#authentication--authorization)
6. [Error Handling](#error-handling)
7. [Testing](#testing)
8. [Deployment](#deployment)

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── api/                 # API routes
│   │   ├── __init__.py
│   │   ├── deps.py          # Dependencies
│   │   └── v1/              # API version 1
│   │       ├── __init__.py
│   │       ├── api.py       # Main API router
│   │       ├── endpoints/   # API endpoints by resource
│   │       └── models/      # Pydantic models
│   ├── core/                # Core functionality
│   │   ├── __init__.py
│   │   ├── config.py        # Configuration settings
│   │   └── security.py      # Security utilities
│   ├── db/                  # Database setup
│   │   ├── __init__.py
│   │   ├── base.py          # Base database setup
│   │   └── session.py       # Database session management
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   └── user.py          # User model
│   └── services/            # Business logic
│       ├── __init__.py
│       ├── auth.py          # Authentication service
│       └── chat.py          # Chat service
├── alembic/                 # Database migrations
├── tests/                   # Test files
├── .env.example             # Example environment variables
├── .flake8                  # Flake8 configuration
├── alembic.ini              # Alembic configuration
├── pyproject.toml           # Project metadata and dependencies
└── requirements.txt         # Project dependencies
```

## Code Style & Best Practices

### General Guidelines
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide
- Use type hints for all function signatures
- Keep functions small and focused on a single responsibility
- Write docstrings for all public modules, classes, and functions
- Use absolute imports

### Naming Conventions
- Variables, functions, methods: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private members: prefix with `_`

## API Design

### RESTful Principles
- Use HTTP methods appropriately (GET, POST, PUT, DELETE, PATCH)
- Use plural nouns for resources (e.g., `/users`, `/conversations`)
- Use status codes correctly
- Version your API (e.g., `/api/v1/...`)

### Response Format
```json
{
    "data": { ... },
    "message": "Success message",
    "success": true
}
```

### Error Responses
```json
{
    "error": {
        "code": "error_code",
        "message": "Error description"
    },
    "success": false
}
```

## Database Layer

### SQLAlchemy ORM
- Use SQLAlchemy 2.0+ style
- Keep models in separate files
- Use type hints with SQLAlchemy models
- Use migrations for schema changes

### Session Management
- Use FastAPI's dependency injection for database sessions
- Keep sessions short-lived
- Handle transactions explicitly when needed

## Authentication & Authorization

### JWT Authentication
- Use access and refresh tokens
- Set appropriate token expiration times
- Implement token refresh mechanism

### Protected Endpoints
- Use FastAPI's `Depends` for route protection
- Check user roles and permissions
- Log authentication events

## Error Handling

### Custom Exceptions
- Create specific exception types for different error cases
- Use HTTP exceptions for API errors
- Log all exceptions

### Validation
- Use Pydantic for request/response validation
- Validate all user input
- Provide clear error messages

## Testing

### Test Structure
- Unit tests for services and utilities
- Integration tests for API endpoints
- Use pytest fixtures for test data

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## Deployment

### Environment Variables
- Use environment variables for configuration
- Keep sensitive data out of version control
- Document all required environment variables

### Production Checklist
- [ ] Enable CORS for production domains
- [ ] Set up proper logging
- [ ] Configure rate limiting
- [ ] Set up monitoring and alerting
- [ ] Regular database backups

## Development Workflow

1. Create a feature branch
2. Write tests for new features
3. Implement the feature
4. Run linters and tests
5. Create a pull request
6. Get code review
7. Deploy to staging for testing
8. Deploy to production

## Code Review Guidelines
- Check for security vulnerabilities
- Ensure error handling is in place
- Verify test coverage
- Check for performance issues
- Ensure documentation is updated
