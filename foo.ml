[@@@ocaml.warning "-4-26-27-32-33-34-37-41-42-69"]

open Catala_runtime

type asset = {
    amount: decimal;
    qualifies: bool;
}

type remic_assets = {
    assets: asset list;
    nested_remic: remic_assets list;
}

(* External module satisfying Value.External signature *)
module RemicAssets_External : Value.External with type t = remic_assets = struct
    type t = remic_assets
    type _ Value.external_tag += T : t Value.external_tag

    let name = "RemicAssets"
    let equal _pos t1 t2 = t1 = t2
    let compare _pos t1 t2 = Stdlib.compare t1 t2
    let print _ = "<RemicAssets>"

    let rec to_json t =
        let assets_json = List.map (fun a ->
            Printf.sprintf {|{"amount": %s, "qualifies": %b}|}
                (decimal_to_string ~max_prec_digits:10 a.amount) a.qualifies
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
                amount = a |> member "amount" |> to_float |> decimal_of_float;
                qualifies = a |> member "qualifies" |> to_bool;
            }
        ) in
        let nested_remic = j |> member "nested_remic" |> to_list |> List.map (fun nested_j ->
            from_json _pos (Yojson.Safe.to_string nested_j)
        ) in
        { assets; nested_remic }
end

(* Public module satisfying CatalaType - exposes concrete t and rtype *)
module RemicAssets = struct
    type t = remic_assets
    let rtype = Value.External (module RemicAssets_External)
end

(* Top-level function that operates on the concrete record type *)
let rec total_qualifying (t : remic_assets) : money =
    let amt1 = List.fold_left
        (fun acc a ->
            if a.qualifies then o_add_mon_mon acc (money_of_decimal a.amount)
            else acc)
        (money_of_decimal (decimal_of_float 0.0))
        t.assets in
    let amt2 = List.fold_left
        (fun acc r -> o_add_mon_mon acc (total_qualifying r))
        (money_of_decimal (decimal_of_float 0.0))
        t.nested_remic in
    o_add_mon_mon amt1 amt2

let empty : remic_assets = { assets = []; nested_remic = [] }

let () =
    Catala_runtime.register_module "Foo"
        [ "empty", Obj.repr empty
        ; "total_qualifying", Obj.repr total_qualifying
        ]
        ~types:["RemicAssets", (module RemicAssets)]
        "*external*"
