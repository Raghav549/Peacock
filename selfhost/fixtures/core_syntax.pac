// Core-syntax fixture for the self-hosted parser parity test.
module core_syntax

struct Pair {
    a: Int
    b: String
}

fn classify(n: Int) -> String {
    if n < 0 {
        return "negative";
    } else if n == 0 {
        return "zero";
    }
    return "positive";
}

fn main() -> Unit {
    let mut values: List<Int> = [1, 2, 3];
    values.push(4);
    let first = values[0];
    let pair = Pair(2, "two");

    let mut i = 0;
    while i < 10 {
        i += 1;
        if i % 2 == 0 {
            continue;
        }
        if i > 7 {
            break;
        }
    }

    let power = 2 ** 3 ** 2;
    let negated = -power;
    let flag = not (negated == 0) and true or false;

    let mut range_total = 0;
    for n in 1..4 {
        range_total += n;
    }

    {
        let nested = "block";
        print(nested);
    }

    assert range_total == 6;
    print(classify(-1) + " " + classify(0) + " " + classify(1));
    print(str(first) + " " + pair.b + " " + str(flag));
    if true {
        print("done");
    } else {
        print("nope");
    }
}
