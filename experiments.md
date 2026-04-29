# Relevant Priors — Experiments Write-up

## Approach: rule-based body-region matching, no LLM

I built a pure-Python region/modality matcher rather than calling an LLM
per prior. The challenge brief warns that per-prior LLM calls time out,
and the public split has up to ~28 priors per case. With 996 cases and
~28k pairs against a 360 s wall budget, an LLM per pair is infeasible
even with batching. Token-overlap baselines were also poor on the
abbreviated, lowercase, often-misspelled descriptions in the data
("MAM screen BI with tomo", "MRI LUMBAR SPNE WITHOUT/WITH C", "NMmyo
perf str/rest SPEC-no p"), so I went the other direction and invested
in a careful taxonomy.

The predictor extracts a set of canonical **body regions**
(e.g. `cspine`, `pelvis`, `cardiac`, `breast`) and a **modality** (CT,
MRI, XR, US, MAMMO, NM, PET, DEXA) from each description, then decides
relevance via:

1. **Direct overlap** of region sets, OR
2. **Adjacency** between region sets, with modality-conditional rules
   for a few pairs the labels treat differently by modality combo, OR
3. **Token-overlap fallback** when one side fails to parse, OR
4. **Modality-only boost** for MAMMO/MAMMO and DEXA/DEXA pairs (serial
   follow-ups are almost always relevant).

Per-pair results are cached, so the repeated description pairs that
appear across cases are scored once. Cold-cache full-eval runtime is
~0.5 s for all 27,614 priors.

## Building the taxonomy

The first version used uppercase clinical English ("MAMMOGRAM",
"BRAIN", "ABDOMEN") and got **79.64%** — which beats the always-False
baseline of 76.2% but not by much. Inspecting the unparsed descriptions
in the public split showed the actual data format: short, lowercase,
RIS-exported codes like `MAM screen BI`, `MYO PERF STR/REST`,
`CT ABD/PEL WITH CNTRST`, `MRI LUMBAR SPNE`. The 660 mammograms in the
data didn't match `MAMMOGRAM` because they say `MAM`. Same for echo
(`ECHO`, `TTE`), nuclear cardiac (`MYO PERF`, `NMMYO`), and so on.

Adding those abbreviations got me to **90.06%**.

## Adjacency: anatomy vs. labels

I initially used clinical anatomic adjacency — chest is "next to"
upper abdomen, lumbar spine is "near" pelvis, etc. The labels disagree
sharply with that:

| pair                        | label rate of True |
|-----------------------------|-------------------|
| CT abd/pel ↔ CT chest       | 1.7%              |
| chest XR ↔ echo             | 2.7%              |
| cspine ↔ lspine             | 0.0%              |
| lone abdomen ↔ lone pelvis  | 8.0%              |
| lspine ↔ pelvis             | 20.3%             |
| brain ↔ carotid             | 23.6%             |
| cspine ↔ tspine             | 36.8%             |

The labels treat "anatomically nearby" pairs as **not relevant** —
they want **same body region**, with a few specific exceptions.
Pruning the adjacency table to just the edges supported by the labels
(intra-head, intra-extremity, abdomen↔vascular_abd, sacrum↔pelvis,
ribs↔chest, spine umbrella → segments) and using direct overlap for
abd/pel ↔ either single region (which still fires via plain set
intersect on the full `{abdomen, pelvis}` region) gave most of the
remaining gains.

## Modality-conditional adjacency

Three pairs flip from "almost never relevant" to "almost always
relevant" depending on modality combo:

| pair             | combo            | label rate |
|------------------|------------------|------------|
| cardiac ↔ chest  | CT × CT          | **90.2%**  |
| cardiac ↔ chest  | CT × US (echo)   | 34.0%      |
| cardiac ↔ chest  | NM × XR          | 0.0%       |
| carotid ↔ head   | CTA × CTA        | **87.5%**  |
| carotid ↔ head   | CT × US          | 16.4%      |
| tspine ↔ chest   | XR × XR          | **72.7%**  |
| tspine ↔ chest   | CT × XR          | ~25%       |

The predictor handles these as positive rules in `_predict_one`:
cardiac↔chest fires only when both modalities are cross-sectional
(CT or MRI), carotid↔head only when both descriptions contain
`CTA`/`ANGIO`, tspine↔chest only when both modalities are XR.

## Bug worth calling out

`"L SPINE"` as a substring keyword false-matched `"cervicAL SPINE"` —
the trailing `L` of `cervical` plus the literal ` SPINE` looks
identical to my `lspine` keyword. The same trap caught `T SPINE` and
`C SPINE`. After requiring the leading space (`" L SPINE"`), accuracy
jumped 0.66 percentage points in a single change, fixing 180 spurious
multi-segment extractions that were creating cspine↔lspine spurious
matches via shared spine adjacency.

## Generic-region suppression

When a specific region is matched, the parser strips the parent. A
lumbar spine MRI extracts `cspine` for `CERVICAL SPINE` only when the
keyword actually appears, and the generic `spine` is dropped if any of
`cspine`/`tspine`/`lspine`/`sacrum` is present — this prevents two
unrelated spine segments from overlapping via the shared `spine`.
Same trick for `head` when `brain`/`sinus`/`orbit`/etc. is present, and
for stripping anatomic regions when `dexa` is matched (a "DXA
Hip/Spine Only" study is bone density, not spine imaging).

## Iteration log on the public split

| step | accuracy |
|------|----------|
| baseline (clinical anatomic taxonomy)         | 79.64% |
| add MAM/ECHO/MYO/CNTRST/SPNE/etc. abbreviations | 90.06% |
| symmetric adjacency check + add ribs/extremity generics | 91.92% |
| word-boundary fix on C/T/L SPINE keywords     | 92.58% |
| drop abdomen↔pelvis & lspine↔pelvis adjacency, cardiac↔chest CT/MRI gate | 93.43% |
| breast keyword expansion + carotid↔head CTA gate + tspine↔chest XR gate | 94.09% |
| add LUMBAR/ENTEROGRAPHY/PARACENTESIS/STERNUM/THORACENTESIS keywords | 94.62% |
| DEXA suppresses spine/hip/femur/lspine in same description | **94.93%** |

## Final result on public split

```
accuracy: 0.9493  (26214/27614)
confusion matrix (actual, predicted):
  actual=T predicted=T: 6068
  actual=T predicted=F: 499
  actual=F predicted=T: 901
  actual=F predicted=F: 20146
```

precision: 6068 / (6068 + 901) = **87.07%**
recall:    6068 / (6068 + 499) = **92.40%**

## What's left

The remaining ~5% errors are mostly noise inside high-rate patterns
that I can't fix without breaking many more correct predictions:

- `breast` ↔ `breast` direct match: 168 FPs vs 1829 TPs (91.6% True
  overall, so predicting True is right; 168 is the inherent label
  noise within a pattern that's mostly correct).
- `abd/pel` ↔ `abdomen` direct match: 65 FPs vs 213 TPs (76.6% True
  pattern).
- `cardiac` ↔ `chest` cross-modality (echo vs CT chest): 110 FNs.
  The labels are 34% True for this combo — predicting False on it
  saves more than it costs (93 correct, 48 wrong vs the inverse), so
  the rule is intentionally not adjacent here even though it loses
  some TPs.
- Description-only ambiguity: `"CT guided FNA"` (no body part info,
  21 True out of mixed labels), `"OUTSIDE FILMS"` (always False, 64/64).

## What I'd do next

If I had more time, the next two ideas in order of expected payoff:

1. **Train a small classifier on top of the rule-based features.**
   Region overlap, modality match, modality combo, parse-status, body
   description bag-of-tokens, etc. as features → logistic regression
   or gradient-boosted trees on the public split, with k-fold CV. The
   patterns where labels are 30–60% True are exactly where a
   classifier would learn the residual signal that pure rules can't
   capture (e.g. specific echo subtype × specific chest CT subtype).

2. **Light LLM batch call as a tie-breaker.** For the ~300 pairs per
   case where rules are uncertain (region missing on one side, or in
   the 30–60% ambiguous adjacency zone), batch them all into a single
   structured call asking the LLM to mark each pair Y/N. With one call
   per case across 996 cases that fits well under the 360 s budget,
   and it would only run on the hard subset where rules don't have a
   clear answer.
