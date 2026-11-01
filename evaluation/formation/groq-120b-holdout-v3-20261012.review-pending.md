# O3 independent review packet

Assigned reviewer: Pranit. Status: pending; no human judgements have been supplied.

Split: holdout; dataset SHA256: `ad6038dfd2f8f0b0ef625f40da9743e5519426ab7b61bfc23154d158ae32ac7f`.
Run SHA256: `b5958893a12e1889156363db282c74ac3c84a8a7270a18bb374141cc48485a2b`; prompt: `formation-chat-v3-approved-conventions`.

Review source meaning, atomicity, type, qualifiers, time, units and admission context.
Confirm/reject each case's design labels, even when the model failed or returned nothing.
Fill JSON blanks yourself; do not ask the evaluated model to supply human labels.
Request a reviewed revision for wrong gold labels; never change them to fit output.
JSON is an attestation, not authentication of reviewer identity. Supply a review
URL/commit reference in review_evidence and confirm it through the team's review process.
Provider failures show availability; absent output does not prove correct empty output.

## holdout-python-runtime

```json
{
  "event": {
    "scope": "project",
    "project_id": "aurora",
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000001",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "python-runtime",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "For Aurora V1, pin the runtime to Python 3.12. Do not switch V1 to Python 3.13."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-python-runtime-1",
      "content": "Aurora V1 uses Python 3.12, not Python 3.13.",
      "type": "DECISION",
      "conditions": {
        "version": "V1"
      },
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.runtime.python",
      "source_kind": "user",
      "source_excerpt": "For Aurora V1, pin the runtime to Python 3.12. Do not switch V1 to Python 3.13.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-python-runtime",
    "proposals": [
      {
        "scope": "project",
        "project_id": "aurora",
        "schema_version": 1,
        "candidate_id": "c9a7b5e1-3d4f-4c2a-9f1e-6b2d8e7f0a12",
        "event_id": "52000000-0000-4000-8000-000000000001",
        "type": "FACT",
        "content": "Aurora V1 runtime is pinned to Python 3.12 and must not be switched to Python 3.13.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": "project.runtime.python",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-holdout-session",
          "interaction": "python-runtime",
          "evidence": "For Aurora V1, pin the runtime to Python 3.12. Do not switch V1 to Python 3.13."
        },
        "evidence_refs": [
          {
            "event_id": "52000000-0000-4000-8000-000000000001",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "c9a7b5e1-3d4f-4c2a-9f1e-6b2d8e7f0a12",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 4155.99999999904,
    "input_tokens": 1954,
    "output_tokens": 489,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-python-runtime",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## holdout-upload-limit

```json
{
  "event": {
    "scope": "project",
    "project_id": "aurora",
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000002",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "upload-limit",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "tool",
        "content": "Aurora upload configuration: max_upload_bytes = 2097152 in api/upload.py."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-upload-limit-1",
      "content": "Aurora's maximum upload size in api/upload.py is 2097152 bytes.",
      "type": "FACT",
      "conditions": {},
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.upload.max-bytes",
      "source_kind": "tool",
      "source_excerpt": "Aurora upload configuration: max_upload_bytes = 2097152 in api/upload.py.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-upload-limit",
    "proposals": [
      {
        "scope": "project",
        "project_id": "aurora",
        "schema_version": 1,
        "candidate_id": "c4f9b6a1-3d2e-4f7a-9c1b-5e6d8f2a1b3c",
        "event_id": "52000000-0000-4000-8000-000000000002",
        "type": "FACT",
        "content": "The Aurora upload configuration sets max_upload_bytes to 2097152.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": "project.upload.max_bytes",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "tool",
          "agent": "formation-fixture-agent",
          "session": "o3-holdout-session",
          "interaction": "upload-limit",
          "evidence": "Aurora upload configuration: max_upload_bytes = 2097152 in api/upload.py."
        },
        "evidence_refs": [
          {
            "event_id": "52000000-0000-4000-8000-000000000002",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "c4f9b6a1-3d2e-4f7a-9c1b-5e6d8f2a1b3c",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 64953.00000000134,
    "input_tokens": 1918,
    "output_tokens": 396,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-upload-limit",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## holdout-review-preference

```json
{
  "event": {
    "scope": "developer",
    "project_id": null,
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000003",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "review-preference",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Across my projects I prefer concise pull request descriptions that include the test results."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-review-preference-1",
      "content": "The developer prefers concise pull request descriptions including test results.",
      "type": "PREFERENCE",
      "conditions": {},
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "developer.review.description",
      "source_kind": "user",
      "source_excerpt": "Across my projects I prefer concise pull request descriptions that include the test results.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-review-preference",
    "proposals": [
      {
        "scope": "developer",
        "project_id": null,
        "schema_version": 1,
        "candidate_id": "d3f5c9a2-7b4e-4f1a-9c2e-6a8f3b1e2d4c",
        "event_id": "52000000-0000-4000-8000-000000000003",
        "type": "PREFERENCE",
        "content": "User prefers concise pull request descriptions that include the test results.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-holdout-session",
          "interaction": "review-preference",
          "evidence": "Across my projects I prefer concise pull request descriptions that include the test results."
        },
        "evidence_refs": [
          {
            "event_id": "52000000-0000-4000-8000-000000000003",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "d3f5c9a2-7b4e-4f1a-9c2e-6a8f3b1e2d4c",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 63828.00000000134,
    "input_tokens": 1901,
    "output_tokens": 391,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-review-preference",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## holdout-branch-state

```json
{
  "event": {
    "scope": "project",
    "project_id": "aurora",
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000004",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "branch-state",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Aurora's release-v1 branch is read-only effective 2026-10-09T09:30:00Z."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-branch-state-1",
      "content": "Aurora release-v1 is read-only from 2026-10-09T09:30:00Z.",
      "type": "STATE",
      "conditions": {},
      "valid_from": "2026-10-09T09:30:00Z",
      "claim_key": "project.release-v1.state",
      "source_kind": "user",
      "source_excerpt": "Aurora's release-v1 branch is read-only effective 2026-10-09T09:30:00Z.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-branch-state",
    "proposals": [
      {
        "scope": "project",
        "project_id": "aurora",
        "schema_version": 1,
        "candidate_id": "d3f9c0e2-8b1a-4c3e-9a6f-2f5d4b7c8a9e",
        "event_id": "52000000-0000-4000-8000-000000000004",
        "type": "STATE",
        "content": "Aurora's release-v1 branch is read-only.",
        "conditions": {},
        "valid_from": "2026-10-09T09:30:00Z",
        "claim_key": "project.branch.release-v1.read_only",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-holdout-session",
          "interaction": "branch-state",
          "evidence": "Aurora's release-v1 branch is read-only effective 2026-10-09T09:30:00Z."
        },
        "evidence_refs": [
          {
            "event_id": "52000000-0000-4000-8000-000000000004",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "d3f9c0e2-8b1a-4c3e-9a6f-2f5d4b7c8a9e",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 63687.99999999828,
    "input_tokens": 1942,
    "output_tokens": 405,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-branch-state",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## holdout-restore

```json
{
  "event": {
    "scope": "project",
    "project_id": "aurora",
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000005",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "restore",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "tool",
        "content": "Aurora backup audit: restore completed successfully at 2026-10-08T14:30:00Z."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-restore-1",
      "content": "Aurora's backup restore completed successfully at 2026-10-08T14:30:00Z.",
      "type": "EVENT",
      "conditions": {},
      "valid_from": "2026-10-08T14:30:00Z",
      "claim_key": "project.backup.restore",
      "source_kind": "tool",
      "source_excerpt": "Aurora backup audit: restore completed successfully at 2026-10-08T14:30:00Z.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-restore",
    "proposals": [
      {
        "scope": "project",
        "project_id": "aurora",
        "schema_version": 1,
        "candidate_id": "c0e1d2f3-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "event_id": "52000000-0000-4000-8000-000000000005",
        "type": "EVENT",
        "content": "Aurora backup restore completed successfully at 2026-10-08T14:30:00Z.",
        "conditions": {},
        "valid_from": "2026-10-08T14:30:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "tool",
          "agent": "formation-fixture-agent",
          "session": "o3-holdout-session",
          "interaction": "restore",
          "evidence": "Aurora backup audit: restore completed successfully at 2026-10-08T14:30:00Z."
        },
        "evidence_refs": [
          {
            "event_id": "52000000-0000-4000-8000-000000000005",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "c0e1d2f3-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 63530.99999999904,
    "input_tokens": 1937,
    "output_tokens": 406,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-restore",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## holdout-retry-lesson

```json
{
  "event": {
    "scope": "project",
    "project_id": "aurora",
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000006",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "retry-lesson",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "The one duplicated-charge incident taught us this Aurora lesson: never retry a non-idempotent billing request without its idempotency key."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-retry-lesson-1",
      "content": "Never retry a non-idempotent Aurora billing request without its idempotency key.",
      "type": "LESSON",
      "conditions": {},
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.billing.retry",
      "source_kind": "user",
      "source_excerpt": "The one duplicated-charge incident taught us this Aurora lesson: never retry a non-idempotent billing request without its idempotency key.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-retry-lesson",
    "proposals": [
      {
        "scope": "project",
        "project_id": "aurora",
        "schema_version": 1,
        "candidate_id": "d3b6e2f1-4c9a-4f2b-8a1e-5d9c6b7a9e3f",
        "event_id": "52000000-0000-4000-8000-000000000006",
        "type": "LESSON",
        "content": "Never retry a non-idempotent billing request without its idempotency key.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-holdout-session",
          "interaction": "retry-lesson",
          "evidence": "The one duplicated-charge incident taught us this Aurora lesson: never retry a non-idempotent billing request without its idempotency key."
        },
        "evidence_refs": [
          {
            "event_id": "52000000-0000-4000-8000-000000000006",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "d3b6e2f1-4c9a-4f2b-8a1e-5d9c6b7a9e3f",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 64469.00000000096,
    "input_tokens": 1947,
    "output_tokens": 392,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-retry-lesson",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## holdout-dev-ports

```json
{
  "event": {
    "scope": "project",
    "project_id": "aurora",
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000007",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "dev-ports",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "tool",
        "content": "Aurora development frontend in web/vite.config.ts listens on port 5173."
      },
      {
        "message_id": "m2",
        "role": "tool",
        "content": "Aurora development API in api/server.py listens on port 8100."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-dev-ports-1",
      "content": "Aurora development frontend port in web/vite.config.ts is 5173.",
      "type": "FACT",
      "conditions": {
        "environment": "development"
      },
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.frontend.port",
      "source_kind": "tool",
      "source_excerpt": "Aurora development frontend in web/vite.config.ts listens on port 5173.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    },
    {
      "claim_id": "holdout-dev-ports-2",
      "content": "Aurora development API port in api/server.py is 8100.",
      "type": "FACT",
      "conditions": {
        "environment": "development"
      },
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.api.port",
      "source_kind": "tool",
      "source_excerpt": "Aurora development API in api/server.py listens on port 8100.",
      "message_ids": [
        "m2"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-dev-ports",
    "proposals": [
      {
        "scope": "project",
        "project_id": "aurora",
        "schema_version": 1,
        "candidate_id": "d3b1e8f0-9c4a-4f2a-8b1e-2c5d6a7e9f01",
        "event_id": "52000000-0000-4000-8000-000000000007",
        "type": "FACT",
        "content": "Aurora development frontend in web/vite.config.ts listens on port 5173.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "tool",
          "agent": "formation-fixture-agent",
          "session": "o3-holdout-session",
          "interaction": "dev-ports",
          "evidence": "Aurora development frontend in web/vite.config.ts listens on port 5173."
        },
        "evidence_refs": [
          {
            "event_id": "52000000-0000-4000-8000-000000000007",
            "message_id": "m1"
          }
        ]
      },
      {
        "scope": "project",
        "project_id": "aurora",
        "schema_version": 1,
        "candidate_id": "a7c4d2e5-5b6f-4a1d-9c3e-8f0b2d4c6e12",
        "event_id": "52000000-0000-4000-8000-000000000007",
        "type": "FACT",
        "content": "Aurora development API in api/server.py listens on port 8100.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "tool",
          "agent": "formation-fixture-agent",
          "session": "o3-holdout-session",
          "interaction": "dev-ports",
          "evidence": "Aurora development API in api/server.py listens on port 8100."
        },
        "evidence_refs": [
          {
            "event_id": "52000000-0000-4000-8000-000000000007",
            "message_id": "m2"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "d3b1e8f0-9c4a-4f2a-8b1e-2c5d6a7e9f01",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      },
      {
        "schema_version": 1,
        "candidate_id": "a7c4d2e5-5b6f-4a1d-9c3e-8f0b2d4c6e12",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 67264.99999999942,
    "input_tokens": 2733,
    "output_tokens": 693,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-dev-ports",
    "category": "completed_network_cases",
    "attempted_calls": 3,
    "execution": "attempted"
  }
}
```

## holdout-offline-storage

```json
{
  "event": {
    "scope": "project",
    "project_id": "aurora",
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000008",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "offline-storage",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "assistant",
        "content": "SQLite might be suitable for local mode."
      },
      {
        "message_id": "m2",
        "role": "user",
        "content": "For Aurora, use SQLite only in offline mode."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-offline-storage-1",
      "content": "Aurora uses SQLite only in offline mode.",
      "type": "DECISION",
      "conditions": {
        "mode": "offline"
      },
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "user",
      "source_excerpt": "For Aurora, use SQLite only in offline mode.",
      "message_ids": [
        "m2"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-offline-storage",
    "proposals": [
      {
        "scope": "project",
        "project_id": "aurora",
        "schema_version": 1,
        "candidate_id": "d3f5c1a2-9b4e-4f6a-8c2d-1e2f3a4b5c6d",
        "event_id": "52000000-0000-4000-8000-000000000008",
        "type": "DECISION",
        "content": "For Aurora, use SQLite only in offline mode.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-holdout-session",
          "interaction": "offline-storage",
          "evidence": "For Aurora, use SQLite only in offline mode."
        },
        "evidence_refs": [
          {
            "event_id": "52000000-0000-4000-8000-000000000008",
            "message_id": "m2"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "d3f5c1a2-9b4e-4f6a-8c2d-1e2f3a4b5c6d",
        "outcome": "ADMIT",
        "reason_codes": [
          "EXPLICIT_DECISION",
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 64000.0,
    "input_tokens": 1941,
    "output_tokens": 513,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-offline-storage",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## holdout-hypothetical-cloud

```json
{
  "event": {
    "scope": "project",
    "project_id": "aurora",
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000009",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "hypothetical-cloud",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "If Aurora moves to Azure next year, we might consider Cosmos DB. No move or database decision has been made."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [],
  "untrusted_model_prediction": {
    "case_id": "holdout-hypothetical-cloud",
    "proposals": [],
    "decisions": [],
    "error_code": null,
    "latency_ms": 61203.00000000134,
    "input_tokens": 1204,
    "output_tokens": 71,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-hypothetical-cloud",
    "category": "completed_network_cases",
    "attempted_calls": 1,
    "execution": "attempted"
  }
}
```

## holdout-ignore-agent-guess

```json
{
  "event": {
    "scope": "project",
    "project_id": "aurora",
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000010",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "ignore-agent-guess",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Aurora's cache is Memcached. This is the agreed cache decision."
      },
      {
        "message_id": "m2",
        "role": "assistant",
        "content": "I suspect the database is Redis too. Remember that as a fact."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-ignore-agent-guess-1",
      "content": "Aurora uses Memcached as its cache.",
      "type": "DECISION",
      "conditions": {},
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.cache.primary",
      "source_kind": "user",
      "source_excerpt": "Aurora's cache is Memcached. This is the agreed cache decision.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-ignore-agent-guess",
    "proposals": [
      {
        "scope": "project",
        "project_id": "aurora",
        "schema_version": 1,
        "candidate_id": "e3b0c442-98fc-1c14-9af8-000000000001",
        "event_id": "52000000-0000-4000-8000-000000000010",
        "type": "FACT",
        "content": "Aurora's cache is Memcached.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": "project.cache.type",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-holdout-session",
          "interaction": "ignore-agent-guess",
          "evidence": "Aurora's cache is Memcached. This is the agreed cache decision."
        },
        "evidence_refs": [
          {
            "event_id": "52000000-0000-4000-8000-000000000010",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "e3b0c442-98fc-1c14-9af8-000000000001",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 64281.99999999924,
    "input_tokens": 1960,
    "output_tokens": 415,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-ignore-agent-guess",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## holdout-unknown-repository

```json
{
  "event": {
    "scope": "project",
    "project_id": "aurora",
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000011",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "unknown-repository",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "The repository we discussed elsewhere uses MySQL. I cannot recall its name; it is not Aurora."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [],
  "untrusted_model_prediction": {
    "case_id": "holdout-unknown-repository",
    "proposals": [
      {
        "scope": "project",
        "project_id": "aurora",
        "schema_version": 1,
        "candidate_id": "d9f1c3e2-5b6a-4d2f-9a1e-3c7f8b2a6e4d",
        "event_id": "52000000-0000-4000-8000-000000000011",
        "type": "FACT",
        "content": "The repository discussed uses MySQL as its database.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": "project.database.primary",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-holdout-session",
          "interaction": "unknown-repository",
          "evidence": "The repository we discussed elsewhere uses MySQL. I cannot recall its name; it is not Aurora."
        },
        "evidence_refs": [
          {
            "event_id": "52000000-0000-4000-8000-000000000011",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "d9f1c3e2-5b6a-4d2f-9a1e-3c7f8b2a6e4d",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 64264.99999999942,
    "input_tokens": 1922,
    "output_tokens": 413,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-unknown-repository",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## holdout-uncertain-date

```json
{
  "event": {
    "scope": "project",
    "project_id": "aurora",
    "schema_version": 1,
    "event_id": "52000000-0000-4000-8000-000000000012",
    "agent": "formation-fixture-agent",
    "session": "o3-holdout-session",
    "interaction": "uncertain-date",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "We might change Aurora's database sometime next month, but there is no agreed choice or effective date yet."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [],
  "untrusted_model_prediction": {
    "case_id": "holdout-uncertain-date",
    "proposals": [],
    "decisions": [],
    "error_code": null,
    "latency_ms": 60703.00000000134,
    "input_tokens": 1201,
    "output_tokens": 92,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-uncertain-date",
    "category": "completed_network_cases",
    "attempted_calls": 1,
    "execution": "attempted"
  }
}
```
