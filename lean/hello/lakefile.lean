import Lake
open Lake DSL

require catalaRuntime from "../../lean/CatalaRuntime"

package "hello"

lean_lib Hello
lean_lib Proofs

@[default_target]
lean_exe hello where
  root := `Main
