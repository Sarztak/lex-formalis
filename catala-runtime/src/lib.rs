// Catala runtime for the Rust backend.
// Uses num-bigint / num-rational for correct integer and rational arithmetic.

use num_bigint::BigInt;
use num_rational::BigRational;
use num_traits::{Zero, One, ToPrimitive};
use std::fmt;
use std::ops::{Add, Sub, Mul, Div, Neg};

// ── Core numeric types ────────────────────────────────────────────────────────

/// Arbitrary-precision integer (maps to Catala integer / TLit TInt).
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Integer(pub BigInt);

impl Integer {
    pub fn from_str(s: &str) -> Self {
        Integer(s.parse().expect("bad integer literal"))
    }
    pub fn to_usize(&self) -> Option<usize> { self.0.to_usize() }
}

impl fmt::Display for Integer {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result { self.0.fmt(f) }
}

impl From<i64> for Integer { fn from(n: i64) -> Self { Integer(BigInt::from(n)) } }
impl From<usize> for Integer { fn from(n: usize) -> Self { Integer(BigInt::from(n)) } }
impl Zero for Integer {
    fn zero() -> Self { Integer(BigInt::zero()) }
    fn is_zero(&self) -> bool { self.0.is_zero() }
}
impl One for Integer {
    fn one() -> Self { Integer(BigInt::one()) }
}
impl Add for Integer { type Output = Self; fn add(self, r: Self) -> Self { Integer(self.0 + r.0) } }
impl Sub for Integer { type Output = Self; fn sub(self, r: Self) -> Self { Integer(self.0 - r.0) } }
impl Mul for Integer { type Output = Self; fn mul(self, r: Self) -> Self { Integer(self.0 * r.0) } }
impl Div for Integer { type Output = Self; fn div(self, r: Self) -> Self { Integer(self.0 / r.0) } }
impl Neg for Integer { type Output = Self; fn neg(self) -> Self { Integer(-self.0) } }
impl std::iter::Sum for Integer {
    fn sum<I: Iterator<Item = Self>>(iter: I) -> Self {
        iter.fold(Integer::zero(), |a, b| a + b)
    }
}

/// Rational number (maps to Catala decimal / TLit TRat).
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Decimal(pub BigRational);

impl Decimal {
    pub fn from_str(s: &str) -> Self {
        if let Some(pos) = s.find('/') {
            let n: BigInt = s[..pos].parse().expect("bad rational numer");
            let d: BigInt = s[pos+1..].parse().expect("bad rational denom");
            Decimal(BigRational::new(n, d))
        } else {
            let n: BigInt = s.parse().expect("bad decimal literal");
            Decimal(BigRational::from(n))
        }
    }
}

impl From<i64> for Decimal { fn from(n: i64) -> Self { Decimal(BigRational::from(BigInt::from(n))) } }
impl From<Integer> for Decimal { fn from(n: Integer) -> Self { Decimal(BigRational::from(n.0)) } }
impl Zero for Decimal {
    fn zero() -> Self { Decimal(BigRational::zero()) }
    fn is_zero(&self) -> bool { self.0.is_zero() }
}
impl Add for Decimal { type Output = Self; fn add(self, r: Self) -> Self { Decimal(self.0 + r.0) } }
impl Sub for Decimal { type Output = Self; fn sub(self, r: Self) -> Self { Decimal(self.0 - r.0) } }
impl Mul for Decimal { type Output = Self; fn mul(self, r: Self) -> Self { Decimal(self.0 * r.0) } }
impl Div for Decimal { type Output = Self; fn div(self, r: Self) -> Self { Decimal(self.0 / r.0) } }
impl std::iter::Sum for Decimal {
    fn sum<I: Iterator<Item = Self>>(iter: I) -> Self {
        iter.fold(Decimal::zero(), |a, b| a + b)
    }
}

impl fmt::Display for Decimal {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result { self.0.fmt(f) }
}

// ── Money ─────────────────────────────────────────────────────────────────────

/// Integer number of cents (Catala money / TLit TMoney).
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Money(pub BigInt);

impl Money {
    pub fn from_cents_str(s: &str) -> Self {
        Money(s.parse().expect("bad money literal"))
    }
    pub fn cents(&self) -> &BigInt { &self.0 }
}

