# Tax Law Formalization — 26 USC § 7701

Experimental pipeline that converts US federal tax code into machine-checkable OCaml, starting with the definitions section (§ 7701).

## The Problem

Tax law is written in natural language but is fundamentally computational — it defines terms, sets conditions, and specifies exceptions that override base rules. Lawyers and accountants manually trace this logic case by case. The goal here is to make it formal enough that a machine can evaluate it: given facts about an entity, derive the correct legal conclusion deterministically.

The hard part is not the translation itself — it is the exception structure. Tax law uses a layered override system: a base rule applies unless an exception fires, and exceptions can themselves be overridden by sub-exceptions. This is exactly what Catala was designed to formalize, but Catala's syntax is rigid and difficult to generate reliably at scale with LLMs. OCaml — the language Catala itself compiles to — turns out to be a cleaner target: strong static types, exhaustive pattern matching, and a familiar syntax that models follow well.

## What This Does

```
parse_7701.py       scrapes Cornell LII and builds a JSON tree of § 7701
      ↓
7701_tree.json      531 nodes, hierarchically structured
      ↓
resolve_refs.py     resolves cross-references between provisions
      ↓
formalize_ocaml.py  LLM agent formalizes each node bottom-up into OCaml
      ↓
section_7701.ml     compiled OCaml module with types + functions for each provision
      ↓
exception_dag.py    runtime DAG evaluates exception priority for a given set of inputs
```

The formalization is bottom-up: leaf provisions are formalized first, then parents call their already-formalized children. Cross-section references (e.g., "within the meaning of § 911(d)(3)") become typed boolean parameters that the caller supplies.

## Output

`section_7701.ml` is the current output: 686 lines of OCaml covering § 7701, including:
- **61 type declarations** — `person`, `corporation`, `partnership`, `fiduciary`, `taxpayer`, etc.
- **37 functions** — one per provision, typed and named from statutory language
- **6 modules** — grouping wrappers for subsections with independent sub-provisions

Example (§ 7701(a)(30) — United States person):

```ocaml
(* 7701(a)(30): US person - citizen/resident individual, domestic partnership,
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

## Exception Resolution

Provisions phrased as exceptions (language like "notwithstanding", "shall not apply", "except as provided in") are formalized as separate functions. At runtime, `exception_dag.py` evaluates the override hierarchy: given a set of inputs, it walks the DAG and returns the value of the highest-priority applicable rule, raising `ConflictError` if two rules at the same priority level conflict and `GapError` if no rule applies.

## Running

```bash
# dependencies (Python 3.12+, requires Claude CLI in PATH)
uv sync

# scrape and parse § 7701
python parse_7701.py

# formalize (LLM agent — calls claude CLI per node, runs in parallel)
python formalize_ocaml.py

# assemble output
python assemble_ml.py
```

The formalization agent uses `ocaml_system_prompt.txt` and `type_system_prompt.txt`. A checker agent validates each output and retries up to 2 times if issues are found.

## Status

Work in progress. § 7701 is the definitions section and a natural starting point — every other section of the IRC uses terms defined here. The pipeline handles the main structural patterns but exception DAG integration (wiring generated OCaml functions into the runtime evaluator) is the active next step.
