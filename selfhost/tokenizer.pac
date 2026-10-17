// First self-hosting component: a PEACOCK tokenizer written in PEACOCK.
//
// It is compiled and executed by the PEACOCK toolchain like any other program.
// It is NOT the compiler: parsing, typing, IR and code generation are still
// implemented in the bootstrap language. Its token counts are compared against
// the bootstrap lexer in tests/integration/test_selfhost.py.
module selfhost_tokenizer

use text
use fs
use process

fn is_ident_start(ch: String) -> Bool {
    if len(ch) == 0 {
        return false;
    }
    return text.is_alpha(ch) or ch == "_";
}

fn is_ident_continue(ch: String) -> Bool {
    if len(ch) == 0 {
        return false;
    }
    return text.is_alnum(ch) or ch == "_";
}

fn scan_number(source: String, start: Int) -> Int {
    let n = len(source);
    let mut i = start;
    let ch = text.char_at(source, i);
    if ch == "0" and i + 1 < n {
        let next = text.char_at(source, i + 1);
        if next == "x" or next == "X" or next == "b" or next == "B" or next == "o" or next == "O" {
            i += 2;
            while i < n {
                let c = text.char_at(source, i);
                if text.is_alnum(c) or c == "_" {
                    i += 1;
                } else {
                    break;
                }
            }
            return i;
        }
    }
    while i < n {
        let c = text.char_at(source, i);
        if text.is_digit(c) or c == "_" {
            i += 1;
        } else {
            break;
        }
    }
    if i + 1 < n {
        let dot = text.char_at(source, i);
        let after = text.char_at(source, i + 1);
        if dot == "." and text.is_digit(after) {
            i += 1;
            while i < n {
                let c = text.char_at(source, i);
                if text.is_digit(c) or c == "_" {
                    i += 1;
                } else {
                    break;
                }
            }
        }
    }
    if i < n {
        let e = text.char_at(source, i);
        if e == "e" or e == "E" {
            let mut j = i + 1;
            if j < n {
                let sign = text.char_at(source, j);
                if sign == "+" or sign == "-" {
                    j += 1;
                }
            }
            if j < n {
                if text.is_digit(text.char_at(source, j)) {
                    i = j;
                    while i < n {
                        if text.is_digit(text.char_at(source, i)) {
                            i += 1;
                        } else {
                            break;
                        }
                    }
                }
            }
        }
    }
    return i;
}

fn main() -> Unit {
    capability fs;

    let args = process.args();
    if args.len() < 1 {
        print("usage: tokenizer.pac <path.pac> [--dump]");
        return;
    }
    let path = args.get(0);
    let source = fs.read_text(path);
    let n = len(source);
    let keywords = [
        "module", "use", "as", "fn", "let", "mut", "if", "else", "while", "for",
        "in", "return", "break", "continue", "struct", "model", "training",
        "capability", "try", "catch", "throw", "assert", "true", "false",
        "and", "or", "not"
    ];
    let two_char_ops = [
        "**", "==", "!=", "<=", ">=", "->", "+=", "-=", "*=", "/=", "%=", ".."
    ];
    let single_char_ops = [
        "+", "-", "*", "/", "%", "<", ">", "=", ".", ",", ":", ";", "(",
        ")", "{", "}", "[", "]", "?"
    ];

    let tokens: List<String> = [];
    let mut i = 0;
    while i < n {
        let ch = text.char_at(source, i);
        if text.is_space(ch) {
            i += 1;
            continue;
        }
        if ch == "/" and i + 1 < n {
            let nxt = text.char_at(source, i + 1);
            if nxt == "/" {
                i += 2;
                while i < n {
                    if text.char_at(source, i) == "\n" {
                        break;
                    }
                    i += 1;
                }
                continue;
            }
            if nxt == "*" {
                let mut depth = 1;
                i += 2;
                while i < n and depth > 0 {
                    if i + 1 < n {
                        let a = text.char_at(source, i);
                        let b = text.char_at(source, i + 1);
                        if a == "/" and b == "*" {
                            depth += 1;
                            i += 2;
                            continue;
                        }
                        if a == "*" and b == "/" {
                            depth -= 1;
                            i += 2;
                            continue;
                        }
                    }
                    i += 1;
                }
                continue;
            }
        }
        if ch == "\"" {
            i += 1;
            let mut value = "";
            while i < n {
                let c = text.char_at(source, i);
                if c == "\\" {
                    if i + 1 < n {
                        value = value + c + text.char_at(source, i + 1);
                        i += 2;
                    } else {
                        i += 1;
                    }
                    continue;
                }
                if c == "\"" {
                    i += 1;
                    break;
                }
                value = value + c;
                i += 1;
            }
            tokens.push("str:" + value);
            continue;
        }
        if text.is_digit(ch) {
            let end = scan_number(source, i);
            tokens.push("num:" + source.substring(i, end));
            i = end;
            continue;
        }
        if is_ident_start(ch) {
            let start = i;
            i += 1;
            while i < n {
                if is_ident_continue(text.char_at(source, i)) {
                    i += 1;
                } else {
                    break;
                }
            }
            let word = source.substring(start, i);
            if keywords.contains(word) {
                tokens.push("kw:" + word);
            } else {
                tokens.push("id:" + word);
            }
            continue;
        }
        if i + 1 < n {
            let pair = source.substring(i, i + 2);
            if two_char_ops.contains(pair) {
                tokens.push("op:" + pair);
                i += 2;
                continue;
            }
        }
        if single_char_ops.contains(ch) {
            tokens.push("op:" + ch);
            i += 1;
            continue;
        }
        tokens.push("other:" + ch);
        i += 1;
    }

    print(str(tokens.len()));
    if args.len() > 1 and args.get(1) == "--dump" {
        for token in tokens {
            print(token);
        }
    }
}
