open Alcotest
open Remic.Foo.RemicAssets

let test_to_json_empty () =
  let t = { assets = []; nested_remic = [] } in
  let got = to_json t in
  let expect = {|{"assets": [], "nested_remic": []}|} in
  check string "empty" expect got

let () =
  run "RemicAssets" [
    ("to_json", [
       ("empty", `Quick, test_to_json_empty);
    ]);
  ]
