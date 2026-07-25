# 25. Coding Standards

This project follows modern Python development practices.

The primary objective is readability and maintainability.

Optimization should never reduce code clarity.

---

## General Principles

Prefer explicit code over implicit behavior.

Prefer readable code over clever code.

Prefer composition over inheritance when appropriate.

Avoid premature optimization.

Write code for humans first.

---

## Naming Convention

Use descriptive names.

Examples

Good

validate_target()

build_nmap_command()

resource_loader.py

wizard_state.py

Bad

run()

data()

abc()

test2()

new_file.py

---

## Type Hint Policy

Public functions should include type hints whenever practical.

Example

def validate_target(target: str) -> bool

Avoid ambiguous return types.

---

## Constants

Magic values should not be scattered throughout the project.

Store reusable constants in one location.

Examples

Timeout

Retry Count

Maximum Threads

Risk Levels

Default Scan Profiles

Do not duplicate constants.

---

## Documentation

Public modules should include a module description.

Public classes should include a class description.

Public methods should include concise documentation describing

Purpose

Arguments

Return value

Exceptions (if applicable)

Documentation should explain WHY.

Avoid explaining obvious implementation details.

---

# 26. Logging Architecture

Logging should provide enough information to diagnose issues without exposing sensitive information.

---

## Logging Levels

DEBUG

Development diagnostics

INFO

Normal execution

WARNING

Recoverable problems

ERROR

Execution failure

CRITICAL

Application cannot continue

---

## Log Content

Each log entry should include when appropriate

Timestamp

Module

Action

Execution ID

Tool Name

Target

Status

Message

Avoid logging sensitive credentials.

---

# 27. Dependency Management

Dependencies should remain minimal.

Only introduce external libraries when there is clear long-term value.

Prefer Python Standard Library when it satisfies requirements.

Review every dependency before adding it.

Avoid overlapping libraries with similar functionality.

---

# 28. Testing Philosophy

Architecture should support testing even if automated tests are added later.

Modules should be designed to allow

Unit Testing

Integration Testing

System Testing

Avoid tightly coupled modules.

Business logic should be testable independently from GUI.

---

# 29. Versioning Strategy

Project versions should follow Semantic Versioning.

Major

Breaking architectural changes

Minor

New functionality

Patch

Bug fixes

Architecture changes should be documented.

---

# 30. Backward Compatibility

Whenever possible

Existing public APIs should continue working.

Existing configuration files should remain compatible.

Existing user workflows should remain unchanged.

Breaking changes must be documented.

---

# 31. Future Expansion

The architecture should support future growth without redesign.

Examples

New Security Tools

Additional AI Providers

Remote Execution

Distributed Scanning

Plugin Marketplace

Session Management

User Profiles

Cloud Synchronization

REST API

Web Dashboard

RBAC

Database Storage

Historical Scan Database

Collaborative Projects

Every new feature should integrate into the existing architecture instead of creating isolated implementations.

---

# 32. AI Development Rules

Any AI modifying this repository must follow these requirements.

Always understand existing architecture before making changes.

Read related modules before editing.

Do not rewrite working code without architectural benefit.

Preserve existing behavior.

Avoid introducing duplicate logic.

Extract reusable functionality.

Separate business logic from resources.

Separate business logic from GUI.

Avoid circular imports.

Avoid hidden side effects.

Avoid unnecessary global state.

Explain architectural decisions.

Maintain consistent naming.

Keep implementations cohesive.

---

# 33. AI Refactoring Workflow

Before modifying any module

Step 1

Understand the module responsibility.

Step 2

Identify duplicated logic.

Step 3

Identify hardcoded resources.

Step 4

Extract reusable functionality.

Step 5

Replace duplicated code.

Step 6

Verify existing behavior.

Step 7

Document changes.

Never perform large uncontrolled rewrites.

Refactor incrementally.

---

# 34. Definition of Done

A task is considered complete only when

✓ Existing functionality remains unchanged

✓ No duplicated logic introduced

✓ Resources extracted where appropriate

✓ No unnecessary dependencies added

✓ Naming follows project standards

✓ Documentation updated

✓ Architecture remains consistent

✓ No circular imports introduced

✓ Code remains readable

✓ Public interfaces preserved

---

# 35. Architecture Decision Records (ADR)

Significant architectural decisions should be documented.

Each ADR should include

Decision

Context

Alternatives

Consequences

Status

This ensures future contributors understand why decisions were made.

---

# 36. Guiding Principles

The following principles take precedence over implementation convenience.

1. Safety before automation.

2. Readability before optimization.

3. Maintainability before cleverness.

4. Modularity before convenience.

5. Configuration before hardcoding.

6. Resources before embedded text.

7. Validation before execution.

8. Human confirmation before dangerous actions.

9. Reuse before duplication.

10. Architecture before implementation.

---

# 37. Conclusion

TheRecon is designed as a modular, extensible, and safety-oriented reconnaissance framework.

Every architectural decision should reinforce the following objectives:

- Separation of Concerns
- Single Responsibility
- Extensibility
- Maintainability
- Security
- Predictability
- Readability
- Backward Compatibility

This document serves as the authoritative architectural reference for the project.

All future development, refactoring, and AI-assisted modifications should follow this specification unless a documented architectural decision explicitly supersedes it.

END OF DOCUMENT