impl fmt::Display for Money {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let cents: BigInt = &self.0 % 100i64;
        write!(f, "{}.{:02}", &self.0 / 100i64, cents.magnitude())
    }
}

impl std::iter::Sum for Money {
    fn sum<I: Iterator<Item = Self>>(iter: I) -> Self {
        iter.fold(Money(BigInt::zero()), |a, b| Money(a.0 + b.0))
    }
}

// ── Date ──────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Date { pub year: i32, pub month: u8, pub day: u8 }

impl Date {
    pub fn new(year: i32, month: i32, day: i32) -> Self {
        Date { year, month: month as u8, day: day as u8 }
    }
}

// ── Duration ──────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Duration { pub years: i32, pub months: i32, pub days: i32 }

impl Duration {
    pub fn new(years: i32, months: i32, days: i32) -> Self {
        Duration { years, months, days }
    }
}

// ── SourcePosition ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SourcePosition {
    pub file: &'static str,
    pub start_line: i32,
    pub start_column: i32,
    pub end_line: i32,
    pub end_column: i32,
}

// ── DateRounding ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum DateRounding { RoundUp, RoundDown, AbortOnRound }

// ── Errors ────────────────────────────────────────────────────────────────────

pub fn catala_fatal_error(kind: &str, pos: SourcePosition) -> ! {
    panic!("Catala fatal error [{}] at {}:{}:{}", kind, pos.file, pos.start_line, pos.start_column)
}

pub fn catala_debug_print(label: &str, value: &str) {
    eprintln!("[{}] {}", label, value)
}

// ── Exception handling ────────────────────────────────────────────────────────

pub fn handle_exceptions<T: Clone>(
    items: Vec<T>,
    is_none: impl Fn(&T) -> bool,
    none: T,
) -> T {
    let mut found: Option<T> = None;
    for item in &items {
        if !is_none(item) {
            match found {
                None => found = Some(item.clone()),
                Some(_) => panic!("Catala conflict error: multiple active exceptions"),
            }
        }
    }
    found.unwrap_or(none)
}

// ── Arithmetic operators ──────────────────────────────────────────────────────

pub fn o_add_int_int(a: Integer, b: Integer) -> Integer { a + b }
pub fn o_sub_int_int(a: Integer, b: Integer) -> Integer { a - b }
pub fn o_mult_int_int(a: Integer, b: Integer) -> Integer { a * b }
pub fn o_div_int_int(pos: SourcePosition, a: Integer, b: Integer) -> Integer {
    if b.is_zero() { catala_fatal_error("DivisionByZero", pos) }
    Integer(a.0 / b.0)
}

pub fn o_add_rat_rat(a: Decimal, b: Decimal) -> Decimal { a + b }
pub fn o_sub_rat_rat(a: Decimal, b: Decimal) -> Decimal { a - b }
pub fn o_mult_rat_rat(a: Decimal, b: Decimal) -> Decimal { a * b }
pub fn o_div_rat_rat(pos: SourcePosition, a: Decimal, b: Decimal) -> Decimal {
    if b.is_zero() { catala_fatal_error("DivisionByZero", pos) }
    a / b
}

pub fn o_add_mon_mon(a: Money, b: Money) -> Money { Money(a.0 + b.0) }
pub fn o_sub_mon_mon(a: Money, b: Money) -> Money { Money(a.0 - b.0) }

pub fn o_mult_mon_rat(m: Money, r: Decimal) -> Money {
    let result = BigRational::from(m.0) * r.0;
    // truncate toward zero (matching Catala's money rounding)
    Money(result.numer() / result.denom())
}

pub fn o_div_mon_mon(pos: SourcePosition, a: Money, b: Money) -> Decimal {
    if b.0.is_zero() { catala_fatal_error("DivisionByZero", pos) }
    Decimal(BigRational::new(a.0, b.0))
}
pub fn o_div_mon_int(pos: SourcePosition, a: Money, b: Integer) -> Money {
    if b.is_zero() { catala_fatal_error("DivisionByZero", pos) }
    Money(a.0 / b.0)
}
pub fn o_div_mon_rat(pos: SourcePosition, a: Money, r: Decimal) -> Money {
    if r.is_zero() { catala_fatal_error("DivisionByZero", pos) }
    let result = BigRational::from(a.0) / r.0;
    Money(result.numer() / result.denom())
}
pub fn o_mult_mon_int(m: Money, n: Integer) -> Money { Money(m.0 * n.0) }

