"""
Catala-style exception DAG resolution.

Build a DAG once per exception chain from Rule declarations (static structure only).
Only rules that participate in an override relationship belong in a DAG — standalone
rules with no exceptions have no use for it. Each chain has exactly one root (base case).

Call dag.evaluate(conditions, values) per case with precomputed booleans and values.

Each Rule declares:
  - id: section identifier
  - overrides: list of rule IDs this rule overrides (higher priority than those)

evaluate() arguments:
  - conditions: {rule_id: bool} — does each rule's condition hold for this case?
  - values: {rule_id: any} — precomputed result for each rule;
            use the _BLOCKS sentinel for defeater rules (blocks target, no value)

Returns NOT_APPLICABLE if the root condition is false or the chain is entirely blocked.
Raises ConflictError if two rules at the same level produce conflicting values.
Raises ValueError if conditions or values are missing rule ids, or DAG is malformed.
"""

from dataclasses import dataclass, field

NOT_APPLICABLE = (
    object()
)  # chain doesn't apply: root condition false or blocked by defeater
_BLOCKS = object()  # stored in values dict for defeater rules; blocks the target rule


@dataclass
class Rule:
    id: str
    overrides: list = field(default_factory=list)  # rule IDs this rule overrides


class ConflictError(Exception):
    def __init__(self, rule_ids):
        self.rule_ids = rule_ids
        super().__init__(
            f"conflict: rules {rule_ids} each produced a non-blocking return value"
        )


class CycleError(Exception):
    def __init__(self, msg="circular override chain detected"):
        super().__init__(msg)


class DAG:
    def __init__(self, rules):
        if not rules:
            raise ValueError("DAG requires at least one rule")
        self._overrides_of, self._all_ids = _build_adjacency(rules)
        _detect_cycles(rules)
        roots = [r for r in rules if not r.overrides]
        if len(roots) != 1:
            raise ValueError(
                f"DAG requires exactly one root (one default case only), "
                f"got {len(roots)}: {[r.id for r in roots]}"
            )
        self._root = roots[0]

    def evaluate(self, conditions, values):
        """
        conditions: {rule_id: bool}
        values:     {rule_id: any}  — use _BLOCKS sentinel for defeater rules
        Returns NOT_APPLICABLE if root condition false or chain is entirely blocked.
        Raises ConflictError if two rules at the same level conflict.
        Raises ValueError if conditions or values are missing rule ids.
        """
        missing_c = self._all_ids - set(conditions)
        if missing_c:
            raise ValueError(f"conditions missing rule ids: {sorted(missing_c)}")
        missing_v = self._all_ids - set(values)
        if missing_v:
            raise ValueError(f"values missing rule ids: {sorted(missing_v)}")

        return self._resolve(self._root.id, conditions, values)

    def _resolve(self, rule_id, conditions, values):
        if not conditions[rule_id]:
            return NOT_APPLICABLE
        fired = []
        # blockers first so we short-circuit before evaluating sibling value-rules
        children = sorted(
            self._overrides_of[rule_id], key=lambda r: values[r.id] is not _BLOCKS
        )
        for child in children:
            result = self._resolve(child.id, conditions, values)
            if result is _BLOCKS:
                return NOT_APPLICABLE  # defeater fired: this rule is blocked
            if result is not NOT_APPLICABLE:
                fired.append((child.id, result))

        if not fired:
            return values[rule_id]

        # multiple siblings can fire simultaneously; only a conflict if they disagree on the value
        vals = [v for _, v in fired]
        if all(v == vals[0] for v in vals):
            return vals[0]  # unanimous — any element would do
        raise ConflictError([rid for rid, _ in fired])


def _build_adjacency(rules):
    seen_ids = set()
    for rule in rules:
        if rule.id in seen_ids:
            raise ValueError(f"duplicate rule id: {rule.id!r}")
        seen_ids.add(rule.id)

    # invert: rule.overrides (rules this rule overrides) → overrides_of[id] (rules that override id)
    overrides_of = {r.id: [] for r in rules}
    for rule in rules:
        for target_id in rule.overrides:
            if target_id not in overrides_of:
                raise ValueError(
                    f"rule {rule.id!r} references unknown id {target_id!r}"
                )
            overrides_of[target_id].append(rule)

    # every rule must participate in at least one override relationship
    overridden = {tid for r in rules for tid in r.overrides}
    overriding = {r.id for r in rules if r.overrides}
    standalone = seen_ids - (overriding | overridden)
    if standalone:
        raise ValueError(
            f"standalone rules not in any override chain: {standalone} — "
            "evaluate them directly without a DAG"
        )

    return overrides_of, seen_ids


def _detect_cycles(rules):
    graph = {r.id: list(r.overrides) for r in rules}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {r.id: WHITE for r in rules}

    def dfs(node):
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if color[neighbor] == GRAY:
                raise CycleError(f"cycle detected: {node!r} -> {neighbor!r}")
            if color[neighbor] == WHITE:
                dfs(neighbor)
        color[node] = BLACK

    for rule in rules:
        if color[rule.id] == WHITE:
            dfs(rule.id)
