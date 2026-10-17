module invalid_chained_comparison

fn main() -> Unit {
    let x = 1;
    if 0 < x < 10 {
        print("yes");
    }
}
