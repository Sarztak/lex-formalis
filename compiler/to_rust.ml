(* Catala → Rust backend
   Targets the Scalc IR (statement calculus), same layer as the C/Python/Java backends.
   Generated code depends on the catala-runtime Rust crate. *)

open Catala_utils
open Shared_ast
open Scalc.Ast
module Runtime = Catala_runtime

(* ── Renaming ────────────────────────────────────────────────────────────────── *)

let rust_keywords =
  [ "as"; "break"; "const"; "continue"; "crate"; "else"; "enum"; "extern";
    "false"; "fn"; "for"; "if"; "impl"; "in"; "let"; "loop"; "match"; "mod";
    "move"; "mut"; "pub"; "ref"; "return"; "self"; "Self"; "static"; "struct";
    "super"; "trait"; "true"; "type"; "unsafe"; "use"; "where"; "while";
    "async"; "await"; "dyn"; "abstract"; "become"; "box"; "do"; "final";
    "macro"; "override"; "priv"; "typeof"; "unsized"; "virtual"; "yield";
    "try"; "union"; "i8"; "i16"; "i32"; "i64"; "i128"; "isize";
    "u8"; "u16"; "u32"; "u64"; "u128"; "usize"; "f32"; "f64"; "bool";
    "char"; "str"; "String"; "Vec"; "Option"; "Result"; "Box"; "Rc"; "Arc";
    "None"; "Some"; "Ok"; "Err" ]

let op_needs_pos (type a) (op : a Op.t) _ty =
  match op with
  | Div_int_int | Div_rat_rat | Div_mon_mon | Div_mon_int | Div_mon_rat
  | Div_dur_dur | Add_dat_dur _ | Sub_dat_dur _ | Map2 | Eq | Lt | Lte | Gt
  | Gte | Sort _ | ValueFromJson _ ->
    true
  | _ -> false

let renaming =
  let cap s = String.to_id s |> Stdlib.String.capitalize_ascii in
  let snake s = String.to_snake_case (String.to_id s) in
  Renaming.program ()
    ~reserved:rust_keywords
    ~skip_constant_binders:false ~constant_binder_name:None
    ~namespaced_fields:false ~namespaced_constrs:false
    ~prefix_module:false ~modnames_conflict:false
    ~f_var:snake ~f_struct:cap ~f_field:snake
    ~f_enum:cap ~f_constr:cap

(* ── Environment (tracks which VarNames are global-scope functions) ───────────── *)

(* Global vars are emitted as `pub fn v() -> T { ... }` and must be called
   as `v()` at every use site rather than `v.clone()`. *)
type env = { global_vars : VarName.Set.t }

let empty_env = { global_vars = VarName.Set.empty }

(* ── Helpers ─────────────────────────────────────────────────────────────────── *)

let is_dummy_var v = VarName.to_string v = "_"

let rec is_unit_typ (ty : typ) =
  match Mark.remove ty with
  | TLit TUnit -> true
  | TDefault t -> is_unit_typ t
  | TForAll b -> let _, t = Bindlib.unmbind b in is_unit_typ t
  | _ -> false

(* ── Literals ────────────────────────────────────────────────────────────────── *)

let format_lit fmt (l : lit Mark.pos) =
  match Mark.remove l with
  | LBool true  -> Format.pp_print_string fmt "true"
  | LBool false -> Format.pp_print_string fmt "false"
  | LInt i  -> Format.fprintf fmt "Integer::from_str(\"%s\")" (Runtime.integer_to_string i)
  | LUnit   -> Format.pp_print_string fmt "()"
  | LRat q  -> Format.fprintf fmt "Decimal::from_str(\"%s\")" (Q.to_string q)
  | LMoney e ->
    Format.fprintf fmt "Money::from_cents_str(\"%s\")"
      (Runtime.integer_to_string (Runtime.money_to_cents e))
  | LDate d ->
    let y, m, day = Runtime.date_to_years_months_days d in
    Format.fprintf fmt "Date::new(%d, %d, %d)" y m day
  | LDuration dt ->
    let y, m, d = Runtime.duration_to_years_months_days dt in
    Format.fprintf fmt "Duration::new(%d, %d, %d)" y m d

