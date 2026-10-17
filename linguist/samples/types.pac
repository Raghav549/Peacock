// Types, structs, lists, loops and error handling.
module type_sample

struct Point {
    x: Int
    y: Int
}

fn distance_squared(a: Point, b: Point) -> Int {
    let dx = a.x - b.x;
    let dy = a.y - b.y;
    return dx * dx + dy * dy;
}

fn main() -> Unit {
    let mut squares: List<Int> = [];
    for i in 1..6 {
        squares.push(i * i);
    }
    let origin = Point(0, 0);
    let corner = Point(3, 4);
    print("distance squared: " + str(distance_squared(origin, corner)));
    print("squares: " + str(squares));
}
