> **WITHDRAWN INTERPRETATION.** Population I is NOT established to be "defects the specification determines". The six construction filters do not establish specification entailment: F6 was registered as recovering the first failing hidden input and is implemented as a truthiness check on `witness_input`, and F2 to F5 each accept cases their registered wording excludes (RESULTS-INJECT.md §5). Both headline figures -- 97.8% and 84.2% -- are withdrawn, and this study gives claim C4 no prospective test. The counts below are reproducible and are kept as descriptive observations about small injected edits; the population label is not.

<!-- TABLE primary -->

| population | n (problems) | union recall at K = 8 | 95% cluster CI |
|---|---:|---|---|
| I — injected edits accepted by the filters and both gates (**NOT established as specification-determined**) | 92 (54) | **90 of 92** | — |
| ceiling 1's stratum P — the natural residual | 110 (56) | **33 of 110** = 30.0% (Wilson [22.2, 39.1]) | [20.0, 40.7] |
| **difference (two-sample, not paired)** | | **+67.8 points** | **[+56.3, +78.9]** |

<!-- TABLE rejected -->

Amendment 6's gate-rejected arm: the six filters accepted these instances and a gate then refused them. Same auditor, same K. Round 2 of the review moved this table out of hand-written prose and into the records, where it can be regenerated. Every figure reproduces the hand-computed one exactly, at the registered seed 20260916. Round 2 of this report claimed the published cluster interval could not be reproduced because its seed was never recorded; that was wrong on both counts, and round 3 disproved it by reproducing the interval from the seed the registration names.

| population | n (problems) | union recall at K = 8 | 95% cluster CI |
|---|---:|---|---|
| gate-**rejected** sample | 40 (35 problems, 35 distinct programmes) | **31 of 40** = 77.5% (Wilson [62.5, 87.7]) | [62.2, 90.5] |

The instances the gate discarded are caught nearly as often as the ones it kept. **That is why Amendment 3's "the gate is conservative" is withdrawn**: the gate selects on detectability, so conditioning on it cannot be assumed to lower recall. This observation survives the withdrawal of both headline figures.

<!-- TABLE paired -->

Each injected instance against its own unmodified twin: same problem, same specification, same generator, same code but for the injected lines, same auditor, same K = 8 (Amendment 4).

| arm | flagged | 95% Wilson |
|---|---:|---|
| injected | 90 of 92 | [92.4, 99.4] |
| unmodified twin | 11 of 92 | [6.8, 20.2] |
| **difference (paired)** | **+85.9 points** | **cluster [+77.3, +93.3]** |

Discordant pairs: 79 where only the injected instance was flagged, 0 where only the twin was. Exact McNemar p = 3.31e-24; cluster sign-flip p = 5.00e-06. Every discordant pair points one way, so the percentile bootstrap's bound is an artefact and the Tango interval [+77.3, +91.6] is the one to read (ceiling 1 Amendment 5).

<!-- TABLE curve -->

| K | union recall on I |
|---:|---|
| 1 | 94.4% |
| 2 | 96.5% |
| 3 | 97.0% |
| 4 | 97.4% |
| 5 | 97.6% |
| 6 | 97.7% |
| 7 | 97.8% |
| 8 | 97.8% |

Last-step gain 0.00 points; the preregistered flattening bar (at most 1.0) is met, so the fitted asymptote 97.4% would be quotable on the flattening bar alone, but is NOT quotable: the bar speaks to the shape of the curve, not to what the population is.
Single reading, I against the natural residual: +78.9 points [+69.0, +87.8].

<!-- TABLE probe -->

| quantity | value |
|---|---|
| prober | `anthropic:claude-opus-4-8` — not the auditor, but **one of the two gate models**, so this probe is not independent of the gate |
| items | 92 injected, 92 natural |
| answered | 152; unparsed 32 |
| accuracy on the answered | **96.7%** (Wilson [92.5, 98.6]) |
| accuracy over all 184 items | between 79.9% and 97.3% |
| covers chance | **no** |
| injected called edited | 65 of 69 |
| natural called edited | 1 of 83 |

<!-- TABLE xtab -->

POST HOC: asked after the probe and the audit were both in hand.

| the probe called it | n | the auditor caught |
|---|---:|---:|
| it would not say | 23 | 23 |
| edited (artificial) | 65 | 63 |
| written in one pass (natural) | 4 | 4 |

The auditor's only misses were `b1:Mbpp/404`, `b2:Mbpp/404`, which the probe called edited and edited.

<!-- TABLE splits -->

| split | group | caught |
|---|---|---:|
| more than 2 changed lines | yes | 13 of 13 |
| | no | 77 of 79 |
| the changed line sits under a conditional | yes | 30 of 30 |
| | no | 60 of 62 |