(* ── Operator names ──────────────────────────────────────────────────────────── *)

let format_op fmt (op : operator Mark.pos) =
  match Mark.remove op with
  | Log _                          -> assert false
  | Add_dat_dur _ | Sub_dat_dur _  -> assert false (* handled in format_expr *)
  | op -> Format.pp_print_string fmt (Operator.name op)

(* ── Types ───────────────────────────────────────────────────────────────────── *)

let rec format_typ ctx fmt (typ : typ) =
  match Mark.remove (Type.unquantify typ) with
  | TLit TBool     -> Format.pp_print_string fmt "bool"
  | TLit TUnit     -> Format.pp_print_string fmt "()"
  | TLit TInt      -> Format.pp_print_string fmt "Integer"
  | TLit TRat      -> Format.pp_print_string fmt "Decimal"
  | TLit TMoney    -> Format.pp_print_string fmt "Money"
  | TLit TDate     -> Format.pp_print_string fmt "Date"
  | TLit TDuration -> Format.pp_print_string fmt "Duration"
  | TLit TPos      -> Format.pp_print_string fmt "SourcePosition"
  | TStruct s      -> StructName.format fmt s
  | TEnum e        -> EnumName.format fmt e
  | TOption t      -> Format.fprintf fmt "Option<%a>" (format_typ ctx) t
  | TArray t       -> Format.fprintf fmt "Vec<%a>" (format_typ ctx) t
  | TArrow ([t1], t2) ->
    Format.fprintf fmt "Box<dyn Fn(%a) -> %a>"
      (format_typ ctx) t1 (format_typ ctx) t2
  | TArrow (ts, t2) ->
    Format.fprintf fmt "Box<dyn Fn(%a) -> %a>"
      (Format.pp_print_list
         ~pp_sep:(fun fmt () -> Format.pp_print_string fmt ", ")
         (format_typ ctx))
      ts (format_typ ctx) t2
  | TTuple [tf; (TClosureEnv, _)] when Type.is_arrow tf ->
    format_typ ctx fmt tf
  | TTuple ts ->
    Format.fprintf fmt "(%a,)"
      (Format.pp_print_list
         ~pp_sep:(fun fmt () -> Format.pp_print_string fmt ", ")
         (format_typ ctx))
      ts
  | TDefault t     -> format_typ ctx fmt t
  | TAbstract a    -> Format.pp_print_string fmt (AbstractType.base a)
  | TVar _         -> Format.pp_print_string fmt "Box<dyn std::any::Any>"
  | TForAll tb ->
    let _, typ = Bindlib.unmbind tb in
    format_typ ctx fmt typ
  | TClosureEnv -> Format.pp_print_string fmt "Box<dyn std::any::Any>"
  | TError -> assert false

(* ── Expressions ─────────────────────────────────────────────────────────────── *)

(* All EVar reads either call the global as a function `v()` (if it's a
   global_var) or use `.clone()` so that the Scalc single-assignment pattern
   maps to valid Rust ownership without requiring Copy on every type. *)

