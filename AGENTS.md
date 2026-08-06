# Project Agent Instructions

This repository builds the complete Faz 1–7 startup research and decision platform.

For non-trivial planning, architecture, implementation, review, verification, integration, or resume work, use `.agents/skills/orchestrate-research-platform/SKILL.md` and the `.orchestrator` control plane.

Read in order: `Ust-Yonetim-Ana-Mimari-Plani.md`, `Platform-Temeli.md`, relevant `FazN-Plan.md`, `.orchestrator/SYSTEM.md`, active run and assigned role.

- Do not reduce approved scope for speed.
- Do not design Faz 8 without explicit user approval.
- Use contract-first dependency graphs.
- Implementers only edit assigned write scopes and never push. When the active run contains explicit user authorization for Git commits, every completed write item must be recorded after its checks pass as an atomic Conventional Commit.
- Commit messages use `type(scope): summary`, with the phase, platform module, or work-item area as the scope; vague messages such as `updates`, `changes`, or `wip` are forbidden.
- Push requires explicit user authorization and is performed only by the upper manager for a reviewed, verified, and accepted integration checkpoint. Force-push is forbidden.
- High-risk work requires independent review and verification.
- Conversation memory is not completion evidence; run/result artifacts are.
- Preserve user changes and unrelated dirty-worktree content.
