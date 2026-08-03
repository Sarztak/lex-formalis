"""
Catala-style exception DAG resolution.

Build a DAG once from Rule declarations. Call dag.evaluate(inputs) per case.

Each Rule declares:
  - id: section identifier
  - condition: function(inputs) -> bool — does this rule apply?
  - value: function(inputs) -> any — what value does it produce?
  - overrides: list of rule IDs this rule defeats (higher priority over those)

Rules with overrides=[] are base cases (lowest priority).
Rules listing other IDs in overrides are higher priority than those rules.
"""

from dataclasses import dataclass, field

_EMPTY = object()  # sentinel: rule did not fire (condition false)


@dataclass
class Rule:
    id: str
    condition: object  # callable (inputs) -> bool
    value: object      # callable (inputs) -> any
    overrides: list = field(default_factory=list)  # list of rule IDs this rule defeats


class ConflictError(Exception):
    def __init__(self, rule_ids):
        self.rule_ids = rule_ids
        super().__init__(
            f"conflict: rules {rule_ids} all apply simultaneously at the same priority level"
        )


class GapError(Exception):
    def __init__(self, msg="no rule applies to this case"):
        super().__init__(msg)


class CycleError(Exception):
    def __init__(self, msg="circular override chain detected"):
        super().__init__(msg)


class DAG:
    def __init__(self, rules):
        if not rules:
            self._id_to_rule = {}
            self._overridden_by = {}
            self._roots = []
            return
        self._id_to_rule, self._overridden_by = _build_adjacency(rules)
        _detect_cycles(rules)
        self._roots = [r for r in rules if not r.overrides]

    def evaluate(self, inputs):
        """
        Evaluate the DAG for a given inputs object passed to condition and value callables.

        Returns the value of the winning rule.
        Raises ConflictError if multiple rules at the same priority level fire with different values.
        Raises GapError if no rule applies.
        """
        active_roots = []
        for root in self._roots:
            result = _evaluate(root.id, self._id_to_rule, self._overridden_by, inputs)
            if result is not _EMPTY:
                active_roots.append((root.id, result))

        if len(active_roots) == 0:
            raise GapError()
        elif len(active_roots) == 1:
            return active_roots[0][1]
        else:
            values = [v for _, v in active_roots]
            if all(v == values[0] for v in values):
                return values[0]
            raise ConflictError([rid for rid, _ in active_roots])


def _build_adjacency(rules):
    id_to_rule = {}
    for rule in rules:
        if rule.id in id_to_rule:
            raise ValueError(f"duplicate rule id: {rule.id!r}")
        id_to_rule[rule.id] = rule

    overridden_by = {r.id: [] for r in rules}
    for rule in rules:
        for target_id in rule.overrides:
            if target_id not in id_to_rule:
                raise ValueError(f"rule {rule.id!r} references unknown id {target_id!r}")
            overridden_by[target_id].append(rule)

    return id_to_rule, overridden_by


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


def _evaluate(rule_id, id_to_rule, overridden_by, inputs):
    rule = id_to_rule[rule_id]
    exc_children = overridden_by[rule_id]

    active = []
    for child in exc_children:
        result = _evaluate(child.id, id_to_rule, overridden_by, inputs)
        if result is not _EMPTY:
            active.append((child.id, result))

    if len(active) == 0:
        return rule.value(inputs) if rule.condition(inputs) else _EMPTY
    elif len(active) == 1:
        return active[0][1]
    else:
        raise ConflictError([rid for rid, _ in active])