let rec format_expr (ctx : ctx) (env : env) fmt (e : expr) =
  match Mark.remove e with
  | EVar v ->
    if VarName.Set.mem v env.global_vars then
      Format.fprintf fmt "%a()" VarName.format v
    else
      Format.fprintf fmt "%a.clone()" VarName.format v

  | EFunc f ->
    FuncName.format fmt f

  | EStruct { fields; name = s } ->
    Format.fprintf fmt "%a { %a }"
      StructName.format s
      (Format.pp_print_list
         ~pp_sep:(fun fmt () -> Format.pp_print_string fmt ", ")
         (fun fmt (field, ex) ->
           Format.fprintf fmt "%a: %a"
             StructField.format field (format_expr ctx env) ex))
      (StructField.Map.bindings fields)

  | EStructFieldAccess { e1; field; _ } ->
    Format.fprintf fmt "(%a).%a.clone()"
      (format_expr ctx env) e1 StructField.format field

  (* Option special cases — only fire for the canonical (pre-monomorphization) enum *)
  | EInj { cons; name = e_name; _ }
    when EnumName.equal e_name ConstantNames.option_enum
      && EnumConstructor.equal cons ConstantNames.none_constr ->
    Format.pp_print_string fmt "None"

  | EInj { e1; cons; name = e_name; _ }
    when EnumName.equal e_name ConstantNames.option_enum
      && EnumConstructor.equal cons ConstantNames.some_constr ->
    Format.fprintf fmt "Some(%a)" (format_expr ctx env) e1

  (* General enum injection — unit payload → unit variant in Rust (no parens) *)
  | EInj { e1 = ELit LUnit, _; cons; name = enum_name; _ } ->
    Format.fprintf fmt "%a::%a"
      EnumName.format enum_name
      EnumConstructor.format cons

  | EInj { e1; cons; name = enum_name; _ } ->
    Format.fprintf fmt "%a::%a(%a)"
      EnumName.format enum_name
      EnumConstructor.format cons
      (format_expr ctx env) e1

  | EArray { elts; _ } ->
    Format.fprintf fmt "vec![%a]"
      (Format.pp_print_list
         ~pp_sep:(fun fmt () -> Format.pp_print_string fmt ", ")
         (format_expr ctx env))
      elts

  | ELit l -> format_lit fmt (Mark.copy e l)

  | EPosLit ->
    let pos = Mark.get e in
    Format.fprintf fmt
      "SourcePosition { file: %S, start_line: %d, start_column: %d, \
       end_line: %d, end_column: %d }"
      (Pos.get_file pos)
      (Pos.get_start_line pos) (Pos.get_start_column pos)
      (Pos.get_end_line pos) (Pos.get_end_column pos)


  (* Function call on a named function *)
  | EApp { f = EFunc f, _; args; _ } ->
    Format.fprintf fmt "%a(%a)"
      FuncName.format f
      (Format.pp_print_list
         ~pp_sep:(fun fmt () -> Format.pp_print_string fmt ", ")
         (format_expr ctx env))
      args

  (* General function application (closures, externals) *)
  | EApp { f; args; _ } ->
    Format.fprintf fmt "(%a)(%a)"
      (format_expr ctx env) f
      (Format.pp_print_list
         ~pp_sep:(fun fmt () -> Format.pp_print_string fmt ", ")
         (format_expr ctx env))
      args

  (* Logging nodes — pass through *)
  | EAppOp { op = (Log _, _); args = [arg]; _ } ->
    format_expr ctx env fmt arg

  (* Constructor check *)
  | EAppOp { op = (ConstructorCheck (enum, case), _); args = [a]; _ } ->
    if EnumName.equal enum ConstantNames.option_enum then
      if EnumConstructor.equal case ConstantNames.none_constr then
        Format.fprintf fmt "(%a).is_none()" (format_expr ctx env) a
      else
        Format.fprintf fmt "(%a).is_some()" (format_expr ctx env) a
    else
      Format.fprintf fmt "matches!(%a, %a::%a(..)|%a::%a)"
        (format_expr ctx env) a
        EnumName.format enum EnumConstructor.format case
        EnumName.format enum EnumConstructor.format case

  (* Array indexing *)
  | EAppOp { op = (ArrayAccess n, _); args = [a]; _ } ->
    Format.fprintf fmt "(%a)[%d].clone()" (format_expr ctx env) a n

  (* Date/duration arithmetic with rounding *)
  | EAppOp
      { op = ((Add_dat_dur rounding | Sub_dat_dur rounding) as op), _;
        args; _ } ->
    let fname = match op with
      | Add_dat_dur _ -> "o_add_dat_dur"
      | Sub_dat_dur _ -> "o_sub_dat_dur"
      | _ -> assert false
    in
    let rstr = match rounding with
      | RoundUp       -> "DateRounding::RoundUp"
      | RoundDown     -> "DateRounding::RoundDown"
      | AbortOnRound  -> "DateRounding::AbortOnRound"
    in
    Format.fprintf fmt "%s(%s, %a)" fname rstr
      (Format.pp_print_list
         ~pp_sep:(fun fmt () -> Format.pp_print_string fmt ", ")
         (format_expr ctx env))
      args

  (* Debug print *)
  | EAppOp { op = (DebugPrint str, _); args = [a]; _ } ->
    Format.fprintf fmt "catala_debug_print(%S, &format!(\"{:?}\", %a))"
      str (format_expr ctx env) a

  (* FromClosureEnv / ToClosureEnv — only appear with closure conversion on *)
  | EAppOp { op = (FromClosureEnv, _); args = [a]; _ } ->
    format_expr ctx env fmt a
  | EAppOp { op = (ToClosureEnv, _); args = [a]; _ } ->
    format_expr ctx env fmt a

  (* ValueFromJson — stub *)
  | EAppOp { op = (ValueFromJson (_, _), _); _ } ->
    Format.pp_print_string fmt "unimplemented!(\"ValueFromJson\")"

  (* handle_exceptions: unwrap Array_N{content:vec![..],..} → pass Vec directly with closures *)
  | EAppOp { op = (HandleExceptions, _); args = [arg]; _ } ->
    let find_field name m =
      snd (List.find (fun (k, _) ->
        String.equal (Format.asprintf "%a" StructField.format k) name)
        (StructField.Map.bindings m))
    in
    (match Mark.remove arg with
     | EStruct { fields; name = arr_struct } ->
       let content_expr = find_field "content" fields in
       let arr_fields = StructName.Map.find arr_struct ctx.decl_ctx.ctx_structs in
       let opt_enum =
         let content_typ = find_field "content" arr_fields in
         match Mark.remove (Type.unquantify content_typ) with
         | TArray t -> (match Mark.remove (Type.unquantify t) with
             | TEnum e -> e | _ -> assert false)
         | _ -> assert false
       in
       let opt_cons_map = EnumName.Map.find opt_enum ctx.decl_ctx.ctx_enums in
       let none_cons =
         fst (List.find (fun (_, ty) -> is_unit_typ ty)
           (EnumConstructor.Map.bindings opt_cons_map))
       in
       Format.fprintf fmt "handle_exceptions(%a, |__x| matches!(__x, %a::%a), %a::%a)"
         (format_expr ctx env) content_expr
         EnumName.format opt_enum EnumConstructor.format none_cons
         EnumName.format opt_enum EnumConstructor.format none_cons
     | _ ->
       Format.fprintf fmt "handle_exceptions(%a)" (format_expr ctx env) arg)

  (* General operator application *)
  | EAppOp { op; args; _ } ->
    Format.fprintf fmt "%a(%a)"
      format_op op
      (Format.pp_print_list
         ~pp_sep:(fun fmt () -> Format.pp_print_string fmt ", ")
         (format_expr ctx env))
      args

  | ETuple elts ->
    Format.fprintf fmt "(%a,)"
      (Format.pp_print_list
         ~pp_sep:(fun fmt () -> Format.pp_print_string fmt ", ")
         (format_expr ctx env))
      elts

  | ETupleAccess { e1; index; _ } ->
    Format.fprintf fmt "(%a).%d" (format_expr ctx env) e1 index

  | EExternal { modname; name } ->
    Format.fprintf fmt "%a::%s"
      VarName.format (Mark.remove modname)
      (Mark.remove name)

