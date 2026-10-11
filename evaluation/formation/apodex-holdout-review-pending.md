# O3 independent review packet

Assigned reviewer: Pranit. Status: pending; no human judgements have been supplied.

Split: holdout; dataset SHA256: `ad6038dfd2f8f0b0ef625f40da9743e5519426ab7b61bfc23154d158ae32ac7f`.
Run SHA256: `5f98321ab90852c1e163f89ab46a2af2a3ef60bdb62b78ca684046755cc6ba19`; prompt: `formation-chat-v2`.

Review source meaning, atomicity, type, qualifiers, time, units and admission context.
Confirm/reject each case's design labels, even when the model failed or returned nothing.
Fill the companion JSON's blank fields yourself; do not use the evaluated model to label it.
If a gold label is wrong, request a reviewed dataset revision; do not change it to fit output.
A completed JSON is an attestation, not authentication of reviewer identity. Supply a review
URL/commit reference in review_evidence and confirm it through the team's review process.
Provider failures are availability results; absent output is not evidence of correct empty output.

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
        "candidate_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "event_id": "52000000-0000-4000-8000-000000000001",
        "type": "DECISION",
        "content": "Pin the Aurora V1 runtime to Python 3.12 and do not switch V1 to Python 3.13",
        "conditions": {
          "project_version": "V1"
        },
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": "aurora_v1_python_version",
        "confidence": 0.95,
        "usefulness": 0.9,
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
        "candidate_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "outcome": "ADMIT",
        "reason_codes": [
          "EXPLICIT_DECISION",
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 12765.999999999622,
    "input_tokens": 1867,
    "output_tokens": 1590,
    "cost": 0.0
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
        "candidate_id": "a1b2c3d4-e5f6-4789-a012-345678901234",
        "event_id": "52000000-0000-4000-8000-000000000002",
        "type": "FACT",
        "content": "Aurora project has max_upload_bytes = 2097152 configured in api/upload.py (2 MB upload limit).",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": "max_upload_bytes_limit",
        "confidence": 0.9,
        "usefulness": 0.7,
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
        "candidate_id": "a1b2c3d4-e5f6-4789-a012-345678901234",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 10218.000000000757,
    "input_tokens": 1844,
    "output_tokens": 1236,
    "cost": 0.0
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
        "candidate_id": "a1b2c3d4-e5f6-4789-9abc-def012345678",
        "event_id": "52000000-0000-4000-8000-000000000003",
        "type": "PREFERENCE",
        "content": "Developer prefers concise pull request descriptions that include the test results, applied across all projects.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": "pr_description_preference",
        "confidence": 0.9,
        "usefulness": 0.7,
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
        "candidate_id": "a1b2c3d4-e5f6-4789-9abc-def012345678",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 8360.000000000582,
    "input_tokens": 1801,
    "output_tokens": 860,
    "cost": 0.0
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
    "proposals": [],
    "decisions": [],
    "error_code": "INVALID_PROVIDER_OUTPUT",
    "latency_ms": 7202.999999997701,
    "input_tokens": 1158,
    "output_tokens": 1085,
    "cost": 0.0
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
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": 41594.00000000096,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
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
    "proposals": [],
    "decisions": [],
    "error_code": "INVALID_PROVIDER_OUTPUT",
    "latency_ms": 7170.9999999984575,
    "input_tokens": 1154,
    "output_tokens": 1134,
    "cost": 0.0
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
    "proposals": [],
    "decisions": [],
    "error_code": "INVALID_PROVIDER_OUTPUT",
    "latency_ms": 10407.000000002881,
    "input_tokens": 1182,
    "output_tokens": 1544,
    "cost": 0.0
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
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": 50155.99999999904,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
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
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": 49921.99999999866,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
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
    "proposals": [],
    "decisions": [],
    "error_code": "INVALID_PROVIDER_OUTPUT",
    "latency_ms": 28734.00000000038,
    "input_tokens": 1175,
    "output_tokens": 4773,
    "cost": 0.0
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
    "proposals": [],
    "decisions": [],
    "error_code": "INVALID_PROVIDER_OUTPUT",
    "latency_ms": 6610.000000000582,
    "input_tokens": 1144,
    "output_tokens": 957,
    "cost": 0.0
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
    "latency_ms": 8953.000000001339,
    "input_tokens": 1146,
    "output_tokens": 1238,
    "cost": 0.0
  }
}
```
