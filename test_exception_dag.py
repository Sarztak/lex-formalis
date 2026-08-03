import pytest

from exception_dag import ConflictError, CycleError, DAG, GapError, Rule


# helpers — condition/value functions take an inputs dict

def always_true(inputs):
    return True

def always_false(inputs):
    return False

def val(v):
    return lambda inputs: v

def cond(key):
    return lambda inputs: inputs[key]

def get(key):
    return lambda inputs: inputs[key]


# ── basic resolution ───────────────────────────────────────────────────────────

def test_simple_exception_fires():
    dag = DAG([
        Rule("A", always_true, val("A_val"), exceptions=[]),
        Rule("B", always_true, val("B_val"), exceptions=["A"]),
    ])
    assert dag.evaluate({}) == "B_val"


def test_simple_exception_does_not_fire():
    dag = DAG([
        Rule("A", always_true,  val("A_val"), exceptions=[]),
        Rule("B", always_false, val("B_val"), exceptions=["A"]),
    ])
    assert dag.evaluate({}) == "A_val"


def test_chain_deepest_fires():
    dag = DAG([
        Rule("A", always_true, val("A_val"), exceptions=[]),
        Rule("B", always_true, val("B_val"), exceptions=["A"]),
        Rule("C", always_true, val("C_val"), exceptions=["B"]),
    ])
    assert dag.evaluate({}) == "C_val"


def test_chain_middle_fires():
    dag = DAG([
        Rule("A", always_true,  val("A_val"), exceptions=[]),
        Rule("B", always_true,  val("B_val"), exceptions=["A"]),
        Rule("C", always_false, val("C_val"), exceptions=["B"]),
    ])
    assert dag.evaluate({}) == "B_val"


def test_chain_none_fire_falls_to_base():
    dag = DAG([
        Rule("A", always_true,  val("A_val"), exceptions=[]),
        Rule("B", always_false, val("B_val"), exceptions=["A"]),
        Rule("C", always_false, val("C_val"), exceptions=["B"]),
    ])
    assert dag.evaluate({}) == "A_val"


# ── inputs passed through ─────────────────────────────────────────────────────

def test_inputs_passed_to_condition_and_value():
    dag = DAG([
        Rule("A", always_true,   get("base"),     exceptions=[]),
        Rule("B", cond("b_on"),  get("override"), exceptions=["A"]),
    ])
    assert dag.evaluate({"b_on": True,  "base": 10, "override": 99}) == 99
    assert dag.evaluate({"b_on": False, "base": 10, "override": 99}) == 10


# ── error cases ────────────────────────────────────────────────────────────────

def test_conflict_two_sibling_exceptions():
    dag = DAG([
        Rule("A", always_true, val("A_val"), exceptions=[]),
        Rule("B", always_true, val("B_val"), exceptions=["A"]),
        Rule("D", always_true, val("D_val"), exceptions=["A"]),
    ])
    with pytest.raises(ConflictError) as exc_info:
        dag.evaluate({})
    assert "B" in exc_info.value.rule_ids or "D" in exc_info.value.rule_ids


def test_gap_base_condition_false():
    dag = DAG([
        Rule("A", always_false, val("A_val"), exceptions=[]),
    ])
    with pytest.raises(GapError):
        dag.evaluate({})


def test_gap_exception_doesnt_fire_base_false():
    dag = DAG([
        Rule("A", always_false, val("A_val"), exceptions=[]),
        Rule("B", always_false, val("B_val"), exceptions=["A"]),
    ])
    with pytest.raises(GapError):
        dag.evaluate({})


def test_cycle_detection():
    with pytest.raises(CycleError):
        DAG([
            Rule("A", always_true, val("A"), exceptions=["B"]),
            Rule("B", always_true, val("B"), exceptions=["A"]),
        ])


def test_three_way_cycle():
    with pytest.raises(CycleError):
        DAG([
            Rule("A", always_true, val("A"), exceptions=["C"]),
            Rule("B", always_true, val("B"), exceptions=["A"]),
            Rule("C", always_true, val("C"), exceptions=["B"]),
        ])


def test_unknown_override_target():
    with pytest.raises(ValueError):
        DAG([Rule("A", always_true, val("A"), exceptions=["UNKNOWN"])])


def test_duplicate_rule_id():
    with pytest.raises(ValueError):
        DAG([
            Rule("A", always_true, val("A1"), exceptions=[]),
            Rule("A", always_true, val("A2"), exceptions=[]),
        ])


def test_empty_rules():
    with pytest.raises(GapError):
        DAG([]).evaluate({})


# ── 7701(b)(3) ────────────────────────────────────────────────────────────────

def spt(inputs):
    d0 = inputs["days_current"]
    d1 = inputs["days_1st"]
    d2 = inputs["days_2nd"]
    return (d0 >= 31) and (d0 + d1 / 3.0 + d2 / 6.0 >= 183)

def closer_connection(inputs):
    return inputs["days_current"] < 183 and inputs["has_foreign_home"] and inputs["has_closer_connection"]

def bars_closer(inputs):
    return inputs["pending_lpr"] or inputs["took_lpr_steps"]


SUBSTANTIAL_PRESENCE_DAG = DAG([
    Rule("7701(b)(3)(A)", lambda i: True,      spt,          exceptions=[]),
    Rule("7701(b)(3)(B)", closer_connection,   lambda i: False, exceptions=["7701(b)(3)(A)"]),
    Rule("7701(b)(3)(C)", bars_closer,         spt,          exceptions=["7701(b)(3)(B)"]),
])


def make_inputs(days_current, days_1st, days_2nd,
                has_foreign_home=False, has_closer_connection=False,
                pending_lpr=False, took_lpr_steps=False):
    return dict(
        days_current=days_current,
        days_1st=days_1st,
        days_2nd=days_2nd,
        has_foreign_home=has_foreign_home,
        has_closer_connection=has_closer_connection,
        pending_lpr=pending_lpr,
        took_lpr_steps=took_lpr_steps,
    )


def test_7701_b_3_spt_met_no_exceptions():
    # 200 days current year, no exceptions — resident
    inputs = make_inputs(200, 0, 0)
    assert SUBSTANTIAL_PRESENCE_DAG.evaluate(inputs) is True


def test_7701_b_3_spt_not_met():
    # only 10 days — not resident
    inputs = make_inputs(10, 0, 0)
    assert SUBSTANTIAL_PRESENCE_DAG.evaluate(inputs) is False


def test_7701_b_3_closer_connection_exception():
    # SPT met but closer connection applies — not resident
    inputs = make_inputs(100, 100, 100, has_foreign_home=True, has_closer_connection=True)
    assert SUBSTANTIAL_PRESENCE_DAG.evaluate(inputs) is False


def test_7701_b_3_closer_connection_barred_by_lpr():
    # SPT met (100 + 249/3 = 183), closer connection would apply, but pending LPR bars it
    inputs = make_inputs(100, 249, 0,
                         has_foreign_home=True, has_closer_connection=True,
                         pending_lpr=True)
    assert SUBSTANTIAL_PRESENCE_DAG.evaluate(inputs) is True
