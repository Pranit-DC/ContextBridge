# O3 independent review packet

Assigned reviewer: Pranit. Status: pending; no human judgements have been supplied.

Split: tuning; dataset SHA256: `c98957503bea13f4b5c52741fd889f2dffdbd9b03576744327549e2103f6b192`.
Run SHA256: `a468909ad7604fc540b0e75e5780a60e91e173340a80258cd9f97d6e3f76467e`; prompt: `formation-chat-v2`.

Review source meaning, atomicity, type, qualifiers, time, units and admission context.
Confirm/reject each case's design labels, even when the model failed or returned nothing.
Fill JSON blanks yourself; do not ask the evaluated model to supply human labels.
Request a reviewed revision for wrong gold labels; never change them to fit output.
JSON is an attestation, not authentication of reviewer identity. Supply a review
URL/commit reference in review_evidence and confirm it through the team's review process.
Provider failures show availability; absent output does not prove correct empty output.

## tuning-database-choice

```json
{
  "event": {
    "scope": "project",
    "project_id": "neptune",
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000001",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "database-choice",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "For Neptune, use PostgreSQL as the primary database. This is the agreed project decision."
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
      "claim_id": "tuning-database-choice-1",
      "content": "Neptune uses PostgreSQL as its primary database.",
      "type": "DECISION",
      "conditions": {},
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "user",
      "source_excerpt": "For Neptune, use PostgreSQL as the primary database. This is the agreed project decision.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-database-choice",
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": 1234.0000000003783,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-database-choice",
    "category": "attempted_failed_network_cases",
    "attempted_calls": 1,
    "execution": "attempted"
  }
}
```

## tuning-disabled-flag

```json
{
  "event": {
    "scope": "project",
    "project_id": "neptune",
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000002",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "disabled-flag",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "tool",
        "content": "Neptune configuration check: feature_flags.auto_capture = false in settings/runtime.toml."
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
      "claim_id": "tuning-disabled-flag-1",
      "content": "Neptune disables auto_capture in settings/runtime.toml.",
      "type": "FACT",
      "conditions": {},
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.capture.enabled",
      "source_kind": "tool",
      "source_excerpt": "Neptune configuration check: feature_flags.auto_capture = false in settings/runtime.toml.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-disabled-flag",
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-disabled-flag",
    "category": "unattempted_cases",
    "attempted_calls": 0,
    "execution": "provider_stop"
  }
}
```

## tuning-developer-language

```json
{
  "event": {
    "scope": "developer",
    "project_id": null,
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000003",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "developer-language",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "For my own new side projects, I prefer TypeScript. This is a general preference, not just Neptune."
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
      "claim_id": "tuning-developer-language-1",
      "content": "The developer prefers TypeScript for new personal side projects.",
      "type": "PREFERENCE",
      "conditions": {},
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "developer.language.preference",
      "source_kind": "user",
      "source_excerpt": "For my own new side projects, I prefer TypeScript. This is a general preference, not just Neptune.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-developer-language",
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-developer-language",
    "category": "unattempted_cases",
    "attempted_calls": 0,
    "execution": "provider_stop"
  }
}
```

## tuning-release-state

```json
{
  "event": {
    "scope": "project",
    "project_id": "neptune",
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000004",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "release-state",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Neptune release-v1 is now frozen for feature work."
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
      "claim_id": "tuning-release-state-1",
      "content": "Neptune release-v1 is frozen for feature work.",
      "type": "STATE",
      "conditions": {},
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.release-v1.state",
      "source_kind": "user",
      "source_excerpt": "Neptune release-v1 is now frozen for feature work.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-release-state",
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-release-state",
    "category": "unattempted_cases",
    "attempted_calls": 0,
    "execution": "provider_stop"
  }
}
```

## tuning-rollback

```json
{
  "event": {
    "scope": "project",
    "project_id": "neptune",
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000005",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "rollback",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "tool",
        "content": "Neptune operations log: the migration rollback completed at 2026-10-08T12:00:00Z."
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
      "claim_id": "tuning-rollback-1",
      "content": "Neptune's migration rollback completed at 2026-10-08T12:00:00Z.",
      "type": "EVENT",
      "conditions": {},
      "valid_from": "2026-10-08T12:00:00Z",
      "claim_key": "project.migration.rollback",
      "source_kind": "tool",
      "source_excerpt": "Neptune operations log: the migration rollback completed at 2026-10-08T12:00:00Z.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-rollback",
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-rollback",
    "category": "unattempted_cases",
    "attempted_calls": 0,
    "execution": "provider_stop"
  }
}
```

## tuning-logging-lesson

```json
{
  "event": {
    "scope": "project",
    "project_id": "neptune",
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000006",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "logging-lesson",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "After the one token-logging incident, remember this lesson: never log session headers in auth/session.ts, including on error paths."
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
      "claim_id": "tuning-logging-lesson-1",
      "content": "Never log session headers in auth/session.ts, including on error paths.",
      "type": "LESSON",
      "conditions": {},
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.auth.header-logging",
      "source_kind": "user",
      "source_excerpt": "After the one token-logging incident, remember this lesson: never log session headers in auth/session.ts, including on error paths.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-logging-lesson",
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-logging-lesson",
    "category": "unattempted_cases",
    "attempted_calls": 0,
    "execution": "provider_stop"
  }
}
```

## tuning-database-environments

