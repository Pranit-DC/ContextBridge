# O3 independent review packet

Assigned reviewer: Pranit. Status: pending; no human judgements have been supplied.

Split: holdout; dataset SHA256: `70305bd82a894518b5ab5a4ad4cc2bab110c2da69029d2a732f8017996315133`.
Run SHA256: `df103cda6edbaa4dddf92ec0dd680d29d1ebf2774298df9ecd006d3c1242ee65`; prompt: `formation-chat-v4.4-grounded-batch`.

Review source meaning, atomicity, type, qualifiers, time, units and admission context.
Confirm/reject each case's design labels, even when the model failed or returned nothing.
Fill JSON blanks yourself; do not ask the evaluated model to supply human labels.
Request a reviewed revision for wrong gold labels; never change them to fit output.
JSON is an attestation, not authentication of reviewer identity. Supply a review
URL/commit reference in review_evidence and confirm it through the team's review process.
Provider failures show availability; absent output does not prove correct empty output.

## holdout-v2-runtime-choice

```json
{
  "event": {
    "scope": "project",
    "project_id": "lyra",
    "schema_version": 1,
    "event_id": "63a7a945-48d4-5def-99ca-b40ab072bd92",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-runtime-choice",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "For Lyra V3, pin the runtime to Rust. This is our adopted choice for V3 only."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-v2-runtime-choice-1",
      "content": "Lyra V3 uses Rust.",
      "type": "DECISION",
      "conditions": {
        "version": "V3"
      },
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.runtime.rust",
      "source_kind": "user",
      "source_excerpt": "For Lyra V3, pin the runtime to Rust. This is our adopted choice for V3 only.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-runtime-choice",
    "proposals": [
      {
        "scope": "project",
        "project_id": "lyra",
        "schema_version": 1,
        "candidate_id": "6d1bf75c-935c-5dfb-9203-99af123c624b",
        "event_id": "63a7a945-48d4-5def-99ca-b40ab072bd92",
        "type": "DECISION",
        "content": "Pin the runtime to Rust for Lyra V3.",
        "conditions": {
          "version": "V3"
        },
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "holdout-v2-runtime-choice",
          "interaction": "synthetic-interaction",
          "evidence": "For Lyra V3, pin the runtime to Rust. This is our adopted choice for V3 only."
        },
        "evidence_refs": [
          {
            "event_id": "63a7a945-48d4-5def-99ca-b40ab072bd92",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "6d1bf75c-935c-5dfb-9203-99af123c624b",
        "outcome": "ADMIT",
        "reason_codes": [
          "EXPLICIT_DECISION",
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-runtime-choice",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```

## holdout-v2-environments

```json
{
  "event": {
    "scope": "project",
    "project_id": "lyra",
    "schema_version": 1,
    "event_id": "a58dac9f-50fa-5038-b9c5-81e3e969baee",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-environments",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "tool",
        "content": "Lyra production uses MariaDB; Lyra development uses DuckDB."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-v2-environments-1",
      "content": "Lyra production uses MariaDB.",
      "type": "FACT",
      "conditions": {
        "environment": "production"
      },
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "tool",
      "source_excerpt": "Lyra production uses MariaDB; Lyra development uses DuckDB.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    },
    {
      "claim_id": "holdout-v2-environments-2",
      "content": "Lyra development uses DuckDB.",
      "type": "FACT",
      "conditions": {
        "environment": "development"
      },
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "tool",
      "source_excerpt": "Lyra production uses MariaDB; Lyra development uses DuckDB.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-environments",
    "proposals": [
      {
        "scope": "project",
        "project_id": "lyra",
        "schema_version": 1,
        "candidate_id": "a50b8c16-5a7d-56d9-a519-0b03a4198a0a",
        "event_id": "a58dac9f-50fa-5038-b9c5-81e3e969baee",
        "type": "FACT",
        "content": "Lyra production uses MariaDB.",
        "conditions": {
          "environment": "production"
        },
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": "project.database.primary",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "tool",
          "agent": "synthetic-dataset",
          "session": "holdout-v2-environments",
          "interaction": "synthetic-interaction",
          "evidence": "Lyra production uses MariaDB; Lyra development uses DuckDB."
        },
        "evidence_refs": [
          {
            "event_id": "a58dac9f-50fa-5038-b9c5-81e3e969baee",
            "message_id": "m1"
          }
        ]
      },
      {
        "scope": "project",
        "project_id": "lyra",
        "schema_version": 1,
        "candidate_id": "31aa338c-7a38-5020-9119-37f8eb13ed1b",
        "event_id": "a58dac9f-50fa-5038-b9c5-81e3e969baee",
        "type": "FACT",
        "content": "Lyra development uses DuckDB.",
        "conditions": {
          "environment": "development"
        },
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": "project.database.primary",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "tool",
          "agent": "synthetic-dataset",
          "session": "holdout-v2-environments",
          "interaction": "synthetic-interaction",
          "evidence": "Lyra production uses MariaDB; Lyra development uses DuckDB."
        },
        "evidence_refs": [
          {
            "event_id": "a58dac9f-50fa-5038-b9c5-81e3e969baee",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "a50b8c16-5a7d-56d9-a519-0b03a4198a0a",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      },
      {
        "schema_version": 1,
        "candidate_id": "31aa338c-7a38-5020-9119-37f8eb13ed1b",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-environments",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```

