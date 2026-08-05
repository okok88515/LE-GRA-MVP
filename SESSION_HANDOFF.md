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
4. Multi-feature k-means: k-means directly on normalized hand-crafted features.
5. Offline teacher: users are sorted by resource cost; contiguous partition
   boundaries up to `Kmax` are searched and evaluated by exact DP.
6. LE-GRA MVP: NumPy MLP embedding, k-means, then the same DP evaluator.

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

The standard matrix now uses `history_cost` as the main LE-GRA training mode.
`full` remains in the ablation matrix rather than being assumed to be better.

### Teacher-imitation diagnostics

`run_standard_matrix.py` now writes `teacher_imitation_diagnostics.csv` with:

- `pairwise_accuracy`: same/different-group accuracy against teacher groups;
- `ari`: adjusted Rand index;
- `nmi`: normalized mutual information.

These diagnostics are computed on held-out test scenarios for:

- `Multi-feature k-means`
- `LE-GRA MVP`

### Learner update before the latest rerun

After the `v2` medium run, the NumPy MLP was updated to backpropagate through
embedding L2 normalization with the correct analytic gradient instead of the
earlier approximation. This is a small but meaningful learner-side fix. A tiny
smoke test (`small_validation_results_after_grad_fix`) showed improved utility
for LE-GRA in one ambiguous/medium validation slice, but teacher-imitation
metrics did not yet improve consistently. Treat this as a correctness-oriented
learner fix, not as evidence that the learner bottleneck is solved.

## Latest Medium Experiment

Command used:

```powershell
.\run_standard_matrix.cmd `
  --train-scenarios 40 `
  --test-scenarios 20 `
  --epochs 5 `
  --scenario-modes aligned ambiguous `
  --load-levels light medium heavy `
  --kmax-values 3 `
  --seeds 9 17 23 `
  --feature-modes history_only history_cost full `
  --ablation-kmax 3 `
  --out-dir medium_matrix_results_v2_after_grad_fix
```

Raw results:

- `medium_matrix_results_v2_after_grad_fix/main_comparison_matrix.csv`
- `medium_matrix_results_v2_after_grad_fix/feature_ablation.csv`
- `medium_matrix_results_v2_after_grad_fix/teacher_imitation_diagnostics.csv`

### Main conclusions

The corrected normalization gradient materially improved LE-GRA. In the main
utility comparison, LE-GRA now beats CQI k-means, resource-cost k-means, and
multi-feature k-means in:

- `aligned/light`
- `aligned/medium`

Mean utility by scenario/load:

| Scenario/load | CQI | Resource-cost | Multi-feature | Teacher | LE-GRA |
|---|---:|---:|---:|---:|---:|
| aligned/light | 0.8337 | 0.8300 | 0.8349 | **0.8421** | **0.8357** |
| aligned/medium | 0.7905 | 0.7855 | 0.7928 | **0.8059** | **0.7950** |
| aligned/heavy | **0.5928** | 0.5914 | 0.5914 | **0.6211** | 0.5901 |
| ambiguous/light | 0.8089 | **0.8183** | 0.8120 | **0.8280** | 0.8126 |
| ambiguous/medium | **0.7704** | **0.7716** | 0.7700 | **0.7872** | 0.7698 |
| ambiguous/heavy | **0.5793** | 0.5639 | 0.5747 | **0.5964** | 0.5750 |

Across the 18 scenario/load/seed slices, LE-GRA beat:

- `CQI k-means` in `10/18`
- `Multi-feature k-means` in `11/18`
- `Resource-cost k-means` in `13/18`
- `Offline teacher` in `0/18`

This is a meaningful step up from the earlier `v2` conclusion. However, the
result is still not strong enough to claim a stable learned-embedding win in
the most important ambiguous settings or under heavy load. The teacher remains
the clear upper bound.

### Strongest current result: resource-cost features

Resource-cost features still matter, but the learner fix makes the ablation
story slightly more nuanced than before. Mean ablation utilities are:

| Scenario/load | History only | History + cost | Full |
|---|---:|---:|---:|
| Aligned/light | 0.8330 | **0.8364** | 0.8321 |
| Aligned/medium | 0.7889 | 0.7914 | **0.7930** |
| Aligned/heavy | 0.5916 | **0.5929** | 0.5925 |
| Ambiguous/light | 0.8069 | 0.8153 | **0.8157** |
| Ambiguous/medium | 0.7668 | **0.7699** | 0.7690 |
| Ambiguous/heavy | 0.5770 | 0.5770 | **0.5777** |