pub fn o_int_to_rat(n: Integer) -> Decimal { Decimal::from(n) }
pub fn o_money_to_rat(m: Money) -> Decimal { Decimal(BigRational::new(m.0, BigInt::from(100))) }
pub fn o_rat_to_int(r: Decimal) -> Integer { Integer(r.0.numer() / r.0.denom()) }
pub fn o_rat_to_money(r: Decimal) -> Money {
    let cents = r.0 * BigRational::from(BigInt::from(100));
    Money(cents.numer() / cents.denom())
}

pub fn o_add_dat_dur(_r: DateRounding, d: Date, dur: Duration) -> Date {
    let mut y = d.year + dur.years;
    let mut m = d.month as i32 + dur.months;
    let day = d.day as i32 + dur.days;
    while m > 12 { m -= 12; y += 1; }
    while m < 1  { m += 12; y -= 1; }
    Date { year: y, month: m as u8, day: day as u8 }
}
pub fn o_sub_dat_dur(r: DateRounding, d: Date, dur: Duration) -> Date {
    o_add_dat_dur(r, d, Duration { years: -dur.years, months: -dur.months, days: -dur.days })
}
pub fn o_sub_dat_dat(a: Date, b: Date) -> Duration {
    Duration {
        years: a.year - b.year,
        months: a.month as i32 - b.month as i32,
        days: a.day as i32 - b.day as i32,
    }
}

// ── Comparison operators ──────────────────────────────────────────────────────

pub fn o_lt<T: PartialOrd>(_pos: SourcePosition, a: T, b: T) -> bool { a < b }
pub fn o_lte<T: PartialOrd>(_pos: SourcePosition, a: T, b: T) -> bool { a <= b }
pub fn o_gt<T: PartialOrd>(_pos: SourcePosition, a: T, b: T) -> bool { a > b }
pub fn o_gte<T: PartialOrd>(_pos: SourcePosition, a: T, b: T) -> bool { a >= b }
pub fn o_eq_int_int(_pos: SourcePosition, a: Integer, b: Integer) -> bool { a == b }
pub fn o_eq_rat_rat(_pos: SourcePosition, a: Decimal, b: Decimal) -> bool { a == b }
pub fn o_eq_mon_mon(_pos: SourcePosition, a: Money, b: Money) -> bool { a == b }
pub fn o_eq_dat_dat(_pos: SourcePosition, a: Date, b: Date) -> bool { a == b }
pub fn o_eq_boo_boo(_pos: SourcePosition, a: bool, b: bool) -> bool { a == b }

pub fn o_lt_int_int(_pos: SourcePosition, a: Integer, b: Integer) -> bool { a < b }
pub fn o_lt_rat_rat(_pos: SourcePosition, a: Decimal, b: Decimal) -> bool { a < b }
pub fn o_lt_mon_mon(_pos: SourcePosition, a: Money, b: Money) -> bool { a < b }
pub fn o_lt_dat_dat(_pos: SourcePosition, a: Date, b: Date) -> bool { a < b }

pub fn o_lte_int_int(_pos: SourcePosition, a: Integer, b: Integer) -> bool { a <= b }
pub fn o_lte_rat_rat(_pos: SourcePosition, a: Decimal, b: Decimal) -> bool { a <= b }
pub fn o_lte_mon_mon(_pos: SourcePosition, a: Money, b: Money) -> bool { a <= b }
pub fn o_lte_dat_dat(_pos: SourcePosition, a: Date, b: Date) -> bool { a <= b }

pub fn o_gt_int_int(_pos: SourcePosition, a: Integer, b: Integer) -> bool { a > b }
pub fn o_gt_rat_rat(_pos: SourcePosition, a: Decimal, b: Decimal) -> bool { a > b }
pub fn o_gt_mon_mon(_pos: SourcePosition, a: Money, b: Money) -> bool { a > b }
pub fn o_gt_dat_dat(_pos: SourcePosition, a: Date, b: Date) -> bool { a > b }

