(* Catala plugin: registers the "lean" subcommand in the catala CLI.
   Build with dune and load with: catala lean --plugin-dir ./_build/default/compiler lean ... *)

open Cmdliner
open Catala_utils
open Shared_ast

let run includes stdlib output optimize check_invariants autotest
    closure_conversion options =
  let prg, type_ordering, _ren_ctx =
    Driver.Passes.lcalc options ~includes ~stdlib ~optimize ~check_invariants
      ~autotest ~closure_conversion ~keep_special_ops:true
      ~typed:Expr.typed
      ~monomorphize_types:true
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
  with_fmt (fun ppf ->
      To_lean.format_program fname ppf prg type_ordering)

let () =
  let term =
    Term.(
      const run
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
