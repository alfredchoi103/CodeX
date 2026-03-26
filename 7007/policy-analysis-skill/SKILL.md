---
name: policy-analysis-skill
description: Use when the user wants a repeatable analysis skill for policy, governance, planning, resilience, flood, drainage, or urban management topics, especially when the analysis should be done with a selectable framework, matrix, or structured table rather than free-form commentary.
---

# Policy Analysis Skill

Use this skill when the user wants a structured analysis based on a named or selectable framework.

## What this skill does

- Selects a suitable analysis framework for the question.
- Produces a reusable table or matrix instead of only narrative summary.
- Connects theory to an applied case, such as Hong Kong inland flooding governance.

## Workflow

1. Identify the analysis object.
   Examples: a paper, a policy package, a governance arrangement, a city case, a project proposal.
2. Check whether the user named a framework.
   If yes, use that framework.
3. If the user did not name one, read [framework catalog](./references/framework-catalog.md) and choose the best fit.
4. Read only the selected framework reference file.
5. Deliver the result in four parts:
   - `Framework chosen`
   - `Core analysis table`
   - `Case application`
   - `Actionable use`

If the user wants recommendations for government or implementation actors, add:

- `Policy mix recommendations`
- `Lead actors and sequencing`

## Default output rules

- Keep the explanation concise and decision-oriented.
- Prefer one primary table.
- If useful, add one secondary table for gaps, actions, or next steps.
- Explicitly separate what comes from the source from what is your applied inference.
- For urban resilience or flood topics, connect the framework to:
  - goals
  - tools
  - institutions
  - implementation constraints
  - sequencing

## Framework selection rules

- If the task is about policy mixes, policy instruments, institutional layering, path dependency, or coordination across departments, prioritize `patching-packaging`.
- If the task is about research design, literature review, analytical blind spots, under-studied dimensions, or what a policy-instrument analysis is still missing, prioritize `instrument-gap-scan`.
- If the task is about generating practical recommendations for government, bureaus, departments, or delivery actors to form a policy mix, prioritize `policy-mix-recommendation`.
- If the user asks for comparison across frameworks, use at most two unless the user asks for more.
- If no existing framework fits well, say so briefly and proceed with the closest match.

## Extension rule

This skill is designed to grow.

When adding a new framework later:

1. Add one file under `references/`.
2. Update [framework catalog](./references/framework-catalog.md).
3. Keep the new file focused on:
   - when to use it
   - key questions
   - output table template
   - interpretation guidance
