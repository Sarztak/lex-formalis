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