pub fn o_gte_int_int(_pos: SourcePosition, a: Integer, b: Integer) -> bool { a >= b }
pub fn o_gte_rat_rat(_pos: SourcePosition, a: Decimal, b: Decimal) -> bool { a >= b }
pub fn o_gte_mon_mon(_pos: SourcePosition, a: Money, b: Money) -> bool { a >= b }
pub fn o_gte_dat_dat(_pos: SourcePosition, a: Date, b: Date) -> bool { a >= b }

// ── Boolean operators ─────────────────────────────────────────────────────────

pub fn o_not(b: bool) -> bool { !b }
pub fn o_and(a: bool, b: bool) -> bool { a && b }
pub fn o_or(a: bool, b: bool) -> bool { a || b }
pub fn o_xor(a: bool, b: bool) -> bool { a ^ b }

// ── Rounding ──────────────────────────────────────────────────────────────────

pub fn o_round_rat(r: Decimal) -> Integer {
    let half = BigRational::new(BigInt::from(1), BigInt::from(2));
    let shifted = if r.0 >= BigRational::zero() { r.0 + half } else { r.0 - half };
    Integer(shifted.numer() / shifted.denom())
}
pub fn o_round_mon(m: Money) -> Money { m }

pub fn o_minus_int(a: Integer) -> Integer { Integer(-a.0) }
pub fn o_minus_rat(a: Decimal) -> Decimal { Decimal(-a.0) }
pub fn o_minus_mon(a: Money) -> Money { Money(-a.0) }
pub fn o_minus_dur(a: Duration) -> Duration {
    Duration { years: -a.years, months: -a.months, days: -a.days }
}

// ── Array operators ───────────────────────────────────────────────────────────

pub fn o_length<T>(v: &[T]) -> Integer { Integer(BigInt::from(v.len())) }

pub fn o_get<T: Clone>(pos: SourcePosition, v: &[T], i: Integer) -> T {
    let idx = i.to_usize().expect("index out of range");
    if idx >= v.len() { catala_fatal_error("IndexOutOfBounds", pos) }
    v[idx].clone()
}

pub fn o_map<T: Clone, U>(v: Vec<T>, f: impl Fn(T) -> U) -> Vec<U> {
    v.into_iter().map(f).collect()
}
pub fn o_filter<T: Clone>(v: Vec<T>, f: impl Fn(&T) -> bool) -> Vec<T> {
    v.into_iter().filter(|x| f(x)).collect()
}
pub fn o_reduce<T: Clone>(v: Vec<T>, default: T, f: impl Fn(T, T) -> T) -> T {
    v.into_iter().reduce(f).unwrap_or(default)
}
pub fn o_fold<T: Clone, U: Clone>(v: Vec<T>, init: U, f: impl Fn(U, T) -> U) -> U {
    v.into_iter().fold(init, f)
}
pub fn o_concat<T: Clone>(a: Vec<T>, b: Vec<T>) -> Vec<T> {
    let mut result = a; result.extend(b); result
}
pub fn o_contains<T: PartialEq>(v: &[T], x: &T) -> bool { v.contains(x) }
pub fn o_count<T>(v: &[T]) -> Integer { Integer(BigInt::from(v.len())) }
pub fn o_exists<T>(v: Vec<T>, f: impl Fn(T) -> bool) -> bool { v.into_iter().any(f) }
pub fn o_for_all<T>(v: Vec<T>, f: impl Fn(T) -> bool) -> bool { v.into_iter().all(f) }
pub fn o_sum_int(v: Vec<Integer>) -> Integer { v.into_iter().sum() }
pub fn o_sum_mon(v: Vec<Money>) -> Money { v.into_iter().sum() }
pub fn o_sum_rat(v: Vec<Decimal>) -> Decimal { v.into_iter().sum() }
pub fn o_sum_dur(v: Vec<Duration>) -> Duration {
    v.into_iter().fold(Duration::new(0, 0, 0), |a, b| Duration {
        years: a.years + b.years,
        months: a.months + b.months,
        days: a.days + b.days,
    })
}