## holdout-v2-offline-choice

```json
{
  "event": {
    "scope": "project",
    "project_id": "lyra",
    "schema_version": 1,
    "event_id": "9f86be02-1f76-5161-b3bf-28ff6d0c098e",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-offline-choice",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "For Lyra, use DuckDB only in offline mode. This choice does not apply online."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-v2-offline-choice-1",
      "content": "Lyra uses DuckDB only offline.",
      "type": "DECISION",
      "conditions": {
        "mode": "offline"
      },
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "user",
      "source_excerpt": "For Lyra, use DuckDB only in offline mode. This choice does not apply online.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-offline-choice",
    "proposals": [
      {
        "scope": "project",
        "project_id": "lyra",
        "schema_version": 1,
        "candidate_id": "21f5f9fa-f39b-5d2c-ac71-ddbae016367d",
        "event_id": "9f86be02-1f76-5161-b3bf-28ff6d0c098e",
        "type": "DECISION",
        "content": "Use DuckDB only in offline mode for Lyra; this choice does not apply online.",
        "conditions": {
          "mode": "offline"
        },
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": "project.database.primary",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "holdout-v2-offline-choice",
          "interaction": "synthetic-interaction",
          "evidence": "For Lyra, use DuckDB only in offline mode. This choice does not apply online."
        },
        "evidence_refs": [
          {
            "event_id": "9f86be02-1f76-5161-b3bf-28ff6d0c098e",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "21f5f9fa-f39b-5d2c-ac71-ddbae016367d",
        "outcome": "ADMIT",
        "reason_codes": [
          "EXPLICIT_DECISION",
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-offline-choice",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```

## holdout-v2-adopted-cache

```json
{
  "event": {
    "scope": "project",
    "project_id": "lyra",
    "schema_version": 1,
    "event_id": "da39c0e2-7155-5220-a9fe-20d4265c3bc7",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-adopted-cache",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Lyra: we choose Memcached as the cache. This is an agreed decision."
      },
      {
        "message_id": "m2",
        "role": "assistant",
        "content": "I guess Lyra also uses MongoDB for everything. Save that guess."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-v2-adopted-cache-1",
      "content": "Lyra uses Memcached as its cache.",
      "type": "DECISION",
      "conditions": {},
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.cache.primary",
      "source_kind": "user",
      "source_excerpt": "Lyra: we choose Memcached as the cache. This is an agreed decision.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-adopted-cache",
    "proposals": [
      {
        "scope": "project",
        "project_id": "lyra",
        "schema_version": 1,
        "candidate_id": "4c80b8e6-b9a4-584b-bc6b-3e700a30e09c",
        "event_id": "da39c0e2-7155-5220-a9fe-20d4265c3bc7",
        "type": "DECISION",
        "content": "Lyra chooses Memcached as the cache.",
        "conditions": {},
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": "project.cache.primary",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "holdout-v2-adopted-cache",
          "interaction": "synthetic-interaction",
          "evidence": "Lyra: we choose Memcached as the cache. This is an agreed decision."
        },
        "evidence_refs": [
          {
            "event_id": "da39c0e2-7155-5220-a9fe-20d4265c3bc7",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "4c80b8e6-b9a4-584b-bc6b-3e700a30e09c",
        "outcome": "ADMIT",
        "reason_codes": [
          "EXPLICIT_DECISION",
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-adopted-cache",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```

## holdout-v2-personal-preference

```json
{
  "event": {
    "scope": "developer",
    "project_id": null,
    "schema_version": 1,
    "event_id": "c85134f1-411c-50df-a751-120db60c2ebe",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-personal-preference",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "I prefer review comments that show the failing command and its expected result."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-v2-personal-preference-1",
      "content": "The developer prefers review comments showing the failing command and expected result.",
      "type": "PREFERENCE",
      "conditions": {},
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": null,
      "source_kind": "user",
      "source_excerpt": "I prefer review comments that show the failing command and its expected result.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-personal-preference",
    "proposals": [
      {
        "scope": "developer",
        "project_id": null,
        "schema_version": 1,
        "candidate_id": "70398fdc-d6ed-5453-a687-884b902e4391",
        "event_id": "c85134f1-411c-50df-a751-120db60c2ebe",
        "type": "PREFERENCE",
        "content": "User prefers review comments that show the failing command and its expected result.",
        "conditions": {},
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 0.9,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "holdout-v2-personal-preference",
          "interaction": "synthetic-interaction",
          "evidence": "I prefer review comments that show the failing command and its expected result."
        },
        "evidence_refs": [
          {
            "event_id": "c85134f1-411c-50df-a751-120db60c2ebe",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "70398fdc-d6ed-5453-a687-884b902e4391",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-personal-preference",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```

