The previous implementation incorrectly assumed that tools unavailable on Windows Demo should be skipped.

That is NOT the intended architecture.

Please follow ARCHITECTURE.md and RESOURCE_SYSTEM.md exactly.

## Important Clarification

Windows Demo only limits EXECUTION.

It does NOT limit the project architecture.

Every supported tool must follow the same architectural layout regardless of whether it can currently execute on Windows.

Examples include (but are not limited to):

- Nmap
- Ncat
- Masscan
- Hydra
- Ncrack
- Evil-WinRM

If a tool cannot currently execute on Windows:

- DO NOT implement fake functionality.
- DO NOT invent parsing logic.
- DO NOT skip the module.

Instead:

1. Create the complete module structure.
2. Add placeholder implementations where necessary.
3. Add clear TODO docstrings indicating future implementation.
4. Ensure the architecture remains consistent.

Every tool should have the same module layout whenever applicable:

tools/<tool>/
    __init__.py
    builder.py
    validator.py
    parser.py
    analyzer.py
    resources/

If a component is not yet implemented, provide a minimal placeholder instead of omitting it.

Example:

class EvilWinRMParser:
    """
    Placeholder parser.

    Execution is currently unavailable on Windows Demo.

    This parser exists to preserve architectural consistency.
    """
    pass

Architecture consistency is more important than implementation completeness.

Do NOT skip modules simply because execution is unavailable.

---

## Windows Demo Rules

Windows Demo affects only:

- subprocess execution
- runtime availability
- platform-specific functionality

Windows Demo DOES NOT affect:

- project structure
- module layout
- plugin architecture
- parser interfaces
- validator interfaces
- builder interfaces
- analyzer interfaces
- resources
- documentation

---

## Architecture Compliance

After finishing, generate an Architecture Compliance Report.

For every applicable requirement in:

- ARCHITECTURE.md
- RESOURCE_SYSTEM.md

mark

PASS
PARTIAL
FAIL

For every PARTIAL or FAIL explain:

- Why
- Which files are affected
- What remains to be implemented
- Whether the limitation is due to Windows Demo or because the feature is intentionally deferred.

Do not claim the architecture is complete until every applicable section has been evaluated.

# Platform Compatibility Policy

The project architecture is platform-independent.

The implementation of specific execution backends may vary by platform, but the software architecture must remain identical.

Windows Demo is considered an execution profile, not a separate architecture.

Modules must never be omitted solely because execution is unavailable on the current platform.

When execution is unsupported:

- Preserve the module structure.
- Preserve public interfaces.
- Provide placeholder implementations where appropriate.
- Clearly document platform limitations.
- Avoid fake implementations.

The architecture should always represent the complete intended system regardless of platform.