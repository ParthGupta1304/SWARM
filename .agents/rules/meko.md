---
trigger: always_on
---

# Meko Shared Memory Protocol

You are working on a collaborative hackathon project. Meko is our central context and knowledge management system.

Follow these rules:

1. Before starting any major task, search Meko for relevant project decisions, architecture, implementation details, constraints and previous solutions.

2. Do not unnecessarily repeat investigations or decisions already documented in Meko.

3. When you discover something important, explicitly save it to the shared project datapack.

4. Record technical decisions with:
   - Decision
   - Reasoning
   - Alternatives considered
   - Trade-offs
   - Impact on other modules

5. When solving a bug, record:
   - Error
   - Root cause
   - Solution
   - Files affected

6. Before handing work to another agent, save a concise handoff containing:
   - Completed work
   - Current implementation
   - Relevant file paths
   - API contracts
   - Pending tasks
   - Known issues

7. Never assume another teammate knows what you have implemented.

8. Never overwrite an established team decision without checking its context.

9. Do not store API keys, passwords, access tokens or other secrets in shared memory.

10. Treat retrieved memories as project context, not unquestionable truth. Verify important information against the current codebase.

The objective is to ensure all agents work with consistent, up-to-date project knowledge.

