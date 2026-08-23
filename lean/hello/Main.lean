import Hello
open CatalaRuntime

def main : IO Unit := do
  -- 1 child: only the 20% rule fires → tax = 80000 * 0.2 = 16000 (in cents: 1600000)
  let r1 := income_tax_computation { individual_in :=
    { income := 8000000, number_of_children := 1 } }
  IO.println s!"income_tax (1 child)  = {r1.income_tax} cents"

  -- 2 children: both rules fire → ConflictError expected
  try
    let r2 := income_tax_computation { individual_in :=
      { income := 8000000, number_of_children := 2 } }
    IO.println s!"income_tax (2 children) = {r2.income_tax} cents"
  catch e =>
    IO.println s!"income_tax (2 children) = conflict (expected): {e.toString}"
