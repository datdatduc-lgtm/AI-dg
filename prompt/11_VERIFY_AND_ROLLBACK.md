# P1 — VERIFY + ROLLBACK

Never finish at "geometry created".

Compare:
```text
Expected Model Spec
↔
Actual SketchUp Model
```

Verify:
- width/height/depth
- panel thickness
- hierarchy
- count
- materials
- tags
- placement
- naming

Structured deviations:
```json
{
  "status":"FAIL",
  "deviations":[
    {"field":"width_mm","expected":1200,"actual":1198}
  ]
}
```

Auto-fix only when deterministic and LOW/MEDIUM risk.

Ambiguous source errors go back to Review Queue.

Failed build must not leave half-built production state.

PASS requires runtime evidence for:
- correct verify
- intentional mismatch detection
- rollback
