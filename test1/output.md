# IRC § 7701(b) — Skeleton Pass

<catala>
# IRC § 7701(b) — Resident Alien and Nonresident Alien
# Scope: this title other than subtitle B
# Skeleton pass — unresolved items listed in signals block

## Enumerations

declaration enumeration ResidencyPath:
  -- LawfulPermanentResident
  -- SubstantialPresence
  -- FirstYearElection

declaration enumeration ResidencyStatus:
  -- ResidentAlien content ResidencyPath
  -- NonresidentAlien

declaration enumeration ExemptCategory:
  -- ForeignGovernmentRelated content ForeignGovRelatedBasis
  -- TeacherOrTrainee
  -- Student
  -- CharityAthleteEvent

declaration enumeration ForeignGovRelatedBasis:
  -- DiplomaticOrConsularStatus
  -- InternationalOrganizationEmployee
  -- ImmediateFamilyMember

## Structures

declaration structure PresenceDayCounts:
  data days_current_year content integer
  data days_first_preceding_year content integer
  data days_second_preceding_year content integer

## Scope: DayPresence — § 7701(b)(7)
## Per-day determination of whether an individual is "present in the United States."

declaration scope DayPresence:
  input physically_present content boolean
  input regularly_commutes_from_canada_or_mexico content boolean
  input in_transit_between_two_foreign_points content boolean
  input transit_duration_hours content integer
  input is_crew_member_of_foreign_vessel content boolean
  input engages_in_us_trade_or_business_on_day content boolean
  output treated_as_present content boolean

scope DayPresence:
  label general_presence_rule
  definition treated_as_present equals physically_present

  # INPUT_TRANSFORM: commuters from Canada or Mexico — § 7701(b)(7)(B)
  # INPUT_TRANSFORM: transit between two foreign points under 24 hours — § 7701(b)(7)(C)
  # INPUT_TRANSFORM: foreign vessel crew members not engaging in trade or business — § 7701(b)(7)(D)
  exception general_presence_rule
  definition treated_as_present equals false
  when
    regularly_commutes_from_canada_or_mexico
    or (in_transit_between_two_foreign_points and transit_duration_hours < 24)
    or (is_crew_member_of_foreign_vessel and not engages_in_us_trade_or_business_on_day)

## Scope: LprStatus — § 7701(b)(6)
## Determines whether an individual qualifies as a lawful permanent resident.

declaration scope LprStatus:
  input has_privilege_of_permanent_residence content boolean
  input lpr_status_revoked content boolean
  input lpr_status_administratively_abandoned content boolean
  input lpr_status_judicially_abandoned content boolean
  input commenced_treaty_resident_treatment content boolean
  input waived_foreign_country_treaty_benefits content boolean
  input notified_secretary_of_treaty_commencement content boolean
  output is_lawful_permanent_resident content boolean

scope LprStatus:
  label base_lpr_rule
  definition is_lawful_permanent_resident equals
    has_privilege_of_permanent_residence
    and not lpr_status_revoked
    and not lpr_status_administratively_abandoned
    and not lpr_status_judicially_abandoned

  # OUTPUT_OVERRIDE: treaty-resident election terminates LPR treatment for residency purposes
  # — § 7701(b)(6) final paragraph
  exception base_lpr_rule
  definition is_lawful_permanent_resident equals false
  when commenced_treaty_resident_treatment
    and not waived_foreign_country_treaty_benefits
    and notified_secretary_of_treaty_commencement

## Scope: ExemptIndividual — § 7701(b)(5)
## Per-day determination of exempt-individual status.
## Note: tt_or_student_exempt_years_in_preceding_6 counts years exempt as
## teacher/trainee OR student (clauses (ii) and (iii)), per § 7701(b)(5)(E)(i).
## total_tt_or_student_exempt_years is a lifetime count for the student limitation.