```json
{
  "event": {
    "scope": "project",
    "project_id": "neptune",
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000007",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "database-environments",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "For Neptune production, use PostgreSQL."
      },
      {
        "message_id": "m2",
        "role": "user",
        "content": "For Neptune development, use SQLite."
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
      "claim_id": "tuning-database-environments-1",
      "content": "Neptune uses PostgreSQL in production.",
      "type": "DECISION",
      "conditions": {
        "environment": "production"
      },
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "user",
      "source_excerpt": "For Neptune production, use PostgreSQL.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    },
    {
      "claim_id": "tuning-database-environments-2",
      "content": "Neptune uses SQLite in development.",
      "type": "DECISION",
      "conditions": {
        "environment": "development"
      },
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "user",
      "source_excerpt": "For Neptune development, use SQLite.",
      "message_ids": [
        "m2"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-database-environments",
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-database-environments",
    "category": "unattempted_cases",
    "attempted_calls": 0,
    "execution": "provider_stop"
  }
}
```

## tuning-adopt-cache

```json
{
  "event": {
    "scope": "project",
    "project_id": "neptune",
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000008",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "adopt-cache",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "assistant",
        "content": "Redis could be a cache option for Neptune."
      },
      {
        "message_id": "m2",
        "role": "user",
        "content": "Yes, use Redis as Neptune's cache. That is our decision."
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
      "claim_id": "tuning-adopt-cache-1",
      "content": "Neptune uses Redis as its cache.",
      "type": "DECISION",
      "conditions": {},
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.cache.primary",
      "source_kind": "user",
      "source_excerpt": "Yes, use Redis as Neptune's cache. That is our decision.",
      "message_ids": [
        "m2"
      ],
      "expected_admission": "ADMIT",
      "rationale": "The cited synthetic user/tool excerpt explicitly supports this useful atomic claim."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-adopt-cache",
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-adopt-cache",
    "category": "unattempted_cases",
    "attempted_calls": 0,
    "execution": "provider_stop"
  }
}
```

## tuning-polite-filler

```json
{
  "event": {
    "scope": "project",
    "project_id": "neptune",
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000009",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "polite-filler",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Okay, thanks for explaining that."
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
    "case_id": "tuning-polite-filler",
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-polite-filler",
    "category": "unattempted_cases",
    "attempted_calls": 0,
    "execution": "provider_stop"
  }
}
```

## tuning-assistant-only

```json
{
  "event": {
    "scope": "project",
    "project_id": "neptune",
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000010",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "assistant-only",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "assistant",
        "content": "You probably prefer Rust, so Neptune should use it."
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
    "case_id": "tuning-assistant-only",
    "proposals": [],
    "decisions": [],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-assistant-only",
    "category": "local_only_cases",
    "attempted_calls": 0,
    "execution": "local_only"
  }
}
```

## tuning-other-repo-guess

```json
{
  "event": {
    "scope": "project",
    "project_id": "neptune",
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000011",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "other-repo-guess",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "That other repository might use MongoDB, I am only guessing and have not checked."
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
    "case_id": "tuning-other-repo-guess",
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-other-repo-guess",
    "category": "unattempted_cases",
    "attempted_calls": 0,
    "execution": "provider_stop"
  }
}
```

## tuning-duplicate

```json
{
  "event": {
    "scope": "project",
    "project_id": "neptune",
    "schema_version": 1,
    "event_id": "51000000-0000-4000-8000-000000000012",
    "agent": "formation-fixture-agent",
    "session": "o3-tuning-session",
    "interaction": "duplicate",
    "occurred_at": "2026-10-09T10:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "For Neptune, the primary store is MariaDB. This remains our agreed database decision."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-10T10:00:00Z",
    "records": [
      {
        "memory": {
          "id": "53000000-0000-4000-8000-000000000001",
          "scope": "project",
          "project_id": "neptune",
          "type": "DECISION",
          "conditions": {},
          "created_at": "2026-10-09T09:00:01Z",
          "current_version": 1,
          "version": {
            "id": "54000000-0000-4000-8000-000000000001",
            "number": 1,
            "content": "Neptune uses MariaDB as its primary database.",
            "status": "ACTIVE",
            "valid_from": "2026-10-09T09:00:00Z",
            "valid_to": null,
            "recorded_at": "2026-10-09T09:00:01Z",
            "source": {
              "kind": "user",
              "agent": "formation-fixture-agent",
              "session": "earlier-synthetic-session",
              "interaction": "earlier-db-choice",
              "evidence": "For Neptune, the primary store is MariaDB. This remains our agreed database decision."
            }
          }
        },
        "claim_key": "project.database.primary",
        "confidence": null,
        "decision_state": "clear"
      }
    ]
  },
  "design_labels_pending_review": [
    {
      "claim_id": "tuning-duplicate-1",
      "content": "Neptune uses MariaDB as its primary database.",
      "type": "DECISION",
      "conditions": {},
      "valid_from": "2026-10-09T10:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "user",
      "source_excerpt": "For Neptune, the primary store is MariaDB. This remains our agreed database decision.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "REJECT",
      "rationale": "Supported useful extraction, but a clear current scoped duplicate must not be admitted again."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-duplicate",
    "proposals": [],
    "decisions": [],
    "error_code": "PROVIDER_UNAVAILABLE",
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-duplicate",
    "category": "unattempted_cases",
    "attempted_calls": 0,
    "execution": "provider_stop"
  }
}
```