(* ── Statements ──────────────────────────────────────────────────────────────── *)

let rec format_stmt (ctx : ctx) (env : env) fmt (s : stmt Mark.pos) =
  match Mark.remove s with

  (* Inner closure definition *)
  | SInnerFuncDef { name; func = { func_params; func_body; func_return_typ } } ->
    Format.fprintf fmt "@,let %a = move |%a| -> %a {"
      VarName.format (Mark.remove name)
      (Format.pp_print_list
         ~pp_sep:(fun fmt () -> Format.pp_print_string fmt ", ")
         (fun fmt (v, ty) ->
           Format.fprintf fmt "%a: %a"
             VarName.format (Mark.remove v)
             (format_typ ctx) ty))
      func_params
      (format_typ ctx) func_return_typ;
    Format.pp_force_newline fmt ();
    Format.pp_open_vbox fmt 4;
    format_block ctx env fmt func_body;
    Format.pp_close_box fmt ();
    Format.fprintf fmt "@,};"

  (* Declaration without initialiser — Rust allows this for let-before-define *)
  | SLocalDecl { name = v, _; typ } ->
    if is_dummy_var v then ()
    else
      Format.fprintf fmt "@,#[allow(unused_mut)] let mut %a: %a;"
        VarName.format v (format_typ ctx) typ

  (* Unit-typed expression — evaluate for side effects only, or skip *)
  | SLocalInit { expr = ELit LUnit, _; _ }
  | SLocalDef  { expr = ELit LUnit, _; _ } -> ()

  (* Declaration + initialiser in one *)
  | SLocalInit { name = v, _; typ; expr = e } ->
    Format.fprintf fmt "@,#[allow(unused_mut)] let mut %a: %a = %a;"
      VarName.format v (format_typ ctx) typ (format_expr ctx env) e

  (* Assignment to already-declared variable *)
  | SLocalDef { name = v, _; expr = e; _ } ->
    if is_dummy_var v then
      Format.fprintf fmt "@,let _ = %a;" (format_expr ctx env) e
    else
      Format.fprintf fmt "@,%a = %a;" VarName.format v (format_expr ctx env) e

  (* Fatal error → panic with the error kind and source position *)
  | SFatalError { pos_expr; error } ->
    let msg = match Pos.get_attr (Mark.get s)
                      (function ErrorMessage m -> Some m | _ -> None)
              with
              | None   -> ""
              | Some m -> ": " ^ m
    in
    Format.fprintf fmt
      "@,catala_fatal_error(\"%s%s\", %a);"
      (Runtime.error_to_string error) msg (format_expr ctx env) pos_expr

  | SIfThenElse { if_expr; then_block; else_block } ->
    Format.fprintf fmt "@,if %a {" (format_expr ctx env) if_expr;
    Format.pp_force_newline fmt ();
    Format.pp_open_vbox fmt 4;
    format_block ctx env fmt then_block;
    Format.pp_close_box fmt ();
    Format.fprintf fmt "@,} else {";
    Format.pp_force_newline fmt ();
    Format.pp_open_vbox fmt 4;
    format_block ctx env fmt else_block;
    Format.pp_close_box fmt ();
    Format.fprintf fmt "@,}"

  (* Option-typed switch — only fires for the canonical (pre-monomorphization) enum *)
  | SSwitch { switch_var; enum_name = e_name; switch_cases; _ }
    when EnumName.equal e_name ConstantNames.option_enum ->
    let cons_bindings =
      EnumConstructor.Map.bindings
        (EnumName.Map.find e_name ctx.decl_ctx.ctx_enums)
    in
    let cases = List.map2 (fun x (c, _) -> c, x) switch_cases cons_bindings in
    let some_case =
      List.assoc_opt ConstantNames.some_constr cases in
    let none_case =
      List.assoc_opt ConstantNames.none_constr cases in
    (match some_case, none_case with
     | Some sc, Some nc ->
       Format.fprintf fmt "@,match %a {" VarName.format switch_var;
       Format.pp_force_newline fmt ();
       Format.pp_open_vbox fmt 4;
       Format.fprintf fmt "@,Some(%a) => {" VarName.format sc.payload_var_name;
       Format.pp_force_newline fmt ();
       Format.pp_open_vbox fmt 4;
       format_block ctx env fmt sc.case_block;
       Format.pp_close_box fmt ();
       Format.fprintf fmt "@,},";
       Format.fprintf fmt "@,None => {";
       Format.pp_force_newline fmt ();
       Format.pp_open_vbox fmt 4;
       format_block ctx env fmt nc.case_block;
       Format.pp_close_box fmt ();
       Format.fprintf fmt "@,},";
       Format.pp_close_box fmt ();
       Format.fprintf fmt "@,}"
     | _ -> assert false)

  (* General enum switch → Rust match, respecting unit vs non-unit payloads.
     We use the enum definition's constructor type (not payload_var_typ) to
     decide whether the variant is unit — same source of truth as format_ctx. *)
  | SSwitch { switch_var; enum_name; switch_cases; _ } ->
    let cons_bindings =
      EnumConstructor.Map.bindings
        (EnumName.Map.find enum_name ctx.decl_ctx.ctx_enums)
    in
    Format.fprintf fmt "@,match %a {" VarName.format switch_var;
    Format.pp_force_newline fmt ();
    Format.pp_open_vbox fmt 4;
    List.iter2
      (fun { case_block; payload_var_name; _ } (cons_name, cons_typ) ->
        if is_unit_typ cons_typ then begin
          Format.fprintf fmt "@,%a::%a => {"
            EnumName.format enum_name
            EnumConstructor.format cons_name;
          Format.pp_force_newline fmt ();
          Format.pp_open_vbox fmt 4;
          format_block ctx env fmt case_block;
          Format.pp_close_box fmt ();
          Format.fprintf fmt "@,},"
        end else begin
          Format.fprintf fmt "@,%a::%a(%a) => {"
            EnumName.format enum_name
            EnumConstructor.format cons_name
            VarName.format payload_var_name;
          Format.pp_force_newline fmt ();
          Format.pp_open_vbox fmt 4;
          format_block ctx env fmt case_block;
          Format.pp_close_box fmt ();
          Format.fprintf fmt "@,},"
        end)
      switch_cases cons_bindings;
    Format.pp_close_box fmt ();
    Format.fprintf fmt "@,}"

  | SReturn e ->
    Format.fprintf fmt "@,return %a;" (format_expr ctx env) e

  | SSpecialOp _ -> .

