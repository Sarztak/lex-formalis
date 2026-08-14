(* shared types *)
(* shared types for § 7701 *)

(* a(4)-(5): whether corporation/partnership created/organized in US or under US/State law *)
type domesticity = Domestic | Foreign

(* a(1) person; a(2) partnership/partner; a(3) corporation; a(7) stock; a(8) shareholder — mutually recursive: corporation/partnership are persons, and reference persons as members *)
type person =
  | Individual
  | Trust
  | Estate
  | Partnership of partnership
  | Association
  | Company
  | Corporation of corporation

and partnership = {
  partners : partner list;
  partnership_domesticity : domesticity;
}

and partner = person (* a(2): member in a syndicate/group/pool/joint venture/unincorporated org *)

and corporation = {
  shareholders : shareholder list;
  stock : stock list;
  corporation_domesticity : domesticity;
}

and shareholder = person (* a(8): member in an association, joint-stock company, or insurance company *)

and stock = {
  issuing_corporation : corporation; (* a(7): shares in an association, joint-stock company, or insurance company *)
}

(* a(6): capacity in which a fiduciary acts *)
type fiduciary_capacity =
  | Guardian
  | Trustee
  | Executor
  | Administrator
  | Receiver
  | Conservator
  | OtherFiduciaryCapacity

(* a(6): person acting in a fiduciary capacity for another person *)
type fiduciary = {
  capacity : fiduciary_capacity;
  fiduciary_person : person;
  acting_for : person;
}

(* a(10): State, construed to include DC where necessary *)
type state =
  | NamedState of string
  | DistrictOfColumbia

(* a(9): United States in geographical sense — States and DC only *)
type united_states = state list

(* a(11)(A): Secretary of the Treasury personally, excluding any delegate *)
type secretary_of_treasury = SecretaryOfTreasury

(* a(12)(B): special delegate jurisdiction for Guam/American Samoa functions *)
type delegate_jurisdiction = Guam | AmericanSamoa

(* a(11)(B)/a(12)(B): person authorized by the Secretary to perform functions, including redelegations *)
type delegate = {
  officer : person;
  authorized_by : secretary_of_treasury;
  jurisdiction : delegate_jurisdiction option;
}

(* a(11)(B): Secretary of the Treasury or his delegate *)
type secretary =
  | SecretaryPersonally of secretary_of_treasury
  | SecretaryDelegate of delegate

(* a(13): Commissioner of Internal Revenue *)
type commissioner = Commissioner

(* a(14): any person subject to any internal revenue tax *)
type taxpayer = person

(* a(15): branches of the military/naval and armed forces of the United States *)
type armed_forces_branch = Army | Navy | AirForce | CoastGuard

(* a(15): commissioned officers vs. personnel below that grade *)
type service_member_rank = CommissionedOfficer | EnlistedPersonnel

(* a(15): a member of the military/naval or armed forces *)
type armed_forces_member = {
  member : person;
  branch : armed_forces_branch;
  rank : service_member_rank;
}

type armed_forces = armed_forces_member list

(* a(16): sections under which a withholding agent must deduct and withhold tax *)
type withholding_section = Section1441 | Section1442 | Section1443 | Section1461

(* a(16): person required to deduct and withhold tax *)
type withholding_agent = {
  agent : person;
  required_under : withholding_section;
}

(* a(17): substitution of husband/wife with former husband/former wife for section 2516 *)
type spouse_role = Husband | Wife | FormerHusband | FormerWife

(* a(18): public international organization entitled to privileges under the IOIA *)
type international_organization = InternationalOrganization of string

(* a(20): employee, including full-time life insurance salesman treated as employee under chapter 21, for specified benefit provisions *)
type employee = Employee | FullTimeLifeInsuranceSalesman

(* a(21): levy includes power of distraint and seizure by any means *)
type levy_means = Distraint | Seizure | OtherLevyMeans of string

type levy = levy_means list

(* a(22): Attorney General of the United States *)
type attorney_general = AttorneyGeneral

(* a(23)-(24): calendar date used in taxable-year/fiscal-year computations *)
type date = { year : int; month : int; day : int }

(* a(23): period covered by a return made for a fractional part of a year *)
type date_range = { range_start : date; range_end : date }

(* a(24): month of the year, used to express the end of a fiscal year *)
type month =
  | January | February | March | April | May | June
  | July | August | September | October | November | December

(* a(24): 12-month accounting period ending on the last day of any month other than December *)
type fiscal_year = { fiscal_year_end_month : month }

(* a(23): calendar year, fiscal year, or fractional period on which taxable income is computed *)
type taxable_year =
  | CalendarYear of int
  | FiscalYearBasis of fiscal_year
  | FractionalPeriod of date_range

(* a(25): method of accounting governing "paid or incurred" / "paid or accrued" *)
type accounting_method = CashMethod | AccrualMethod

(* a(26): trade or business, including performance of the functions of a public office *)
type trade_or_business = PerformanceOfPublicOffice | OtherTradeOrBusiness of string

