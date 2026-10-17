// PEACOCK language tour: functions, structs, lists, loops, errors, assertions.
module tour

struct Point {
    x: Int
    y: Int
}

fn distance_squared(a: Point, b: Point) -> Int {
    let dx = a.x - b.x;
    let dy = a.y - b.y;
    return dx * dx + dy * dy;
}

fn sum(values: List<Int>) -> Int {
    let mut total = 0;
    for value in values {
        total += value;
    }
    return total;
}

fn doubled(n: Int) -> Int {
    if n < 0 {
        throw "doubled() does not accept negative numbers";
    }
    return n * 2;
}

fn main() -> Unit {
    let mut squares: List<Int> = [];
    for i in 1..6 {
        squares.push(i * i);
    }
    print("squares: " + str(squares));
    print("sum: " + str(sum(squares)));

    let origin = Point(0, 0);
    let corner = Point(3, 4);
    print("distance squared: " + str(distance_squared(origin, corner)));

    let mut i = 0;
    while i < 3 {
        print("loop " + str(i));
        i += 1;
    }

    try {
        print("doubled: " + str(doubled(21)));
        let bad = doubled(-1);
        print("not reached " + str(bad));
    } catch (message) {
        print("caught: " + message);
    }

    assert(sum(squares) == 55, "sum of squares should be 55");

    let label = "  PEACOCK  ";
    print("trimmed: [" + label.trim() + "]");
    print("characters: " + str(len(label)));
    print("split: " + str("a,b,c".split(",")));
    print("types: " + type_name(label) + ", " + type_name(3.5) + ", " + type_name(squares));
}