declaration scope ExemptIndividual:
  input category content ExemptCategory
  input tt_or_student_exempt_years_in_preceding_6 content integer
  input all_compensation_is_section_872_b_3_type content boolean
  input total_tt_or_student_exempt_years content integer
  input student_establishes_no_permanent_residence_intent content boolean
  input student_meets_current_visa_requirements content boolean
  input athlete_event_organized_for_501c3_purpose content boolean
  input athlete_event_all_net_proceeds_to_501c3 content boolean
  input athlete_event_uses_volunteers_for_substantially_all_work content boolean
  output is_exempt content boolean

scope ExemptIndividual:
  label base_exempt_rule
  definition is_exempt equals
    match category with
    -- ExemptCategory.ForeignGovernmentRelated of _: true
    -- ExemptCategory.TeacherOrTrainee: true
    -- ExemptCategory.Student: true
    -- ExemptCategory.CharityAthleteEvent:
         athlete_event_organized_for_501c3_purpose
         and athlete_event_all_net_proceeds_to_501c3
         and athlete_event_uses_volunteers_for_substantially_all_work

  # OUTPUT_OVERRIDE: teacher/trainee or student limitation — § 7701(b)(5)(E)
  # Conditions are mutually exclusive by category; merged into one exception
  # to avoid static conflict detection. Two structurally separate statutory provisions
  # are combined here; see signals for note.
  exception base_exempt_rule
  definition is_exempt equals false
  when
    ((match category with
      -- ExemptCategory.TeacherOrTrainee: true
      -- ExemptCategory.ForeignGovernmentRelated of _: false
      -- ExemptCategory.Student: false
      -- ExemptCategory.CharityAthleteEvent: false)
     and (if all_compensation_is_section_872_b_3_type
          then tt_or_student_exempt_years_in_preceding_6 >= 4
          else tt_or_student_exempt_years_in_preceding_6 >= 2))
    or
    ((match category with
      -- ExemptCategory.Student: true
      -- ExemptCategory.ForeignGovernmentRelated of _: false
      -- ExemptCategory.TeacherOrTrainee: false
      -- ExemptCategory.CharityAthleteEvent: false)
     and total_tt_or_student_exempt_years > 5
     and not (student_establishes_no_permanent_residence_intent
              and student_meets_current_visa_requirements))

## Scope: SubstantialPresenceTest — § 7701(b)(3)
## presence_counts must already exclude exempt-individual days (§ 7701(b)(3)(D)(i))
## and medical-condition days (§ 7701(b)(3)(D)(ii)) — see INPUT_TRANSFORM signals.

declaration scope SubstantialPresenceTest:
  input presence_counts content PresenceDayCounts
  input has_foreign_tax_home content boolean
  input closer_connection_to_foreign_country content boolean
  input adjustment_of_status_application_pending content boolean
  input took_steps_toward_lpr_status content boolean
  output weighted_presence_days content decimal
  output meets_substantial_presence_test content boolean

scope SubstantialPresenceTest:
  definition weighted_presence_days equals
    presence_counts.days_current_year * 1
    + presence_counts.days_first_preceding_year * (1 / 3)
    + presence_counts.days_second_preceding_year * (1 / 6)

  label base_spt_rule
  definition meets_substantial_presence_test equals
    presence_counts.days_current_year >= 31
    and weighted_presence_days >= 183

  # OUTPUT_OVERRIDE: closer-connection exception — § 7701(b)(3)(B)
  exception base_spt_rule
  label closer_connection_exception
  definition meets_substantial_presence_test equals false
  when presence_counts.days_current_year < 183
    and has_foreign_tax_home
    and closer_connection_to_foreign_country

  # Exception to closer-connection exception: pending LPR application — § 7701(b)(3)(C)
  exception closer_connection_exception
  definition meets_substantial_presence_test equals
    presence_counts.days_current_year >= 31
    and weighted_presence_days >= 183
  when adjustment_of_status_application_pending
    or took_steps_toward_lpr_status

## Scope: FirstYearElection — § 7701(b)(4)
## Qualification test and effect of first-year election.
## Exempt-individual days are excluded from presence counts per § 7701(b)(4)(D).

