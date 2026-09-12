# capa-normativa

[![CI](https://github.com/Guille1799/capa-normativa/actions/workflows/ci.yml/badge.svg)](https://github.com/Guille1799/capa-normativa/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10 | 3.12 | 3.14](https://img.shields.io/badge/python-3.10%20%7C%203.12%20%7C%203.14-blue.svg)](https://github.com/Guille1799/capa-normativa/blob/main/.github/workflows/ci.yml)

> Versión en español: [README.es.md](README.es.md)
>
> **Outside knowledge that governs code, as verifiable data.** For systems whose behaviour
> depends on knowledge that comes from outside them — scientific literature, methodology,
> regulation — and which contradicts itself, changes over time, and applies differently
> depending on the subject.
>
> The code stops holding the numbers. It asks a registry, and gets **the value together with
> where it came from and how strong the evidence is**. Three things follow, and they are
> properties of the type rather than conventions someone has to remember:
>
> 1. **A malformed norm is never constructed.** If the registry does not load, the program
>    does not start — rather than starting and being wrong later.
> 2. **A recommendation resting on weak evidence cannot be phrased as a firm one.** The
>    registry raises instead of returning it.
> 3. **A value that fell back to a default says so**, so a general answer is never mistaken
>    for one computed for this particular subject.
>
> The code block below reads the same in any language. `resolve()` returns the value, the
> evidence behind it, how certain that evidence is, and whether it was a fallback.

```python
from capa_normativa import NormRegistry

NORMS = NormRegistry.load("norms/")           # falla al arrancar si algo está mal

r = NORMS.resolve("watch_threshold", kind="alpha")
r.value        # 25.0
r.evidence     # ('EV-0007', 'EV-0009')
r.certainty    # 'baja'  → nunca podrá ser una recomendación fuerte
r.is_fallback  # False   → hubo rama específica para este sujeto
```

## Contents

- [`SEM001` — the correct migration to the wrong number](#sem001--the-correct-migration-to-the-wrong-number)
- [Illegal states that cannot be constructed](#illegal-states-that-cannot-be-constructed)
- [Running the tests](#running-the-tests)
- [Two modules](#two-modules)
- [`init` — start here if you don't have a registry yet](#init--start-here-if-you-dont-have-a-registry-yet)
- [`emit` — if your consumer is not Python](#emit--if-your-consumer-is-not-python)
- [`validate` — check the registry without starting the app, and warn about what is about to expire](#validate--check-the-registry-without-starting-the-app-and-warn-about-what-is-about-to-expire)
- [The watchdog (`vigilante`) — start here if all you want are the checks](#the-watchdog-vigilante--start-here-if-all-you-want-are-the-checks)
- [What it deliberately does NOT do](#what-it-deliberately-does-not-do)
- [Expressiveness, deliberately poor](#expressiveness-deliberately-poor)
- [Missing backing, declared as such](#missing-backing-declared-as-such)
- [And what else lives in this repo, because holding it up required it](#and-what-else-lives-in-this-repo-because-holding-it-up-required-it)
- [The saboteur — a checker that cannot go red is decorative](#the-saboteur--a-checker-that-cannot-go-red-is-decorative)
- [Structure](#structure)
- [Installation](#installation)
- [Migrating](#migrating)
- [Origin](#origin)

---

# Two modules

One artifact, two modules, and **they never import each other** (verified by a test that
checks it via AST — a boundary that is not verified is a boundary that drifts):

| Module | What it does | When it runs |
|---|---|---|
| **`capa_normativa`** — the registry | the numbers live as data with provenance and an expiry date. **Fail-fast**: if something is wrong, the program does not start | in your process, at startup |
| **`capa_normativa.vigilante`** — the watchdog (`vigilante`) | **deterministic** checks over a repo. **Enumerates** findings instead of stopping at the first error | in pre-commit, in CI, or by hand |

## `init` — start here if you don't have a registry yet

```bash
capa-normativa-init norms/            # crea schema.yaml, evidence.yaml y norms.yaml
capa-normativa-validate norms/        # y compruébalo: sale verde tal cual
```

It generates the three YAML files **commented and valid**: they load and resolve without
touching anything. They include **both forms that exist** — a constant norm with evidence,
and one that branches on a subject attribute — because with only one form, the first real
norm that branches gets written by guesswork.

**A generator whose output does not validate is worse than not having one**: your first
experience would be an error in a file the package just handed you, and you would not know
whether the problem is yours or the example's. A test pins this down, and it is the one test
that can never be relaxed.

- **It never overwrites.** If files already exist, it exits with `1` and **touches none of
  them** — all-or-nothing, because a half-overwritten registry is worse than one left
  untouched. Use `--forzar` (force) if you really mean it.
- **It carries no one's domain.** The examples are deliberately generic (a test checks this):
  putting nutrition or training thresholds in here would tie the package to its first tenant.

The comments explain **why** each field exists, not just what it accepts — in particular
that `subject_dimensions` is a **closed list**, that this is the only thing preventing norms
from chaining into each other, and that an expired `expires` **stops the application from
starting**.

## `emit` — if your consumer is not Python

The registry is read with `load()`+`resolve()` **inside a Python process**. `emit` exports
the constants to another language **together with their provenance** — for a TypeScript
frontend, R thresholds, or a universal JSON file. Each call takes a `--formato` (format) and
a `--salida` (output path):

```bash
capa-normativa-emit norms/ --formato typescript --salida frontend/norms.ts
capa-normativa-emit norms/ --formato r          --salida R/constants.R
capa-normativa-emit norms/ --formato json       --salida build/norms.json
capa-normativa-emit norms/ --formato python     --salida app/norms_gen.py
```

**And this is what keeps `emit` from becoming a new problem:**

```bash
capa-normativa-emit norms/ --formato typescript --salida frontend/norms.ts --check
```

`--check` (check) does not write: it **re-emits and compares**. If the result differs, it
exits with **1**. Commit the generated file **and put `--check` in CI** — this is the same
pattern as `protobuf`, `OpenAPI`, and `kubernetes/hack/verify-codegen.sh`. **Without
`--check`, `emit` adds one more artifact that can drift, which is exactly the problem this
package exists to prevent.**

Each value comes out with its unit, its evidence IDs, its certainty, its strength, and its
expiry date:

```typescript
/** puntos porcentuales de grasa · ev=EV-0113 · certeza=baja · condicional · caduca=2027-01-30 */
export const BIA_MEASUREMENT_ERROR_MARGIN = 3.0 as const;
```

> **If `emit` only exported numbers, it would have reinvented the problem in a new place.**
> A generated `EA_FLOOR <- 30` is the same magic number, with a build step in between.

**It only emits the constants** (the ones that do not branch on the subject). One that
branches cannot be dumped without reproducing its decision table and its hit policy in every
language, so **it is not emitted, and it appears in `omitidas` (omitted) with its reason** —
a silent absence would make the generated file look complete when it is not. Against the
first tenant's real registry, measured on **2026-08-30**: **116 constants emitted, 42
omitted**, each with its reason. And **anything the registry would not serve is not emitted
either**: retired and blocked norms stay out, or `emit` would be a back door.

## `validate` — check the registry without starting the app, and warn about what is about to expire

```bash
capa-normativa-validate norms/                          # 0 válido · 1 problemas · 2 no se pudo
capa-normativa-validate norms/ --avisa-en 90            # horizonte del aviso (por defecto 60 días)
capa-normativa-validate norms/ --falla-si-caduca-en 30  # para CI: el aviso pasa a ser un GATE
capa-normativa-validate norms/ --json                   # para consumo por máquina
```

**This is not `load()` under another name.** It covers two gaps that `load()` leaves open,
and neither is cosmetic.

### ① An expired norm is a production outage, and nothing announced it

A `vigente` (active) norm whose `expires` has already passed **makes `load()` raise**: on the
day it expires, **the application does not start**. That design is deliberate — it is the
*"refuse to serve what's stale"* half of the gettext model — but without advance warning it
is a landmine: the mechanism that protects you from stale information shows up as a
deployment failing on a Tuesday, with no apparent link to anything you touched.

**`--avisa-en` (warn-within) is the other half**, and `--falla-si-caduca-en`
(fail-if-expiring-within) turns it into a CI gate. Expiring soon **is not** an error — if it
were, someone would just turn the warning off — so it exits green with a warning until you
decide otherwise.

The gate looks **only at norms that EMIT a value** (v0.16.1). An expired `retirada` (retired)
or `bloqueada` (blocked) norm is still reported — a dead date in the YAML lies to whoever
reads it — but it does not fail the gate: it emits no value, so its expiry cannot break
anything downstream. Up to v0.16.0 it did fail the gate, and that turned it red for no real
reason: on a norm that does not emit, the date that matters is `retirement`, and giving it an
`expires` on top only duplicates a date that governs nothing.

### ② `load()` stops at the first error; whoever writes the YAML wants all seven

Same split as between the registry and the watchdog: the registry **stops**, because its job
is to refuse to start; this **enumerates**, because its job is to let someone fix a file.

Errors are enumerated **per norm**, since norms are independent. Errors in `schema.yaml` and
in the evidence file are **not** enumerated that way, and this is deliberate: everything else
depends on them, so continuing past a broken schema produces a cascade of derived errors that
buries the one that actually matters.

> ⚠️ **It does not reimplement any check**: it calls the same validator `load()` uses. Two
> validators that are supposed to be equivalent drift apart, and then `validate` would say
> green over a registry that does not start — worse than not having it. A test checks this
> via AST.

### What it found on its first run

Against the first tenant's real registry, and without starting their application:

```
✗ [working_sets_by_mode] rama #0 viaja con certainty='baja' pero la MEJOR evidencia
  que ELLA cita es 'muy_baja'.
```

A branch that **presented itself as more reliable than its own single source**, inheriting
certainty from the branch next to it. It would have stopped the app from starting once the
package was updated. That is exactly the use case: finding out beforehand, without standing
anything up.

## The watchdog (`vigilante`) — start here if all you want are the checks

It does not need the registry. It works on any repo, even without a single `.yaml` file.

```bash
capa-normativa-vigilante <ruta>                      # todos los detectores
capa-normativa-vigilante <ruta> --detector sintaxis  # uno solo
capa-normativa-vigilante <dir-de-md> --detector punteros --tambien ../otro/docs
capa-normativa-vigilante <ruta> --json               # salida para consumo por máquina
```

**Output contract**, because the intended consumer is an agent with no context:

| Code | Means | What to do |
|---|---|---|
| **0** | clean | nothing |
| **1** | there are findings | fix them: each finding **says what to do** |
| **2** | could not run | investigate: "it failed" and "it found things" demand opposite reactions |

### The detectors

| Code | Catches | Note |
|---|---|---|
| **`SYN001`** | a versioned `.py` file that does not parse | it caught a **two-month-old** `SyntaxError` that no other mechanism had seen |
| **`PTR001`** | a `§N.M` pointer that does not resolve | it does not check that the section *says* what is attributed to it — that is not automatable — it checks that it **exists**. It walks the tree **depth-first** (see the warning below) |
| **`SEC001`** | a credential with a recognizable shape in a versioned file | it scans **everything** versioned, reports included. The finding **never contains the secret**. A `# nosec` at the end of the line suppresses it |
| **`TRI001`-`TRI007`** | the **ratchet** (`trinquete`): a declared debt that can only shrink | this is an API, not a subcommand: it needs your baseline and your extractor. See below |
| **`SEM001`** | a constant whose **name** says `..._CAP` (cap) but resolves a norm with `semantics: suelo` (floor) — or the other way round | this is an API: it needs the `slug → semantics` map for **your** registry. See below |

### `SEM001` — the correct migration to the wrong number

This is the youngest detector (`v0.13.0`), and it comes from a **measured** failure, not an
imagined one.

While migrating a constant called `_PLANNED_LOAD_CARB_GKG_CAP` — a **cap** on extra
carbohydrate — the triage tool proposed it as a candidate for the norm
`carb_floor_g_per_kg_ffm`, which is a daily **floor**. Both were worth `1.5`, and the
candidacy looked reasonable: same value, and the names share the word `CARB`. The only thing
that stopped it was reading the comment at the call site.

Afterwards, we measured what would have happened without reading it. The wrong migration was
carried out with the full ritual, and the project's gate was run:

```
2634 passed, 1 skipped, 1 xfailed
```

**Green.** And it makes sense: the entire harness checks that the **value** does not change,
and the value was `1.5` before and `1.5` after. **Nothing looked at the meaning.** The error
would have stayed permanent and invisible — a ceiling working as a floor, with a false
provenance and the look of something already solved.

Worse: the condition that makes this possible — the two numbers matching — is exactly the
condition that makes a value-based triage propose it to you. **This is not a rare failure:
it is this kind of work's natural failure mode.**

```python
from capa_normativa.vigilante import revisar_semantica

# El mapa sale de TU registro en una línea. Se pasa (no se lee) para que el vigilante
# no conozca el formato del registro: la frontera entre los dos módulos es del paquete.
mapa = {s: NORMS.norma(s).semantics for s in NORMS.slugs()}
for h in revisar_semantica("backend", mapa):
    print(h)
```

**How it stays quiet.** It requires **two** conditions at once: that the name carries a word
of *semantic* polarity, and that the norm declares the opposite one. Measured at the time
against a real 81-norm backend, it gave **0 findings** — and it catches the case above the
moment it is introduced. A slug that is not in your map is **silently ignored**, so you can
pass a partial map without generating noise.

Bare `_MIN` and `_MAX` are **not** in the vocabulary, and this is deliberate: in the source
project, that same temptation flagged 100% of the constants, because they are almost always
sample sizes (`_MIN_READINGS`). A signal that fires on everything signals nothing.

> ⚠️ **What it does NOT cover, and it is worth being clear about it so it is never mistaken
> for coverage:** two constants that answer different questions when **neither** is called
> cap nor floor — four protein doses (pre-workout, post-workout, before sleep…) are all "grams
> of protein," and to this detector they are invisible. There, the only defence is still
> **reading the comment at the call site**. This detector closes **one** class of failure: the
> one that could be made deterministic.

> ⚠️ **With no map, it returns `[]`.** That is the silent no-op, so **check with a test that
> your map actually arrives full** (`assert len(mapa) >= N`). A gate that finds no data of its
> own passes green without having looked at anything, and that is exactly the failure mode
> this package exists to prevent.

### ⚠️ About `PTR001`: what counts as "the corpus"

**It walks the directory tree depth-first** (excluding `node_modules`, `venv`, `.git`, and the
like), and the headers of subdirectories **also** count as valid targets.

> **In `v0.10.0` it did NOT walk the tree**: it only looked at the top level. Over a `docs/`
> with subfolders it said **"clean, 0 findings"** and exited with **0**, while there were
> **8 dangling pointers** one folder down. A false negative is the worst possible failure for
> a detector: it hands out confidence. **If you are on `0.10.0`, update.**
>
> It was found by a context-free agent adopting the package with only this README — not by
> the detector's own tests, whose corpora were all a single level deep. *The shape of the
> test copied the shape of the bug.*

And a consequence worth knowing: walking the tree depth-first surfaces **references to
sections of other documents** (a spec, a standard) written with no prefix. Those come out as
dangling, and that is a legitimate false positive. Two ways out: put the document name in
front, in CAPITALS (`DMN §10.3`), or declare its corpus with `--tambien` (also / include-too).
**The detector never guesses what is yours: you tell it.**

### The ratchet (`trinquete`)

An absolute gate exits red on day one and **gets turned off**. The ratchet calibrates itself
against the current state and only forbids things getting worse, so it can enter a repo that
already has debt without blocking it. And it does not die of alert fatigue: it does not ask
for attention on every event, it only asks that a number never goes up.

```python
from capa_normativa.vigilante import Trinquete

t = Trinquete("tests/const_baseline.json", tope=206,
              vocabulario={"norma", "tecnica", "mundo", "clasificador"},
              que_migrar_a="engine/norms/norms.yaml")

for h in t.revisar(mi_extractor_de_constantes()):
    print(h)          # cada uno con su código estable y su arreglo
```

The **extractor and the vocabulary are yours**: this module does not know what constants your
domain has. It checks six things, and **each one came from a real failure**: new entries ·
values changed without changing the name · **stale entries** (an entry that no longer exists
is a *re-entry permit*: without this check, what has already been migrated can be hand-written
back in and nothing objects) · the ceiling exceeded · entries with no explanation for why
they are still there · and **a ceiling set too loose**, because a ceiling above the real
count is just decoration.

What it **cannot** do, and the message says so instead of hiding it: tell apart *"the debt
grew"* from *"the instrument stopped being blind."* That is a question of intent, and intent
cannot be computed.

### Wiring it into a pre-commit hook

```bash
#!/bin/sh
capa-normativa-vigilante . --detector sintaxis --detector secretos || exit 1
```

⚠️ **Local hooks are a courtesy: the copy that can actually block is the one in CI.** A
pre-commit hook is skipped with `--no-verify`, and it does not exist in anyone else's clone.

### Why deterministic, and not an LLM

A detector that changes its mind **is just one more live response**: it makes the problem it
is meant to solve worse. And it costs no tokens, so it keeps working when the budget runs
low. The watchdog's modules have a test that verifies, via AST, that **they import nothing
network-related** — the rule is mechanized, not trusted on faith.

---

## Illegal states that cannot be constructed

Each one corresponds to a real, observed failure mode:

| It cannot be built if… | This avoids |
|---|---|
| `strength: vinculante` (binding) with weak certainty | treating as dogma what the evidence does not support |
| weak certainty with no expiry date | fragile knowledge staying forever |
| an active (`vigente`) norm is **expired** | "review this some day" never arriving |
| a branch cites no evidence | numbers with no provenance |
| evidence that **does not exist** is cited | dangling pointers |
| **the unknown-subject branch is missing** | **specifying only for the subject in front of you** |
| two norms share an identifier | silent collisions between documents |
| there is a declared contradiction with no resolution | collecting conflicts and never adjudicating them |
| a retired norm is read | the fossil comment that outlives its own supersession |
| logic sneaks into a condition | turning this into a rules engine |
| **two branches match the same subject** | the file's order deciding the value |
| **a norm branches on another norm** | **chaining rules through the back door** |
| **two ranges overlap** (`">=40"` and `">=60"`) | a subject of 70 getting the value of the wrong band |
| **a range is empty** (`"[5,3]"`) | a dead branch silently falling through to the wildcard |
| **a key is not recognized** (`valeu:`, `certainy:`) | what is written and what the registry does no longer matching |
| **a `status` is not recognized** (`vigent:`) | a typo silently disabling the expiry check |
| **a pointer points to a norm that does not exist** | sending the reader to something that is not there |
| a **blocked** (`bloqueada`) norm is read | resolving a conflict behind the scenes, by file order |
| **a norm declares more certainty than its evidence supports** | **the certainty scale being purely decorative** |
| two evidence entries share an `id` | collisions in the layer that is never deleted |
| an old citation is marked as recent | citing a classic without saying it is one |
| **a call asks for an undeclared dimension** | **a caller's typo silently falling through to the wildcard** |
| there are **two** unknown-subject branches | the file's order deciding the default value |

## What it deliberately does NOT do

- **It runs no logic.** It returns a value and where it came from.
- **It does not chain norms.** Chaining is done by the calling code, where it can be
  debugged.

This is the difference from a rules engine. Twenty years of documented experience show that
those systems fail exactly there: once rules start depending on each other, priorities,
loops, and impossible-to-debug chains appear, and teams end up going back to plain code.
Here the logic stays in your own language; only **the values and their backing** come out.

Since **v0.2.0** that is not a promise but a check — see `subject_dimensions`.

## Expressiveness, deliberately poor

A condition can only be a **wildcard**, a **simple equality**, or a **numeric range**
(`">=100"`, `"[10,100)"`), **over a declared subject dimension**. Nothing more — no
disjunctions, no composition, no evaluation order. The limit **lives in the code**, not in
the documentation: trying to sneak in an operator fails.

### `subject_dimensions` — why it exists (v0.2.0)

`schema.yaml` declares the **closed** list of subject attributes a norm is allowed to branch
on:

```yaml
subject_dimensions: [kind, mode, size]
```

Without it, *"a norm cannot reference another norm"* held by discipline, not by
construction: the registry checked the **shape** of a condition but could not see its
**meaning**. To the parser, `{otra_norma: ">=0.30"}` was a perfectly valid range — and it
passed. This was found while using the registry in production, looking for it on purpose; it
slipped through on the very first attempt.

As a bonus, it catches **dimension typos**, which were the worst possible failure mode: a
misspelled key never matches, so it silently fell through to the fallback and returned the
default value with nothing failing.

> **Breaking, relative to v0.1.0**, and deliberately so: making it optional would have left
> the hole open by default, which is the exact shape of a limit that stops nothing. Migrating
> is one line — the union of the `when` keys you already use.

### Overlapping ranges (v0.3.0)

Up to v0.2.0, *"two branches cannot match the same subject"* was checked by comparing **sets
of pairs**: it caught equality and subsumption, but two ranges are different literals, and
they coexisted peacefully. With an axis split into bands, that is not a missing warning, it
is the **wrong answer, given silently**:

```yaml
- when: {age_band: ">=40"}   # master
- when: {age_band: ">=60"}   # adulto mayor   ← nunca se alcanzaba
```

A subject aged 70 got the value from the first branch in the file. Now the question the
parser actually asks is the one that matters — **does any subject satisfy both branches?**
— resolved with interval arithmetic over the range grammar. Two conditions over different
dimensions do not get in each other's way; a clash can only come from shared keys.

The **empty range** is now also rejected (`"[5,3]"`, `"(4,4)"`): a branch that can never
match falls through to the wildcard and returns a plausible value that is not actually its
own.

Not breaking: if your ranges were already disjoint, nothing changes. If they were not, you
had a bug.

### Unknown keys (v0.4.0)

The parser accepted any key it did not understand and **silently discarded it**. This was
found while trying to put `certainty` on a **branch**: it was accepted, thrown away, and
`resolve()` kept returning the norm's own certainty — whoever wrote it believed they had
branched the confidence level, and had done nothing at all.

The worst case was a typo in `value`:

```yaml
- when: {kind: alpha}
  valeu: 55.0          # la norma CARGABA y emitía None
```

…indistinguishable from a deliberate `value: null`. Now neither one builds, and the error
message suggests the correct key.

**Declared limitation:** inside `adjudication` and `retirement`, keys are still free-form.
They are prose metadata — who adjudicated, over what conflict, why — and they do not govern
what the registry emits, so a typo there is cosmetic.

Not breaking: it only rejects keys that were already being ignored.

### Real statuses and real pointers (v0.5.0)

Three holes from the same family — *what you declare has to be real*:

**`status` only accepts known values.** This is not tidiness: expiry was checked with
`if status == "vigente"`, so a typo **disabled it**. `status: vigent` with a past date used
to load and keep emitting.

**Pointers point at something that exists.** `retirement.replaced_by` was not validated, and
the damage was not passive: the retirement error **builds its message using the pointer**
and shows it to the reader as if it were help (`→ usa: norma_que_no_existe`). Now
`replaced_by: []` is a valid value — *"there is no replacement"* is a legitimate answer — but
it has to be written; before, the message suggested it while also rejecting it.

**`bloqueada` (blocked) genuinely exists.** A norm with conflicting, unadjudicated evidence
**refuses to emit**:

```yaml
status: bloqueada
blocking:
  reason: dos fuentes dan cortes distintos y nadie ha adjudicado
  conflicting_evidence: [EV-001, EV-002]
```

```python
NORMS.resolve("mi_umbral", kind="alpha")   # BlockedNormError, con el motivo dentro
```

Emitting there would mean resolving the conflict behind the scenes, by picking whichever
branch the file lists first. A norm **either has a value, or is explicitly blocked — never
ambiguous.**

Its branches **can** overlap, and that is not an exception but the intended meaning: they
are the conflicting candidates. Requiring disjoint branches here would be asking it to
already be adjudicated, which is exactly what it declares itself not to be. It is not
required to expire either: on a norm that emits nothing, expiring means nothing.

Not breaking: `bloqueada` is new, and the other two only reject what was already broken.

### Layer ① evidence, finally verified (v0.6.0)

For five versions, the parser checked **only the IDs** of the evidence. Everything else —
what the source says, what year it is from, how reliable it is — went in with no one looking
at it.

The serious part was this: **a norm's certainty was self-declared**. R1 stops something
`vinculante` (binding) from having weak certainty… and all it took to get around that was
writing `alta` (high) by hand, even if all the cited evidence was the weakest on the scale.
The whole scale was decorative.

```yaml
# schema.yaml — todo opcional. El registro no sabe cómo se llaman TUS campos.
evidence_certainty_field: certeza
evidence_year_field: anio
evidence_recent_field: reciente
recency_horizon: 2018
```

With that declared: a norm cannot claim more than its best source supports, two entries
cannot share an `id`, and an old citation cannot be marked as recent — citing a classic is
fine, disguising it is not.

**Genuinely opt-in**: without declaring the fields, behaviour is the same as in v0.5.0.

### The other half of the contract: `resolve()` (v0.7.0)

Six versions spent protecting what gets **written** into the YAML. No one looked at what
happens when the code **asks** — and that was half the contract left uncovered:

```python
NORMS.resolve("pain_threshold", tisue="tendon")   # errata del llamante
```

…was silently ignored and fell through to the wildcard. This is the same typo that
`subject_dimensions` closed off from the other side, and **worse**: you write the file once,
but a mistyped call can sit in any one of the thirty places that query the registry. In a
banded norm, the wildcard means *"no data,"* so the typo turns a real signal into silence.

Alongside it, three more from the same family:

- **`0` is no longer "missing data."** `missing` was computed by truthiness, so a zero, a
  `False`, or an empty string all counted as *"you gave me nothing."* A zero is a value.
- **The registry hands out copies, not its own insides.** `value` and `matched` were
  references: a `.append()` by whoever asked changed the norm for everyone. This was the
  literal negation of *"there is only one copy."*
- **At most ONE unknown-subject branch.** With two, the last one in the file wins — file
  order deciding the value, right in the blind spot the anti-overlap rule left open when it
  excluded wildcard branches *"because they overlap by definition."* `bloqueada` (blocked)
  norms are excluded from this: their branches **are** the conflicting candidates.

The only one of these that might require a change on your side is the first one — and if it
fails, you had a bug there.

### Forcing via PRECAUTION, and a claim that does not claim (v0.8.0)

Two gaps that turned up while migrating real safety rules.

**`strength: precautorio` (precautionary).** Up to here, a norm either was binding
(`vinculante`) or was conditional (`condicional`), and *"nothing binding with weak
certainty"* stopped that when the evidence was thin. That is usually right. But it leaves out
a case that actually exists:

> A **precautionary** veto is binding *precisely because* the evidence is weak. It is not
> binding because we know it causes harm: it is binding because **we do not know it is
> safe**.

With only two values, rules like that had to be written as `condicional` while the code
enforced them without exception — the registry misdescribing what the system does, and in
safety of all places. Now they can be declared as such, in exchange for saying **what they
protect against**:

```yaml
strength: precautorio
certainty: baja
precaution: >
  Impacto excéntrico alto sobre un tendón ya cargado por carrera y déficit.
  No hay evidencia de que sea seguro a esta densidad; el veto no espera a tenerla.
```

So that this cannot become a back door around the rule above, `precautorio` **requires**
that field and **rejects strong certainty**: if the evidence supports the rule outright, it
is `vinculante`, and saying so is more informative. And `strength` becomes a closed
vocabulary — until now it was only ever compared against the literal string
`"vinculante"`, so a typo like `vinculnte` silently downgraded a binding norm to a mere
suggestion.

Consumers should not know the vocabulary at all: use **`norm.is_binding`**. Every
`if strength == "vinculante"` written before v0.8.0 stopped being correct once `precautorio`
appeared, and it fails **in the wrong direction** — treating a safety veto as a suggestion.

**A `sin_respaldo` (unsupported) piece of evidence is rejected where it lives.** It used to
be accepted and blow up later, in whichever norm cited it, blaming the norm. And there was no
way out: a citation cannot declare itself `sin_respaldo`, and declaring anything stronger
breaks the certainty rule. The entry was unusable by construction, and nothing said so. If a
number has no source, it belongs on the NORM itself (`certainty: sin_respaldo` +
`provenance_note`), with no evidence entry at all.

## Missing backing, declared as such

Most constants in a real system have no source. If the registry rejected them outright, they
would stay hidden in the code — the very problem this started from. So they can enter with
`certainty: sin_respaldo`, in exchange for **saying where they came from**:

```yaml
certainty: sin_respaldo
provenance_note: >
  Nadie sabe de dónde salió. Estaba en el código sin cita ni comentario.
```

*"Nobody knows"* is a valid answer, and a far more useful one than silence. And because it
sits below the weak-certainty threshold, it inherits two things for free: it can never be
binding, and it **always expires**.

> The goal is not for everything to have evidence. It is for **the absence of evidence to be
> visible, to expire, and to never govern as if it were dogma**.

### …and declared PER BRANCH (v0.14.0)

Until this point that was all-or-nothing **at the norm level**, so *"this branch is backed
and that other one is just convention"* could not be written down: a mixed norm had to lie in
one direction or the other — inflating the certainty of the unsupported branch, or erasing
the real backing of the other one.

```yaml
certainty: sin_respaldo          # = la de su rama MÁS DÉBIL
branches:
  - when: {mode: alfa}
    value: 3
    certainty: moderada
    evidence: [EV-A]
  - when: {mode: any}
    value: 9
    certainty: sin_respaldo
    provenance_note: convención del motor — es lo que el código hace hoy, sin fuente
```

And where this is paid off is in `resolve()`: **the certainty and the provenance you get
back are the ones from the branch that answered**, not the norm's own.

Three rules hold this in place, so the new field cannot become a free-floating label:

- **Each branch answers for ITS OWN evidence.** The check that no one claims more than their
  source supports used to look at the **union** of all branches — i.e. the best source across
  the whole norm — so a branch citing only a thin source travelled with the certainty
  supported by its sibling's source instead. Now it is checked branch by branch.
- **The norm's certainty is that of its weakest branch**, and the declared value is checked
  against it. It is still written by hand instead of computed: it is what a human reads in
  the diff, and what needs to be stopped is not that it exists — it is that it lies.
- **`strength` is NOT split per branch.** The consumer reads `norm.is_binding` without
  knowing which branch answered, so a binding norm with one unsupported branch would force
  obedience to a number nobody actually backs. If one band of the subject really can be
  binding and another cannot, **that is two norms with disjoint `when` clauses**, one
  declaring `null` where the other governs.

## And what else lives in this repo, because holding it up required it

An external-knowledge registry is worth nothing if no one checks that it still tells the
truth. So this repository also holds **two pieces that are not the library itself**, and
that govern the seven acceptance boards of a five-project household:

- **`scripts/ronda_de_tableros.py`** — the round (`ronda`). Every morning it runs the
  acceptance board for **each of the seven repositories and working trees**, each in its own
  separate process with its own interpreter, so that one board blowing up does not take the
  other six down with it. It leaves a human-readable report, a machine-readable one, and
  thirty rounds of history. **It warns on a CHANGE of state, not every day**: a warning that
  repeats identically gets learned as noise, and that had already happened here (nineteen
  identical warnings in a row). Its exit code says whether **the round** ran, not whether the
  boards are green — if it exited with an error for every red board, the task would show up
  failing every single morning, and its result would stop meaning anything.
- **`scripts/aceptaciones/censo_de_guardianes.py`** — the census (`censo`). It enumerates
  everything that starts on its own on this machine — hooks, scheduled tasks, pre-commits,
  boards — and requires each one to declare **what breaks if it dies**, with a minimum
  length, because below that there is no room left for a real consequence. The list **is
  derived from the live sources**, it is not kept by hand: whoever forgets to look is the
  same person who forgot to write it down, so installing a new task turns the census red on
  its own.

Both exist because of the same failure, and it has a date: **something that used to run on
its own stopped running, and no one noticed for 41 days.** That is where the rule they share
with this package's watchdog comes from: *a mechanism that only works if someone remembers to
look at it is not a mechanism.*

## The saboteur — a checker that cannot go red is decorative

It takes each **wiring** piece of `scripts/aceptacion.py`, flips its `return False` — leaving it
physically unable to return a negative verdict — and runs the whole suite. If nothing protests,
that piece is watched by nothing, and every checker hanging off it is decorative. It always
restores the board in a `finally`, and checks the restore against a hash before moving on.

It exists because six static measures of what the harness actually tested — naming, `except`
shape, `grep` — were tried the same day, and the docstring says why none of them was trusted:

> "The six measurements all came back **false**, and all six were plausible — round numbers
> with real names next to them."

Its first run:

```
_delega                7 comprobadores    694 passed   <- CIEGO
_fabrica_bug          12 comprobadores      2 failed
_fabrica_inv           9 comprobadores      1 failed
canario_de_los_hooks   1 comprobador        5 failed
guardia_de_commit      1 comprobador        3 failed
revista_de_runtimes    1 comprobador      694 passed   <- CIEGO
```

Eight checkers were hanging off two pieces nobody was watching, and no static measure had seen
it.

- [`scripts/aceptaciones/sabotaje_del_cableado.py`](scripts/aceptaciones/sabotaje_del_cableado.py)
- [`tests/test_sabotaje_del_cableado.py`](tests/test_sabotaje_del_cableado.py)

## Structure

**The registry** reads three files from whatever directory you pass it:

- `schema.yaml` — the certainty scale and the subject dimensions, **declared, not
  hard-wired**: each domain uses its own.
- `evidence.yaml` — what the sources say. **Append-only.** It governs nothing directly.
- `norms.yaml` — what *your* system does. This is the only file the code is allowed to cite.

**The watchdog** reads none of that: you pass it a path, and it works on whatever git knows
about.

## Running the tests

```bash
git clone https://github.com/Guille1799/capa-normativa.git
cd capa-normativa
pip install -e ".[dev]"
python -m pytest -q          # 666 passed, 18 skipped
```

Verified on **2026-08-30**: on a clean clone, **666 passed, 18 skipped**. The 18 that get
skipped check things specific to the author's own machine, and they **say why** when they
skip; on that machine the suite gives **683 passed, 1 skipped**. The clean-clone number is
the one published here because it is the one you will see. CI runs the suite on **3.10, 3.12,
and 3.14** — all three deliberate, and the reason for each one is written in
`.github/workflows/ci.yml` — and it also runs the watchdog **over this very repository**: a
package that sells detectors and does not apply them to itself is hard to defend.

## Installation

```bash
pip install git+https://github.com/Guille1799/capa-normativa.git@v0.17.0
```

This installs both things: the registry (`from capa_normativa import NormRegistry`) and the
`capa-normativa-vigilante` command.

> ⚠️ **Do not install `v0.10.0`.** Until 2026-08-14 this block pinned that tag, which predates
> **SEC001** (added in `v0.13.0`) and carries the tree-walking bug described above: **it only
> looked at the top level** of the tree. The clean-environment verification from 2026-08-11 was
> real, but it was run **against that old tag** — the note is kept because the method still
> holds, not the version.

<details>
<summary>Sin instalar nada, desde un clon</summary>

```bash
PYTHONPATH=src python -m capa_normativa.vigilante.cli <ruta> --detector sintaxis
```
</details>

## Migrating

**From v0.13.0 to v0.14.0** — the YAML **needs no changes**: with no per-branch fields, each
branch inherits the norm's certainty and everything means the same thing it always did. Two
things that can actually bite:

1. The certainty rule is now checked **per branch**, so it can reject a norm that used to
   load: one whose thin branch travelled under the certainty of its sibling's evidence. This
   is not collateral damage — it is a real inflation that nobody could see before. Measured
   at the first tenant: **1 norm out of 74**, and it was `vigente` (active) and resolving in
   production.
2. `Resolution.certainty` is now the **branch's own**. For a norm that does not use the new
   fields, it is identical; if you adopt per-branch provenance, it changes on purpose — up
   for the backed branch, down for the one that is not.

**From v0.7.0 to v0.8.0** — two things. (1) If your `evidence.yaml` has entries at the lowest
certainty on your scale, delete them: they were never citable. (2) Search your code for
`strength ==` and replace it with `norm.is_binding`, or `precautorio` will slip right past it
as if it were not binding.

**From v0.6.0 to v0.7.0** — check your CALLS: `resolve()` no longer accepts kwargs that are
not declared dimensions. If any call fails now, you had a typo there that used to fall
through to the wildcard.

**From v0.5.0 to v0.6.0** — nothing to do. R15 is opt-in: without declaring your evidence
fields in `schema.yaml`, it checks nothing.

**From v0.4.0 to v0.5.0** — nothing to do. R14 only rejects statuses and pointers that were
already broken.

**From v0.3.0 to v0.4.0** — nothing to do. R13 only rejects keys that were already being
ignored.

**From v0.2.0 to v0.3.0** — nothing to do. R12 only rejects ranges that were already wrong.

**From v0.1.0 to v0.2.0** — one line in `schema.yaml`. If the registry does not start, the
message says what is missing:

```yaml
subject_dimensions: [las, claves, de, tus, when]
```

If declaring them makes you discover that one of them is actually the name of another norm,
that **was** the bug: resolve the two separately, and compose the result in your own code.

## Origin

Extracted from a training-and-nutrition prescription system where the same parameter kept
getting re-decided in every work session, and where values tended to drift toward fitting
the one user the system had. Both problems turned out to be the same one: **a contradiction
between sources that gets resolved by picking one number produces a system tailor-made for
one person; resolving it by branching produces one that works for anyone.**

**How this was built.** Most commits here are co-authored with an AI assistant, and the commit
trailers say so. The English README is a translation of the Spanish original
([README.es.md](README.es.md)). The registry's own rule applies to the registry itself: a value
should arrive with where it came from.

MIT.
