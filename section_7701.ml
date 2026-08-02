(* shared types *)
(* shared types for § 7701 *)

(* 7701(a)(4)-(5): domestic vs foreign classification, applied to corporations and partnerships *)
type entity_residency = Domestic | Foreign

(* 7701(a)(3): corporation - includes associations, joint-stock companies, insurance companies *)
type corporation_form = Association_corporation | Joint_stock_company | Insurance_company

(* 7701(a)(3),(4),(5): corporation, with its domestic/foreign classification *)
type corporation = {
  corporation_form : corporation_form;
  residency : entity_residency;
}

(* 7701(a)(2): organizational forms included within "partnership" *)
type partnership_form = Syndicate | Group | Pool | Joint_venture | Other_unincorporated_organization

(* 7701(a)(2): the business/financial/venture activity carried on through a partnership *)
type business_activity = Business | Financial_operation | Venture

(* 7701(a)(1): person - individual, trust, estate, partnership, association, company, or corporation *)
type person =
  | Individual
  | Trust
  | Estate
  | Partnership of partnership
  | Association
  | Company
  | Corporation of corporation
(* 7701(a)(2),(4),(5): partnership - not a trust, estate, or corporation; and its members ("partners") *)
and partnership = {
  partnership_form : partnership_form;
  carries_on : business_activity;
  partners : person list;
  residency : entity_residency;
}

(* 7701(a)(6): fiduciary - guardian, trustee, executor, administrator, receiver, conservator, or any person acting in a fiduciary capacity for any person *)
type fiduciary =
  | Guardian
  | Trustee
  | Executor
  | Administrator
  | Receiver
  | Conservator
  | Fiduciary_capacity_holder of person

(* 7701(a)(7): stock - shares in an association, joint-stock company, or insurance company *)
type stock = { issued_by : corporation_form }

(* 7701(a)(8): shareholder - a member in an association, joint-stock company, or insurance company *)
type shareholder = { member_of : corporation_form; holder : person }

(* 7701(a)(14): taxpayer - any person subject to any internal revenue tax *)
type taxpayer = { taxpayer_person : person }

(* 7701(a)(11)(A): Secretary of the Treasury, personally, excluding any delegate *)
type secretary_of_treasury = Secretary_of_treasury_personally

(* 7701(a)(12)(B): territories where a delegate may perform certain functions *)
type territory = Guam | American_samoa

(* 7701(a)(11)(B),(12)(B): delegate of the Secretary, including territorial delegates for Guam/American Samoa *)
type delegate =
  | Treasury_delegate
  | Territorial_delegate of territory

(* 7701(a)(11)(B): Secretary - the Secretary of the Treasury or his delegate *)
type secretary =
  | Secretary_of_treasury_role
  | Delegate_of_secretary of delegate

(* 7701(a)(13): Commissioner - the Commissioner of Internal Revenue *)
type commissioner = Commissioner_of_internal_revenue

(* 7701(a)(22): Attorney General - the Attorney General of the United States *)
type attorney_general = Attorney_general_of_united_states

(* 7701(a)(16): withholding agent - person required to deduct and withhold tax under specified sections *)
type withholding_code_section = Section_1441 | Section_1442 | Section_1443 | Section_1461

type withholding_agent = {
  agent : person;
  required_under : withholding_code_section list;
}

(* 7701(a)(17): husband/wife term substitution rules for section 2516 upon divorce *)
type marital_role = Husband | Wife | Former_husband | Former_wife

(* 7701(a)(18): international organization - entity entitled to privileges/immunities under the International Organizations Immunities Act *)
type international_organization = International_organization_under_immunities_act

(* 7701(a)(20): statutory purposes for which "employee" is extended to full-time life insurance salesmen *)
type employee_benefit_purpose =
  | Group_term_life_insurance_section_79
  | Accident_and_health_sections_104_105_106
  | Stock_bonus_pension_profit_sharing_or_annuity_plan
  | Cafeteria_plan_section_125

(* 7701(a)(20): employee - includes a full-time life insurance salesman treated as an employee under chapter 21 *)
type employee = Standard_employee | Full_time_life_insurance_salesman

(* 7701(a)(21): levy - includes the power of distraint and seizure by any means *)
type levy = Distraint | Seizure

(* supports 7701(a)(23),(24): a calendar date *)
type date = { year : int; month : int; day : int }

(* supports 7701(a)(24): calendar months *)
type month =
  | January | February | March | April | May | June
  | July | August | September | October | November | December

