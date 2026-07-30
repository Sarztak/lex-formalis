<catala>
# Section 7701(b) — Definition of Resident Alien and Nonresident Alien
# Source: 26 U.S.C. § 7701(b)
# Pass: 1
# Status: INCOMPLETE — see signals

# ── Type Declarations ──────────────────────────────────────────────────────────

declaration enumeration ResidencyBasis:
  -- LawfulPermanentResident
  -- SubstantialPresence
  -- FirstYearElection

declaration enumeration ResidencyStatus:
  -- NonResident
  -- Resident content ResidencyBasis

declaration enumeration ForeignGovRelatedBasis:
  -- DiplomaticStatus
  -- InternationalOrganizationEmployee
  -- ImmediateFamilyMember

declaration structure QualifyingCharityEventDetail:
  data organized_to_benefit_501c3 content boolean
  data all_net_proceeds_to_501c3 content boolean
  data uses_volunteers_for_substantially_all_work content boolean

declaration structure FirstYearElectionQualDetail:
  data consecutive_days_present content integer
  data testing_period_days content integer
  data days_present_in_testing_period content integer

# ── § 7701(b)(7) — Presence in the United States ──────────────────────────────

declaration scope PresenceInUnitedStates:
  input physically_present_at_any_time_during_day content boolean
  input regularly_commutes_from_canada_or_mexico content boolean
  input in_transit_between_two_foreign_points content boolean
  input hours_present_during_transit content integer
  input is_crew_member_of_foreign_vessel content boolean
  input crew_member_engages_in_us_trade_or_business content boolean
  output treated_as_present content boolean

scope PresenceInUnitedStates:

  definition treated_as_present equals
    physically_present_at_any_time_during_day

  # § 7701(b)(7)(B) — Canadian/Mexican commuters
  exception definition treated_as_present
    under condition regularly_commutes_from_canada_or_mexico
    consequence equals false

  # § 7701(b)(7)(C) — Transit between two foreign points under 24 hours
  exception definition treated_as_present
    under condition
      in_transit_between_two_foreign_points and
      hours_present_during_transit < 24
    consequence equals false

  # § 7701(b)(7)(D) — Foreign vessel crew members not engaging in US trade/business
  exception definition treated_as_present
    under condition
      is_crew_member_of_foreign_vessel and
      not crew_member_engages_in_us_trade_or_business
    consequence equals false

# ── § 7701(b)(5) — Exempt Individual ─────────────────────────────────────────

declaration scope ExemptIndividualTest:
  input is_foreign_government_related content boolean
  input is_teacher_or_trainee content boolean
  input is_student content boolean
  input is_professional_athlete_temporarily_competing content boolean
  input professional_athlete_event content QualifyingCharityEventDetail
  input years_exempt_as_teacher_trainee_or_student_in_preceding_6_years content integer
  input all_compensation_described_in_section_872b3 content boolean
  input total_years_exempt_as_teacher_trainee_or_student content integer
  input student_does_not_intend_permanent_residency content boolean
  input student_substantially_complies_with_visa_requirements content boolean
  output is_exempt_individual content boolean

scope ExemptIndividualTest:

  definition qualifies_as_professional_athlete equals
    is_professional_athlete_temporarily_competing and
    professional_athlete_event.organized_to_benefit_501c3 and
    professional_athlete_event.all_net_proceeds_to_501c3 and
    professional_athlete_event.uses_volunteers_for_substantially_all_work

  definition is_exempt_individual equals
    is_foreign_government_related or
    is_teacher_or_trainee or
    is_student or
    qualifies_as_professional_athlete

  # § 7701(b)(5)(E)(i) — Teacher/trainee: exempt 2+ of preceding 6 years (standard)
  exception definition is_exempt_individual
    under condition
      is_teacher_or_trainee and
      not all_compensation_described_in_section_872b3 and
      years_exempt_as_teacher_trainee_or_student_in_preceding_6_years >= 2
    consequence equals false

  # § 7701(b)(5)(E)(i) — Teacher/trainee: exempt 4+ of preceding 6 years (§ 872(b)(3) exception)
  exception definition is_exempt_individual
    under condition
      is_teacher_or_trainee and
      all_compensation_described_in_section_872b3 and
      years_exempt_as_teacher_trainee_or_student_in_preceding_6_years >= 4
    consequence equals false

  # § 7701(b)(5)(E)(ii) — Student: after 5th cumulative exempt year
  exception definition is_exempt_individual
    under condition
      is_student and
      total_years_exempt_as_teacher_trainee_or_student > 5 and
      not (student_does_not_intend_permanent_residency and
           student_substantially_complies_with_visa_requirements)
    consequence equals false

