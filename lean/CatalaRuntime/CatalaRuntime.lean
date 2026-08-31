/-
  CatalaRuntime — Lean 4 runtime for Catala-generated code.

  Generated files import this module and call functions defined here.
  All public names are in the `CatalaRuntime` namespace.
-/

namespace CatalaRuntime

-- ── Source positions ──────────────────────────────────────────────────────────

structure SourcePos where
  file        : String := ""
  startLine   : Nat    := 0
  startColumn : Nat    := 0
  endLine     : Nat    := 0
  endColumn   : Nat    := 0
  deriving Repr, Inhabited

def SourcePos.dummy : SourcePos := {}

-- ── Date and duration ─────────────────────────────────────────────────────────

structure CatalaDate where
  year  : Int
  month : Int
  day   : Int
  deriving Repr, DecidableEq, BEq, Inhabited

structure CatalaDuration where
  years  : Int
  months : Int
  days   : Int
  deriving Repr, DecidableEq, BEq, Inhabited

-- ── Rounding mode (used by date arithmetic) ───────────────────────────────────

inductive RoundingMode where
  | RoundUp
  | RoundDown
  | AbortOnRound
  deriving Repr, DecidableEq

-- ── Error handling ────────────────────────────────────────────────────────────

-- panic! requires Inhabited α; callers in monomorphic context always satisfy it.
def catalaFatalError {α : Type} [Inhabited α] (kind : String) : α :=
  panic! s!"[Catala] fatal error: {kind}"

/--
  Handle a priority-ordered array of optional values.
  Returns none when no exception fires, panics on conflict.
  Matches the OCaml runtime `handle_exceptions` semantics.
-/
def catalaHandleExceptions {α : Type} [Inhabited α] (items : Array (Option α)) : Option α :=
  let active := items.filterMap id
  match active.size with
  | 0 => none
  | 1 => some active[0]!
  | _ => catalaFatalError "ConflictError"

-- ── Array access ─────────────────────────────────────────────────────────────

-- Generated as `catala_o_array_nth(n) arr` — Lean reads `(n)` as a parenthesised arg.
def catala_o_array_nth {α : Type} [Inhabited α] (n : Nat) (arr : Array α) : α :=
  arr[n]!

-- ── Boolean operators ─────────────────────────────────────────────────────────

def catala_o_xor (a b : Bool) : Bool := a != b

-- ── Integer arithmetic ────────────────────────────────────────────────────────

def catala_o_minus_int (a : Int) : Int := -a
def catala_o_add_int_int (a b : Int) : Int := a + b
def catala_o_sub_int_int (a b : Int) : Int := a - b
def catala_o_mult_int_int (a b : Int) : Int := a * b
def catala_o_div_int_int (a b : Int) (_pos : SourcePos) : Int :=
  if b == 0 then catalaFatalError "DivisionByZero" else a / b

-- ── Rational arithmetic ───────────────────────────────────────────────────────

def catala_o_minus_rat (a : Rat) : Rat := -a
def catala_o_add_rat_rat (a b : Rat) : Rat := a + b
def catala_o_sub_rat_rat (a b : Rat) : Rat := a - b
def catala_o_mult_rat_rat (a b : Rat) : Rat := a * b
def catala_o_div_rat_rat (a b : Rat) (_pos : SourcePos) : Rat :=
  if b == 0 then catalaFatalError "DivisionByZero" else a / b

-- ── Money arithmetic (money = Int cents) ──────────────────────────────────────

def catala_o_minus_mon (a : Int) : Int := -a
def catala_o_add_mon_mon (a b : Int) : Int := a + b
def catala_o_sub_mon_mon (a b : Int) : Int := a - b
def catala_o_mult_mon_int (a b : Int) : Int := a * b
-- money × rational: round toward zero after multiplying
def catala_o_mult_mon_rat (m : Int) (r : Rat) : Int :=
  (m * r.num) / (r.den : Int)
def catala_o_div_mon_mon (a b : Int) (_pos : SourcePos) : Rat :=
  if b == 0 then catalaFatalError "DivisionByZero" else (a : Rat) / (b : Rat)
def catala_o_div_mon_int (a b : Int) (_pos : SourcePos) : Int :=
  if b == 0 then catalaFatalError "DivisionByZero" else a / b
def catala_o_div_mon_rat (m : Int) (r : Rat) (_pos : SourcePos) : Int :=
  if r == 0 then catalaFatalError "DivisionByZero"
  else ((m : Rat) / r).num