and format_block ctx env fmt (b : block) =
  List.iter (format_stmt ctx env fmt) b

(* ── Type declarations (structs and enums) ───────────────────────────────────── *)

let emit_struct fmt ctx s =
  let fields = StructName.Map.find s ctx.decl_ctx.ctx_structs in
  let field_list = StructField.Map.bindings fields in
  Format.fprintf fmt "@,#[derive(Debug, Clone, PartialEq)]";
  if field_list = [] then
    Format.fprintf fmt "@,pub struct %a;" StructName.format s
  else begin
    Format.fprintf fmt "@,pub struct %a {" StructName.format s;
    List.iter
      (fun (field, fty) ->
        Format.fprintf fmt "@,    pub %a: %a,"
          StructField.format field
          (format_typ ctx) fty)
      field_list;
    Format.fprintf fmt "@,}"
  end

let format_ctx
    (type_ordering : TypeIdent.t list)
    (fmt : Format.formatter)
    (ctx : ctx) : StructName.Set.t =
  (* Returns the set of struct names that were emitted, for use by caller. *)
  List.fold_left
    (fun emitted type_ident ->
      match type_ident with
      | TypeIdent.Struct s ->
        if StructName.path s = [] then begin
          emit_struct fmt ctx s;
          StructName.Set.add s emitted
        end else emitted
      | TypeIdent.Enum e ->
        if EnumName.path e = []
           && not (EnumName.equal e ConstantNames.option_enum)
        then begin
          let cons_map = EnumName.Map.find e ctx.decl_ctx.ctx_enums in
          Format.fprintf fmt "@,#[derive(Debug, Clone, PartialEq)]";
          Format.fprintf fmt "@,pub enum %a {" EnumName.format e;
          EnumConstructor.Map.iter
            (fun cons cty ->
              if is_unit_typ cty then
                Format.fprintf fmt "@,    %a," EnumConstructor.format cons
              else
                Format.fprintf fmt "@,    %a(%a),"
                  EnumConstructor.format cons
                  (format_typ ctx) cty)
            cons_map;
          Format.fprintf fmt "@,}"
        end;
        emitted
      | TypeIdent.Abstract _ -> emitted)
    StructName.Set.empty
    type_ordering

