# 16. Wizard Engine Architecture

## 16.1 Purpose

The Wizard Engine is the orchestration layer of TheRecon.

It coordinates user interaction, validates user input, selects appropriate tools, constructs execution plans, and manages workflow progression.

The Wizard Engine MUST NOT contain tool-specific implementation.

Its purpose is orchestration, not execution.

---

## 16.2 Responsibilities

The Wizard Engine is responsible for:

- Managing wizard states
- User navigation
- Question flow
- Collecting user input
- Selecting scan profiles
- Calling validators
- Calling command builders
- Requesting confirmation
- Triggering execution
- Passing results to analysis

The Wizard Engine is NOT responsible for:

- Running subprocesses
- Parsing XML
- Parsing JSON
- Performing AI inference
- Displaying GUI widgets
- Reading resource files
- Writing reports

---

## 16.3 Workflow

The Wizard follows the following execution pipeline.

Start

↓

Initialize Wizard

↓

Load Configuration

↓

Load Resources

↓

Select Tool

↓

Select Profile

↓

Collect Parameters

↓

Validate Parameters

↓

Generate Execution Plan

↓

Display Confirmation

↓

User Approval

↓

Execute Tool

↓

Parse Results

↓

Analyze Results

↓

Generate Report

↓

Finish

Every step must complete successfully before moving to the next.

---

## 16.4 Wizard State

The Wizard shall maintain a state object.

The state stores only runtime information.

Example:

- Selected tool
- Target
- Selected profile
- Enabled flags
- User responses
- Execution status
- Parsed result

State objects should never contain UI components.

---

## 16.5 Wizard Navigation

Navigation should support:

Next

Previous

Cancel

Restart

Resume (Future)

Navigation logic must remain independent from GUI.

GUI only triggers navigation events.

---

# 17. AI Integration Architecture

## 17.1 Purpose

Artificial Intelligence acts as an assistant.

It does not replace validation.

It does not replace execution control.

It does not bypass confirmation.

---

## 17.2 AI Responsibilities

AI may

- Explain tools
- Recommend profiles
- Suggest flags
- Explain scan results
- Summarize reports
- Recommend next actions
- Detect obvious mistakes

AI must never

Execute scans automatically

Skip confirmation

Ignore validation

Modify execution results

Fabricate scan output

---

## 17.3 AI Workflow

User Request

↓

AI Interpretation

↓

Validation

↓

Recommendation

↓

User Confirmation

↓

Execution

↓

Parser

↓

AI Summary

↓

Recommendation

Every AI decision must pass validation before execution.

---

## 17.4 AI Safety

Before suggesting any command the AI must

Validate syntax

Validate target

Validate profile

Validate conflicts

Validate dangerous flags

Reject invalid combinations

AI suggestions are recommendations only.

The final decision belongs to the user.

---

# 18. Command Builder Specification

## 18.1 Purpose

Command Builders convert validated wizard states into executable commands.

Builders never execute commands.

---

## 18.2 Responsibilities

Builders

Receive

↓

Validated Input

↓

Generate

↓

Command Object

↓

Return

Nothing else.

---

## 18.3 Rules

Builders must

Never execute

Never display dialogs

Never access GUI

Never call AI

Never parse results

Only generate commands.

---

## 18.4 Command Object

Every generated command should include

Tool

Arguments

Working Directory

Timeout

Execution Profile

Metadata

Future extensions may include

Tags

Execution ID

History ID

Risk Level

---

# 19. Execution Pipeline

The execution pipeline is fixed.

User

↓

Wizard

↓

Validation

↓

Builder

↓

Confirmation

↓

Execution

↓

Parser

↓

Analysis

↓

Report

No component may bypass another component unless explicitly documented.

---

## 19.1 Execution Responsibilities

Execution Layer

Responsible for

Launching processes

Monitoring

Cancellation

Timeout

Streaming output

Collecting exit code

Execution must never analyze output.

---

## 19.2 Process Isolation

Each tool execution should be isolated.

Execution context should contain

Working directory

Environment variables

Temporary files

Execution timeout

Cleanup procedure

One failed tool should not terminate the application.

---

# 20. Result Processing

Results pass through multiple stages.

Raw Output

↓

Parser

↓

Structured Data

↓

Analysis

↓

Report

↓

GUI

Every stage has one responsibility.

---

## Parser

Transforms output into structured information.

Never performs recommendations.

---

## Analysis

Produces

Risk evaluation

Recommendations

Summary

Statistics

Analysis never modifies parsed data.

---

## Report

Responsible for exporting.

Supported formats

JSON

YAML

Future

HTML

PDF

Markdown

---

# 21. Security Policy

TheRecon is designed for authorized security assessment only.

Every module must assume the safest behavior by default.

---

## Human Confirmation

Potentially dangerous actions require explicit user approval.

Confirmation cannot be bypassed by AI.

---

## Validation Before Execution

Validation is mandatory.

Execution without validation is prohibited.

---

## Least Privilege

Modules should request only the permissions required.

Avoid unnecessary privilege escalation.

---

## Safe Defaults

Default scan profiles should prioritize safety.

Aggressive options require explicit user consent.

---

## Auditability

Every execution should be traceable.

Recommended fields

Timestamp

Target

Selected Tool

Generated Command

Profile

Execution Result

Exit Code

---

# 22. Error Handling Policy

Errors should be predictable.

The application should degrade gracefully.

Examples

Missing resource

↓

Fallback

Missing configuration

↓

Load defaults

Plugin unavailable

↓

Disable plugin

Invalid profile

↓

Display validation error

Unexpected exception

↓

Log

↓

Recover if possible

The application should avoid crashing due to recoverable conditions.

---

# 23. Performance Guidelines

Performance optimization must never reduce readability or maintainability.

Preferred optimizations include

Caching frequently used resources

Avoiding repeated file access

Reusing immutable objects

Using lookup tables instead of repetitive branching

Extracting duplicated logic into reusable helpers

Keeping long-running tasks off the UI thread

Lazy-loading optional resources

Avoiding unnecessary subprocess creation

Performance improvements should be measurable or clearly beneficial before increasing implementation complexity.

---

# 24. Refactoring Rules for AI

When modifying the project, AI assistants must follow these principles:

Preserve existing behavior unless explicitly instructed otherwise.

Never introduce breaking changes without documenting them.

Prefer extracting reusable modules over duplicating logic.

Separate business logic from UI, resources, and configuration.

Avoid introducing circular dependencies.

Do not move functionality merely to satisfy arbitrary file size limits.

Keep related logic together.

Favor readability and cohesion over clever implementations.

When extracting resources, replace hardcoded text with stable resource keys.

Document architectural changes clearly.

---

End of Part 3