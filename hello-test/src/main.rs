#![allow(non_snake_case, non_camel_case_types, unused_variables, dead_code,
         unused_mut, unused_imports, clippy::clone_on_copy)]

include!("../../generated/hello.rs");

fn main() {
    // 1 child → only the base 20% rule fires → $16,000 tax on $80,000 income
    let result = income_tax_computation(IncomeTaxComputation_in {
        individual_in: Individual {
            income: Money::from_cents_str("8000000"),
            number_of_children: Integer::from_str("1"),
        },
    });
    println!("income_tax (1 child) = {:?}", result.income_tax);

    // 2 children → both rules fire → conflict (expected)
    let result2 = std::panic::catch_unwind(|| {
        income_tax_computation(IncomeTaxComputation_in {
            individual_in: Individual {
                income: Money::from_cents_str("8000000"),
                number_of_children: Integer::from_str("2"),
            },
        })
    });
    match result2 {
        Ok(r) => println!("income_tax (2 children) = {:?}", r.income_tax),
        Err(_) => println!("income_tax (2 children) = conflict error (expected)"),
    }
}
