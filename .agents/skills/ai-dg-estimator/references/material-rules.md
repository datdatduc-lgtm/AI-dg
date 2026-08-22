# Material normalization rules

## Preserve source codes

Never replace a drawing material code with a guessed product. Keep the source code exactly as shown, then map it only when a verified legend or material library supplies the meaning.

Example:

```text
source_material_code: WD-03
material_code: MDF18-MR
```

Only set `material_code` when evidence supports the mapping.

## Thickness

Thickness belongs to the part record and should be stored in millimetres. Do not infer thickness from a material family name unless the verified library explicitly defines it.

## Sheet calculation

Sheet counts require known sheet dimensions. V0.1 calculates:

- net area from part dimensions;
- required area after waste factor;
- theoretical sheet count only when a matching library record contains sheet length and width.

Theoretical sheet count is not nesting optimization. Clearly label it as theoretical.

## Waste factor

Do not invent waste percentages. Use `waste_factor` from a verified material library or an explicit user/project setting. Default deterministic calculations use zero additional waste when none is supplied.

## Pricing

V0.1 material records may contain reference metadata, but the skill must not present a final quotation unless the user supplies a verified price source and a pricing workflow is executed.
