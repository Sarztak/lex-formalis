import Lake
open Lake DSL

require catalaRuntime from "../../lean/CatalaRuntime"

package "hello"

lean_lib Hello

@[default_target]
lean_exe hello where
  root := `Main
