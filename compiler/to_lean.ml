(* Catala → Lean 4 backend.
   Targets the Lcalc (Lambda Calculus) IR, same layer as the OCaml backend.
   Does NOT monomorphize — uses Lean 4 built-in Option, Int, Rat natively. *)

open Catala_utils
open Shared_ast
open Lcalc.Ast
module Runtime = Catala_runtime

(* ── Keywords ────────────────────────────────────────────────────────────────── *)

let lean_keywords =
  [ "abbrev"; "apply"; "at"; "axiom"; "by"; "calc"; "class"; "constructor";
    "def"; "deriving"; "do"; "else"; "end"; "example"; "exact"; "extends";
    "false"; "field"; "for"; "forall"; "from"; "fun"; "have"; "if"; "import";
    "in"; "inductive"; "instance"; "intro"; "let"; "match"; "namespace";
    "noncomputable"; "obtain"; "of"; "open"; "opaque"; "partial"; "protected";
    "rfl"; "return"; "section"; "show"; "simp"; "sorry"; "structure"; "syntax";
    "termination_by"; "then"; "theorem"; "this"; "true"; "type"; "universe";
    "unsafe"; "variable"; "where"; "with"; "Type"; "Prop"; "Sort"; "Int";
    "Nat"; "Rat"; "Bool"; "String"; "List"; "Array"; "Option"; "some"; "none" ]

(* ── Renaming ────────────────────────────────────────────────────────────────── *)

let renaming =
  let cap s = String.to_id s |> Stdlib.String.capitalize_ascii in
  let snake s = String.to_snake_case (String.to_id s) in
  Renaming.program ()
    ~reserved:lean_keywords
    ~skip_constant_binders:false ~constant_binder_name:None
    ~namespaced_fields:false ~namespaced_constrs:false
    ~prefix_module:false ~modnames_conflict:false
    ~f_var:snake ~f_struct:cap ~f_field:snake
    ~f_enum:cap ~f_constr:cap

let op_needs_pos (type a) (op : a Op.t) _ty =
  match op with
  | Div_int_int | Div_rat_rat | Div_mon_mon | Div_mon_int | Div_mon_rat
  | Div_dur_dur | Add_dat_dur _ | Sub_dat_dur _ | Map2 | ValueFromJson _ ->
    true
  | _ -> false

(* ── Helpers ─────────────────────────────────────────────────────────────────── *)

let is_option_enum e = EnumName.equal e ConstantNames.option_enum
let is_none_cons c   = EnumConstructor.equal c ConstantNames.none_constr
let is_some_cons c   = EnumConstructor.equal c ConstantNames.some_constr

(* ── Type formatting ─────────────────────────────────────────────────────────── *)

let rec format_typ fmt (typ : typ) =
  match Mark.remove (Type.unquantify typ) with
  | TLit TBool     -> Format.pp_print_string fmt "Bool"
  | TLit TUnit     -> Format.pp_print_string fmt "Unit"
  | TLit TInt      -> Format.pp_print_string fmt "Int"
  | TLit TRat      -> Format.pp_print_string fmt "Rat"
  | TLit TMoney    -> Format.pp_print_string fmt "Int"
  | TLit TDate     -> Format.pp_print_string fmt "CatalaDate"
  | TLit TDuration -> Format.pp_print_string fmt "CatalaDuration"
  | TLit TPos      -> Format.pp_print_string fmt "SourcePos"
  | TStruct s      -> StructName.format fmt s
  | TEnum e when is_option_enum e ->
    (* should not appear directly — wrapped in TOption *)
    Format.pp_print_string fmt "Option _"
  | TEnum e        -> EnumName.format fmt e
  | TOption t      -> Format.fprintf fmt "(Option %a)" format_typ_paren t
  | TArray t       -> Format.fprintf fmt "(Array %a)" format_typ_paren t
  | TTuple []      -> Format.pp_print_string fmt "Unit"
  | TTuple ts      ->
    Format.fprintf fmt "(%a)"
      (Format.pp_print_list ~pp_sep:(fun f () -> Format.pp_print_string f " × ")
         format_typ) ts
  | TArrow (ts, t) ->
    List.iter (fun s -> Format.fprintf fmt "%a → " format_typ_paren s) ts;
    format_typ fmt t
  | TVar v ->
    Format.pp_print_string fmt (Bindlib.name_of v)
  | TForAll tb ->
    let _v, typ, _bctx = Bindlib.unmbind_in Bindlib.empty_ctxt tb in
    format_typ fmt typ
  | TClosureEnv -> Format.pp_print_string fmt "CatalaClosureEnv"
  | TDefault t -> format_typ fmt t
  | TAbstract a -> AbstractType.format fmt a
  | TError -> Format.pp_print_string fmt "CatalaError"

