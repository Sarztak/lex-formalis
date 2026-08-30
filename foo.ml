(* This is a template file following the expected interface and declarations to
 * implement the corresponding Catala module.
 *
 * You should replace all `raise (Error (Impossible))` place-holders with your
 * implementation and rename it to remove the ".template" suffix. *)

[@@@ocaml.warning "-4-26-27-32-33-34-37-41-42-69"]

open Catala_runtime

module RemicAssets = struct
    type asset = {
        amount: float;
        qualifies: bool;
    }

    type t = {
        assets: asset list;
        nested_remic: t list;
    }

    let name = "RemicAssets"
    let equal _pos t1 t2 = t1 = t2
    let compare _pos t1 t2 = Stdlib.compare t1 t2
    let print _ = "<RemicAssets>"

    let rec to_json t =
        let assets_json = List.map (fun a ->
            Printf.sprintf {|{"amount": %f, "qualifies": %b}|}
                a.amount a.qualifies
        ) t.assets in
        let nested_json = List.map to_json t.nested_remic in
        Printf.sprintf {|{"assets": [%s], "nested_remic": [%s]}|}
            (String.concat "," assets_json)
            (String.concat "," nested_json)

    let rec from_json _pos _s = 
        let j = Yojson.Safe.from_string _s in
        let open Yojson.Safe.Util in 
        let assets = j |> member "assets" |> to_list |> List.map (fun a ->
            {
                amount = a |> member "amount" |> to_float;
                qualifies = a |> member "qualifies" |> to_bool;
            }
        ) in 
        let nested_remic = j |> member "nested_remic" |> to_list |> List.map (fun nested_j ->
            from_json _pos (Yojson.Safe.to_string nested_j)
        ) in 
        { assets; nested_remic }

    let rec to_expr t = 
        let assets_str = List.map (fun a ->
            Printf.sprintf {|{amount=%f; qualifies=%b}|} a.amount a.qualifies
        ) t.assets in
        let nested_str = List.map to_expr t.nested_remic in
        Printf.sprintf {|{assets=[%s]; nested_remic=[%s]}|}
            (String.concat ";" assets_str)
            (String.concat ";" nested_str)
end

(*
let () =
  Catala_runtime.register_module "Foo" [  ] "*external*"
 *)