## holdout-v2-current-status

```json
{
  "event": {
    "scope": "project",
    "project_id": "lyra",
    "schema_version": 1,
    "event_id": "48022f30-a742-5373-80c2-ee5cac2d8d91",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-current-status",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Lyra release branch is currently frozen for feature changes."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-v2-current-status-1",
      "content": "Lyra release branch is frozen for feature changes.",
      "type": "STATE",
      "conditions": {},
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": null,
      "source_kind": "user",
      "source_excerpt": "Lyra release branch is currently frozen for feature changes.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-current-status",
    "proposals": [
      {
        "scope": "project",
        "project_id": "lyra",
        "schema_version": 1,
        "candidate_id": "4831c876-0398-5c09-8a47-2414ca6676b9",
        "event_id": "48022f30-a742-5373-80c2-ee5cac2d8d91",
        "type": "STATE",
        "content": "Lyra release branch is currently frozen for feature changes.",
        "conditions": {},
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": "project.release.branch_status",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "holdout-v2-current-status",
          "interaction": "synthetic-interaction",
          "evidence": "Lyra release branch is currently frozen for feature changes."
        },
        "evidence_refs": [
          {
            "event_id": "48022f30-a742-5373-80c2-ee5cac2d8d91",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "4831c876-0398-5c09-8a47-2414ca6676b9",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-current-status",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```

## holdout-v2-dated-event

```json
{
  "event": {
    "scope": "project",
    "project_id": "lyra",
    "schema_version": 1,
    "event_id": "f733862c-e602-516f-9920-cd2c9814b14d",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-dated-event",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "tool",
        "content": "Lyra backup restore finished successfully at 2026-10-11T07:20:00Z."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-v2-dated-event-1",
      "content": "Lyra backup restore completed at 2026-10-11T07:20:00Z.",
      "type": "EVENT",
      "conditions": {},
      "valid_from": "2026-10-11T07:20:00Z",
      "claim_key": null,
      "source_kind": "tool",
      "source_excerpt": "Lyra backup restore finished successfully at 2026-10-11T07:20:00Z.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-dated-event",
    "proposals": [
      {
        "scope": "project",
        "project_id": "lyra",
        "schema_version": 1,
        "candidate_id": "bc1f004a-f86c-5ef4-9cb9-063c22bde396",
        "event_id": "f733862c-e602-516f-9920-cd2c9814b14d",
        "type": "EVENT",
        "content": "Lyra backup restore finished successfully at 2026-10-11T07:20:00Z.",
        "conditions": {},
        "valid_from": "2026-10-11T07:20:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "tool",
          "agent": "synthetic-dataset",
          "session": "holdout-v2-dated-event",
          "interaction": "synthetic-interaction",
          "evidence": "Lyra backup restore finished successfully at 2026-10-11T07:20:00Z."
        },
        "evidence_refs": [
          {
            "event_id": "f733862c-e602-516f-9920-cd2c9814b14d",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "bc1f004a-f86c-5ef4-9cb9-063c22bde396",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-dated-event",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```

## holdout-v2-rare-lesson

```json
{
  "event": {
    "scope": "project",
    "project_id": "lyra",
    "schema_version": 1,
    "event_id": "b3dd961c-832a-5e0f-b465-6eb9976d9a40",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-rare-lesson",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Lyra lesson: never remove audit.sql before retaining its 9-day backup, even during emergency rollback."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-v2-rare-lesson-1",
      "content": "Never remove audit.sql before retaining its 9-day backup, including emergency rollback.",
      "type": "LESSON",
      "conditions": {},
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": null,
      "source_kind": "user",
      "source_excerpt": "Lyra lesson: never remove audit.sql before retaining its 9-day backup, even during emergency rollback.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-rare-lesson",
    "proposals": [
      {
        "scope": "project",
        "project_id": "lyra",
        "schema_version": 1,
        "candidate_id": "308ccd4c-172b-5b4c-9f55-e99ecaedbb16",
        "event_id": "b3dd961c-832a-5e0f-b465-6eb9976d9a40",
        "type": "LESSON",
        "content": "Never remove audit.sql before retaining its 9‑day backup, even during emergency rollback.",
        "conditions": {},
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "holdout-v2-rare-lesson",
          "interaction": "synthetic-interaction",
          "evidence": "Lyra lesson: never remove audit.sql before retaining its 9-day backup, even during emergency rollback."
        },
        "evidence_refs": [
          {
            "event_id": "b3dd961c-832a-5e0f-b465-6eb9976d9a40",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "308ccd4c-172b-5b4c-9f55-e99ecaedbb16",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-rare-lesson",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```

