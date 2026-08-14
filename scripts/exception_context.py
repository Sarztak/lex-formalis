import argparse
import json

from statute import load_lookup, build_child_map, build_context  # type: ignore

SYSTEM = (
    "You are an expert tax attorney with deep knowledge of the Internal Revenue Code (IRC). "
    "You reason carefully about statutory structure and interpret provisions with precision."
)

TASK = (
    "Identify which specific IRC provision the following exception clause is modifying or qualifying. "
    "You are given the text of the exception and the provisions that precede it within the same parent section. "
    "Determine which of those preceding provisions the exception overrides or qualifies. "
    "Provisions are structured as: id: provision header, followed by its chapeau or body. "
    "Subprovisions follow the same structure — id: header, followed by their own body or chapeau and further subprovisions. "
    "The reference you return must be the id of a provision explicitly present in the context. "
    "Do not invent or infer a provision id that does not appear in the context. "
    "An exception may override one or more provisions — return all that apply."
)

OUTPUT_SCHEMA = {
    "found": "true if at least one provision being excepted was identified, false otherwise",
    "references": ["id of each provision overridden, present in the context (e.g. '101(a)(1)')"],
}


def build_prompt(exception_id, lookup, child_map):
    exc_text, context_text = build_context(exception_id, lookup, child_map)
    user_message = "\n\n".join([
        TASK,
        json.dumps({"exception": exc_text, "context": context_text}, indent=2, ensure_ascii=False),
        "Respond with JSON only:\n" + json.dumps(OUTPUT_SCHEMA, indent=2),
    ])
    return SYSTEM, user_message


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("section")
    parser.add_argument("exception_id")
    args = parser.parse_args()

    lookup = load_lookup(args.section)
    child_map = build_child_map(lookup)
    system, user_message = build_prompt(args.exception_id, lookup, child_map)

    print("=== SYSTEM ===")
    print(system)
    print("\n=== USER ===")
    print(user_message)


if __name__ == "__main__":
    main()
