# TheRecon Architecture Specification

Version: 1.0.0

Status: Approved

Last Updated: 2026-07-25

---

# 1. Introduction

## 1.1 Purpose

This document defines the software architecture of TheRecon.

It serves as the single source of truth for the entire project architecture and must be followed by every developer, contributor, and AI-assisted coding system.

This specification defines:

- Project architecture
- Design principles
- Module boundaries
- Folder organization
- Resource management
- Component responsibilities
- Development standards
- Refactoring rules
- Scalability guidelines

This document does NOT explain implementation details.

Implementation belongs inside the source code.

---

## 1.2 Scope

This architecture applies to every component inside TheRecon including but not limited to:

- Wizard Engine
- GUI
- AI Integration
- Command Builder
- Command Validation
- Resource System
- Configuration Management
- Security Tools
- Scan Chain
- Reporting
- Parser
- Execution Engine

Every future feature must follow this architecture.

---

## 1.3 Goals

The architecture has the following objectives.

### Maintainability

Code should be easy to understand.

Adding new features should require modifying as few modules as possible.

---

### Modularity

Each module should have one primary responsibility.

Avoid giant modules performing multiple unrelated tasks.

---

### Extensibility

Adding a new security tool should not require rewriting existing components.

---

### Scalability

The project should continue to grow without becoming difficult to maintain.

---

### Safety

Every execution path must prioritize operational safety.

Human confirmation remains mandatory before dangerous operations.

---

### Readability

The project should be understandable by developers unfamiliar with the original implementation.

---

### Consistency

Naming conventions, project structure and resource organization must remain consistent throughout the project.

---

# 2. Design Philosophy

TheRecon is designed around several architectural principles.

These principles are mandatory.

---

## 2.1 Separation of Concerns

Business logic must never be mixed with presentation.

Static resources must never be mixed with algorithms.

Configuration must never be hardcoded.

Every concern belongs to its own layer.

---

## 2.2 Single Responsibility Principle

Each module should solve one problem.

Examples

Good

wizard/validator.py

Responsible only for validating wizard inputs.

Good

nmap/builder.py

Responsible only for building Nmap commands.

Bad

wizard_engine.py

Contains

- Menu
- UI
- Validation
- Help
- Builder
- Parser
- Logging
- AI
- Navigation

---

## 2.3 Open for Extension

Adding

Masscan

Hydra

Ncrack

Evil-WinRM

Gobuster

Nikto

or future tools

should require adding new modules instead of modifying existing logic whenever possible.

---

## 2.4 Configurable First

Behavior should be configurable.

Examples

Good

JSON

YAML

Configuration Files

Profiles

Resource Files

Bad

Hardcoded constants scattered across source files.

---

## 2.5 Resource Driven Architecture

Python files should contain logic.

Resources should contain data.

Resources include

Menus

Help

Warning Messages

Descriptions

Prompt Templates

Suggestions

Impact Descriptions

Tool Information

Wizard Text

Dialog Text

Confirmation Messages

Static Dictionaries

These resources must live outside Python.

---

## 2.6 Safety by Default

Every execution starts from the safest possible configuration.

Unsafe operations require explicit confirmation.

The system must never assume authorization.

---

# 3. High Level Architecture

TheRecon is divided into multiple layers.

Each layer has a specific responsibility.

```
                GUI Layer
                     │
                     ▼
            Wizard / AI Layer
                     │
                     ▼
            Validation Layer
                     │
                     ▼
          Command Builder Layer
                     │
                     ▼
          Security Tool Layer
                     │
                     ▼
           Execution Engine
                     │
                     ▼
              Parser Layer
                     │
                     ▼
           Analysis Layer
                     │
                     ▼
          Reporting Layer
```

No layer should bypass another layer unless explicitly documented.

---

# 4. Layer Responsibilities

## GUI Layer

Responsible for

- Windows
- Dialogs
- Widgets
- User Input
- Progress Display
- Tables
- Charts
- Output Panels

The GUI must not build commands.

The GUI must not contain security logic.

---

## Wizard Layer

Responsible for

Wizard workflow

Navigation

Questions

State transitions

Decision flow

Recommendation flow

The wizard should never execute tools directly.

---

## Validation Layer

Responsible for

Target validation

Parameter validation

Conflict detection

Dangerous option detection

Profile validation

Configuration validation

Validation always happens before command generation.

---

## Command Builder Layer

Responsible for converting validated input into executable commands.

Each supported tool owns its own builder.

Examples

Nmap Builder

Masscan Builder

Hydra Builder

Ncrack Builder

Evil-WinRM Builder

Builders must never execute commands.

Builders only generate commands.

---

## Execution Layer

Responsible for

Launching subprocesses

Monitoring execution

Cancelling execution

Timeout management

Streaming output

Execution does not perform analysis.

---

## Parser Layer

Responsible for converting raw tool output into structured information.

Parsers must not execute tools.

Parsers must not generate commands.

---

## Analysis Layer

Responsible for

Summaries

Recommendations

Workflow continuation

AI analysis

Risk evaluation

The analysis layer never modifies execution results.

---

## Reporting Layer

Responsible for

Export

History

Reports

YAML

JSON

Future PDF support

---

# 5. Core Architecture Rules

The following rules are mandatory.

Rule 1

Business logic must not depend on GUI.

---

Rule 2

GUI must never contain business logic.

---

Rule 3

Resources must never contain executable logic.

---

Rule 4

Configuration files must never contain application logic.

---

Rule 5

Builders generate commands only.

---

Rule 6

Validators validate only.

---

Rule 7

Execution executes only.

---

Rule 8

Parsers parse only.

---

Rule 9

Analysis analyzes only.

---

Rule 10

Reporting generates reports only.

---

# 6. Folder Organization Principles

Folders should represent responsibilities.

Not technologies.

Not file size.

Examples

Good

wizard/

nmap/

parser/

resources/

analysis/

report/

Bad

misc/

temp/

utils2/

new_folder/

Folders should have clear purposes.

Avoid dumping unrelated files into a common directory.

---

# 7. Future Compatibility

The architecture must support future additions without requiring redesign.

Examples

Future Security Tools

- Gobuster
- Nikto
- WhatWeb
- Enum4Linux
- CrackMapExec
- NetExec

Future AI Models

- Gemini
- Claude
- OpenAI
- Ollama
- Local Models

Future Output Formats

- PDF
- HTML
- Markdown
- CSV
- XML

Future Interfaces

- CLI
- Desktop GUI
- Web Dashboard
- REST API

Future expansion must integrate into the existing architecture rather than introducing parallel systems.

---

End of Part 1