# ── § 7701(b)(6) — Lawful Permanent Resident ─────────────────────────────────

declaration scope LawfulPermanentResidentTest:
  input has_lpr_privilege content boolean
  input lpr_status_revoked content boolean
  input lpr_status_administratively_abandoned content boolean
  input lpr_status_judicially_abandoned content boolean
  input treated_as_foreign_country_resident_under_tax_treaty content boolean
  input waived_foreign_country_treaty_benefits content boolean
  input notified_secretary_of_treaty_treatment content boolean
  output is_lawful_permanent_resident content boolean

scope LawfulPermanentResidentTest:

  definition is_lawful_permanent_resident equals
    has_lpr_privilege and
    not lpr_status_revoked and
    not lpr_status_administratively_abandoned and
    not lpr_status_judicially_abandoned

  # Cessation rule — treaty-based foreign residency terminates LPR status
  exception definition is_lawful_permanent_resident
    under condition
      treated_as_foreign_country_resident_under_tax_treaty and
      not waived_foreign_country_treaty_benefits and
      notified_secretary_of_treaty_treatment
    consequence equals false

# ── § 7701(b)(3) — Substantial Presence Test ─────────────────────────────────

declaration scope SubstantialPresenceTest:
  input days_current_year content integer
  input days_first_preceding_year content integer
  input days_second_preceding_year content integer
  input has_foreign_tax_home content boolean
  input closer_connection_to_foreign_country content boolean
  input adjustment_of_status_pending content boolean
  input steps_toward_permanent_residency content boolean
  output meets_test content boolean

scope SubstantialPresenceTest:

  definition weighted_days equals
    days_current_year * 1 +
    days_first_preceding_year * (1 / 3) +
    days_second_preceding_year * (1 / 6)

  definition meets_test equals
    days_current_year >= 31 and weighted_days >= 183

  # § 7701(b)(3)(B)-(C) — Closer connection exception (subparagraph (C) removes the exception)
  exception definition meets_test
    under condition
      days_current_year < 183 and
      has_foreign_tax_home and
      closer_connection_to_foreign_country and
      not adjustment_of_status_pending and
      not steps_toward_permanent_residency
    consequence equals false

# ── § 7701(b)(4) — First-Year Election ───────────────────────────────────────

declaration scope FirstYearElectionQualification:
  input is_lpr_in_election_year content boolean
  input meets_spt_in_election_year content boolean
  input was_resident_in_preceding_year content boolean
  input meets_spt_in_following_year content boolean
  input qual_detail content FirstYearElectionQualDetail
  input made_election content boolean
  input election_revoked_with_secretary_consent content boolean
  output qualifies_for_election content boolean
  output election_in_effect content boolean

scope FirstYearElectionQualification:

  definition absent_days_in_testing_period equals
    qual_detail.testing_period_days - qual_detail.days_present_in_testing_period

  # § 7701(b)(4)(A)(iv)(II) — up to 5 absent days treated as present
  definition absent_days_to_add equals
    if absent_days_in_testing_period <= 5 then
      absent_days_in_testing_period
    else 5

  definition days_effectively_present_in_testing_period equals
    qual_detail.days_present_in_testing_period + absent_days_to_add

  # 75% expressed as integer arithmetic: days * 4 >= period * 3
  definition meets_75_percent_test equals
    days_effectively_present_in_testing_period * 4 >=
    qual_detail.testing_period_days * 3

  definition qualifies_for_election equals
    not is_lpr_in_election_year and
    not meets_spt_in_election_year and
    not was_resident_in_preceding_year and
    meets_spt_in_following_year and
    qual_detail.consecutive_days_present >= 31 and
    meets_75_percent_test

  definition election_in_effect equals
    made_election and
    qualifies_for_election and
    not election_revoked_with_secretary_consent

