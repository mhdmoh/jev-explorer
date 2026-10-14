# Jev Explorer

The behavior below is the gateway experiment: typed Jev signals, deterministic policy, and sandboxed tools. That code now lives in `backend/`. The user-facing application is the React app in `frontend/`.

## Overview

Jev Explorer is a small AI engineering experiment that places a typed decision layer and a deterministic policy engine between an agent’s proposed tool call and tool execution. It demonstrates an execution boundary for tool-using agents without claiming to be a production security product.

## Problem

Agents that can call tools are useful because they can change systems: write files, delete artifacts, notify external services, run maintenance tasks. Those same capabilities create risk when model intent is treated as authorization. The question is not only “can the model propose a useful action?” but “should this process be allowed to run?”

## Why agent tool calls are different

Chat completions mainly produce text. Tool calls produce side effects. Side effects need:

- clear proposal structure
- independent evaluation
- policy that can be inspected and tested
- optional human approval
- an audit trail

## Constraints

- No arbitrary shell or network execution in the demo
- Tools confined to a sandbox workspace
- Runnable without a Jev API key (explicit DEMO MODE)
- One batched Jev request (choice + score + noul)
- Jev must not be the final authorizer

## Architecture

```text
Agent → ToolCall → Jev Explorer → JevEvaluator → PolicyEngine → ToolExecutor
```

Strict import boundaries keep network I/O, policy math, and side effects separable for testing.

## Why Jev

Jev Explorer needs calibrated, typed signals:

- **choice** for action category
- **score** for consequence severity
- **noul** for automatic-execution suitability

Those signals are more suitable for policy code than unstructured natural language.

## Decision model

For each proposal, Jev Explorer sends a compact state (goal, tool, arguments, resource hints). Jev returns action type, risk, and safe probability in one round trip. Risk is treated as a 1–5 consequence scale, not a probability.

## Policy engine

Deterministic rules combine Jev signals with tool metadata (destructive, external, confirmation-required). Outcomes:

- EXECUTE
- REQUIRE_CONFIRMATION
- BLOCK

Thresholds are configuration, not model outputs. Hard rules block credential-style and high-risk privileged paths even when scores look favorable.

## Human-in-the-loop

Confirmation-gated actions pause until the operator approves or rejects. Approval is recorded in the audit trail before execution.

## Tool isolation

The registry exposes only predefined demo tools. Path resolution rejects escapes from `demo/workspace`. `execute_demo_task` runs only allowlisted task names.

## Evaluation

A 35-scenario dataset covers safe, ambiguous, external, destructive, and edge cases. The emphasized metric is false allow rate. Results are illustrative of gateway behavior on that set, not a security certification.

## Results

In DEMO MODE, the flagship paths are stable:

- Read notes → EXECUTE
- Create note → REQUIRE_CONFIRMATION → Approve → EXECUTE
- Delete report / deployment cleanup → BLOCK

Unit and integration tests cover policy branches, Jev parsing, sandbox confinement, and end-to-end gateway flows without live API calls.

## Trade-offs

- Rule-based agent proposals are predictable for demos but less flexible than an LLM planner
- Mock Jev signals enable offline runs but must stay clearly labeled
- Conservative block thresholds reduce false allows and increase confirmation/block rates
- Simulated tools limit realism in exchange for safe public demos

## Limitations

Not production-ready. No multi-tenant auth, no real secrets vault, no durable audit store, limited evaluation coverage, policy defaults are opinionated.

## Lessons learned

1. Separate **signals** from **authorization**.
2. Batch typed decisions when the gateway needs multiple dimensions of judgment.
3. Keep destructive demos sandboxed if the project is meant to be published.
4. Make offline/demo mode honest — never present mocks as live model outputs.
5. False allows matter more than false blocks for a safety gateway narrative.