(* 7701(a)(24): fiscal year - 12-month accounting period ending on the last day of any month other than December *)
type fiscal_year = { fiscal_year_end_month : month }

(* 7701(a)(23): taxable year - calendar year, fiscal year, or a fractional period covered by a return *)
type taxable_year =
  | Calendar_year_basis
  | Fiscal_year_basis of fiscal_year
  | Fractional_period of { period_start : date; period_end : date }

(* 7701(a)(25): paid or incurred / paid or accrued - construed per the taxpayer's method of accounting *)
type accounting_method = Cash_method | Accrual_method

(* 7701(a)(26): trade or business - includes performance of the functions of a public office *)
type trade_or_business = Performance_of_public_office_functions | Other_trade_or_business

(* 7701(a)(27): Tax Court - the United States Tax Court *)
type tax_court = United_states_tax_court

(* 7701(a)(29): Internal Revenue Code - the 1986 Code or the 1939 Code *)
type internal_revenue_code = Code_of_1986 | Code_of_1939

(* 7701(a)(31)(B): foreign trust - any trust other than a domestic trust *)
type trust_residency = Domestic_trust | Foreign_trust

(* 7701(a)(31)(A): foreign estate - an estate whose qualifying foreign-source income is excluded from gross income *)
type estate_residency = Domestic_estate | Foreign_estate

(* 7701(a)(35): enrolled actuary - enrolled by the Joint Board for the Enrollment of Actuaries *)
type enrolled_actuary = Enrolled_by_joint_board_for_enrollment_of_actuaries

(* 7701(a)(36)(A): tax return preparer - prepares for compensation, or employs others to prepare for compensation *)
type tax_return_preparer =
  | Direct_preparer_for_compensation of person
  | Employer_of_compensated_preparers of person

(* 7701(a)(38): joint return - a single return made jointly under section 6013 by a husband and wife *)
type joint_return = { husband : person; wife : person }

(* 7701(a)(40)(A): governing bodies recognized as Indian tribal governments *)
type tribal_entity = Tribe | Band | Community | Village | Group_of_indians | Alaska_natives

type indian_tribal_government = {
  governing_body_of : tribal_entity;
  exercises_governmental_functions : bool;
}

(* 7701(a)(41): TIN - identifying number assigned to a person under section 6109 *)
type tin = { identifying_number : string }

(* 7701(a)(43),(44): transferred basis property and exchanged basis property *)
type basis_property = Transferred_basis_property | Exchanged_basis_property

(* 7701(a)(45): nonrecognition transaction - disposition where gain or loss is not recognized under subtitle A *)
type nonrecognition_transaction = Nonrecognition_transaction

(* 7701(a)(46): employee representatives - excludes organizations majority-controlled by owners/officers/executives *)
type employee_representatives = { majority_are_owners_officers_or_executives : bool }

(* 7701(a)(46): collective bargaining agreement - bona fide agreement between bona fide employee representatives and employers *)
type collective_bargaining_agreement = {
  representatives : employee_representatives;
  employers : person list;
  is_bona_fide : bool;
}

(* 7701(a)(51)(A)(i): prohibited foreign entity - a specified foreign entity or a foreign-influenced entity *)
type prohibited_foreign_entity = Specified_foreign_entity | Foreign_influenced_entity

(* 7701(a)(51)(D)(ii)(V): contractual counterparty - entity with which the taxpayer has entered a contract, agreement, or arrangement *)
type contractual_counterparty = { counterparty : person }

(* 7701(a)(51)(D)(ii)(IV): taxpayer term extended to include persons related to the taxpayer *)
type taxpayer_including_related_persons = {
  primary_taxpayer : taxpayer;
  related_persons : person list;
}

(* 7701(a)(51)(D)(ii)(I)(aa): effective control - contractual arrangements giving counterparties specific authority beyond authority/ownership/debt-based control *)
type effective_control = { counterparties_with_specific_authority : contractual_counterparty list }

(* 7701(a)(51)(I)(i): applicable critical mineral - meaning per section 45X(c)(6) *)
type applicable_critical_mineral = Applicable_critical_mineral

(* 7701(a)(51)(I)(ii): covered nation - meaning per 10 U.S.C. 4872(f)(2) *)
type covered_nation = Covered_nation

(* 7701(a)(51)(I)(iii): eligible component - meaning per section 45X(c)(1) *)
type eligible_component = Eligible_component

(* 7701(a)(51)(I)(iv),(a)(52)(E)(ii),(e)(3)(F): energy storage technology - meaning per section 48E(c)(2) (also cross-referenced via section 48(c)(6)) *)
type energy_storage_technology = Energy_storage_technology

(* 7701(a)(51)(I)(vi): related - meaning per sections 267(b) and 707(b) *)
type related_person_relationship = Related

(* 7701(e)(3)(B)-(F): facility categories for purposes of subparagraph (A) *)
type facility_type =
  | Qualified_solid_waste_disposal_facility of {
      governmental_units_served : int;
      substantially_all_waste_from_general_public : bool;
    }
  | Cogeneration_facility
  | Alternative_energy_facility of { primary_energy_source_is_oil_gas_coal_or_nuclear : bool }
  | Water_treatment_works_facility
  | Storage_facility of { technology : energy_storage_technology }

(* supports 7701(h)(2)(A): a motor vehicle, including a trailer *)
type motor_vehicle = { is_trailer : bool }

(* 7701(h)(2)(A): qualified motor vehicle operating agreement - meets requirements of subparagraphs (B),(C),(D) *)
type qualified_motor_vehicle_operating_agreement = {
  vehicle : motor_vehicle;
  meets_requirements_b_c_d : bool;
}

(* 7701(h)(3)(A)-(B): terminal rental adjustment clause - rental price adjustment by reference to sale proceeds, including lessee-dealer resale variant *)
type terminal_rental_adjustment_clause =
  | Adjustment_by_reference_to_sale_proceeds
  | Lessee_dealer_predetermined_price_resale

(* 7701(j)(4): Member/employee as participants in the Thrift Savings Fund, per subchapter III of chapter 84, title 5 U.S.C. *)
type thrift_savings_participant = Member | Employee_participant

(* 7701(j)(4): Thrift Savings Fund, per subchapter III of chapter 84, title 5 U.S.C. *)
type thrift_savings_fund = Thrift_savings_fund

(* 7701(j)(3): coordination rule - basic pay contributed to the Thrift Savings Fund remains included in "wages" under SSA section 209 / section 3121(a) *)
type thrift_savings_fund_contribution = { included_in_wages_under_ssa_or_3121a : bool }

(* 7701(o)(5)(D): transaction - includes a series of transactions *)
type transaction = Single_transaction | Series_of_transactions of transaction list

(* 7701(o)(5)(A): economic substance doctrine - denies tax benefits where a transaction lacks economic substance or business purpose *)
type economic_substance_doctrine = { has_economic_substance : bool; has_business_purpose : bool }

(* 7701(b)(3)(A) — code *)
(* substantial presence test: 31-day floor plus weighted 3-year day count >= 183 *)
let meets_substantial_presence_test
    (days_present_current_year : int)
    (days_present_1st_preceding_year : int)
    (days_present_2nd_preceding_year : int) : bool =
  let at_least_31_days_current_year = days_present_current_year >= 31 in
  let weighted_day_sum =
    (float_of_int days_present_current_year *. 1.0) +.
    (float_of_int days_present_1st_preceding_year *. (1.0 /. 3.0)) +.
    (float_of_int days_present_2nd_preceding_year *. (1.0 /. 6.0))
  in
  let weighted_sum_meets_183 = weighted_day_sum >= 183.0 in
  at_least_31_days_current_year && weighted_sum_meets_183

(* 7701(b)(3)(B) — code *)
(* 7701(b)(3)(B): individual escapes substantial presence test if present <183 days
   and has foreign tax home (per section 911(d)(3), second sentence disregarded) with
   closer connection to that foreign country than to the United States. *)
let is_closer_connection_exception (individual : person) (days_present_current_year : int) (has_foreign_tax_home : bool) (has_closer_connection_to_foreign_country : bool) : bool =
  days_present_current_year < 183 &&
  has_foreign_tax_home &&
  has_closer_connection_to_foreign_country

(* 7701(b)(3)(D) — code *)
(* 7701(b)(3)(D): day excluded from US presence count if exempt individual or medical-condition-bound *)
let is_excepted_from_us_presence (is_exempt_individual : bool) (unable_to_leave_due_to_medical_condition : bool) : bool =
  is_exempt_individual ||
  unable_to_leave_due_to_medical_condition

(* 7701(b)(4)(A)(iv) — code *)
(* 7701(b)(4)(A)(iv): 31-day-in-election-year + 75%-of-testing-period presence test *)
let meets_31_consecutive_day_test (days_present_in_31_day_period : int) : bool =
  days_present_in_31_day_period >= 31

let meets_75_percent_testing_period_test (days_present_in_testing_period : int) (days_absent_in_testing_period : int) (testing_period_length : int) : bool =
  let counted_absent_days = min days_absent_in_testing_period 5 in
  let effective_days_present = days_present_in_testing_period + counted_absent_days in
  float_of_int effective_days_present >= 0.75 *. float_of_int testing_period_length

let is_present_for_31_day_and_testing_period (days_present_in_31_day_period : int) (days_present_in_testing_period : int) (days_absent_in_testing_period : int) (testing_period_length : int) : bool =
  meets_31_consecutive_day_test days_present_in_31_day_period &&
  meets_75_percent_testing_period_test days_present_in_testing_period days_absent_in_testing_period testing_period_length

(* 7701(b)(5)(A)(iv) — code *)
(* 7701(b)(5)(A)(iv): professional athlete temporarily in US for charitable sports event, exempt individual for substantial presence test *)
let is_exempt_professional_athlete (is_temporarily_in_united_states : bool) (competes_in_sports_event : bool) (event_primary_purpose_benefits_501c3_organization : bool) (all_net_proceeds_contributed_to_organization : bool) (volunteers_perform_substantially_all_event_work : bool) : bool =
  is_temporarily_in_united_states &&
  competes_in_sports_event &&
  event_primary_purpose_benefits_501c3_organization &&
  all_net_proceeds_contributed_to_organization &&
  volunteers_perform_substantially_all_event_work

(* 7701(b)(5)(C) — code *)
(* 7701(b)(5)(C): defines "teacher or trainee" for an individual *)
let is_teacher_or_trainee (individual : person) (present_under_j_or_q_visa : bool) (is_student : bool) (substantially_complies_with_presence_requirements : bool) : bool =
  (* (i): temporarily present under INA 101(15)(J) or (Q), excluding students *)
  present_under_j_or_q_visa && not is_student &&
  (* (ii): substantially complies with requirements for such presence *)
  substantially_complies_with_presence_requirements

(* 7701(b)(5)(D)(i) — code *)
(* temporarily present under F/M visa or J/Q student visa, per INA section 101(15) subparagraphs *)
let is_temporarily_present_under_exempt_visa
  (has_f_or_m_visa_status : bool)
  (has_j_or_q_student_status : bool) : bool =
  has_f_or_m_visa_status ||
  has_j_or_q_student_status

(* 7701(b)(6) — code *)
(* 7701(b)(6): lawful permanent resident status *)
let is_lawful_permanent_resident
    (has_lawful_permanent_residence_status : bool)
    (status_revoked : bool)
    (status_abandoned_by_determination : bool) : bool =
  has_lawful_permanent_residence_status
  && not status_revoked
  && not status_abandoned_by_determination

(* cessation rule: treaty residency claim without waiver, notified to Secretary *)
let ceases_to_be_lawful_permanent_resident
    (treated_as_foreign_resident_under_tax_treaty : bool)
    (waives_treaty_benefits : bool)
    (notifies_secretary_of_treatment : bool) : bool =
  treated_as_foreign_resident_under_tax_treaty
  && not waives_treaty_benefits
  && notifies_secretary_of_treatment

(* 7701(b)(10) — ambiguous *)
(* stub — tax computed in manner provided in section 877(b) *)
let tax_under_section_877b (taxpayer : taxpayer) (gap_start : date) (gap_end : date) : float =
  (* unresolved — needs §877(b) *)
  failwith "unresolved cross-reference"

(* stub — tax imposed pursuant to section 871, without regard to this paragraph *)
let tax_under_section_871 (taxpayer : taxpayer) (gap_start : date) (gap_end : date) : float =
  (* unresolved — needs §871 *)
  failwith "unresolved cross-reference"

(* 7701(b)(10)(A): alien individual treated as US resident for a period including at least 3 consecutive calendar years (the initial residency period) *)
let has_initial_residency_period (consecutive_resident_years : int) : bool =
  consecutive_resident_years >= 3

(* 7701(b)(10)(B): individual ceases to be a resident but again becomes a resident before close of the 3rd calendar year after the initial residency period ends *)
let resumes_residency_in_time (initial_residency_period_end_year : int) (resumed_residency_year : int) : bool =
  resumed_residency_year <= initial_residency_period_end_year + 3

(* 7701(b)(10): coordination with section 877 — applies only if tax under 877(b) exceeds tax under 871 for the gap period *)
let coordination_with_section_877
    (taxpayer : taxpayer)
    (consecutive_resident_years : int)
    (initial_residency_period_end_year : int)
    (resumed_residency_year : int)
    (gap_period_start : date)
    (gap_period_end : date)
    : bool =
  has_initial_residency_period consecutive_resident_years &&
  resumes_residency_in_time initial_residency_period_end_year resumed_residency_year &&
  tax_under_section_877b taxpayer gap_period_start gap_period_end >
  tax_under_section_871 taxpayer gap_period_start gap_period_end

(* 7701(b)(2)(B) — code *)
(* 7701(b)(2)(B): alien individual not treated as US resident during portion of calendar year if (i)-(iii) hold *)
let is_excluded_from_residency_last_year
    (portion_is_after_last_presence_or_described_day : bool)
    (has_closer_connection_to_foreign_country_during_portion : bool)
    (is_resident_next_calendar_year : bool) : bool =
  portion_is_after_last_presence_or_described_day &&
  has_closer_connection_to_foreign_country_during_portion &&
  not is_resident_next_calendar_year

(* 7701(b)(3)(C) — code *)
(* 7701(b)(3)(C): bars (B) closer-connection exception if individual sought LPR status during year *)
let bars_closer_connection_exception (individual : person) (has_pending_status_adjustment_application : bool) (took_other_steps_toward_lawful_permanent_resident_status : bool) : bool =
  has_pending_status_adjustment_application ||
  took_other_steps_toward_lawful_permanent_resident_status

(* 7701(b)(5)(A) — code *)
(* 7701(b)(5)(A): exempt individual for substantial presence test if foreign govt-related individual, teacher/trainee, student, or professional athlete under (iv) *)
let is_exempt_individual (is_foreign_government_related_individual : bool) (is_teacher_or_trainee : bool) (is_student : bool) (is_temporarily_in_united_states : bool) (competes_in_sports_event : bool) (event_primary_purpose_benefits_501c3_organization : bool) (all_net_proceeds_contributed_to_organization : bool) (volunteers_perform_substantially_all_event_work : bool) : bool =
  is_foreign_government_related_individual ||
  is_teacher_or_trainee ||
  is_student ||
  is_exempt_professional_athlete is_temporarily_in_united_states competes_in_sports_event event_primary_purpose_benefits_501c3_organization all_net_proceeds_contributed_to_organization volunteers_perform_substantially_all_event_work

(* 7701(b)(5)(B) — code *)
(* foreign government-related individual : temporarily present in US by reason of diplomatic status, visa determined by Secretary to represent full-time diplomatic/consular status, full-time employment at international organization, or immediate family membership with such an individual *)
let is_foreign_government_related_individual
    (has_diplomatic_status : bool)
    (has_secretary_determined_diplomatic_or_consular_visa : bool)
    (is_full_time_employee_of_international_organization : bool)
    (is_immediate_family_member_of_qualifying_individual : bool)
  : bool =
  has_diplomatic_status ||
  has_secretary_determined_diplomatic_or_consular_visa ||
  is_full_time_employee_of_international_organization ||
  is_immediate_family_member_of_qualifying_individual

(* 7701(b)(5)(D) — code *)
(* student : individual temporarily present under exempt visa who substantially complies with presence requirements *)
let is_student
  (has_f_or_m_visa_status : bool)
  (has_j_or_q_student_status : bool)
  (substantially_complies_with_presence_requirements : bool) : bool =
  is_temporarily_present_under_exempt_visa has_f_or_m_visa_status has_j_or_q_student_status &&
  substantially_complies_with_presence_requirements

(* 7701(b)(5)(E) — code *)
module Special_rules_for_teachers_trainees_and_students = struct
  (* (i) — bars teacher/trainee exemption under (A)(ii) if exempt under (A)(ii) or (A)(iii) in >= threshold of preceding 6 calendar years; threshold is 4 (not 2) if all compensation is described in section 872(b)(3) *)
  let is_teacher_or_trainee_exempt (current_year : int) (exempt_calendar_years_under_A_ii_or_A_iii : int list) (all_compensation_under_section_872_b_3 : bool) : bool =
    let threshold = if all_compensation_under_section_872_b_3 then 4 else 2 in
    let exempt_years_in_preceding_six =
      List.filter (fun y -> y < current_year && y >= current_year - 6) exempt_calendar_years_under_A_ii_or_A_iii
    in
    List.length exempt_years_in_preceding_six < threshold

  (* (ii) — bars student exemption under (A)(iii) after the 5th calendar year of exemption under (A)(ii) or (A)(iii), unless individual establishes no intent to permanently reside in the US and meets subparagraph (D)(ii) requirements *)
  let is_student_exempt (current_year : int) (exempt_calendar_years_under_A_ii_or_A_iii : int list) (does_not_intend_permanent_residence : bool) (meets_subparagraph_D_ii : bool) : bool =
    let prior_exempt_year_count =
      List.length (List.filter (fun y -> y < current_year) exempt_calendar_years_under_A_ii_or_A_iii)
    in
    if prior_exempt_year_count < 5 then true
    else does_not_intend_permanent_residence && meets_subparagraph_D_ii
end

(* 7701(b)(7) — code *)
(* is_present_in_united_states : determines whether individual treated as present in US on given day, per 7701(b)(7) general rule plus commuter, transit, and crew exceptions *)
let is_present_in_united_states
    (physically_present : bool)
    (commutes_from_canada_or_mexico : bool)
    (in_transit_between_two_foreign_points : bool)
    (hours_present_during_transit : float)
    (is_regular_crew_member_of_foreign_vessel : bool)
    (vessel_engaged_in_us_foreign_transportation : bool)
    (engages_in_trade_or_business_in_us : bool)
  : bool =
  (* (B) commuter from Canada or Mexico on day of commute *)
  if commutes_from_canada_or_mexico then false
  (* (C) in transit between 2 foreign points, present less than 24 hours *)
  else if in_transit_between_two_foreign_points && hours_present_during_transit < 24.0 then false
  (* (D) regular crew member of foreign vessel, unless also engaged in US trade or business that day *)
  else if is_regular_crew_member_of_foreign_vessel
          && vessel_engaged_in_us_foreign_transportation
          && not engages_in_trade_or_business_in_us then false
  (* (A) general rule: physical presence any time during day *)
  else physically_present

(* 7701(b)(3) — code *)
(* 7701(b)(3): substantial presence test overall, subject to (B) closer-connection
   exception unless barred by (C). Day counts passed in must already exclude days
   excepted under (D) (exempt individual / medical condition). *)
let meets_substantial_presence_test_overall
    (individual : person)
    (days_present_current_year : int)
    (days_present_1st_preceding_year : int)
    (days_present_2nd_preceding_year : int)
    (has_foreign_tax_home : bool)
    (has_closer_connection_to_foreign_country : bool)
    (has_pending_status_adjustment_application : bool)
    (took_other_steps_toward_lawful_permanent_resident_status : bool) : bool =
  let raw_test_met =
    meets_substantial_presence_test
      days_present_current_year
      days_present_1st_preceding_year
      days_present_2nd_preceding_year
  in
  let exception_applies =
    is_closer_connection_exception
      individual days_present_current_year has_foreign_tax_home has_closer_connection_to_foreign_country
    && not (bars_closer_connection_exception
              individual has_pending_status_adjustment_application took_other_steps_toward_lawful_permanent_resident_status)
  in
  raw_test_met && not exception_applies

(* 7701(b)(5) — code *)
(* 7701(b)(5): groups definitions used throughout subsection (b) — exempt individual and its components *)
module Exempt_individual = struct
  let is_exempt_individual = is_exempt_individual
  let is_foreign_government_related_individual = is_foreign_government_related_individual
  let is_teacher_or_trainee = is_teacher_or_trainee
  let is_student = is_student
  module Special_rules_for_teachers_trainees_and_students = Special_rules_for_teachers_trainees_and_students
end

(* 7701(b)(2)(C) — code *)
(* days present in US disregarded under closer-connection exception, capped at 10 days per (b)(2)(C)(ii) *)
let days_disregarded_for_closer_connection (days_with_closer_connection_established : int) : int =
  min days_with_closer_connection_established 10

(* 7701(b)(1)(A) — ambiguous *)
let is_lawful_permanent_resident (individual : person) (year : int) : bool =
  (* clause (i): permanent resident status under immigration law, not modeled in person type *)
  failwith "unresolved cross-reference"

let meets_substantial_presence_test (individual : person) (year : int) : bool =
  (* clause (ii): delegated to §7701(b)(3), not yet formalized *)
  failwith "unresolved cross-reference"

let makes_first_year_election (individual : person) (year : int) : bool =
  (* clause (iii): delegated to §7701(b)(4), not yet formalized *)
  failwith "unresolved cross-reference"

let is_resident_alien (individual : person) (year : int) : bool =
  (* 7701(b)(1)(A): alien treated as US resident if any clause (i)-(iii) holds *)
  is_lawful_permanent_resident individual year ||
  meets_substantial_presence_test individual year ||
  makes_first_year_election individual year

(* 7701(b)(2)(A) — code *)
(* residency_starting_date : determines first day of US residency depending on which basis (i)(ii)(iii)(iv) applies *)
let residency_starting_date
    (is_lawful_permanent_resident : bool)
    (meets_substantial_presence_test : bool)
    (makes_first_year_election : bool)
    (first_day_present_as_lawful_permanent_resident : date option)
    (first_day_present_in_united_states : date option)
    (first_day_treated_as_resident_under_election : date option)
    : date =
  if meets_substantial_presence_test then
    (* (iii) substantial presence test: residency starting date is first day present in US during the year *)
    match first_day_present_in_united_states with
    | Some d -> d
    | None -> failwith "missing first day present in United States"
  else if is_lawful_permanent_resident then
    (* (ii) lawful permanent resident not meeting substantial presence test: first day present in US as LPR *)
    match first_day_present_as_lawful_permanent_resident with
    | Some d -> d
    | None -> failwith "missing first day present as lawful permanent resident"
  else if makes_first_year_election then
    (* (iv) first-year election under paragraph (4): first day treated as resident under that election *)
    match first_day_treated_as_resident_under_election with
    | Some d -> d
    | None -> failwith "missing first day treated as resident under election"
  else
    failwith "no residency basis established for residency starting date"

(* first_year_residency_period : (i) alien individual resident this calendar year under (1)(A) but not resident preceding calendar year is treated as resident only for portion of year beginning on residency starting date *)
let first_year_residency_period
    (is_resident_under_1A_this_year : bool)
    (was_resident_preceding_calendar_year : bool)
    (is_lawful_permanent_resident : bool)
    (meets_substantial_presence_test : bool)
    (makes_first_year_election : bool)
    (first_day_present_as_lawful_permanent_resident : date option)
    (first_day_present_in_united_states : date option)
    (first_day_treated_as_resident_under_election : date option)
    (calendar_year_end : date)
    : taxable_year option =
  if is_resident_under_1A_this_year && not was_resident_preceding_calendar_year then
    let start_date =
      residency_starting_date
        is_lawful_permanent_resident
        meets_substantial_presence_test
        makes_first_year_election
        first_day_present_as_lawful_permanent_resident
        first_day_present_in_united_states
        first_day_treated_as_resident_under_election
    in
    Some (Fractional_period { period_start = start_date; period_end = calendar_year_end })
  else
    None

(* 7701(b)(4)(A) — code *)
(* 7701(b)(4)(A): alien deemed to meet requirements if not resident in election year and prior year under (1)(A)(i)/(ii), but resident under (1)(A)(ii) in following year, plus presence test *)
let meets_first_year_election_requirements (is_nonresident_election_year : bool) (is_nonresident_preceding_year : bool) (is_resident_following_year_under_substantial_presence : bool) (days_present_in_31_day_period : int) (days_present_in_testing_period : int) (days_absent_in_testing_period : int) (testing_period_length : int) : bool =
  is_nonresident_election_year &&
  is_nonresident_preceding_year &&
  is_resident_following_year_under_substantial_presence &&
  is_present_for_31_day_and_testing_period days_present_in_31_day_period days_present_in_testing_period days_absent_in_testing_period testing_period_length

(* 7701(b)(9)(B) — code *)
(* fiscal-year alien resident under (b)(1): treated resident for the portion of taxable year within the calendar year *)
let is_resident_for_fiscal_year_portion (is_resident_under_paragraph_1_for_calendar_year : bool) (taxable_year_after_9a : taxable_year) : bool =
  is_resident_under_paragraph_1_for_calendar_year &&
  (match taxable_year_after_9a with
   | Calendar_year_basis -> false
   | Fiscal_year_basis _ -> true
   | Fractional_period _ -> true)

(* 7701(b)(1) — ambiguous *)
let is_us_citizen (individual : person) : bool =
  (* citizenship status not modeled in person type; determined under nationality law, not Title 26 *)
  failwith "unresolved cross-reference"

let is_nonresident_alien (individual : person) (year : int) : bool =
  (* 7701(b)(1)(B): alien who is neither citizen nor resident (per subparagraph (A)) *)
  not (is_us_citizen individual) &&
  not (is_resident_alien individual year)

(* 7701(b)(2) — code *)
(* 7701(b)(2): groups special rules for first year residency, last year residency, and nominal presence disregarded — independent sub-rules, no shared computation *)
module Special_rules_first_last_year_of_residency = struct
  let first_year_residency_period = first_year_residency_period
  let is_excluded_from_residency_last_year = is_excluded_from_residency_last_year
  let days_disregarded_for_closer_connection = days_disregarded_for_closer_connection
end

(* 7701(b)(4) — code *)
(* 7701(b)(4)(B): elect first-year residency treatment if requirements of (A) met *)
let is_first_year_election_resident
    (meets_first_year_election_requirements : bool) (* from 7701(b)(4)(A) *)
    (elects_first_year_treatment : bool) (* (B): election choice *)
    (revoked_with_secretary_consent : bool) (* (F): revocation *)
  : bool =
  meets_first_year_election_requirements &&
  elects_first_year_treatment &&
  not revoked_with_secretary_consent

(* 7701(b)(4)(C): residency begins 1st day of earliest qualifying testing period *)
let first_year_election_residency_start_date
    (meets_first_year_election_requirements : bool)
    (earliest_qualifying_testing_period_start : date) (* start of earliest testing period meeting (A)(iv) *)
  : date option =
  if meets_first_year_election_requirements then
    Some earliest_qualifying_testing_period_start
  else None

(* 7701(b)(4)(D): presence under this paragraph determined by (3)(D)(i) rules, already folded into (A)'s presence test helper *)

(* 7701(b)(4)(E): election timing — cannot elect before meeting substantial presence test for year after election year *)
let is_first_year_election_timely
    (has_met_substantial_presence_test_for_following_calendar_year : bool)
    (filed_on_tax_return_for_election_year : bool)
  : bool =
  has_met_substantial_presence_test_for_following_calendar_year &&
  filed_on_tax_return_for_election_year

(* 7701(b)(4): wraps election eligibility, effective date, and timing rules for first-year election *)
module First_year_election = struct
  let is_resident = is_first_year_election_resident
  let residency_start_date = first_year_election_residency_start_date
  let is_timely = is_first_year_election_timely
end

(* 7701(b)(9) — code *)
module Taxable_year_alien = struct
  (* (A): alien individual who has not established a taxable year for any prior period is treated as having a taxable year which is the calendar year *)
  let default_taxable_year_for_alien (has_established_taxable_year_for_prior_period : bool) : taxable_year option =
    if has_established_taxable_year_for_prior_period then None
    else Some Calendar_year_basis

  (* (B): fiscal-year alien resident under (b)(1): treated resident for the portion of taxable year within the calendar year *)
  let is_resident_for_fiscal_year_portion = is_resident_for_fiscal_year_portion
end

(* 7701(b) — code *)
(* 7701(b): definition of resident alien and nonresident alien — groups general residency test, special first/last year rules, substantial presence test, first-year election, exempt individual, lawful permanent resident status, presence rules, annual statement requirement, taxable year rules, and coordination with section 877 *)
module Resident_and_nonresident_alien = struct
  let is_nonresident_alien = is_nonresident_alien

  module Special_rules_first_last_year_of_residency = Special_rules_first_last_year_of_residency

  let meets_substantial_presence_test_overall = meets_substantial_presence_test_overall

  module First_year_election = First_year_election

  module Exempt_individual = Exempt_individual

  let is_lawful_permanent_resident = is_lawful_permanent_resident
  let ceases_to_be_lawful_permanent_resident = ceases_to_be_lawful_permanent_resident

  let is_present_in_united_states = is_present_in_united_states

  (* 7701(b)(8): Secretary may require annual statement from individual who would meet substantial presence test but for closer-connection (3)(B) or medical-condition (3)(D) exception *)
  let must_submit_annual_statement
      (individual : person)
      (would_meet_test_but_for_closer_connection_exception : bool)
      (would_meet_test_but_for_medical_condition_exception : bool) : bool =
    (* unresolved — needs regulations prescribed by Secretary under 7701(b)(8) *)
    failwith "unresolved cross-reference"

  module Taxable_year_alien = Taxable_year_alien

  let coordination_with_section_877 = coordination_with_section_877
end

