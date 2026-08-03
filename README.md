# Statutory Formalization Pipeline — 26 USC § 7701

A pipeline that converts US federal tax code from statutory prose into typed, machine-checkable OCaml — one function per provision, one-to-one with the law.

## The Upstream Problem

Formal verification of tax law requires a structured, typed representation of the law as input. You cannot feed raw statutory text to a verifier. The question of how to get from prose to a representation that is:

- **typed** — legal concepts expressed as algebraic types with exhaustive case analysis
- **traceable** — every function maps to a specific provision by section identifier
- **dependency-ordered** — definitions appear before the provisions that use them
- **exception-aware** — overrides encoded structurally, not as conditional branches

is unsolved and non-trivial. This pipeline solves it.

## Why Not Raw LLM Calls on Statutory Text?

Passing raw statutory text to an LLM and asking it to "formalize this" has two fundamental problems:

**No traceability.** LLM output has no provenance. When a proof fails or a contradiction is found, you cannot point to which provision produced it. Explainability requires one-to-one correspondence between code and law — one function per provision, named by section identifier.

**Too much freedom.** An LLM given a full section will combine provisions, inline definitions, and collapse exception hierarchies into conditional branches. This destroys the structural information that makes verification meaningful. You need the exceptions kept separate so the override hierarchy can be encoded as a DAG, not merged into an if-else chain that erases the legal structure.

## Why OCaml, Not Catala

[Catala](https://catala-lang.org/) is the natural starting point — it was designed for formalizing law, and its default/exception semantics directly model statutory override hierarchies. But Catala has practical limitations at LLM generation scale:

- **Designed for human pair-programming.** Catala's tooling (LSP, editor integration) targets a human writing law alongside a programmer. Batch LLM generation over hundreds of provisions is not the intended use case.

OCaml gives the same static guarantees — exhaustive pattern matching on variant types, strong typing, no implicit coercions — with a type system that LLMs generate reliably. Catala's runtime is OCaml; the semantic model is preserved.

## Pipeline

```
pipeline/parse_7701.py              Scrape Cornell LII → data/7701_tree.json (531 nodes, 16 subsections)
          ↓
pipeline/classify_rules.py          Rule-based bottom-up tagger (leaf, definition, exception, scope_rule, ...)
          ↓
pipeline/resolve_refs.py            Build cross-reference graph across all provisions
          ↓
pipeline/formalize_ocaml.py         Pass 1 (--gen-types): one LLM call generates all shared OCaml types
          ↓                         from definition leaves → data/types.ml
pipeline/formalize_ocaml.py         Pass 2: LLM agent formalizes each provision in topological order,
          ↓                         using data/types.ml as shared context
pipeline/assemble_ml.py             Assemble types + formalized provisions into a single .ml file
          ↓
data/section_7701.ml                686 lines of typed OCaml: 61 types, 37 functions, 6 modules
```

## Key Contributions

### 1. Dependency Graph + Topological Sort

§ 7701 defines "person", "corporation", "partnership", "fiduciary", and 50+ other terms — many of which reference each other. If multiple provisions are formalized independently, the same type gets defined multiple times with incompatible declarations, producing compiler errors.

`resolve_refs.py` builds a dependency graph over all 531 nodes by parsing cross-references in the statutory text. `formalize_ocaml.py` runs a topological sort over this graph (Kahn's algorithm, with cycle detection) and processes nodes in dependency order. Each definition is formalized exactly once; downstream provisions call the already-formalized version rather than redefining it. This is a compiler correctness guarantee.

### 2. Exception DAG

Tax law uses a layered override system. § 7701(b)(3)(A) defines the substantial presence test. § 7701(b)(3)(B) carves out an exception. § 7701(b)(3)(C) carves out an exception to the exception. Collapsing this into nested `if/else` loses the legal structure and makes it impossible to audit which rule applied.

`pipeline/exception_dag.py` implements a Catala-style exception DAG. Each provision becomes a `Rule` with a condition, a value, and an `overrides` list pointing to the rules it defeats. The DAG evaluator walks from base rules upward, fires conditions, and returns the value of the highest-priority applicable rule — raising `ConflictError` if two rules at the same priority level conflict and `GapError` if no rule applies. The override hierarchy is explicit, auditable, and separate from the computation.

Exception provisions in the statutory text are detected automatically during parsing and preprocessed so each gets its own formalized function rather than being merged into its parent.

### 3. One-to-One Traceability

Every OCaml type, function, and module is named from the statutory text and annotated with its section identifier. `is_united_states_person` traces to `7701(a)(30)`. `entity_residency` traces to `7701(a)(4)-(5)`. When a proof fails, you can point to the exact provision.

```ocaml
(* 7701(a)(30): US person — citizen/resident individual, domestic partnership,
   domestic corporation, domestic estate, domestic trust *)
let is_united_states_person (p : person) : bool =
  match p with
  | Individual -> is_citizen_or_resident_individual p
  | Partnership pship -> is_domestic pship.residency
  | Corporation corp -> is_domestic corp.residency
  | Estate -> is_domestic_estate p
  | Trust -> is_domestic_trust p
  | _ -> false
```

Cross-section references that cannot be resolved within § 7701 become typed boolean parameters named by section identifier (`sec_911_d_3`, `sec_7701_b_5`), so the caller supplies them explicitly rather than the LLM inventing values.

## Output

`data/section_7701.ml` — current output for § 7701:

- **61 type declarations**: `person`, `corporation`, `partnership`, `fiduciary`, `taxpayer`, `entity_residency`, `stock`, `shareholder`, and more
- **37 functions**: one per provision, typed and named from statutory language
- **6 modules**: grouping wrappers for subsections with independent sub-provisions

## Toward Verification

The OCaml representation is a structured intermediate layer — not the final target. The natural next step is generating [Lean 4](https://lean4.dev/) type declarations and definitions from this structure. OCaml variant types map directly to Lean 4 inductive types; OCaml functions map to Lean 4 definitions. The translation is mechanical, not a re-extraction from statutory text.

The exception DAG structure in particular maps well to Lean 4's dependent type system: an exception rule presupposes that the base rule's applicability conditions are expressible as propositions, and the override semantics can be encoded as a proof obligation rather than a runtime check.

## Running

```bash
# dependencies (Python 3.12+, requires claude CLI in PATH)
uv sync

# step 1: scrape and parse
python pipeline/parse_7701.py

# step 2: classify nodes (rule-based, no LLM)
python pipeline/classify_rules.py

# step 3: generate shared types (one LLM call)
python pipeline/formalize_ocaml.py --gen-types

# step 4: formalize all provisions (parallel LLM calls)
python pipeline/formalize_ocaml.py

# step 5: assemble
python pipeline/assemble_ml.py
```

All scripts run from the repo root. Logs write to `logs/classify/`, `logs/formalize/`, etc.
