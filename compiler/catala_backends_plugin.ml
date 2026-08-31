(* Combined Catala plugin: registers "rust" and "lean" subcommands. *)

open Cmdliner
open Catala_utils
open Shared_ast

(* ── Rust backend ────────────────────────────────────────────────────────────── *)

let run_rust includes stdlib output optimize check_invariants autotest
    closure_conversion options =
  let prg, type_ordering, _ren_ctx =
    Driver.Passes.scalc options ~includes ~stdlib ~optimize ~check_invariants
      ~autotest ~closure_conversion ~keep_special_ops:false
      ~dead_value_assignment:false ~no_struct_literals:false
      ~keep_module_names:false ~monomorphize_types:true
      ~renaming:(Some To_rust.renaming)
      ~lift_pos:(Some To_rust.op_needs_pos)
  in
  Message.debug "Compiling program into Rust...";
  let output_file = Option.map options.Global.path_rewrite output in
  let fname, with_fmt =
    File.get_main_out_formatter
      ~source_file:options.Global.input_src
      ~output_file
      ~ext:(if Global.options.gen_external then "template.rs" else "rs")
      ()
  in
  Message.debug "Writing to %s" (Option.value ~default:"stdout" fname);
  with_fmt (fun ppf -> To_rust.format_program fname ppf prg type_ordering)

let () =
  let term =
    Term.(
      const run_rust
      $ Cli.Flags.include_dirs
      $ Cli.Flags.stdlib_dir
      $ Cli.Flags.output
      $ Cli.Flags.optimize
      $ Cli.Flags.check_invariants
      $ Cli.Flags.autotest
      $ Cli.Flags.closure_conversion)
  in
  Driver.Plugin.register "rust"
    ~doc:"Generates a Rust translation of the Catala program."
    ~man:Cli.man_base
    term

(* ── Lean 4 backend ──────────────────────────────────────────────────────────── *)

let run_lean includes stdlib output optimize check_invariants autotest
    closure_conversion options =
  let prg, type_ordering, _ren_ctx =
    Driver.Passes.lcalc options ~includes ~stdlib ~optimize ~check_invariants
      ~autotest ~closure_conversion ~keep_special_ops:true
      ~typed:Expr.typed
      ~monomorphize_types:false
      ~renaming:(Some To_lean.renaming)
      ~lift_pos:(Some To_lean.op_needs_pos)
  in
  Message.debug "Compiling program into Lean 4...";
  let output_file = Option.map options.Global.path_rewrite output in
  let fname, with_fmt =
    File.get_main_out_formatter
      ~source_file:options.Global.input_src
      ~output_file
      ~ext:"lean"
      ()
  in
  Message.debug "Writing to %s" (Option.value ~default:"stdout" fname);
  with_fmt (fun ppf -> To_lean.format_program fname ppf prg type_ordering)

let () =
  let term =
    Term.(
      const run_lean
      $ Cli.Flags.include_dirs
      $ Cli.Flags.stdlib_dir
      $ Cli.Flags.output
      $ Cli.Flags.optimize
      $ Cli.Flags.check_invariants
      $ Cli.Flags.autotest
      $ Cli.Flags.closure_conversion)
  in
  Driver.Plugin.register "lean"
    ~doc:"Generates a Lean 4 translation of the Catala program."
    ~man:Cli.man_base
    term