# ── § 7701(b)(2)(C) — Nominal Presence Disregard ─────────────────────────────

declaration scope NominalPresenceDisregard:
  input days_with_closer_foreign_connection content integer
  output days_disregarded content integer

scope NominalPresenceDisregard:

  # Cap at 10 days per year
  definition days_disregarded equals
    if days_with_closer_foreign_connection <= 10 then
      days_with_closer_foreign_connection
    else 10

# ── § 7701(b)(2)(A) — Residency Starting Date ────────────────────────────────

declaration scope ResidencyStartingDate:
  input residency_basis content ResidencyBasis
  input first_day_present_in_year_as_lpr content date
  input first_day_present_in_year content date
  input first_day_of_earliest_qualifying_testing_period content date
  output residency_starting_date content date

scope ResidencyStartingDate:

  definition residency_starting_date equals
    match residency_basis with pattern
    -- LawfulPermanentResident : first_day_present_in_year_as_lpr
    -- SubstantialPresence : first_day_present_in_year
    -- FirstYearElection : first_day_of_earliest_qualifying_testing_period

# ── § 7701(b)(2)(B) — Last Year of Residency ─────────────────────────────────

declaration scope LastYearResidency:
  input residency_basis content ResidencyBasis
  input last_day_present_in_us content date
  input last_day_as_lpr content date
  input has_closer_connection_to_foreign_country_after_departure content boolean
  input is_resident_in_following_year content boolean
  input calendar_year_end content date
  output last_day_of_residency content date

scope LastYearResidency:

  definition departure_cutoff equals
    match residency_basis with pattern
    -- LawfulPermanentResident : last_day_as_lpr
    -- SubstantialPresence : last_day_present_in_us
    -- FirstYearElection : last_day_present_in_us

  definition last_year_cutoff_applies equals
    has_closer_connection_to_foreign_country_after_departure and
    not is_resident_in_following_year

  definition last_day_of_residency equals
    if last_year_cutoff_applies then departure_cutoff
    else calendar_year_end

# ── § 7701(b)(1) — Residency Determination ───────────────────────────────────

declaration scope ResidencyDetermination:
  input is_lawful_permanent_resident content boolean
  input meets_substantial_presence_test content boolean
  input first_year_election_in_effect content boolean
  output residency_status content ResidencyStatus

scope ResidencyDetermination:

  definition residency_status equals
    if is_lawful_permanent_resident then
      Resident content LawfulPermanentResident
    else if meets_substantial_presence_test then
      Resident content SubstantialPresence
    else if first_year_election_in_effect then
      Resident content FirstYearElection
    else
      NonResident
</catala>