(* ── Top-level code items ────────────────────────────────────────────────────── *)

let format_func_item fmt var func ctx env =
  let { func_params; func_body; func_return_typ } = func in
  Format.fprintf fmt "@,pub fn %a(%a) -> %a {"
    FuncName.format var
    (Format.pp_print_list
       ~pp_sep:(fun fmt () -> Format.pp_print_string fmt ", ")
       (fun fmt (v, ty) ->
         Format.fprintf fmt "%a: %a"
           VarName.format (Mark.remove v)
           (format_typ ctx) ty))
    func_params
    (format_typ ctx) func_return_typ;
  Format.pp_force_newline fmt ();
  Format.pp_open_vbox fmt 4;
  format_block ctx env fmt func_body;
  Format.pp_close_box fmt ();
  Format.fprintf fmt "@,}@,"

(* Returns an updated env recording any new global vars *)
let format_code_item ctx fmt (env : env) item : env =
  match item with
  | SVar { var; expr; typ; _ } ->
    (* Global variables are lazy functions, like the C backend.
       We record [var] in global_vars so call sites emit [var()] not [var.clone()]. *)
    Format.fprintf fmt "@,pub fn %a() -> %a {" VarName.format var (format_typ ctx) typ;
    Format.pp_force_newline fmt ();
    Format.pp_open_vbox fmt 4;
    Format.fprintf fmt "%a" (format_expr ctx env) expr;
    Format.pp_close_box fmt ();
    Format.fprintf fmt "@,}@,";
    { global_vars = VarName.Set.add var env.global_vars }

  | SFunc { var; func; _ } ->
    format_func_item fmt var func ctx env;
    env

  | SScope { scope_body_var = var; scope_body_func = func; _ } ->
    format_func_item fmt var func ctx env;
    env

