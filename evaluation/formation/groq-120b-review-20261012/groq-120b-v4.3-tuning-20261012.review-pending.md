# O3 independent review packet

Assigned reviewer: Pranit. Status: pending; no human judgements have been supplied.

Split: tuning; dataset SHA256: `01109c9356f27a2a6eb4316a5f6fd094c01a2edde635da564dad980e5475168a`.
Run SHA256: `8e6303d46cad4aab51a47a9560b41a0e416448e81f410b8004ce6c8180e6fcc1`; prompt: `formation-chat-v4.3-grounded-batch`.

Review source meaning, atomicity, type, qualifiers, time, units and admission context.
Confirm/reject each case's design labels, even when the model failed or returned nothing.
Fill JSON blanks yourself; do not ask the evaluated model to supply human labels.
Request a reviewed revision for wrong gold labels; never change them to fit output.
JSON is an attestation, not authentication of reviewer identity. Supply a review
URL/commit reference in review_evidence and confirm it through the team's review process.
Provider failures show availability; absent output does not prove correct empty output.

## tuning-v2-runtime-choice

```json
{
  "event": {
    "scope": "project",
    "project_id": "cedar",
    "schema_version": 1,
    "event_id": "5a712726-5af0-54c1-a80c-14b2a00fc17c",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-runtime-choice",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "For Cedar V2, pin the runtime to Python. This is our adopted choice for V2 only."
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
      "claim_id": "tuning-v2-runtime-choice-1",
      "content": "Cedar V2 uses Python.",
      "type": "DECISION",
      "conditions": {
        "version": "V2"
      },
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.runtime.python",
      "source_kind": "user",
      "source_excerpt": "For Cedar V2, pin the runtime to Python. This is our adopted choice for V2 only.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-v2-runtime-choice",
    "proposals": [
      {
        "scope": "project",
        "project_id": "cedar",
        "schema_version": 1,
        "candidate_id": "1766c837-0d51-5fd5-827a-b7461dfdc1fa",
        "event_id": "5a712726-5af0-54c1-a80c-14b2a00fc17c",
        "type": "DECISION",
        "content": "Pin the runtime to Python for Cedar V2",
        "conditions": {
          "version": "V2"
        },
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": "project.runtime.python",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "tuning-v2-runtime-choice",
          "interaction": "synthetic-interaction",
          "evidence": "For Cedar V2, pin the runtime to Python. This is our adopted choice for V2 only."
        },
        "evidence_refs": [
          {
            "event_id": "5a712726-5af0-54c1-a80c-14b2a00fc17c",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "1766c837-0d51-5fd5-827a-b7461dfdc1fa",
        "outcome": "ADMIT",
        "reason_codes": [
          "EXPLICIT_DECISION",
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 17969.00000000096,
    "input_tokens": 1630,
    "output_tokens": 386,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-runtime-choice",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## tuning-v2-environments

```json
{
  "event": {
    "scope": "project",
    "project_id": "cedar",
    "schema_version": 1,
    "event_id": "28bafbd1-6e1a-5b4f-9677-2df923a7b6f6",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-environments",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "tool",
        "content": "Cedar production uses PostgreSQL; Cedar development uses SQLite."
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
      "claim_id": "tuning-v2-environments-1",
      "content": "Cedar production uses PostgreSQL.",
      "type": "FACT",
      "conditions": {
        "environment": "production"
      },
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "tool",
      "source_excerpt": "Cedar production uses PostgreSQL; Cedar development uses SQLite.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    },
    {
      "claim_id": "tuning-v2-environments-2",
      "content": "Cedar development uses SQLite.",
      "type": "FACT",
      "conditions": {
        "environment": "development"
      },
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "tool",
      "source_excerpt": "Cedar production uses PostgreSQL; Cedar development uses SQLite.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-v2-environments",
    "proposals": [
      {
        "scope": "project",
        "project_id": "cedar",
        "schema_version": 1,
        "candidate_id": "1ac9794c-5001-55d0-9bb4-0cd266db0862",
        "event_id": "28bafbd1-6e1a-5b4f-9677-2df923a7b6f6",
        "type": "FACT",
        "content": "Cedar production uses PostgreSQL.",
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
          "session": "tuning-v2-environments",
          "interaction": "synthetic-interaction",
          "evidence": "Cedar production uses PostgreSQL; Cedar development uses SQLite."
        },
        "evidence_refs": [
          {
            "event_id": "28bafbd1-6e1a-5b4f-9677-2df923a7b6f6",
            "message_id": "m1"
          }
        ]
      },
      {
        "scope": "project",
        "project_id": "cedar",
        "schema_version": 1,
        "candidate_id": "b346a28c-9abf-5181-9304-606ac09566aa",
        "event_id": "28bafbd1-6e1a-5b4f-9677-2df923a7b6f6",
        "type": "FACT",
        "content": "Cedar development uses SQLite.",
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
          "session": "tuning-v2-environments",
          "interaction": "synthetic-interaction",
          "evidence": "Cedar production uses PostgreSQL; Cedar development uses SQLite."
        },
        "evidence_refs": [
          {
            "event_id": "28bafbd1-6e1a-5b4f-9677-2df923a7b6f6",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "1ac9794c-5001-55d0-9bb4-0cd266db0862",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      },
      {
        "schema_version": 1,
        "candidate_id": "b346a28c-9abf-5181-9304-606ac09566aa",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 23984.00000000038,
    "input_tokens": 1674,
    "output_tokens": 517,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-environments",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## tuning-v2-offline-choice

```json
{
  "event": {
    "scope": "project",
    "project_id": "cedar",
    "schema_version": 1,
    "event_id": "e48c1751-d350-5162-8a6f-a709cb3898f5",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-offline-choice",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "For Cedar, use SQLite only in offline mode. This choice does not apply online."
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
      "claim_id": "tuning-v2-offline-choice-1",
      "content": "Cedar uses SQLite only offline.",
      "type": "DECISION",
      "conditions": {
        "mode": "offline"
      },
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "user",
      "source_excerpt": "For Cedar, use SQLite only in offline mode. This choice does not apply online.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-v2-offline-choice",
    "proposals": [
      {
        "scope": "project",
        "project_id": "cedar",
        "schema_version": 1,
        "candidate_id": "bd632cff-b6ba-5062-ae8d-99b78fb2ef2c",
        "event_id": "e48c1751-d350-5162-8a6f-a709cb3898f5",
        "type": "DECISION",
        "content": "Use SQLite for Cedar when operating in offline mode.",
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
          "session": "tuning-v2-offline-choice",
          "interaction": "synthetic-interaction",
          "evidence": "For Cedar, use SQLite only in offline mode. This choice does not apply online."
        },
        "evidence_refs": [
          {
            "event_id": "e48c1751-d350-5162-8a6f-a709cb3898f5",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "bd632cff-b6ba-5062-ae8d-99b78fb2ef2c",
        "outcome": "ADMIT",
        "reason_codes": [
          "EXPLICIT_DECISION",
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 23937.999999998283,
    "input_tokens": 1617,
    "output_tokens": 405,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-offline-choice",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## tuning-v2-adopted-cache

```json
{
  "event": {
    "scope": "project",
    "project_id": "cedar",
    "schema_version": 1,
    "event_id": "6e5f6273-6a5c-57df-9f7c-6620ae41b97a",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-adopted-cache",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Cedar: we choose Redis as the cache. This is an agreed decision."
      },
      {
        "message_id": "m2",
        "role": "assistant",
        "content": "I guess Cedar also uses MongoDB for everything. Save that guess."
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
      "claim_id": "tuning-v2-adopted-cache-1",
      "content": "Cedar uses Redis as its cache.",
      "type": "DECISION",
      "conditions": {},
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.cache.primary",
      "source_kind": "user",
      "source_excerpt": "Cedar: we choose Redis as the cache. This is an agreed decision.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-v2-adopted-cache",
    "proposals": [
      {
        "scope": "project",
        "project_id": "cedar",
        "schema_version": 1,
        "candidate_id": "e8e1a134-8a21-56f7-b4a3-612d318e6b32",
        "event_id": "6e5f6273-6a5c-57df-9f7c-6620ae41b97a",
        "type": "DECISION",
        "content": "Cedar chooses Redis as the cache.",
        "conditions": {},
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": "project.cache.primary",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "tuning-v2-adopted-cache",
          "interaction": "synthetic-interaction",
          "evidence": "Cedar: we choose Redis as the cache. This is an agreed decision."
        },
        "evidence_refs": [
          {
            "event_id": "6e5f6273-6a5c-57df-9f7c-6620ae41b97a",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "e8e1a134-8a21-56f7-b4a3-612d318e6b32",
        "outcome": "ADMIT",
        "reason_codes": [
          "EXPLICIT_DECISION",
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 22093.000000000757,
    "input_tokens": 1673,
    "output_tokens": 328,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-adopted-cache",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## tuning-v2-personal-preference

```json
{
  "event": {
    "scope": "developer",
    "project_id": null,
    "schema_version": 1,
    "event_id": "6cf71143-2246-5521-a189-9ccd3a7676e1",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-personal-preference",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "I prefer short review comments that include one concrete example; this is my personal preference."
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
      "claim_id": "tuning-v2-personal-preference-1",
      "content": "The developer prefers short review comments with one concrete example.",
      "type": "PREFERENCE",
      "conditions": {},
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": null,
      "source_kind": "user",
      "source_excerpt": "I prefer short review comments that include one concrete example; this is my personal preference.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-v2-personal-preference",
    "proposals": [
      {
        "scope": "developer",
        "project_id": null,
        "schema_version": 1,
        "candidate_id": "7e7fce4b-d0fc-559f-9c31-97bae15b9216",
        "event_id": "6cf71143-2246-5521-a189-9ccd3a7676e1",
        "type": "PREFERENCE",
        "content": "User prefers short review comments that include one concrete example.",
        "conditions": {},
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": "project.review.comment_style",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "tuning-v2-personal-preference",
          "interaction": "synthetic-interaction",
          "evidence": "I prefer short review comments that include one concrete example; this is my personal preference."
        },
        "evidence_refs": [
          {
            "event_id": "6cf71143-2246-5521-a189-9ccd3a7676e1",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "7e7fce4b-d0fc-559f-9c31-97bae15b9216",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 21671.99999999866,
    "input_tokens": 1609,
    "output_tokens": 272,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-personal-preference",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## tuning-v2-current-status

```json
{
  "event": {
    "scope": "project",
    "project_id": "cedar",
    "schema_version": 1,
    "event_id": "f7ec0ffd-b916-5f0d-95ed-38e4480dc638",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-current-status",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Cedar release branch is currently frozen for feature changes."
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
      "claim_id": "tuning-v2-current-status-1",
      "content": "Cedar release branch is frozen for feature changes.",
      "type": "STATE",
      "conditions": {},
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": null,
      "source_kind": "user",
      "source_excerpt": "Cedar release branch is currently frozen for feature changes.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-v2-current-status",
    "proposals": [
      {
        "scope": "project",
        "project_id": "cedar",
        "schema_version": 1,
        "candidate_id": "effb68f7-afd4-59c7-bbad-711c74e97641",
        "event_id": "f7ec0ffd-b916-5f0d-95ed-38e4480dc638",
        "type": "FACT",
        "content": "Cedar release branch is currently frozen for feature changes.",
        "conditions": {},
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "tuning-v2-current-status",
          "interaction": "synthetic-interaction",
          "evidence": "Cedar release branch is currently frozen for feature changes."
        },
        "evidence_refs": [
          {
            "event_id": "f7ec0ffd-b916-5f0d-95ed-38e4480dc638",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "effb68f7-afd4-59c7-bbad-711c74e97641",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 21015.99999999962,
    "input_tokens": 1594,
    "output_tokens": 285,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-current-status",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## tuning-v2-dated-event

```json
{
  "event": {
    "scope": "project",
    "project_id": "cedar",
    "schema_version": 1,
    "event_id": "9a1458c9-fcff-5669-ab91-bb7af4e7bf4e",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-dated-event",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "tool",
        "content": "Cedar backup restore finished successfully at 2026-10-11T07:20:00Z."
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
      "claim_id": "tuning-v2-dated-event-1",
      "content": "Cedar backup restore completed at 2026-10-11T07:20:00Z.",
      "type": "EVENT",
      "conditions": {},
      "valid_from": "2026-10-11T07:20:00Z",
      "claim_key": null,
      "source_kind": "tool",
      "source_excerpt": "Cedar backup restore finished successfully at 2026-10-11T07:20:00Z.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-v2-dated-event",
    "proposals": [
      {
        "scope": "project",
        "project_id": "cedar",
        "schema_version": 1,
        "candidate_id": "88a5e6c7-2636-5a19-9b68-0fd5dfc339ba",
        "event_id": "9a1458c9-fcff-5669-ab91-bb7af4e7bf4e",
        "type": "FACT",
        "content": "Cedar backup restore finished successfully at 2026-10-11T07:20:00Z.",
        "conditions": {},
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 0.9,
        "source": {
          "kind": "tool",
          "agent": "synthetic-dataset",
          "session": "tuning-v2-dated-event",
          "interaction": "synthetic-interaction",
          "evidence": "Cedar backup restore finished successfully at 2026-10-11T07:20:00Z."
        },
        "evidence_refs": [
          {
            "event_id": "9a1458c9-fcff-5669-ab91-bb7af4e7bf4e",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "88a5e6c7-2636-5a19-9b68-0fd5dfc339ba",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 21109.00000000038,
    "input_tokens": 1638,
    "output_tokens": 317,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-dated-event",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## tuning-v2-rare-lesson

```json
{
  "event": {
    "scope": "project",
    "project_id": "cedar",
    "schema_version": 1,
    "event_id": "07563c40-aa6d-5e51-9a67-14d27b296858",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-rare-lesson",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Cedar lesson: never remove audit.sql before retaining its 9-day backup, even during emergency rollback."
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
      "claim_id": "tuning-v2-rare-lesson-1",
      "content": "Never remove audit.sql before retaining its 9-day backup, including emergency rollback.",
      "type": "LESSON",
      "conditions": {},
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": null,
      "source_kind": "user",
      "source_excerpt": "Cedar lesson: never remove audit.sql before retaining its 9-day backup, even during emergency rollback.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "ADMIT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-v2-rare-lesson",
    "proposals": [
      {
        "scope": "project",
        "project_id": "cedar",
        "schema_version": 1,
        "candidate_id": "c9445279-dc89-5ddf-b180-a83fefc6c3d6",
        "event_id": "07563c40-aa6d-5e51-9a67-14d27b296858",
        "type": "LESSON",
        "content": "Cedar lesson: never remove audit.sql before retaining its 9-day backup, even during emergency rollback.",
        "conditions": {},
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": null,
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "tuning-v2-rare-lesson",
          "interaction": "synthetic-interaction",
          "evidence": "Cedar lesson: never remove audit.sql before retaining its 9-day backup, even during emergency rollback."
        },
        "evidence_refs": [
          {
            "event_id": "07563c40-aa6d-5e51-9a67-14d27b296858",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "c9445279-dc89-5ddf-b180-a83fefc6c3d6",
        "outcome": "ADMIT",
        "reason_codes": [
          "REUSABLE_PROJECT_CONTEXT"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 21813.00000000192,
    "input_tokens": 1635,
    "output_tokens": 302,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-rare-lesson",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## tuning-v2-duplicate

```json
{
  "event": {
    "scope": "project",
    "project_id": "cedar",
    "schema_version": 1,
    "event_id": "133a7c1d-84e7-5cc1-a997-83b0148b2463",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-duplicate",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "For Cedar, use PostgreSQL as the primary database. We have already agreed this."
      }
    ]
  },
  "comparison_context": {
    "schema_version": 1,
    "checked_at": "2026-10-12T09:00:00Z",
    "records": [
      {
        "memory": {
          "id": "0301cee4-187e-537e-883f-7b6b7c9f0d44",
          "scope": "project",
          "project_id": "cedar",
          "type": "DECISION",
          "conditions": {},
          "created_at": "2026-10-11T07:20:00Z",
          "current_version": 1,
          "version": {
            "id": "29d0cb4b-8328-5961-ad3f-ea24fe3e6ae8",
            "number": 1,
            "content": "PostgreSQL is the primary store for Cedar.",
            "status": "ACTIVE",
            "valid_from": "2026-10-11T07:20:00Z",
            "valid_to": null,
            "recorded_at": "2026-10-11T07:20:00Z",
            "source": {
              "kind": "user",
              "agent": "synthetic-dataset",
              "session": "tuning-v2-duplicate",
              "interaction": "synthetic-interaction",
              "evidence": "For Cedar, use PostgreSQL as the primary database. We have already agreed this."
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
      "claim_id": "tuning-v2-duplicate-1",
      "content": "Cedar uses PostgreSQL as its primary database.",
      "type": "DECISION",
      "conditions": {},
      "valid_from": "2026-10-12T08:00:00Z",
      "claim_key": "project.database.primary",
      "source_kind": "user",
      "source_excerpt": "For Cedar, use PostgreSQL as the primary database. We have already agreed this.",
      "message_ids": [
        "m1"
      ],
      "expected_admission": "REJECT",
      "rationale": "Proposed design label: the cited synthetic source establishes the claim, qualifiers, type and time. Independent review is pending."
    }
  ],
  "untrusted_model_prediction": {
    "case_id": "tuning-v2-duplicate",
    "proposals": [
      {
        "scope": "project",
        "project_id": "cedar",
        "schema_version": 1,
        "candidate_id": "f2a4f8d8-585f-50d0-bc1e-c99222fb23be",
        "event_id": "133a7c1d-84e7-5cc1-a997-83b0148b2463",
        "type": "DECISION",
        "content": "Use PostgreSQL as the primary database for Cedar.",
        "conditions": {},
        "valid_from": "2026-10-12T08:00:00Z",
        "claim_key": "project.database.primary",
        "confidence": 1.0,
        "usefulness": 1.0,
        "source": {
          "kind": "user",
          "agent": "synthetic-dataset",
          "session": "tuning-v2-duplicate",
          "interaction": "synthetic-interaction",
          "evidence": "For Cedar, use PostgreSQL as the primary database. We have already agreed this."
        },
        "evidence_refs": [
          {
            "event_id": "133a7c1d-84e7-5cc1-a997-83b0148b2463",
            "message_id": "m1"
          }
        ]
      }
    ],
    "decisions": [
      {
        "schema_version": 1,
        "candidate_id": "f2a4f8d8-585f-50d0-bc1e-c99222fb23be",
        "outcome": "REJECT",
        "reason_codes": [
          "DUPLICATE"
        ]
      }
    ],
    "error_code": null,
    "latency_ms": 21389.999999999418,
    "input_tokens": 1612,
    "output_tokens": 338,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-duplicate",
    "category": "completed_network_cases",
    "attempted_calls": 2,
    "execution": "attempted"
  }
}
```

## tuning-v2-unknown-other-project

```json
{
  "event": {
    "scope": "project",
    "project_id": "cedar",
    "schema_version": 1,
    "event_id": "c5e33139-a035-59e0-815f-f48b57c9d770",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-unknown-other-project",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "The unnamed repository discussed elsewhere uses Oracle. I cannot recall its name; it is not Cedar."
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
    "case_id": "tuning-v2-unknown-other-project",
    "proposals": [],
    "decisions": [],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-unknown-other-project",
    "category": "local_only_cases",
    "attempted_calls": 0,
    "execution": "scope_abstention"
  }
}
```

## tuning-v2-assistant-only

```json
{
  "event": {
    "scope": "project",
    "project_id": "cedar",
    "schema_version": 1,
    "event_id": "46ab6d90-bca4-5023-b68a-c7feb920e34e",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-assistant-only",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "assistant",
        "content": "I think Cedar needs a new database, but nobody has agreed or supplied evidence."
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
    "case_id": "tuning-v2-assistant-only",
    "proposals": [],
    "decisions": [],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-assistant-only",
    "category": "local_only_cases",
    "attempted_calls": 0,
    "execution": "local_only"
  }
}
```

## tuning-v2-undecided

```json
{
  "event": {
    "scope": "project",
    "project_id": "cedar",
    "schema_version": 1,
    "event_id": "d9850976-850d-50a0-a4a0-f5c1b086fd8f",
    "agent": "synthetic-dataset",
    "session": "tuning-v2-undecided",
    "interaction": "synthetic-interaction",
    "occurred_at": "2026-10-12T08:00:00Z",
    "capture_method": "manual_import",
    "messages": [
      {
        "message_id": "m1",
        "role": "user",
        "content": "Cedar might migrate its cache someday; there is no chosen replacement or effective date."
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
    "case_id": "tuning-v2-undecided",
    "proposals": [],
    "decisions": [],
    "error_code": null,
    "latency_ms": null,
    "input_tokens": null,
    "output_tokens": null,
    "cost": null
  },
  "saved_execution": {
    "case_id": "tuning-v2-undecided",
    "category": "local_only_cases",
    "attempted_calls": 0,
    "execution": "uncertain_abstention"
  }
}
```