(* a(27): United States Tax Court *)
type tax_court = UnitedStatesTaxCourt

(* a(29): Internal Revenue Code of 1986 vs. of 1939 *)
type internal_revenue_code = Code1986 | Code1939

(* a(31)(A): estate whose foreign-source income not effectively connected with a US trade or business is excluded from gross income *)
type foreign_estate = {
  foreign_source_income_effectively_connected : bool;
  includible_in_gross_income : bool;
}

(* a(31)(B): trust type, distinguishing foreign trust from domestic trust described in a(30)(E) *)
type trust_type = DomesticTrust | ForeignTrust

(* a(35): person enrolled by the Joint Board for the Enrollment of Actuaries under ERISA *)
type enrolled_actuary = EnrolledActuary

(* a(36)(A): person who prepares, or employs others to prepare, tax returns/refund claims for compensation *)
type tax_return_preparer = {
  preparer : person;
  compensated : bool;
  employs_preparers : person list;
  prepares_substantial_portion : bool;
}

(* a(38): single return made jointly by husband and wife under section 6013 *)
type joint_return = { joint_return_husband : person; joint_return_wife : person }

(* a(40)(A): type of Indian group whose governing body may be an Indian tribal government *)
type tribal_group_type = Tribe | Band | Community | Village | AlaskaNativeGroup

(* a(40)(A): governing body determined by the Secretary to exercise governmental functions *)
type indian_tribal_government = {
  governing_body : person;
  group_type : tribal_group_type;
  exercises_governmental_functions : bool;
}

(* a(41): identifying number assigned to a person under section 6109 *)
type tin = TIN of string

(* a(43): property whose basis is determined by reference to the basis in the hands of a donor/grantor/transferor *)
type transferred_basis_property = { transferor : person }

(* a(44): property whose basis is determined by reference to other property held at any time by the same person *)
type exchanged_basis_property = { other_property_held_by : person }

(* o(5)(D): a transaction, which may itself be a series of transactions *)
type transaction = SingleTransaction | SeriesOfTransactions of transaction list

(* a(45): extent to which gain or loss is recognized on a disposition *)
type recognition_extent = FullyRecognized | PartiallyRecognized | NotRecognized

(* a(45): disposition of property in which gain or loss is not recognized in whole or part *)
type nonrecognition_transaction = {
  underlying_transaction : transaction;
  recognition : recognition_extent;
}

(* a(51)(A)(i): specified foreign entity or foreign-influenced entity *)
type prohibited_foreign_entity = SpecifiedForeignEntity | ForeignInfluencedEntity

(* a(51)(D)(ii)(V): entity with which the taxpayer has entered into a contract, agreement, or arrangement *)
type contractual_counterparty = { counterparty : person; contract_with : person }

(* a(51)(D)(ii)(I)(aa): aspects of production/generation/storage over which a counterparty may hold specific authority *)
type key_aspect =
  | ProductionOfEligibleComponents
  | EnergyGenerationInQualifiedFacility
  | EnergyStorage

(* a(51)(D)(ii)(I)(aa): contractual arrangements granting a counterparty specific authority not captured by authority/ownership/debt control *)
type effective_control = {
  counterparty : contractual_counterparty;
  authority_over : key_aspect list;
}

(* a(51)(D)(ii)(IV): "taxpayer," for subclauses (I)-(III), includes persons related to the taxpayer *)
type prohibited_foreign_entity_taxpayer = { taxpayer : person; related_persons : person list }

(* a(51)(I)(i): meaning per section 45X(c)(6) *)
type applicable_critical_mineral = ApplicableCriticalMineral of string

(* a(51)(I)(ii): meaning per 10 U.S.C. 4872(f)(2) *)
type covered_nation = CoveredNation of string

(* a(51)(I)(iii): meaning per section 45X(c)(1) *)
type eligible_component = EligibleComponent of string

(* a(51)(I)(iv)/a(52)(E)(ii): meaning per section 48E(c)(2)/48(c)(6) *)
type energy_storage_technology = EnergyStorageTechnology of string

(* a(51)(I)(vi): meaning per sections 267(b) and 707(b) *)
type related = Related | NotRelated

(* e(3)(C)/(D): forms of useful energy output from a facility *)
type energy_output = ElectricalPower | MechanicalPower | Steam | Heat | OtherUsefulEnergy

(* e(3)(B): facility providing solid waste disposal services collected substantially from the general public *)
type solid_waste_disposal_facility = {
  service_area_governmental_units : string list;
  substantially_all_from_general_public : bool;
}

(* e(3)(C): facility using one energy source for sequential generation of power combined with other useful energy *)
type cogeneration_facility = {
  energy_source : string;
  outputs : energy_output list;
}

(* e(3)(D): primary energy source of a facility, used to test alternative energy facility status *)
type primary_energy_source = Oil | NaturalGas | Coal | NuclearPower | OtherSource of string

