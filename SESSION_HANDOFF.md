# LE-GRA Research Session Handoff

Last updated: 2026-08-05

This document is the continuity note for resuming the LE-GRA discussion in a
new Codex task or on another computer. After pulling the repository, ask Codex
to read this file together with `medium_matrix_results/*.csv` before proposing
the next experiment.

## Research Goal

The project studies grouping and resource allocation for vehicular 5G MBS.
The current prototype, LE-GRA (Learning-based Embedding Grouping and Resource
Allocation), learns a user embedding from channel-history and resource-cost
features, applies k-means to the embedding, and uses an exact DP backend to
select group video qualities under an RB budget.

The immediate research question is not whether more methods can be added. It
is whether resource-cost features and learned embeddings provide a stable
advantage over CQI k-means, particularly under channel ambiguity and resource
pressure.

## Current Comparison Methods

1. No grouping: all users belong to one MBS group.
2. CQI k-means: k-means on current CQI.
3. Resource-cost k-means: k-means on per-quality RB cost vectors.
4. Offline teacher: users are sorted by resource cost; contiguous partition
   boundaries up to `Kmax` are searched and evaluated by exact DP.
5. LE-GRA MVP: NumPy MLP embedding, k-means, then the same DP evaluator.

`Multi-feature k-means` exists in the code but is not yet included in the
standard experiment matrix. Adding it is a high-priority next step because it
separates the value of extra input features from the value of learned
embeddings.

## Implemented During This Session

### Reproducible resource pressure

The standard experiment matrix now uses fixed RB-budget ratios:

- `light`: 0.50 of configured RBs,
- `medium`: 0.25,
- `heavy`: 0.10.

This replaced the old random 0.45-0.85 RB availability in standard experiments.
Single runs can use `--rb-budget-ratio`.

### Evaluation metrics

The evaluator and CSV files now report:

- `utility`: normalized log-bitrate utility minus switching and unserved
  penalties;
- `adr_kbps`: mean delivered user bitrate;
- `used_spectral_efficiency`: total successfully delivered user bitrate divided
  by the bandwidth of RBs actually used;
- `system_spectral_efficiency`: the same delivered bitrate divided by all
  currently available RB bandwidth; use this as the primary SE metric for
  comparisons within a fixed load level;
- `served_ratio` and `unserved_ratio`;
- `average_quality`: mean assigned quality index among served users (0-5);
- RB utilization, average switching, Jain fairness, and group count.

Do not compare the absolute value of `system_spectral_efficiency` across load
levels without qualification because its denominator changes with available
bandwidth. Compare methods within the same scenario and load.

### Progress reporting

`run_standard_matrix.py` now prints the current matrix job, teacher-label
progress, elapsed time, training epoch/loss, and evaluation method with
immediate flushing. Use `python -u` in PowerShell for unbuffered output.

### Feature ablation modes

- `history_only`: CQI history only;
- `history_cost`: CQI history plus resource-cost vector;
- `full`: CQI history, RB statistics, mobility, and resource-cost vector.

## Latest Medium Experiment

Command used:

```powershell
python -u .\run_standard_matrix.py `
  --train-scenarios 40 `
  --test-scenarios 20 `
  --epochs 5 `
  --scenario-modes aligned ambiguous `
  --load-levels light medium heavy `
  --kmax-values 3 `
  --seeds 9 17 23 `
  --feature-modes history_only history_cost full `
  --ablation-kmax 3 `
  --out-dir medium_matrix_results
```

Raw results:

- `medium_matrix_results/main_comparison_matrix.csv`
- `medium_matrix_results/feature_ablation.csv`

### Main conclusions

LE-GRA utility improvement over No grouping:

| Scenario | Light | Medium | Heavy |
|---|---:|---:|---:|
| Aligned | +7.6% | +13.7% | +12.1% |
| Ambiguous | +7.1% | +14.0% | +16.8% |