declaration scope FirstYearElection:
  input not_lpr_or_spt_resident_in_election_year content boolean
  input not_resident_in_preceding_year content boolean
  input meets_spt_for_following_year content boolean
  input has_31_consecutive_present_days_in_election_year content boolean
  input testing_period_days_actually_present content integer
  input testing_period_total_calendar_days content integer
  input testing_period_absent_days_treated_as_present content integer
  input election_filed_on_tax_return content boolean
  input secretary_has_consented_to_revoke content boolean
  input first_day_of_earliest_qualifying_testing_period content date
  output qualifies_for_election content boolean
  output election_is_in_effect content boolean
  output election_year_residency_start content date

scope FirstYearElection:
  # 75% threshold: (actual_present + excused_absences capped at 5) * 4 >= total_days * 3
  definition qualifies_for_election equals
    not_lpr_or_spt_resident_in_election_year
    and not_resident_in_preceding_year
    and meets_spt_for_following_year
    and has_31_consecutive_present_days_in_election_year
    and (testing_period_days_actually_present
         + (if testing_period_absent_days_treated_as_present <= 5
            then testing_period_absent_days_treated_as_present
            else 5))
        * 4 >= testing_period_total_calendar_days * 3

  definition election_is_in_effect equals
    qualifies_for_election
    and election_filed_on_tax_return
    and not secretary_has_consented_to_revoke

  definition election_year_residency_start equals
    first_day_of_earliest_qualifying_testing_period

## Scope: ResidencyPeriod — § 7701(b)(2)
## First-year residency starting date and last-year residency cutoff.
## residency_starting_date is only operative when not was_resident_in_preceding_year.

declaration scope ResidencyPeriod:
  input residency_path content ResidencyPath
  input was_resident_in_preceding_year content boolean
  input first_day_present_as_lpr_current_year content date
  input first_day_physically_present_current_year content date
  input first_day_of_election_testing_period content date
  input last_day_present_in_current_year content date
  input is_lpr_path content boolean
  input last_day_individual_was_lpr content date
  input has_closer_connection_to_foreign_country content boolean
  input will_be_resident_in_next_year content boolean
  input nominal_presence_days_with_closer_connection content integer
  output residency_starting_date content date
  output last_year_exception_applies content boolean
  output effective_last_day_as_resident content date
  output nominal_presence_days_disregarded content integer

scope ResidencyPeriod:
  # § 7701(b)(2)(A)(ii)-(iv)
  definition residency_starting_date equals
    match residency_path with
    -- ResidencyPath.LawfulPermanentResident: first_day_present_as_lpr_current_year
    -- ResidencyPath.SubstantialPresence: first_day_physically_present_current_year
    -- ResidencyPath.FirstYearElection: first_day_of_election_testing_period

  # § 7701(b)(2)(B)
  definition last_year_exception_applies equals
    has_closer_connection_to_foreign_country
    and not will_be_resident_in_next_year

  definition effective_last_day_as_resident equals
    if is_lpr_path
    then last_day_individual_was_lpr
    else last_day_present_in_current_year

  # Nominal presence disregard cap: 10 days — § 7701(b)(2)(C)
  definition nominal_presence_days_disregarded equals
    if has_closer_connection_to_foreign_country
    then if nominal_presence_days_with_closer_connection <= 10
         then nominal_presence_days_with_closer_connection
         else 10
    else 0

## Scope: ResidentAlienDetermination — § 7701(b)(1)
## Main alien residency classification. Invoke only for alien individuals;
## § 7701(b) does not apply to US citizens or for subtitle B purposes.

declaration scope ResidentAlienDetermination:
  input is_lawful_permanent_resident content boolean
  input meets_substantial_presence_test content boolean
  input has_made_first_year_election content boolean
  output residency_status content ResidencyStatus

scope ResidentAlienDetermination:
  definition residency_status equals
    if is_lawful_permanent_resident
    then ResidencyStatus.ResidentAlien content ResidencyPath.LawfulPermanentResident
    else if meets_substantial_presence_test
    then ResidencyStatus.ResidentAlien content ResidencyPath.SubstantialPresence
    else if has_made_first_year_election
    then ResidencyStatus.ResidentAlien content ResidencyPath.FirstYearElection
    else ResidencyStatus.NonresidentAlien
