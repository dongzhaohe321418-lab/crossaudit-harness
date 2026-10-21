# Audit rules

### CA-META-001
BLOCKER. Every increment declares metadata.yml and results.json.

### CA-DATA-001
BLOCKER. Every quantity carries a unit and a source.

### CA-DATA-002
BLOCKER. Prose agrees with the data and the declared method.

### CA-DATA-003
BLOCKER. Every source is a declared, committed input.

### CA-METH-002
BLOCKER. Unconverged numbers are not results.

### CA-NUM-002
BLOCKER. An annotated number resolves to the line that holds it.

### CA-PHYS-001
BLOCKER. Quantities obey the declared physical ranges.

### CA-REPRO-001
ADVISORY. Stochastic work declares command, environment and seed.

```crossaudit-ranges
[{"name": "n_points", "unit": "1", "min": 2}]
```
