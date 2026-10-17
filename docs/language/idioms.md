# PEACOCK 0.1 idioms and common mistakes

Valid patterns:

```peacock
fn main() -> Unit {
    let mut total = 0;
    for i in 0..5 { total += i; }          // half-open range
    let xs: List<Int> = [];                // empty list needs annotation
    xs.push(total);
    if xs.contains(10) { print("ten"); }
}
```

```peacock
fn divide(a: Int, b: Int) -> Int {
    if b == 0 { throw "division by zero"; }
    return a / b;
}
```

```peacock
fn main() -> Unit {
    capability fs;
    let text = fs.read_text("input.txt");
    for line in text.split_lines() { print(line); }
}
```

```peacock
use fs
fn main() -> Unit {
    capability fs;
    fs.create_dir("out/reports");
    fs.write_text("out/reports/status.txt", "ready");
}
```

`fs.create_dir` is sandbox-rooted and still requires both the source declaration
and host `--grant fs`; see [capabilities](../security/capabilities.md).

```peacock
fn main() -> Unit {
    capability ui;
    let canvas = graphics.canvas(320, 180);
    let colors = [colour.oklch(0.2, 0.05, 250.0), colour.oklch(0.6, 0.15, 60.0)];
    graphics.gradient(canvas, colors, 30.0);
    graphics.present(canvas);       // host decides where the frame goes
}
```

Common mistakes and diagnostics:

| Mistake | Diagnostic |
|---|---|
| `1 + 2.0` | PE3003; use `float(1) + 2.0` |
| `let x = 1; x = 2;` | PE3007; declare `let mut x` |
| `xs = []` without annotation | PE3003 |
| named argument before a positional one | PE2033 |
| chained comparison `a < b < c` | PE2031 |
| calling `graphs.canvas` | PE3006; unknown namespace |
| `fs.read_text` without `capability fs;` | PE3005 |
| `fs.read_text` declared but host did not grant | PE4001 |
| integer overflow | PE4004 |
| out-of-bounds list access | PE4002 (catchable) |
| `panic` inside `try` | PE4011; not catchable |
| `graphics.present` without `capability ui;` | PE3005 |
| `graphics.present` declared but no host backend | PE4006 (host configuration) |

Formatting: four spaces, one statement per line, braces on the same line,
trailing commas allowed in structs and lists. The source extension is `.pac`.