</catala>

<signals>
MISSING_INPUT: physically_present content boolean
MISSING_INPUT: regularly_commutes_from_canada_or_mexico content boolean
MISSING_INPUT: in_transit_between_two_foreign_points content boolean
MISSING_INPUT: transit_duration_hours content integer
MISSING_INPUT: is_crew_member_of_foreign_vessel content boolean
MISSING_INPUT: engages_in_us_trade_or_business_on_day content boolean
MISSING_INPUT: has_privilege_of_permanent_residence content boolean
MISSING_INPUT: lpr_status_revoked content boolean
MISSING_INPUT: lpr_status_administratively_abandoned content boolean
MISSING_INPUT: lpr_status_judicially_abandoned content boolean
MISSING_INPUT: commenced_treaty_resident_treatment content boolean
MISSING_INPUT: waived_foreign_country_treaty_benefits content boolean
MISSING_INPUT: notified_secretary_of_treaty_commencement content boolean
MISSING_INPUT: category content ExemptCategory
MISSING_INPUT: tt_or_student_exempt_years_in_preceding_6 content integer
MISSING_INPUT: all_compensation_is_section_872_b_3_type content boolean
MISSING_INPUT: total_tt_or_student_exempt_years content integer
MISSING_INPUT: student_establishes_no_permanent_residence_intent content boolean
MISSING_INPUT: student_meets_current_visa_requirements content boolean
MISSING_INPUT: athlete_event_organized_for_501c3_purpose content boolean
MISSING_INPUT: athlete_event_all_net_proceeds_to_501c3 content boolean
MISSING_INPUT: athlete_event_uses_volunteers_for_substantially_all_work content boolean
MISSING_INPUT: presence_counts content PresenceDayCounts
MISSING_INPUT: has_foreign_tax_home content boolean
MISSING_INPUT: closer_connection_to_foreign_country content boolean
MISSING_INPUT: adjustment_of_status_application_pending content boolean
MISSING_INPUT: took_steps_toward_lpr_status content boolean
MISSING_INPUT: not_lpr_or_spt_resident_in_election_year content boolean
MISSING_INPUT: not_resident_in_preceding_year content boolean
MISSING_INPUT: meets_spt_for_following_year content boolean
MISSING_INPUT: has_31_consecutive_present_days_in_election_year content boolean
MISSING_INPUT: testing_period_days_actually_present content integer
MISSING_INPUT: testing_period_total_calendar_days content integer
MISSING_INPUT: testing_period_absent_days_treated_as_present content integer
MISSING_INPUT: election_filed_on_tax_return content boolean
MISSING_INPUT: secretary_has_consented_to_revoke content boolean
MISSING_INPUT: first_day_of_earliest_qualifying_testing_period content date
MISSING_INPUT: was_resident_in_preceding_year content boolean
MISSING_INPUT: first_day_present_as_lpr_current_year content date
MISSING_INPUT: first_day_physically_present_current_year content date
MISSING_INPUT: first_day_of_election_testing_period content date
MISSING_INPUT: last_day_present_in_current_year content date
MISSING_INPUT: is_lpr_path content boolean
MISSING_INPUT: last_day_individual_was_lpr content date
MISSING_INPUT: has_closer_connection_to_foreign_country content boolean
MISSING_INPUT: will_be_resident_in_next_year content boolean
MISSING_INPUT: nominal_presence_days_with_closer_connection content integer
MISSING_INPUT: is_lawful_permanent_resident content boolean
MISSING_INPUT: meets_substantial_presence_test content boolean
MISSING_INPUT: has_made_first_year_election content boolean
EXTERNAL_DEPENDENCY: tax_home defined in section_911_d_3
EXTERNAL_DEPENDENCY: second sentence of section_911_d_3 excluded from tax_home definition per § 7701(b)(3)(B)(ii) defined in section_911_d_3
EXTERNAL_DEPENDENCY: J_visa_status subparagraph (J) of INA section 101(15) defined in immigration_and_nationality_act_section_101_15
EXTERNAL_DEPENDENCY: Q_visa_status subparagraph (Q) of INA section 101(15) defined in immigration_and_nationality_act_section_101_15
EXTERNAL_DEPENDENCY: F_visa_status subparagraph (F) of INA section 101(15) defined in immigration_and_nationality_act_section_101_15
EXTERNAL_DEPENDENCY: M_visa_status subparagraph (M) of INA section 101(15) defined in immigration_and_nationality_act_section_101_15
EXTERNAL_DEPENDENCY: section_501_c_3_organization_status defined in section_501_c_3
EXTERNAL_DEPENDENCY: section_501_a_tax_exemption defined in section_501_a
EXTERNAL_DEPENDENCY: section_872_b_3_compensation_type defined in section_872_b_3
EXTERNAL_DEPENDENCY: subtitle_B_scope_exclusion — this section does not apply for subtitle B purposes defined in unknown
INPUT_TRANSFORM: days present in the United States are not counted on any day the individual is an exempt individual — presence_counts must exclude such days before SubstantialPresenceTest is evaluated per § 7701(b)(3)(D)(i)
INPUT_TRANSFORM: days present in the United States are not counted when the individual was unable to leave due to a medical condition which arose while present in the United States — presence_counts must exclude such days per § 7701(b)(3)(D)(ii)
INPUT_TRANSFORM: commuters from Canada or Mexico are not treated as present in the United States on days they regularly commute to US employment or self-employment per § 7701(b)(7)(B)
INPUT_TRANSFORM: individuals in transit between two points outside the United States and physically present for less than 24 hours are not treated as present in the United States per § 7701(b)(7)(C)
INPUT_TRANSFORM: crew members of foreign vessels engaged in US-foreign transportation are not treated as present in the United States unless they engage in US trade or business on that day per § 7701(b)(7)(D)
INPUT_TRANSFORM: up to 10 days of presence during which the individual establishes closer connection to a foreign country are not counted as presence for purposes of subparagraphs (A)(iii) and (B) of § 7701(b)(2) — nominal_presence_days_with_closer_connection feeds the disregard cap in ResidencyPeriod per § 7701(b)(2)(C)
INPUT_TRANSFORM: exempt-individual day exclusion under § 7701(b)(3)(D)(i) also applies when computing presence days for first-year election testing period per § 7701(b)(4)(D)
OUTPUT_OVERRIDE: individual not treated as meeting the substantial presence test when present fewer than 183 days in current year and has established a foreign tax home with closer connection to that country, unless adjustment-of-status application was pending or steps toward LPR status were taken during the year per § 7701(b)(3)(B)-(C)
OUTPUT_OVERRIDE: alien treated as US resident only from residency starting date (not from January 1) in the first year of residency when not a resident at any time during the preceding calendar year per § 7701(b)(2)(A)
OUTPUT_OVERRIDE: alien not treated as US resident during portion of year after effective last day of presence when closer connection to foreign country exists during that portion and individual will not be a US resident in the following calendar year per § 7701(b)(2)(B)
OUTPUT_OVERRIDE: lawful permanent resident status ceases for residency purposes when individual commences treatment as a foreign country resident under a tax treaty, does not waive treaty benefits, and notifies the Secretary per § 7701(b)(6) final paragraph
AMBIGUOUS_PRECEDENCE: residency starting date for an LPR individual who also meets the substantial presence test — § 7701(b)(2)(A)(ii) supplies the LPR starting date only when the individual does not meet the SPT, but § 7701(b)(2)(A)(iii) supplies the first-presence starting date for any individual who meets the SPT; statute does not explicitly resolve which controls when both conditions hold; ResidencyPeriod currently uses the LPR path starting date (first_day_present_as_lpr_current_year) for all LPR-classified individuals, which may be incorrect for dual-status individuals
</signals>
