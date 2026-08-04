import pytest
from exception_dag import _BLOCKS, DAG, NOT_APPLICABLE, ConflictError, CycleError, Rule


def dag(rules_spec):
    """rules_spec: list of (id, condition, value, overrides)"""
    rules = [Rule(r[0], r[3]) for r in rules_spec]
    conditions = {r[0]: r[1] for r in rules_spec}
    values = {r[0]: r[2] for r in rules_spec}
    return DAG(rules), conditions, values


def ev(rules_spec):
    d, c, v = dag(rules_spec)
    return d.evaluate(c, v)


# ── basic resolution ───────────────────────────────────────────────────────────


def test_simple_exception_fires():
    assert ev([("A", True, "A_val", []), ("B", True, "B_val", ["A"])]) == "B_val"


def test_simple_exception_does_not_fire():
    assert ev([("A", True, "A_val", []), ("B", False, "B_val", ["A"])]) == "A_val"


def test_chain_deepest_fires():
    assert (
        ev(
            [
                ("A", True, "A_val", []),
                ("B", True, "B_val", ["A"]),
                ("C", True, "C_val", ["B"]),
            ]
        )
        == "C_val"
    )


def test_chain_middle_fires():
    assert (
        ev(
            [
                ("A", True, "A_val", []),
                ("B", True, "B_val", ["A"]),
                ("C", False, "C_val", ["B"]),
            ]
        )
        == "B_val"
    )


def test_chain_none_fire_falls_to_base():
    assert (
        ev(
            [
                ("A", True, "A_val", []),
                ("B", False, "B_val", ["A"]),
                ("C", False, "C_val", ["B"]),
            ]
        )
        == "A_val"
    )


# ── base condition false → NOT_APPLICABLE ─────────────────────────────────────


def test_base_false_exception_true_not_applicable():
    d, c, v = dag([("A", False, "A_val", []), ("B", True, "B_val", ["A"])])
    assert d.evaluate(c, v) is NOT_APPLICABLE


def test_base_false_deep_chain_not_applicable():
    d, c, v = dag(
        [
            ("A", False, "A_val", []),
            ("B", True, "B_val", ["A"]),
            ("C", True, "C_val", ["B"]),
        ]
    )
    assert d.evaluate(c, v) is NOT_APPLICABLE


def test_base_false_all_false_not_applicable():
    d, c, v = dag([("A", False, "A_val", []), ("B", False, "B_val", ["A"])])
    assert d.evaluate(c, v) is NOT_APPLICABLE


# ── build-time validation ──────────────────────────────────────────────────────


def test_standalone_rule_rejected():
    with pytest.raises(ValueError, match="standalone"):
        DAG([Rule("A", [])])


def test_empty_dag_raises():
    with pytest.raises(ValueError):
        DAG([])


def test_two_roots_raises():
    with pytest.raises(ValueError, match="exactly one root"):
        DAG([Rule("A", []), Rule("B", ["A"]), Rule("X", []), Rule("Y", ["X"])])


def test_cycle_detection():
    with pytest.raises(CycleError):
        DAG([Rule("A", ["B"]), Rule("B", ["A"])])


def test_three_way_cycle():
    with pytest.raises(CycleError):
        DAG([Rule("A", ["C"]), Rule("B", ["A"]), Rule("C", ["B"])])


def test_unknown_override_target():
    with pytest.raises(ValueError):
        DAG([Rule("A", ["UNKNOWN"])])


def test_duplicate_rule_id():
    with pytest.raises(ValueError):
        DAG([Rule("A", []), Rule("A", [])])


# ── evaluate-time input validation ────────────────────────────────────────────


def test_evaluate_missing_condition_raises():
    d = DAG([Rule("A", []), Rule("B", ["A"])])
    with pytest.raises(ValueError, match="conditions missing"):
        d.evaluate({"A": True}, {"A": "A_val", "B": "B_val"})


def test_evaluate_missing_value_raises():
    d = DAG([Rule("A", []), Rule("B", ["A"])])
    with pytest.raises(ValueError, match="values missing"):
        d.evaluate({"A": True, "B": True}, {"A": "A_val"})


# ── conflict ───────────────────────────────────────────────────────────────────


def test_conflict_two_sibling_exceptions():
    d, c, v = dag(
        [
            ("A", True, "A_val", []),
            ("B", True, "B_val", ["A"]),
            ("D", True, "D_val", ["A"]),
        ]
    )
    with pytest.raises(ConflictError) as exc_info:
        d.evaluate(c, v)
    assert set(exc_info.value.rule_ids) >= {"B", "D"}


# ── defeater rules (_BLOCKS) ───────────────────────────────────────────────────


def test_blocker_blocks_exception_base_applies():
    assert (
        ev(
            [
                ("A", True, "A_val", []),
                ("B", True, "B_val", ["A"]),
                ("C", True, _BLOCKS, ["B"]),
            ]
        )
        == "A_val"
    )