## holdout-v2-duplicate

```json
{
  "event": {
    "scope": "project",
    "project_id": "lyra",
    "schema_version": 1,
    "event_id": "672751d3-7eda-59c9-af4a-a506d1f590fc",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-duplicate",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "For Lyra, use MariaDB as the primary database. We have already agreed this."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": [
      {
        "memory": {
          "id": "1a7a249a-3be9-5c3d-a523-28eebf33b60b",
          "scope": "project",
          "project_id": "lyra",
          "type": "DECISION",
          "conditions": {},
          "created_at": "2026-10-11T07:20:00Z",
          "current_version": 1,
          "version": {
            "id": "6c8f08a6-b33d-5349-9ca9-bf7682eab5bb",
            "number": 1,
            "content": "MariaDB is the primary store for Lyra.",
            "status": "ACTIVE",
            "valid_from": "2026-10-11T07:20:00Z",
            "valid_to": null,
            "recorded_at": "2026-10-11T07:20:00Z",
            "source": {
              "kind": "user",
              "agent": "synthetic-dataset",
              "session": "holdout-v2-duplicate",
              "interaction": "synthetic-interaction",
              "evidence": "For Lyra, use MariaDB as the primary database. We have already agreed this."
            }
          }
        },
        "claim_key": "project.database.primary",
        "confidence": 0.95,
        "decision_state": "clear"
      }
    ]
  },
  "design_labels_pending_review": [
    {
      "claim_id": "holdout-v2-duplicate-1",
      "content": "Lyra uses MariaDB as its primary database.",
      "type": "DECISION",
      "conditions": {},
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "user",
      "source_excerpt": "For Lyra, use MariaDB as the primary database. We have already agreed this.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "REJECT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-duplicate",
    "proposals": [
      {
        "scope": "project",
        "project_id": "lyra",
        "schema_version": 1,
        "candidate_id": "0defa6d1-bade-5e12-9ba6-e20cb9e89f33",
        "event_id": "672751d3-7eda-59c9-af4a-a506d1f590fc",
        "type": "DECISION",
        "content": "Use MariaDB as the primary database for Lyra.",
        "conditions": {},
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": "project.database.primary",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "holdout-v2-duplicate",
          "interaction": "synthetic-interaction",
          "evidence": "For Lyra, use MariaDB as the primary database. We have already agreed this."
        },
        "evidence_refs": [
          {
            "event_id": "672751d3-7eda-59c9-af4a-a506d1f590fc",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "0defa6d1-bade-5e12-9ba6-e20cb9e89f33",
        "outcome": "REJECT",
        "reason_codes": [
          "DUPLICATE"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-duplicate",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```

## holdout-v2-unknown-other-project

```json
{
  "event": {
    "scope": "project",
    "project_id": "lyra",
    "schema_version": 1,
    "event_id": "88693f4e-be0f-5565-9c32-24bc5d7c4deb",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-unknown-other-project",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "The unnamed repository discussed elsewhere uses Oracle. I cannot recall its name; it is not Lyra."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-unknown-other-project",
    "proposals": [],
    "decisions": [],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-unknown-other-project",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```

## holdout-v2-assistant-only

```json
{
  "event": {
    "scope": "project",
    "project_id": "lyra",
    "schema_version": 1,
    "event_id": "0bd56b57-e3e0-5d96-9f8c-e8fafc70d971",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-assistant-only",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "assistant",
        "content": "I think Lyra needs a new database, but nobody has agreed or supplied evidence."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-assistant-only",
    "proposals": [],
    "decisions": [],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-assistant-only",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```

## holdout-v2-undecided

```json
{
  "event": {
    "scope": "project",
    "project_id": "lyra",
    "schema_version": 1,
    "event_id": "0fdd2e41-4826-592b-9ba9-c5b2d67b7cd2",
    "agent": "synthetic-dataset",
    "session": "holdout-v2-undecided",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Lyra might migrate its cache someday; there is no chosen replacement or effective date."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": []
  },
  "design_labels_pending_review": [],
  "untrusted_model_prediction": {
    "case_id": "holdout-v2-undecided",
    "proposals": [],
    "decisions": [],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "holdout-v2-undecided",
    "category": "unknown_cases",
    "attempted_calls": null,
    "execution": "unknown"
  }
}
```