<signals>
EXTERNAL_DEPENDENCY: tax_home | defined_in: § 911(d)(3) (second sentence excluded per § 7701(b)(3)(B)(ii))
EXTERNAL_DEPENDENCY: teacher_or_trainee visa status | defined_in: § 101(15)(J) and (Q) of Immigration and Nationality Act
EXTERNAL_DEPENDENCY: student visa status | defined_in: § 101(15)(F), (M), (J), and (Q) of Immigration and Nationality Act
EXTERNAL_DEPENDENCY: section_501c3_organization | defined_in: 26 U.S.C. § 501(c)(3)
EXTERNAL_DEPENDENCY: section_501a_tax_exemption | defined_in: 26 U.S.C. § 501(a)
EXTERNAL_DEPENDENCY: section_872b3_compensation | defined_in: 26 U.S.C. § 872(b)(3)
EXTERNAL_DEPENDENCY: diplomatic_status_visa_categories | defined_in: Secretary of Treasury determination after consultation with Secretary of State per § 7701(b)(5)(B)(i)
INPUT_TRANSFORM: days_current_year in SubstantialPresenceTest | condition: individual is an exempt individual on that day per § 7701(b)(3)(D)(i) | reduces_by: each day individual qualifies as exempt individual
INPUT_TRANSFORM: days_current_year in SubstantialPresenceTest | condition: individual unable to leave United States due to medical condition which arose while present per § 7701(b)(3)(D)(ii) | reduces_by: each medically unable-to-leave day
INPUT_TRANSFORM: days_present_in_testing_period in FirstYearElectionQualification | condition: individual is an exempt individual per § 7701(b)(4)(D) incorporating § 7701(b)(3)(D)(i) | reduces_by: each exempt-status day during testing period
INPUT_TRANSFORM: presence day counts for § 7701(b)(2)(A)(iii) and § 7701(b)(2)(B) | condition: individual establishes closer connection to foreign country during that period per § 7701(b)(2)(C) | reduces_by: up to 10 days per calendar year
MISSING_INPUT: first_day_present_in_year_as_lpr content date — requires preprocessing: scan per-day LPR status and presence records to find first day individual was both present and LPR
MISSING_INPUT: first_day_of_earliest_qualifying_testing_period content date — requires algorithmic search: find earliest 31-consecutive-day period in election year, then return its first day
MISSING_INPUT: is_resident_in_following_year content boolean — temporal dependency: next calendar year residency status not available during current year computation; requires iterative multi-year pass
MISSING_INPUT: was_resident_in_preceding_year content boolean — temporal dependency: prior year residency must be computed before current year
MISSING_INPUT: last_day_present_in_us content date — requires per-day presence records
MISSING_INPUT: last_day_as_lpr content date — requires per-day LPR status records
AMBIGUOUS: Residency starting date when individual qualifies as both LPR and SPT — § 7701(b)(2)(A)(ii) expressly covers LPR who does NOT meet SPT; § 7701(b)(2)(A)(iii) covers SPT individuals; statute silent on priority when both apply | options: (A) LPR governs because § 7701(b)(1)(A) lists LPR first and (ii) applies "but does not meet SPT" only to distinguish the LPR-only case, not to exclude LPR+SPT from (ii) — starting date = first day present as LPR | (B) SPT clause (iii) governs whenever SPT is met regardless of LPR status — starting date = first day present in US during the year
AMBIGUOUS: Modeling partial-year residency — § 7701(b)(2)(A) and (B) impose residency for a date-bounded "portion" of the calendar year; no native Catala partial-year output type | options: (A) output start date from ResidencyStartingDate and end date from LastYearResidency separately; calling scope composes the period | (B) declare a ResidencyPeriod structure with start_date and end_date fields and output from a unified PartialYearResidency scope
AMBIGUOUS: NominalPresenceDisregard integration — § 7701(b)(2)(C) says individual "shall not be treated as present" for up to 10 days with closer foreign connection; scope of that override is limited to § 7701(b)(2)(A)(iii) and (B) only | options: (A) INPUT_TRANSFORM: preprocessing scope reduces day counts fed into ResidencyStartingDate and LastYearResidency | (B) OUTPUT_OVERRIDE: exception on PresenceInUnitedStates.treated_as_present conditioned on purpose-of-use context — not expressible in current scope design
AMBIGUOUS: ResidencyDetermination priority when multiple bases simultaneously qualify — § 7701(b)(1)(A) says "meets requirements of clause (i), (ii), or (iii)" without explicit dominance ordering | options: (A) priority follows statutory clause order: LPR > SPT > FYE, as implemented in current if/else chain | (B) any qualifying basis suffices for residency_status = Resident; basis selection for starting date purposes handled separately by calling scope
AMBIGUOUS: First-year election filing timing — § 7701(b)(4)(E) prohibits making the election before SPT is met for the following year, yet election is filed on the election-year return; this is a procedural temporal constraint with no declarative Catala analog | options: (A) harness enforces timing by setting made_election = false until following-year SPT is confirmed | (B) add election_timely_filed content boolean as a separate input capturing the procedural constraint
</signals>
