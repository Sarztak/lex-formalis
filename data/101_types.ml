(* shared types for § 101 *)

type date = { year : int; month : int; day : int }
(* a calendar date, used for certification dates and contract issue dates *)

type age = int
(* an individual's age in whole years, e.g. the age-95 benchmark in 101(f)(2)(C) *)

type premium_amount = float
(* a dollar amount of premium payable under a life insurance contract *)

type guideline_computation_rate = Rate_4_percent | Rate_6_percent
(* 101(f)(2)(C): interest rate basis used to compute a guideline premium; 4% is substituted for the ordinary 6% used for the guideline single premium *)

type guideline_level_premium = {
  annual_amount : premium_amount;
  minimum_years_from_issue : int;
  maximum_age : age option;
  computation_rate : guideline_computation_rate;
}
(* 101(f)(2)(C): guideline level premium, a level annual amount payable over the longest permitted period, ending not less than the given number of years from issue or not later than the given age if earlier *)

type qualified_additional_benefit = Qualified_additional_benefit
(* 101(f)(3)(A): a qualified additional benefit that may be included within a flexible premium life insurance contract *)

type premium_schedule = Fixed_timing_and_amount | Flexible_timing_or_amount
(* 101(f)(3)(A): whether a contract's premiums are fixed by the insurer as to both timing and amount *)

type annuity_benefit_treatment = Settlement_option | Other_annuity_benefit
(* 101(f)(3)(A): State-law characterization of a contract portion as providing annuity benefits, relevant to the exclusion from flexible premium contract treatment *)

type flexible_premium_life_insurance_contract = {
  qualified_additional_benefits : qualified_additional_benefit list;
  premium_schedule : premium_schedule;
  excluded_annuity_portion : annuity_benefit_treatment option;
}
(* 101(f)(3)(A): flexible premium life insurance contract, excluding any portion treated under State law as an annuity benefit other than as a settlement option *)

type physician = Physician
(* 101(g)(4)(D): a physician as defined in section 1861(r)(1) of the Social Security Act *)

type terminally_ill_individual = {
  certifying_physician : physician;
  certification_date : date;
  expected_death_within_months : int;
}
(* 101(g)(4)(A): an individual certified by a physician as reasonably expected to die within a given number of months (24) after the certification date *)

type chronically_ill_individual = {
  meets_7702b_c2_definition : bool;
  terminally_ill_status : terminally_ill_individual option;
}
(* 101(g)(4)(B): an individual meeting the chronically ill definition of section 7702B(c)(2), excluding any individual who is terminally ill *)

type qualified_long_term_care_services = Qualified_long_term_care_services
(* 101(g)(4)(C): services meeting the definition in section 7702B(c) *)

type citizenship_status = US_citizen | US_resident
(* 101(j)(5)(B): an insured must be a United States citizen or resident *)

type individual = { citizenship_status : citizenship_status }
(* a natural person, characterized by citizenship/residency status relevant to insured status *)

type insured =
  | Single_insured of individual
  | Joint_insured of individual * individual
(* 101(j)(5)(B): the individual(s) covered by an employer-owned life insurance contract; a contract on joint lives covers both individuals *)

type employee =
  | Common_law_employee
  | Self_employed_individual
  | Officer
  | Director
  | Highly_compensated_employee
(* 101(i)(3) and 101(j)(5)(A): "employee" as extended to include a self-employed individual (section 401(c)(1)), and an officer, director, or highly compensated employee (section 414(q)) *)

type person = Person
(* 101(j)(3)(A)(i): the person described as owning an employer-owned life insurance contract *)

type applicable_policyholder = { owning_person : person }
(* 101(j)(3)(B)(i): the person described in subparagraph (A)(i) who owns an employer-owned life insurance contract *)

type employer_owned_life_insurance_contract = {
  policyholder : applicable_policyholder;
  insured : insured;
}
(* the employer-owned life insurance contract referenced by 101(j)(3)(B)(i) and 101(j)(5)(B), relating an applicable policyholder to its insured *)