-- ── Duration arithmetic ───────────────────────────────────────────────────────

def catala_o_minus_dur (d : CatalaDuration) : CatalaDuration :=
  { years := -d.years, months := -d.months, days := -d.days }
def catala_o_add_dur_dur (a b : CatalaDuration) : CatalaDuration :=
  { years := a.years + b.years, months := a.months + b.months, days := a.days + b.days }
def catala_o_sub_dur_dur (a b : CatalaDuration) : CatalaDuration :=
  catala_o_add_dur_dur a (catala_o_minus_dur b)
def catala_o_mult_dur_int (d : CatalaDuration) (n : Int) : CatalaDuration :=
  { years := d.years * n, months := d.months * n, days := d.days * n }
def catala_o_div_dur_dur (a b : CatalaDuration) (_pos : SourcePos) : Rat :=
  let aDays : Int := a.years * 365 + a.months * 30 + a.days
  let bDays : Int := b.years * 365 + b.months * 30 + b.days
  if bDays == 0 then catalaFatalError "DivisionByZero"
  else (aDays : Rat) / (bDays : Rat)

-- ── Date arithmetic ───────────────────────────────────────────────────────────

def catala_o_add_dat_dur (mode : RoundingMode) (d : CatalaDate) (dur : CatalaDuration)
    (_pos : SourcePos) : CatalaDate :=
  let _ := mode  -- rounding advisory; simplified implementation ignores it
  { year  := d.year  + dur.years
  , month := d.month + dur.months
  , day   := d.day   + dur.days }

def catala_o_sub_dat_dur (mode : RoundingMode) (d : CatalaDate) (dur : CatalaDuration)
    (_pos : SourcePos) : CatalaDate :=
  catala_o_add_dat_dur mode d (catala_o_minus_dur dur) _pos

def catala_o_sub_dat_dat (a b : CatalaDate) : CatalaDuration :=
  { years := a.year - b.year, months := a.month - b.month, days := a.day - b.day }

-- ── Type conversions ──────────────────────────────────────────────────────────

def catala_o_torat_int (n : Int) : Rat := (n : Rat)
def catala_o_torat_mon (m : Int) : Rat := (m : Rat) / 100
def catala_o_toint_rat (r : Rat) : Int := r.floor
def catala_o_toint_mon (m : Int) : Int := m / 100
def catala_o_tomoney_int (n : Int) : Int := n * 100
def catala_o_tomoney_rat (r : Rat) : Int := (r * 100).floor

def catala_o_round_rat (r : Rat) : Rat :=
  if r - r.floor >= (1 / 2 : Rat) then r.ceil else r.floor
def catala_o_round_mon (m : Int) : Int := m

-- ── Collection operators ──────────────────────────────────────────────────────

def catala_o_length {α : Type} (arr : Array α) : Int := arr.size

def catala_o_map {α β : Type} (f : α → β) (arr : Array α) : Array β := arr.map f

def catala_o_filter {α : Type} (pred : α → Bool) (arr : Array α) : Array α :=
  arr.filter pred

def catala_o_fold {α β : Type} (f : β → α → β) (init : β) (arr : Array α) : β :=
  arr.foldl f init

def catala_o_reduce {α : Type} [Inhabited α] (f : α → α → α) (init : α) (arr : Array α) : α :=
  arr.foldl f init

def catala_o_map2 {α β γ : Type} [Inhabited γ] (f : α → β → γ)
    (as_ : Array α) (bs : Array β) (_pos : SourcePos) : Array γ :=
  if as_.size != bs.size then catalaFatalError "Map2SizeMismatch"
  else (as_.zip bs).map (fun (a, b) => f a b)

def catala_o_find {α : Type} (pred : α → Bool) (arr : Array α) : Option α :=
  arr.find? pred

def catala_o_sort_asc {α : Type} [Ord α] (arr : Array α) : Array α :=
  arr.qsort (fun a b => compare a b == Ordering.lt)

def catala_o_sort_desc {α : Type} [Ord α] (arr : Array α) : Array α :=
  arr.qsort (fun a b => compare a b == Ordering.gt)

-- ── String operators ──────────────────────────────────────────────────────────

def catala_o_concat (a b : String) : String := a ++ b

-- ── Closure env stubs ─────────────────────────────────────────────────────────

def catala_o_toclosureenv {α : Type} (x : α) : α := x
def catala_o_fromclosureenv {α β : Type} [Inhabited β] (_env : α) : β :=
  catalaFatalError "ClosureEnvAccess"

end CatalaRuntime
