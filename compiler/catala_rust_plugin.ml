(* Catala plugin: registers the "rust" subcommand in the catala CLI.
   Build with dune and load with: catala --plugin ./catala_rust_plugin.cmxs rust ... *)

open Cmdliner
open Catala_utils

let run includes stdlib output optimize check_invariants autotest
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
  with_fmt (fun ppf ->
      To_rust.format_program fname ppf prg type_ordering)

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
  Driver.Plugin.register "rust"
    ~doc:"Generates a Rust translation of the Catala program."
    ~man:Cli.man_base
    term
