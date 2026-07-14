# Task for ce-correctness-reviewer

You are an adversarial reviewer focusing on **Correctness and Regressions**. 

Your task is to review the 'Admin Activity Monitor - View Logs Integration' work based on the goals in `TODO.md`. 
Specifically, inspect:
1. `app/templates/layout.html` and `app/templates/index.html`. Ensure the `logModal` is only in `layout.html` and removed from `index.html` to prevent ID collisions.
2. Check `app/static/js/logs.js` and `app/static/js/tasks.js`. Verify that log-related functions (`openLogs`, `refreshLogs`, etc.) are correctly extracted into `logs.js` and that `tasks.js` doesn't contain redundant or conflicting implementations.
3. Check `app/templates/admin_activity.html`. Verify the "View Logs" button is present and correctly calls the shared logic.
4. Identify any runtime risks: Are there missing script dependencies in `layout.html` that would prevent the modal from working on pages other than `index.html`?

Return concise, evidence-backed findings with file/line references and suggested fixes. No context summaries.

## Acceptance Contract
Acceptance level: attested
Completion is not accepted from prose alone. End with a structured acceptance report.

Criteria:
- criterion-1: Return concrete findings with file paths and severity when applicable

Required evidence: review-findings, residual-risks

Finish with a fenced JSON block tagged `acceptance-report` in this shape:
Use empty arrays when no items apply; array fields contain strings unless object entries are shown.
```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "specific proof"
    }
  ],
  "changedFiles": [
    "src/file.ts"
  ],
  "testsAddedOrUpdated": [
    "test/file.test.ts"
  ],
  "commandsRun": [
    {
      "command": "command",
      "result": "passed",
      "summary": "short result"
    }
  ],
  "validationOutput": [
    "validation output or concise summary"
  ],
  "residualRisks": [
    "none"
  ],
  "noStagedFiles": true,
  "diffSummary": "short description of the diff",
  "reviewFindings": [
    "blocker: file.ts:12 - issue found, or no blockers"
  ],
  "manualNotes": "anything else the parent should know"
}
```