# O3 independent review packet

Assigned reviewer: Pranit. Status: pending; no human judgements have been supplied.

Split: tuning; dataset SHA256: `c98957503bea13f4b5c52741fd889f2dffdbd9b03576744327549e2103f6b192`.
Run SHA256: `f8d33d5c1857756311302fbd126b426e5a07ff90c6bce30dbe1eac3c7e962939`; prompt: `formation-chat-v2`.

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
    "proposals": [
      {
        "scope": "project",
        "project_id": "neptune",
        "schema_version": 1,
        "candidate_id": "d3f5c9a2-9b4e-4f1a-8c2d-7e6a9b0c1234",
        "event_id": "51000000-0000-4000-8000-000000000001",
        "type": "DECISION",
        "content": "For Neptune, use PostgreSQL as the primary database.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 0.9,
        "usefulness": 0.9,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-tuning-session",
          "interaction": "database-choice",
          "evidence": "For Neptune, use PostgreSQL as the primary database. This is the agreed project decision."
        },
        "evidence_refs": [
          {
            "event_id": "51000000-0000-4000-8000-000000000001",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "d3f5c9a2-9b4e-4f1a-8c2d-7e6a9b0c1234",
        "outcome": "ADMIT",
        "reason_codes": [
          "EXPLICIT_DECISION",
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 4281.000000002678,
    "input_tokens": 1805,
    "output_tokens": 400,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-database-choice",
    "category": "completed_network_cases",
    "attempted_calls": 2,
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
    "proposals": [
      {
        "scope": "project",
        "project_id": "neptune",
        "schema_version": 1,
        "candidate_id": "d3b0f1a2-9c4e-4f6a-8b2d-1e5f9c7a3b6d",
        "event_id": "51000000-0000-4000-8000-000000000002",
        "type": "FACT",
        "content": "feature_flags.auto_capture = false in settings/runtime.toml.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "tool",
          "agent": "formation-fixture-agent",
          "session": "o3-tuning-session",
          "interaction": "disabled-flag",
          "evidence": "Neptune configuration check: feature_flags.auto_capture = false in settings/runtime.toml."
        },
        "evidence_refs": [
          {
            "event_id": "51000000-0000-4000-8000-000000000002",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "d3b0f1a2-9c4e-4f6a-8b2d-1e5f9c7a3b6d",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 64250.0,
    "input_tokens": 1807,
    "output_tokens": 467,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-disabled-flag",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
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
    "proposals": [
      {
        "scope": "developer",
        "project_id": null,
        "schema_version": 1,
        "candidate_id": "a1111111-1111-1111-1111-111111111111",
        "event_id": "51000000-0000-4000-8000-000000000003",
        "type": "PREFERENCE",
        "content": "User prefers TypeScript for their own new side projects.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-tuning-session",
          "interaction": "developer-language",
          "evidence": "For my own new side projects, I prefer TypeScript. This is a general preference, not just Neptune."
        },
        "evidence_refs": [
          {
            "event_id": "51000000-0000-4000-8000-000000000003",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "a1111111-1111-1111-1111-111111111111",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 63952.9999999977,
    "input_tokens": 1795,
    "output_tokens": 391,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-developer-language",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
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
    "proposals": [
      {
        "scope": "project",
        "project_id": "neptune",
        "schema_version": 1,
        "candidate_id": "d3f8a1e2-6b4c-4f9a-9c2e-5d8f7b6c1a2b",
        "event_id": "51000000-0000-4000-8000-000000000004",
        "type": "FACT",
        "content": "Neptune release-v1 is now frozen for feature work.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 0.9,
        "usefulness": 0.9,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-tuning-session",
          "interaction": "release-state",
          "evidence": "Neptune release-v1 is now frozen for feature work."
        },
        "evidence_refs": [
          {
            "event_id": "51000000-0000-4000-8000-000000000004",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "d3f8a1e2-6b4c-4f9a-9c2e-5d8f7b6c1a2b",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 63797.0000000023,
    "input_tokens": 1789,
    "output_tokens": 443,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-release-state",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
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
    "proposals": [
      {
        "scope": "project",
        "project_id": "neptune",
        "schema_version": 1,
        "candidate_id": "e3b0c442-98fc-1c14-9af4-000000000001",
        "event_id": "51000000-0000-4000-8000-000000000005",
        "type": "FACT",
        "content": "The migration rollback completed at 2026-10-08T12:00:00Z.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 0.93,
        "usefulness": 0.9,
        "source": {
          "kind": "tool",
          "agent": "formation-fixture-agent",
          "session": "o3-tuning-session",
          "interaction": "rollback",
          "evidence": "Neptune operations log: the migration rollback completed at 2026-10-08T12:00:00Z."
        },
        "evidence_refs": [
          {
            "event_id": "51000000-0000-4000-8000-000000000005",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "e3b0c442-98fc-1c14-9af4-000000000001",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 64233.99999999674,
    "input_tokens": 1819,
    "output_tokens": 440,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-rollback",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
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
    "proposals": [
      {
        "scope": "project",
        "project_id": "neptune",
        "schema_version": 1,
        "candidate_id": "a1b2c3d4-1111-2222-3333-444455556666",
        "event_id": "51000000-0000-4000-8000-000000000006",
        "type": "LESSON",
        "content": "After the one token-logging incident, remember this lesson: never log session headers in auth/session.ts, including on error paths.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 0.9,
        "usefulness": 0.9,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-tuning-session",
          "interaction": "logging-lesson",
          "evidence": "After the one token-logging incident, remember this lesson: never log session headers in auth/session.ts, including on error paths."
        },
        "evidence_refs": [
          {
            "event_id": "51000000-0000-4000-8000-000000000006",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "a1b2c3d4-1111-2222-3333-444455556666",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 63860.00000000058,
    "input_tokens": 1835,
    "output_tokens": 467,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-logging-lesson",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
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
    "proposals": [
      {
        "scope": "project",
        "project_id": "neptune",
        "schema_version": 1,
        "candidate_id": "d3e1f2a4-5b6c-7d8e-9f01-23456789abcd",
        "event_id": "51000000-0000-4000-8000-000000000007",
        "type": "FACT",
        "content": "Neptune production uses PostgreSQL.",
        "conditions": {
          "environment": "production"
        },
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": "db_engine",
        "confidence": 0.9,
        "usefulness": 0.9,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-tuning-session",
          "interaction": "database-environments",
          "evidence": "For Neptune production, use PostgreSQL."
        },
        "evidence_refs": [
          {
            "event_id": "51000000-0000-4000-8000-000000000007",
            "message_id": "m1"
          }
        ]
      },
      {
        "scope": "project",
        "project_id": "neptune",
        "schema_version": 1,
        "candidate_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "event_id": "51000000-0000-4000-8000-000000000007",
        "type": "FACT",
        "content": "Neptune development uses SQLite.",
        "conditions": {
          "environment": "development"
        },
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": "db_engine",
        "confidence": 0.9,
        "usefulness": 0.9,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-tuning-session",
          "interaction": "database-environments",
          "evidence": "For Neptune development, use SQLite."
        },
        "evidence_refs": [
          {
            "event_id": "51000000-0000-4000-8000-000000000007",
            "message_id": "m2"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "d3e1f2a4-5b6c-7d8e-9f01-23456789abcd",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      },
      {
        "schema_version": 1,
        "candidate_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 67172.0000000023,
    "input_tokens": 2476,
    "output_tokens": 823,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-database-environments",
    "category": "completed_network_cases",
    "attempted_calls": 3,
    "execution": "attempted"
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
    "proposals": [
      {
        "scope": "project",
        "project_id": "neptune",
        "schema_version": 1,
        "candidate_id": "e3b0c442-98fc-1c14-9afb-4c6a1e2d5f9a",
        "event_id": "51000000-0000-4000-8000-000000000008",
        "type": "DECISION",
        "content": "Use Redis as Neptune's cache.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 0.92,
        "usefulness": 0.9,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-tuning-session",
          "interaction": "adopt-cache",
          "evidence": "Yes, use Redis as Neptune's cache. That is our decision."
        },
        "evidence_refs": [
          {
            "event_id": "51000000-0000-4000-8000-000000000008",
            "message_id": "m2"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "e3b0c442-98fc-1c14-9afb-4c6a1e2d5f9a",
        "outcome": "ADMIT",
        "reason_codes": [
          "EXPLICIT_DECISION",
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 64452.9999999977,
    "input_tokens": 1843,
    "output_tokens": 450,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-adopt-cache",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
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
    "error_code": null,
    "latency_ms": 61469.00000000096,
    "input_tokens": 1142,
    "output_tokens": 45,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-polite-filler",
    "category": "completed_network_cases",
    "attempted_calls": 1,
    "execution": "attempted"
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
    "error_code": null,
    "latency_ms": 60639.99999999942,
    "input_tokens": 1153,
    "output_tokens": 74,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-other-repo-guess",
    "category": "completed_network_cases",
    "attempted_calls": 1,
    "execution": "attempted"
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
    "proposals": [
      {
        "scope": "project",
        "project_id": "neptune",
        "schema_version": 1,
        "candidate_id": "e1a2b3c4-5678-90ab-cdef-1234567890ab",
        "event_id": "51000000-0000-4000-8000-000000000012",
        "type": "DECISION",
        "content": "For Neptune, the primary store is MariaDB. This remains our agreed database decision.",
        "conditions": {},
        "valid_from": "2026-10-09T10:00:00Z",
        "claim_key": null,
        "confidence": 0.9,
        "usefulness": 0.9,
        "source": {
          "kind": "user",
          "agent": "formation-fixture-agent",
          "session": "o3-tuning-session",
          "interaction": "duplicate",
          "evidence": "For Neptune, the primary store is MariaDB. This remains our agreed database decision."
        },
        "evidence_refs": [
          {
            "event_id": "51000000-0000-4000-8000-000000000012",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "e1a2b3c4-5678-90ab-cdef-1234567890ab",
        "outcome": "ADMIT",
        "reason_codes": [
          "EXPLICIT_DECISION",
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 63985.00000000058,
    "input_tokens": 1793,
    "output_tokens": 468,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-duplicate",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```