(* e(3)(D): facility producing electrical or thermal energy whose primary source is not oil, gas, coal, or nuclear *)
type alternative_energy_facility = {
  primary_energy_source : primary_energy_source;
  produces : energy_output;
}

(* e(3)(E): treatment works within the meaning of section 212(2) of the Federal Water Pollution Control Act *)
type water_treatment_works_facility = WaterTreatmentWorksFacility

(* e(3)(F): facility using energy storage technology within the meaning of section 48(c)(6) *)
type storage_facility = { uses : energy_storage_technology }

(* h(2)(A): motor vehicle, including a trailer *)
type motor_vehicle = MotorVehicle | Trailer

(* h(2)(A): agreement w/ respect to a motor vehicle meeting the requirements of h(2)(B)-(D) *)
type qualified_motor_vehicle_operating_agreement = {
  vehicle : motor_vehicle;
  meets_requirements : bool;
}

(* h(3)(A): direction in which the rental price may be adjusted *)
type rental_adjustment_direction = Upward | Downward

(* h(3)(A): provision adjusting rental price by reference to amount realized by lessor on disposition *)
type terminal_rental_adjustment_clause = {
  adjustment_direction : rental_adjustment_direction;
  based_on_amount_realized_by_lessor : bool;
}

(* h(3)(B): special-case terminal rental adjustment clause for a lessee who is a motor vehicle dealer *)
type lessee_dealer_provision = {
  lessee : person;
  predetermined_price : float;
  resells_vehicle : bool;
}

(* j(3): basic pay contributed to the Thrift Savings Fund and its treatment as wages under SSA §209 / IRC §3121(a) *)
type wages = {
  basic_pay_contributed_to_tsp : bool;
  included_in_wages_for_ssa : bool;
}

(* j(4): "Member" and "employee" as used in subchapter III of chapter 84 of title 5, U.S. Code *)
type federal_employee_role = Member | FederalEmployee

(* j(4): the Thrift Savings Fund *)
type thrift_savings_fund = ThriftSavingsFund

(* o(5)(A): common law doctrine denying tax benefits to transactions lacking economic substance or business purpose *)
type economic_substance_doctrine = {
  doctrine_transaction : transaction;
  has_economic_substance : bool;
  has_business_purpose : bool;
}

(* a(46): organization of employee representatives, excluding one where >1/2 of members are owner/officer/executive of the employer *)
type employee_representative_organization = {
  members : person list;
  owner_officer_executive_members : person list;
}

(* a(46): bona fide agreement between bona fide employee representatives and one or more employers *)
type collective_bargaining_agreement = {
  representatives : employee_representative_organization;
  employers : person list;
  bona_fide : bool;
}

(* 7701(b)(3)(A) — code *)
(* days_current_year, days_first_preceding_year, days_second_preceding_year : int — day counts supplied by caller from individual's presence record *)
let meets_substantial_presence_test (days_current_year : int) (days_first_preceding_year : int) (days_second_preceding_year : int) : bool =
  let present_31_days = days_current_year >= 31 in
  let weighted_sum =
    (float_of_int days_current_year *. 1.0) +.
    (float_of_int days_first_preceding_year *. (1.0 /. 3.0)) +.
    (float_of_int days_second_preceding_year *. (1.0 /. 6.0))
  in
  let weighted_183_or_more = weighted_sum >= 183.0 in
  present_31_days && weighted_183_or_more

(* 7701(b)(3) — ambiguous *)
(* 7701(b)(3)(B): exception - present <183 days and closer connection to foreign country established via tax home under §911(d)(3) *)
let is_closer_connection_exception (days_current_year : int) (has_closer_connection_to_foreign_country : bool) (sec_911_d_3 : bool) (* cross-ref: §911(d)(3) *) : bool =
  days_current_year < 183 && sec_911_d_3 && has_closer_connection_to_foreign_country

(* 7701(b)(3)(C): exception to (B) - pending adjustment of status or steps toward lawful permanent residence during year *)
let is_closer_connection_exception_inapplicable (has_pending_adjustment_of_status : bool) (took_steps_toward_lawful_permanent_residence : bool) : bool =
  has_pending_adjustment_of_status || took_steps_toward_lawful_permanent_residence

(* 7701(b)(3)(D): exception - day not counted as present if exempt individual or unable to leave due to medical condition arising while present *)
let is_excluded_presence_day (is_exempt_individual : bool) (medical_condition_prevented_departure : bool) : bool =
  is_exempt_individual || medical_condition_prevented_departure

(* 7701(b)(3): substantial presence test - base test plus its exceptions, priority resolved externally by DAG *)
module SubstantialPresenceTest = struct
  let meets_substantial_presence_test = meets_substantial_presence_test
  let is_closer_connection_exception = is_closer_connection_exception
  let is_closer_connection_exception_inapplicable = is_closer_connection_exception_inapplicable
  let is_excluded_presence_day = is_excluded_presence_day
end