def test_blocker_false_exception_applies():
    assert (
        ev(
            [
                ("A", True, "A_val", []),
                ("B", True, "B_val", ["A"]),
                ("C", False, _BLOCKS, ["B"]),
            ]
        )
        == "B_val"
    )


def test_two_blockers_no_conflict():
    assert (
        ev(
            [
                ("A", True, "A_val", []),
                ("B", True, "B_val", ["A"]),
                ("C", True, _BLOCKS, ["B"]),
                ("E", True, _BLOCKS, ["B"]),
            ]
        )
        == "A_val"
    )


def test_blocker_frees_sibling_exception():
    assert (
        ev(
            [
                ("A", True, "A_val", []),
                ("B", True, "B_val", ["A"]),
                ("D", True, "D_val", ["A"]),
                ("C", True, _BLOCKS, ["B"]),
            ]
        )
        == "D_val"
    )


def test_blocker_false_sibling_conflict():
    d, c, v = dag(
        [
            ("A", True, "A_val", []),
            ("B", True, "B_val", ["A"]),
            ("D", True, "D_val", ["A"]),
            ("C", False, _BLOCKS, ["B"]),
        ]
    )
    with pytest.raises(ConflictError):
        d.evaluate(c, v)


def test_blocker_on_false_base_not_applicable():
    d, c, v = dag(
        [
            ("A", False, "A_val", []),
            ("B", False, "B_val", ["A"]),
            ("C", True, _BLOCKS, ["B"]),
        ]
    )
    assert d.evaluate(c, v) is NOT_APPLICABLE


# ── DAG reuse across evaluations ──────────────────────────────────────────────


def test_dag_reused_different_inputs():
    d = DAG([Rule("A", []), Rule("B", ["A"])])
    assert d.evaluate({"A": True, "B": True}, {"A": "A_val", "B": "B_val"}) == "B_val"
    assert d.evaluate({"A": True, "B": False}, {"A": "A_val", "B": "B_val"}) == "A_val"


def test_two_independent_chains_each_own_dag():
    dag_ab = DAG([Rule("A", []), Rule("B", ["A"])])
    dag_xy = DAG([Rule("X", []), Rule("Y", ["X"])])
    assert (
        dag_ab.evaluate({"A": True, "B": True}, {"A": "A_val", "B": "B_val"}) == "B_val"
    )
    assert (
        dag_xy.evaluate({"X": True, "Y": True}, {"X": "X_val", "Y": "Y_val"}) == "Y_val"
    )


# ── 7701(b)(3) ────────────────────────────────────────────────────────────────

_7701_B3_DAG = DAG(
    [
        Rule("7701(b)(3)(A)", []),
        Rule("7701(b)(3)(B)", ["7701(b)(3)(A)"]),
        Rule("7701(b)(3)(C)", ["7701(b)(3)(B)"]),
    ]
)


def _spt(days_current, days_1st, days_2nd):
    return (days_current >= 31) and (
        days_current + days_1st / 3.0 + days_2nd / 6.0 >= 183
    )


def _closer_connection(days_current, has_foreign_home, has_closer_connection):
    return days_current < 183 and has_foreign_home and has_closer_connection


def _bars_closer(pending_lpr, took_lpr_steps):
    return pending_lpr or took_lpr_steps


def eval_7701_b3(
    days_current,
    days_1st,
    days_2nd,
    has_foreign_home=False,
    has_closer_connection=False,
    pending_lpr=False,
    took_lpr_steps=False,
):
    spt_val = _spt(days_current, days_1st, days_2nd)
    closer_cond = _closer_connection(
        days_current, has_foreign_home, has_closer_connection
    )
    bars_cond = _bars_closer(pending_lpr, took_lpr_steps)
    conditions = {
        "7701(b)(3)(A)": True,
        "7701(b)(3)(B)": closer_cond,
        "7701(b)(3)(C)": bars_cond,
    }
    values = {
        "7701(b)(3)(A)": spt_val,
        "7701(b)(3)(B)": False,
        "7701(b)(3)(C)": spt_val,
    }
    return _7701_B3_DAG.evaluate(conditions, values)


def test_7701_b3_spt_met_no_exceptions():
    assert eval_7701_b3(200, 0, 0) is True


def test_7701_b3_spt_not_met():
    assert eval_7701_b3(10, 0, 0) is False


def test_7701_b3_closer_connection_exception():
    assert (
        eval_7701_b3(100, 100, 100, has_foreign_home=True, has_closer_connection=True)
        is False
    )


def test_7701_b3_closer_connection_barred_by_lpr():
    assert (
        eval_7701_b3(
            100,
            249,
            0,
            has_foreign_home=True,
            has_closer_connection=True,
            pending_lpr=True,
        )
        is True
    )