Interpretation:

- `history_only` is still the weakest input and should no longer be treated as
  a serious main candidate.
- `history_cost` remains a strong compact default.
- `full` is now competitive again after the learner fix, so richer inputs may
  not be inherently harmful; the earlier weakness likely reflected learner
  limitations as much as feature design.

### Teacher-imitation diagnostics

The diagnostics now show that the learner fix helped especially in aligned
scenarios.

Mean agreement with the teacher:

| Scenario/load | Method | Pairwise | ARI | NMI |
|---|---|---:|---:|---:|
| aligned/light | Multi-feature | 0.6425 | 0.2506 | 0.3443 |
| aligned/light | LE-GRA | **0.6787** | **0.3353** | **0.3831** |
| aligned/medium | Multi-feature | **0.6758** | 0.2860 | **0.3374** |
| aligned/medium | LE-GRA | 0.6638 | **0.2866** | 0.3353 |
| aligned/heavy | Multi-feature | 0.9152 | 0.8175 | **0.8383** |
| aligned/heavy | LE-GRA | **0.9175** | **0.8264** | 0.8365 |
| ambiguous/light | Multi-feature | **0.6326** | 0.2513 | **0.3495** |
| ambiguous/light | LE-GRA | 0.6281 | **0.2685** | 0.3324 |
| ambiguous/medium | Multi-feature | **0.7178** | **0.3104** | **0.3483** |
| ambiguous/medium | LE-GRA | 0.7115 | 0.3081 | 0.3383 |
| ambiguous/heavy | Multi-feature | **0.9436** | **0.8730** | **0.8744** |
| ambiguous/heavy | LE-GRA | 0.9385 | 0.8635 | 0.8680 |

The updated interpretation is that the learner is now clearly more credible in
aligned settings, but ambiguous scenarios still expose a real gap between the
current embedding learner and the best hand-crafted clustering baselines.

## Interpretation and Important Caveats

- The new pressure levels work. Quality falls substantially under heavy load;
  served ratio often remains near one because the optimizer can lower quality
  instead of dropping users.
- Used-bandwidth SE naturally favors large multicast groups because one
  transmission serves many users. This is expected and is why system SE,
  utility, quality, and served ratio must be reported together.
- The teacher optimizes QoE utility, not spectral efficiency directly. A method
  can therefore have the highest utility without the highest used-bandwidth SE.
- Current results now establish two things at once:
  - resource-cost features are valuable;
  - learner correctness mattered, because fixing the normalization gradient
    visibly improved LE-GRA.
- The learned embedding still does not dominate ambiguous settings. The
  remaining bottleneck is now better described as learner design and training
  quality, not a missing feature ablation.

## Recommended Next Steps

Do not immediately expand to `Kmax=5` or a much larger experiment matrix. The
next bottleneck is still learner diagnosis rather than more runs.

1. Treat `medium_matrix_results_v2_after_grad_fix` as the new reference result
   set. Do not keep citing the old `v2` matrix as the main conclusion.
2. Keep the focus on ambiguous scenarios. That is where LE-GRA still needs to
   prove value beyond hand-crafted clustering.
3. Run learner-focused improvements next:
   - validation-based model selection,
   - pair sampling / label construction refinements,
   - small sweeps over margin, epochs, hidden size, and learning rate.
4. Keep `history_cost` and `full` as the meaningful feature candidates. Treat
   `history_only` mainly as a weaker ablation baseline.
5. Only after learner quality stabilizes should you expand `Kmax`, seeds, or
   total scenario counts.

## Suggested Prompt on the Next Computer

```text
Please read SESSION_HANDOFF.md and the three CSV files under
medium_matrix_results_v2_after_grad_fix. Then inspect the current implementation
in `le_gra_mvp.py` and `run_standard_matrix.py`. Continue the LE-GRA research
from the recommended next steps. Do not expand the matrix blindly. Focus first
on learner improvements that may help in ambiguous scenarios.
```

## Repository State at Handoff

The code changes implementing progress output, load levels, dual SE metrics,
service/quality metrics, multi-feature diagnostics, the corrected normalization
gradient, and this handoff should travel together with the
`medium_matrix_results_v2_after_grad_fix` evidence. Older smoke-test
directories are useful for local sanity checks but are not the main research
artifact.