(* ── Tests (entry points for catala test scopes) ─────────────────────────────── *)

let format_tests ctx env fmt (p : program) =
  let _lifted, tests = p.tests in
  if tests <> [] then begin
    Format.fprintf fmt "@,#[cfg(feature = \"catala_tests\")]";
    Format.fprintf fmt "@,pub mod catala_tests {";
    Format.fprintf fmt "@,    use super::*;";
    List.iteri
      (fun i (_name, _var, block) ->
        Format.fprintf fmt "@,    #[test]@,    fn test_%d() {@[<v 2>%a@]@,    }@,"
          i (format_block ctx env) block)
      tests;
    Format.fprintf fmt "@,}"
  end

(* ── Program ─────────────────────────────────────────────────────────────────── *)

let format_program
    (output_file : File.t option)
    (fmt : Format.formatter)
    (p : program)
    (type_ordering : TypeIdent.t list) : unit =
  ignore output_file;
  Format.pp_set_geometry fmt ~max_indent:999_990 ~margin:1_000_000;
  Format.pp_open_vbox fmt 0;
  let header =
    if Global.options.gen_external then
      [ "// Template file — replace `unimplemented!()` stubs with your implementation.";
        "// Rename by removing the \".template\" suffix when done." ]
    else
      [ "// Generated by the Catala compiler — do not edit!" ]
  in
  List.iter (fun s -> Format.fprintf fmt "%s@," s) header;
  Format.fprintf fmt "use catala_runtime::*;@,";
  List.iter
    (fun (m, intf_id) ->
      if not intf_id.is_stdlib then
        Format.fprintf fmt "use %a as %a;@,"
          ModuleName.format (ModuleName.normalise m)
          VarName.format (ModuleName.Map.find m p.ctx.modules))
    (Program.modules_to_list ~trim_stdlib:false p.ctx.decl_ctx.ctx_modules);
  Format.pp_print_cut fmt ();
  let emitted_structs = format_ctx type_ordering fmt p.ctx in
  (* Emit any structs referenced in function parameters but missing from type_ordering.
     This happens for empty scope-input structs that Catala's driver omits from ordering. *)
  let collect_param_structs acc item =
    let check_typ acc ty =
      match Mark.remove (Type.unquantify ty) with
      | TStruct s when StructName.path s = [] && not (StructName.Set.mem s acc) ->
        emit_struct fmt p.ctx s;
        StructName.Set.add s acc
      | _ -> acc
    in
    match item with
    | SFunc { func = { func_params; _ }; _ }
    | SScope { scope_body_func = { func_params; _ }; _ } ->
      List.fold_left (fun a (_, ty) -> check_typ a ty) acc func_params
    | _ -> acc
  in
  let _emitted_structs =
    List.fold_left collect_param_structs emitted_structs p.code_items
  in
  Format.pp_print_cut fmt ();
  let env =
    List.fold_left (format_code_item p.ctx fmt) empty_env p.code_items
  in
  format_tests p.ctx env fmt p;
  Format.pp_print_flush fmt ()