However, LE-GRA has not yet demonstrated a stable advantage over CQI k-means:

| Scenario | Light | Medium | Heavy |
|---|---:|---:|---:|
| Aligned | -1.30% | -2.19% | -0.95% |
| Ambiguous | +0.05% | -0.59% | -1.03% |

Across individual seeds, LE-GRA beat CQI k-means in 0/9 aligned settings and
4/9 ambiguous settings. Differences were generally small, but the current
evidence does not support claiming that the learned embedding is superior.

The offline teacher remained consistently best, with a utility gap over LE-GRA
of roughly 0.017-0.034 in aligned cases and 0.018-0.026 in ambiguous cases.
There is therefore useful teacher structure that the present student model has
not fully learned.

### Strongest current result: resource-cost features

`history_cost` beat `history_only` in 17 of 18 scenario/load/seed comparisons.
Mean ablation utilities were:

| Scenario/load | History only | History + cost | Full |
|---|---:|---:|---:|
| Aligned/light | 0.8077 | **0.8283** | 0.8267 |
| Aligned/medium | 0.7610 | 0.7823 | **0.7827** |
| Aligned/heavy | 0.5770 | **0.5895** | 0.5883 |
| Ambiguous/light | 0.7935 | **0.8110** | 0.8090 |
| Ambiguous/medium | 0.7497 | **0.7615** | 0.7609 |
| Ambiguous/heavy | 0.5602 | 0.5726 | **0.5740** |

The full feature set beat `history_cost` in only 5/18 individual comparisons.
The current evidence therefore favors `history_cost` as the primary compact
LE-GRA input and `full` as an ablation, not as an assumed superior default.

## Interpretation and Important Caveats

- The new pressure levels work. Quality falls substantially under heavy load;
  served ratio often remains near one because the optimizer can lower quality
  instead of dropping users.
- Used-bandwidth SE naturally favors large multicast groups because one
  transmission serves many users. This is expected and is why system SE,
  utility, quality, and served ratio must be reported together.
- The teacher optimizes QoE utility, not spectral efficiency directly. A method
  can therefore have the highest utility without the highest used-bandwidth SE.
- Current results establish the value of resource-cost features more strongly
  than the value of learned embeddings.
- The NumPy MLP uses a simplified contrastive-learning implementation and an
  approximate gradient through embedding normalization. This may be limiting
  teacher imitation.

## Recommended Next Steps

Do not immediately expand to `Kmax=5` or a much larger experiment matrix. The
next bottleneck is model diagnosis rather than more runs.

1. Make `history_cost` the main LE-GRA feature mode while retaining full-feature
   ablation results.
2. Add `Multi-feature k-means` to `run_standard_matrix.py` as a standard sanity
   baseline.
3. Add teacher-imitation diagnostics on held-out scenarios, preferably
   pairwise same-group accuracy plus ARI or NMI after handling cluster-label
   permutation.
4. Compare raw feature k-means against learned embedding k-means. This answers
   whether the model contributes beyond resource-cost engineering.
5. Inspect and improve the learner if agreement is weak. Likely options are a
   correct normalization gradient or migration to PyTorch with a standard
   contrastive/triplet loss, validation split, batching, and checkpointing.
6. Only after the learner is credible, test `Kmax=4/5`, more seeds, and larger
   train/test sets.

## Suggested Prompt on the Next Computer

```text
Please read SESSION_HANDOFF.md and the two CSV files under
medium_matrix_results. Continue the LE-GRA research from the recommended next
steps. First inspect the current git status and code. Do not rerun a large
matrix yet; begin by adding the multi-feature k-means baseline and
teacher-imitation diagnostics, then run a small validation experiment.
```

## Repository State at Handoff

The code changes implementing progress output, load levels, dual SE metrics,
service/quality metrics, and this handoff are intended to be committed together
with the medium experiment CSV files. Older local smoke-test directories are
not part of the research evidence and should not be required on another
computer.
