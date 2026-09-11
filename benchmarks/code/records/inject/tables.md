<!-- TABLE primary -->

| population | n (problems) | union recall at K = 8 | 95% cluster CI |
|---|---:|---|---|
| I — defects the specification determines, injected | 92 (54) | **90 of 92** | — |
| ceiling 1's stratum P — the natural residual | 110 (56) | **33 of 110** = 30.0% (Wilson [22.2, 39.1]) | [20.0, 40.7] |
| **difference (two-sample, not paired)** | | **+67.8 points** | **[+56.3, +78.9]** |

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

Last-step gain 0.00 points; the preregistered flattening bar (at most 1.0) is met, so the fitted asymptote 97.4% is quotable.
Single reading, I against the natural residual: +78.9 points [+69.0, +87.8].

<!-- TABLE probe -->

| quantity | value |
|---|---|
| prober | `anthropic:claude-opus-4-8` — not the auditor, not a gate |
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