and format_typ_paren fmt (typ : typ) =
  match Mark.remove (Type.unquantify typ) with
  | TLit _ | TStruct _ | TEnum _ -> format_typ fmt typ
  | _ -> Format.fprintf fmt "(%a)" format_typ typ

(* ── Literals ────────────────────────────────────────────────────────────────── *)

let format_lit fmt (l : lit Mark.pos) =
  match Mark.remove l with
  | LBool true  -> Format.pp_print_string fmt "true"
  | LBool false -> Format.pp_print_string fmt "false"
  | LInt i  -> Format.fprintf fmt "(%s : Int)" (Runtime.integer_to_string i)
  | LUnit   -> Format.pp_print_string fmt "()"
  | LRat q  -> Format.fprintf fmt "(%s : Rat)" (Q.to_string q)
  | LMoney e ->
    Format.fprintf fmt "(%s : Int)"
      (Runtime.integer_to_string (Runtime.money_to_cents e))
  | LDate d ->
    let y, m, day = Runtime.date_to_years_months_days d in
    Format.fprintf fmt "⟨%d, %d, %d⟩" y m day
  | LDuration dt ->
    let y, m, d = Runtime.duration_to_years_months_days dt in
    Format.fprintf fmt "⟨%d, %d, %d⟩" y m d

(* ── Expressions ─────────────────────────────────────────────────────────────── *)

let format_var fmt (v : 'm Var.t) =
  Format.pp_print_string fmt (Bindlib.name_of v)

let needs_parens (e : 'm expr) =
  match Mark.remove e with
  | EVar _ | ELit _ | EStruct _ | ETuple _ | EArray _
  | EInj { e = ELit LUnit, _; _ } -> false
  | EInj { cons; _ } when is_none_cons cons -> false
  | _ -> true

let rec format_expr (ctx : decl_ctx) fmt (e : 'm expr) =
  let fe = format_expr ctx in
  let fep fmt e =
    if needs_parens e then Format.fprintf fmt "(%a)" (format_expr ctx) e
    else format_expr ctx fmt e
  in
  match Mark.remove e with
  | EVar v -> format_var fmt v

  | ELit l -> format_lit fmt (Mark.add (Expr.pos e) l)

  | EAbs { binder; tys; _ } ->
    let xs, body = Bindlib.unmbind binder in
    let xs_tau = List.map2 (fun x t -> x, t) (Array.to_list xs) tys in
    Format.fprintf fmt "fun %a => %a"
      (Format.pp_print_list ~pp_sep:Format.pp_print_space
         (fun fmt (x, t) ->
           Format.fprintf fmt "(%a : %a)" format_var x format_typ t))
      xs_tau (fe) body

  | EApp { f = EAbs { binder; tys; _ }, _; args; _ } ->
    (* inline let-binding: (fun x => body) arg  →  let x := arg \n body *)
    let xs, body = Bindlib.unmbind binder in
    let xs_tau = List.map2 (fun x t -> x, t) (Array.to_list xs) tys in
    let bindings = List.map2 (fun (x, t) a -> x, t, a) xs_tau args in
    Format.pp_open_vbox fmt 0;
    List.iter (fun (x, t, a) ->
      Format.fprintf fmt "let %a : %a := %a@," format_var x format_typ t (fe) a)
      bindings;
    fe fmt body;
    Format.pp_close_box fmt ()

  | EApp { f; args; _ } ->
    Format.fprintf fmt "%a %a" fep f
      (Format.pp_print_list ~pp_sep:Format.pp_print_space fep) args

  | EStruct { name = _; fields } ->
    if StructField.Map.is_empty fields then
      Format.pp_print_string fmt "()"
    else begin
      Format.pp_print_string fmt "{ ";
      let bindings = StructField.Map.bindings fields in
      List.iteri (fun i (field, ev) ->
        if i > 0 then Format.pp_print_string fmt ", ";
        Format.fprintf fmt "%a := %a" StructField.format field (fe) ev)
        bindings;
      Format.pp_print_string fmt " }"
    end

  | EStructAccess { e; field; _ } ->
    Format.fprintf fmt "%a.%a" fep e StructField.format field

  (* Option enum — map to Lean native Option *)
  | EInj { e = ELit LUnit, _; cons; name } when is_option_enum name && is_none_cons cons ->
    Format.pp_print_string fmt "none"

  | EInj { e; cons; name } when is_option_enum name && is_some_cons cons ->
    Format.fprintf fmt "some %a" fep e

  (* Unit-payload constructors of the option enum (shouldn't normally appear) *)
  | EInj { e = ELit LUnit, _; cons; name } ->
    Format.fprintf fmt "%a.%a" EnumName.format name EnumConstructor.format cons

  | EInj { e; cons; name } ->
    Format.fprintf fmt "%a.%a %a"
      EnumName.format name EnumConstructor.format cons fep e

  | EMatch { e = e_match; cases; name } when is_option_enum name ->
    Format.pp_open_hvbox fmt 0;
    Format.fprintf fmt "match %a with" (fe) e_match;
    EnumConstructor.Map.iter (fun cons e_body ->
      match Mark.remove e_body with
      | EAbs { binder; _ } ->
        let xs, body = Bindlib.unmbind binder in
        if is_none_cons cons then
          Format.fprintf fmt "@,| none => %a" (fe) body
        else begin
          match Array.to_list xs with
          | [x] -> Format.fprintf fmt "@,| some %a => %a" format_var x (fe) body
          | _ -> assert false
        end
      | _ -> assert false)
    cases;
    Format.pp_close_box fmt ()

  | EMatch { e = e_match; cases; _ } ->
    Format.pp_open_hvbox fmt 0;
    Format.fprintf fmt "match %a with" (fe) e_match;
    EnumConstructor.Map.iter (fun cons e_body ->
      match Mark.remove e_body with
      | EAbs { binder; _ } ->
        let xs, body = Bindlib.unmbind binder in
        (match Array.to_list xs with
        | [] ->
          Format.fprintf fmt "@,| .%a => %a"
            EnumConstructor.format cons (fe) body
        | [x] ->
          Format.fprintf fmt "@,| .%a %a => %a"
            EnumConstructor.format cons format_var x (fe) body
        | xs ->
          Format.fprintf fmt "@,| .%a (%a) => %a"
            EnumConstructor.format cons
            (Format.pp_print_list ~pp_sep:(fun f () -> Format.pp_print_string f ", ")
               format_var) xs
            (fe) body)
      | _ -> assert false)
    cases;
    Format.pp_close_box fmt ()

  | ETuple es ->
    Format.fprintf fmt "(%a)"
      (Format.pp_print_list ~pp_sep:(fun f () -> Format.pp_print_string f ", ")
         (fe)) es

  | ETupleAccess { e; index; size } ->
    let vars = List.init size (fun i -> if i = index then "x" else "_") in
    Format.fprintf fmt "(let (%a) := %a; x)"
      (Format.pp_print_list ~pp_sep:(fun f () -> Format.pp_print_string f ", ")
         Format.pp_print_string) vars (fe) e

  | EArray es ->
    Format.fprintf fmt "#[%a]"
      (Format.pp_print_list ~pp_sep:(fun f () -> Format.pp_print_string f ", ")
         (fe)) es

  | EIfThenElse { cond; etrue; efalse } ->
    Format.fprintf fmt "if %a then %a else %a" (fe) cond fep etrue fep efalse

  | EAppOp { op = Log _, _; args = [arg]; _ } ->
    fe fmt arg

  | EAppOp { op = (HandleExceptions, _); args = [arr]; _ } ->
    Format.fprintf fmt "catalaHandleExceptions %a" fep arr

  | EAppOp { op = (And, _); args = [a; b]; _ } ->
    Format.fprintf fmt "%a && %a" fep a fep b

  | EAppOp { op = (Or, _); args = [a; b]; _ } ->
    Format.fprintf fmt "%a || %a" fep a fep b

  | EAppOp { op = (Not, _); args = [a]; _ } ->
    Format.fprintf fmt "!%a" fep a

  | EAppOp { op = (Eq, _); args = [a; b]; _ } ->
    Format.fprintf fmt "(%a == %a)" fep a fep b

  | EAppOp { op = (Lt, _); args = [a; b]; _ } ->
    Format.fprintf fmt "(%a < %a)" fep a fep b

  | EAppOp { op = (Lte, _); args = [a; b]; _ } ->
    Format.fprintf fmt "(%a <= %a)" fep a fep b

  | EAppOp { op = (Gt, _); args = [a; b]; _ } ->
    Format.fprintf fmt "(%a > %a)" fep a fep b

  | EAppOp { op = (Gte, _); args = [a; b]; _ } ->
    Format.fprintf fmt "(%a >= %a)" fep a fep b

  | EAppOp { op = (ArrayAccess n, _); args = [arr]; _ } ->
    (* ArrayAccess embeds the index in the op name; emit as a plain Nat literal
       so Lean parses it as `catala_o_array_nth N arr` not `catala_o_array_nth(N) arr` *)
    Format.fprintf fmt "catala_o_array_nth %d %a" n fep arr

  | EAppOp { op = op, _; args; _ } ->
    Format.fprintf fmt "catala_%s %a" (Operator.name op)
      (Format.pp_print_list ~pp_sep:Format.pp_print_space fep) args

  | EFatalError_pos { error; pos_expr = _ } ->
    Format.fprintf fmt "catalaFatalError \"%a\"" Print.runtime_error error

  | EExternal { name } ->
    (match Mark.remove name with
     | External_value n -> Format.pp_print_string fmt (TopdefName.base n)
     | External_scope n -> Format.pp_print_string fmt (ScopeName.base n))

  | EPos _ -> Format.pp_print_string fmt "SourcePos.dummy"

  | EBad -> assert false

  | _ -> .

(* ── Type declarations ───────────────────────────────────────────────────────── *)

let format_ctx (type_ordering : TypeIdent.t list) fmt (ctx : decl_ctx) =
  List.iter (function
    | TypeIdent.Struct s ->
      if StructName.path s = [] then begin
        let fields = StructName.Map.find s ctx.ctx_structs in
        Format.fprintf fmt "@,structure %a where" StructName.format s;
        if StructField.Map.is_empty fields then
          Format.fprintf fmt "@,  deriving Repr, DecidableEq, Inhabited@,"
        else begin
          StructField.Map.iter (fun field fty ->
            Format.fprintf fmt "@,  %a : %a"
              StructField.format field format_typ fty)
            fields;
          Format.fprintf fmt "@,  deriving Repr, DecidableEq, Inhabited@,"
        end
      end
    | TypeIdent.Enum e ->
      if EnumName.path e = [] && not (is_option_enum e) then begin
        let constrs = EnumName.Map.find e ctx.ctx_enums in
        Format.fprintf fmt "@,inductive %a where" EnumName.format e;
        EnumConstructor.Map.iter (fun cons ty ->
          match Mark.remove ty with
          | TLit TUnit ->
            Format.fprintf fmt "@,  | %a" EnumConstructor.format cons
          | _ ->
            Format.fprintf fmt "@,  | %a : %a → %a"
              EnumConstructor.format cons format_typ ty EnumName.format e)
          constrs;
        Format.fprintf fmt "@,  deriving Repr, DecidableEq, Inhabited@,"
      end
    | TypeIdent.Abstract _ -> ())
  type_ordering

(* ── Scope body ──────────────────────────────────────────────────────────────── *)

let format_scope_body_expr ctx fmt (lets : 'm expr scope_body_expr) =
  let last_e =
    BoundList.iter lets ~f:(fun var scope_let ->
      Format.fprintf fmt "let %a : %a := %a@,"
        format_var var
        format_typ scope_let.scope_let_typ
        (format_expr ctx) scope_let.scope_let_expr)
  in
  format_expr ctx fmt last_e

(* ── Top-level program ───────────────────────────────────────────────────────── *)

let format_program _filename fmt (p : 'm program) type_ordering =
  Format.pp_open_vbox fmt 0;
  Format.fprintf fmt "-- Generated by the Catala compiler, do not edit!@,";
  Format.fprintf fmt "import CatalaRuntime@,";
  Format.fprintf fmt "open CatalaRuntime@,";

  format_ctx type_ordering fmt p.decl_ctx;

  let _exports = BoundList.iter p.code_items ~f:(fun var item ->
    match item with
    | Topdef (_name, typ, _vis, e) ->
      Format.fprintf fmt "@,def %a : %a :=" format_var var format_typ typ;
      Format.pp_open_vbox fmt 2;
      Format.pp_print_cut fmt ();
      format_expr p.decl_ctx fmt e;
      Format.pp_close_box fmt ();
      Format.pp_print_cut fmt ()
    | ScopeDef (_name, body) ->
      let input_var, body_expr = Bindlib.unbind body.scope_body_expr in
      Format.fprintf fmt "@,def %a (%a : %a) : %a :="
        format_var var
        format_var input_var
        StructName.format body.scope_body_input_struct
        StructName.format body.scope_body_output_struct;
      Format.pp_open_vbox fmt 2;
      Format.pp_print_cut fmt ();
      format_scope_body_expr p.decl_ctx fmt body_expr;
      Format.pp_close_box fmt ();
      Format.pp_print_cut fmt ())
  in
  Format.pp_close_box fmt ()
