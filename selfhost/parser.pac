// Self-hosted PEACOCK parser (stage 2a).
//
// This program is written in PEACOCK and executed by the real PEACOCK VM. It
// lexes and parses the core language (module/use/struct/fn declarations,
// statements, expressions) and prints a canonical S-expression AST digest.
// tests/integration/test_selfhost_parser.py compares the digest with one
// produced from the bootstrap AST on the core corpus.
//
// Scope and honesty:
//   * the parser covers the full 0.1 grammar, including model and training
//     declarations; the bootstrap parser remains the diagnostics/recovery oracle;
//   * the parser is strict: it stops at the first syntax error instead of
//     recovering like the bootstrap parser;
//   * it parses a file passed as the first program argument and requires the
//     `fs` capability.
//
// This is a genuine self-hosted component, not the full compiler, and it does
// not make the toolchain self-hosting.

module selfhost_parser

use text
use fs
use process

struct Tok {
    kind: String
    text: String
    start: Int
}

struct Parser {
    toks: List<Tok>
    pos: Int
    source: String
}

// ---------------------------------------------------------------------------
// Lexer
// ---------------------------------------------------------------------------

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

fn is_float_literal(s: String) -> Bool {
    if len(s) >= 2 {
        let first = text.char_at(s, 0);
        let second = text.char_at(s, 1);
        if first == "0" and (second == "x" or second == "X" or second == "b" or second == "B" or second == "o" or second == "O") {
            return false;
        }
    }
    return s.contains(".") or s.contains("e") or s.contains("E");
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

fn lex_error(source: String, index: Int, message: String) -> Unit {
    let mut line = 1;
    let mut col = 1;
    let mut i = 0;
    while i < index and i < len(source) {
        if text.char_at(source, i) == "\n" {
            line += 1;
            col = 1;
        } else {
            col += 1;
        }
        i += 1;
    }
    throw "lex error at line " + str(line) + ", column " + str(col) + ": " + message;
}

fn lex(source: String) -> List<Tok> {
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
        "+", "-", "*", "/", "%", "<", ">", "=", ".", ",", ":", ";", "(", ")",
        "{", "}", "[", "]", "?"
    ];

    let tokens: List<Tok> = [];
    let n = len(source);
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
                let start = i;
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
                if depth > 0 {
                    lex_error(source, start, "unterminated block comment");
                }
                continue;
            }
        }
        if ch == "\"" {
            let start = i;
            i += 1;
            let mut closed = false;
            while i < n {
                let c = text.char_at(source, i);
                if c == "\\" {
                    i += 2;
                    continue;
                }
                if c == "\"" {
                    i += 1;
                    closed = true;
                    break;
                }
                i += 1;
            }
            if not closed {
                lex_error(source, start, "unterminated string literal");
            }
            tokens.push(Tok("str", source.substring(start, i), start));
            continue;
        }
        if text.is_digit(ch) {
            let end = scan_number(source, i);
            let raw = source.substring(i, end);
            if is_float_literal(raw) {
                tokens.push(Tok("float", raw, i));
            } else {
                tokens.push(Tok("int", raw, i));
            }
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
                tokens.push(Tok("kw", word, start));
            } else {
                tokens.push(Tok("id", word, start));
            }
            continue;
        }
        if i + 1 < n {
            let pair = source.substring(i, i + 2);
            if two_char_ops.contains(pair) {
                tokens.push(Tok("op", pair, i));
                i += 2;
                continue;
            }
        }
        if single_char_ops.contains(ch) {
            tokens.push(Tok("op", ch, i));
            i += 1;
            continue;
        }
        lex_error(source, i, "invalid character '" + ch + "'");
        i += 1;
    }
    tokens.push(Tok("eof", "", n));
    return tokens;
}

// ---------------------------------------------------------------------------
// Parser state helpers
// ---------------------------------------------------------------------------

fn node(name: String, parts: List<String>) -> String {
    if len(parts) == 0 {
        return "(" + name + ")";
    }
    return "(" + name + " " + parts.join(" ") + ")";
}

fn peek_at(p: Parser, offset: Int) -> Tok {
    let index = p.pos + offset;
    if index < 0 or index >= p.toks.len() {
        return Tok("eof", "", p.source.len());
    }
    return p.toks.get(index);
}

fn peek(p: Parser) -> Tok {
    return peek_at(p, 0);
}

fn at_kind(p: Parser, kind: String) -> Bool {
    return peek(p).kind == kind;
}

fn at_kw(p: Parser, word: String) -> Bool {
    let t = peek(p);
    return t.kind == "kw" and t.text == word;
}

fn at_op(p: Parser, op: String) -> Bool {
    let t = peek(p);
    return t.kind == "op" and t.text == op;
}

fn advance(p: Parser) -> Tok {
    let t = peek(p);
    if t.kind != "eof" {
        p.pos += 1;
    }
    return t;
}

fn accept_op(p: Parser, op: String) -> Bool {
    if at_op(p, op) {
        p.pos += 1;
        return true;
    }
    return false;
}

fn error_at(p: Parser, index: Int, message: String) -> Unit {
    let mut line = 1;
    let mut col = 1;
    let mut i = 0;
    while i < index and i < len(p.source) {
        if text.char_at(p.source, i) == "\n" {
            line += 1;
            col = 1;
        } else {
            col += 1;
        }
        i += 1;
    }
    throw "parse error at line " + str(line) + ", column " + str(col) + ": " + message;
}

fn error_here(p: Parser, message: String) -> Unit {
    error_at(p, peek(p).start, message);
}

fn expect_op(p: Parser, op: String) -> Tok {
    if not at_op(p, op) {
        let t = peek(p);
        error_here(p, "expected '" + op + "', found " + describe_token(t));
    }
    return advance(p);
}

fn expect_kind(p: Parser, kind: String, what: String) -> Tok {
    if not at_kind(p, kind) {
        let t = peek(p);
        error_here(p, "expected " + what + ", found " + describe_token(t));
    }
    return advance(p);
}

fn expect_ident(p: Parser, what: String) -> Tok {
    return expect_kind(p, "id", what);
}

fn describe_token(t: Tok) -> String {
    if t.kind == "eof" {
        return "end of file";
    }
    if t.kind == "id" {
        return "identifier '" + t.text + "'";
    }
    if t.kind == "kw" {
        return "keyword '" + t.text + "'";
    }
    if t.kind == "str" {
        return "string literal";
    }
    return "'" + t.text + "'";
}

// ---------------------------------------------------------------------------
// Type expressions
// ---------------------------------------------------------------------------

fn parse_type(p: Parser) -> String {
    let name_tok = expect_ident(p, "a type name");
    let name = name_tok.text;
    if name == "Tensor" {
        expect_op(p, "<");
        let dtype = expect_ident(p, "a tensor dtype").text;
        let parts = [dtype];
        if accept_op(p, ",") {
            expect_op(p, "[");
            let dims: List<String> = [];
            if not at_op(p, "]") {
                while true {
                    dims.push(expect_kind(p, "int", "a tensor dimension").text);
                    if not accept_op(p, ",") {
                        break;
                    }
                }
            }
            expect_op(p, "]");
            parts.push(node("shape", dims));
        }
        expect_op(p, ">");
        return node("tensor", parts);
    }
    if name == "List" {
        expect_op(p, "<");
        let element = parse_type(p);
        expect_op(p, ">");
        return node("tylist", [element]);
    }
    if at_op(p, "<") {
        advance(p);
        let args: List<String> = [];
        while true {
            args.push(parse_type(p));
            if not accept_op(p, ",") {
                break;
            }
        }
        expect_op(p, ">");
        let parts = [name];
        for arg in args {
            parts.push(arg);
        }
        return node("t", parts);
    }
    return node("t", [name]);
}

fn parse_params(p: Parser) -> String {
    expect_op(p, "(");
    let params: List<String> = [];
    if not at_op(p, ")") {
        while true {
            let name = expect_ident(p, "a parameter name").text;
            expect_op(p, ":");
            let ty = parse_type(p);
            params.push(node("param", [name, ty]));
            if not accept_op(p, ",") {
                break;
            }
            if at_op(p, ")") {
                break;
            }
        }
    }
    expect_op(p, ")");
    return node("params", params);
}

// ---------------------------------------------------------------------------
// Expressions (mirrors the bootstrap precedence grammar)
// ---------------------------------------------------------------------------

fn parse_expr(p: Parser) -> String {
    return parse_or(p);
}

fn parse_or(p: Parser) -> String {
    let mut left = parse_and(p);
    while at_kw(p, "or") {
        advance(p);
        let right = parse_and(p);
        left = node("b", ["or", left, right]);
    }
    return left;
}

fn parse_and(p: Parser) -> String {
    let mut left = parse_not(p);
    while at_kw(p, "and") {
        advance(p);
        let right = parse_not(p);
        left = node("b", ["and", left, right]);
    }
    return left;
}

fn parse_not(p: Parser) -> String {
    if at_kw(p, "not") {
        advance(p);
        let operand = parse_not(p);
        return node("u", ["not", operand]);
    }
    return parse_comparison(p);
}

fn is_comparison_op(p: Parser) -> Bool {
    if at_op(p, "==") or at_op(p, "!=") or at_op(p, "<") or at_op(p, "<=") or at_op(p, ">") or at_op(p, ">=") {
        return true;
    }
    return false;
}

fn parse_comparison(p: Parser) -> String {
    let left = parse_range(p);
    if is_comparison_op(p) {
        let op = advance(p).text;
        let right = parse_range(p);
        if is_comparison_op(p) {
            error_here(p, "chained comparisons are not supported; combine comparisons with 'and'");
        }
        return node("b", [op, left, right]);
    }
    return left;
}

fn parse_range(p: Parser) -> String {
    let left = parse_additive(p);
    if accept_op(p, "..") {
        let right = parse_additive(p);
        return node("range", [left, right]);
    }
    return left;
}

fn parse_additive(p: Parser) -> String {
    let mut left = parse_multiplicative(p);
    while at_op(p, "+") or at_op(p, "-") {
        let op = advance(p).text;
        let right = parse_multiplicative(p);
        left = node("b", [op, left, right]);
    }
    return left;
}

fn parse_multiplicative(p: Parser) -> String {
    let mut left = parse_unary(p);
    while at_op(p, "*") or at_op(p, "/") or at_op(p, "%") {
        let op = advance(p).text;
        let right = parse_unary(p);
        left = node("b", [op, left, right]);
    }
    return left;
}

fn parse_unary(p: Parser) -> String {
    if at_op(p, "-") {
        advance(p);
        let operand = parse_unary(p);
        return node("u", ["-", operand]);
    }
    if at_kw(p, "not") {
        advance(p);
        let operand = parse_unary(p);
        return node("u", ["not", operand]);
    }
    return parse_power(p);
}

fn parse_power(p: Parser) -> String {
    let base = parse_postfix(p);
    if accept_op(p, "**") {
        let exponent = parse_unary(p);
        return node("b", ["**", base, exponent]);
    }
    return base;
}

fn parse_call_args(p: Parser) -> List<String> {
    let args: List<String> = [];
    if not at_op(p, ")") {
        let mut saw_named = false;
        while true {
            if at_kind(p, "id") and peek_at(p, 1).kind == "op" and peek_at(p, 1).text == ":" {
                let name = advance(p).text;
                advance(p);
                let value = parse_expr(p);
                args.push(node("arg", [name, value]));
                saw_named = true;
            } else {
                if saw_named {
                    error_here(p, "positional arguments may not follow named arguments");
                }
                let value = parse_expr(p);
                args.push(node("arg", ["_", value]));
            }
            if not accept_op(p, ",") {
                break;
            }
            if at_op(p, ")") {
                break;
            }
        }
    }
    expect_op(p, ")");
    return args;
}

fn parse_postfix(p: Parser) -> String {
    let mut expr = parse_primary(p);
    while true {
        if accept_op(p, "(") {
            let args = parse_call_args(p);
            let parts = [expr];
            for arg in args {
                parts.push(arg);
            }
            expr = node("call", parts);
            continue;
        }
        if accept_op(p, ".") {
            let name = expect_ident(p, "a field name after '.'").text;
            expr = node("field", [expr, name]);
            continue;
        }
        if accept_op(p, "[") {
            let index = parse_expr(p);
            expect_op(p, "]");
            expr = node("index", [expr, index]);
            continue;
        }
        break;
    }
    return expr;
}

fn parse_primary(p: Parser) -> String {
    let t = peek(p);
    if t.kind == "int" {
        advance(p);
        return node("int", []);
    }
    if t.kind == "float" {
        advance(p);
        return node("float", []);
    }
    if t.kind == "str" {
        advance(p);
        return node("str", []);
    }
    if at_kw(p, "true") {
        advance(p);
        return node("true", []);
    }
    if at_kw(p, "false") {
        advance(p);
        return node("false", []);
    }
    if t.kind == "id" {
        advance(p);
        return node("name", [t.text]);
    }
    if accept_op(p, "(") {
        let inner = parse_expr(p);
        expect_op(p, ")");
        return inner;
    }
    if accept_op(p, "[") {
        let elements: List<String> = [];
        if not at_op(p, "]") {
            while true {
                elements.push(parse_expr(p));
                if not accept_op(p, ",") {
                    break;
                }
                if at_op(p, "]") {
                    break;
                }
            }
        }
        expect_op(p, "]");
        return node("list", elements);
    }
    error_here(p, "expected an expression, found " + describe_token(t));
    return node("error", []);
}

// ---------------------------------------------------------------------------
// Statements
// ---------------------------------------------------------------------------

fn parse_let(p: Parser) -> String {
    advance(p);
    let parts: List<String> = [];
    if at_kw(p, "mut") {
        advance(p);
        parts.push("mut");
    }
    let name = expect_ident(p, "a variable name").text;
    parts.push(name);
    if accept_op(p, ":") {
        parts.push(node("ann", [parse_type(p)]));
    }
    expect_op(p, "=");
    parts.push(parse_expr(p));
    expect_op(p, ";");
    return node("let", parts);
}

fn parse_if(p: Parser) -> String {
    advance(p);
    let condition = parse_expr(p);
    let then_block = parse_block(p);
    let parts = [condition, then_block];
    if at_kw(p, "else") {
        advance(p);
        if at_kw(p, "if") {
            parts.push(parse_if(p));
        } else {
            parts.push(parse_block(p));
        }
    }
    return node("if", parts);
}

fn parse_while(p: Parser) -> String {
    advance(p);
    let condition = parse_expr(p);
    let body = parse_block(p);
    return node("while", [condition, body]);
}

fn parse_for(p: Parser) -> String {
    advance(p);
    let name = expect_ident(p, "a loop variable").text;
    if not at_kw(p, "in") {
        error_here(p, "expected 'in' in for loop");
    }
    advance(p);
    let iterable = parse_expr(p);
    let body = parse_block(p);
    return node("for", [name, iterable, body]);
}

fn parse_return(p: Parser) -> String {
    advance(p);
    if at_op(p, ";") {
        advance(p);
        return node("return", []);
    }
    let value = parse_expr(p);
    expect_op(p, ";");
    return node("return", [value]);
}

fn parse_capability(p: Parser) -> String {
    advance(p);
    let names: List<String> = [];
    while true {
        names.push(expect_ident(p, "a capability name").text);
        if not accept_op(p, ",") {
            break;
        }
    }
    expect_op(p, ";");
    return node("cap", names);
}

fn parse_try(p: Parser) -> String {
    advance(p);
    let body = parse_block(p);
    if not at_kw(p, "catch") {
        error_here(p, "expected 'catch' after try block");
    }
    advance(p);
    expect_op(p, "(");
    let name = expect_ident(p, "a catch binding").text;
    expect_op(p, ")");
    let catch_body = parse_block(p);
    return node("try", [body, name, catch_body]);
}

fn parse_throw(p: Parser) -> String {
    advance(p);
    let value = parse_expr(p);
    expect_op(p, ";");
    return node("throw", [value]);
}

fn parse_assert(p: Parser) -> String {
    advance(p);
    let parenthesised = accept_op(p, "(");
    let condition = parse_expr(p);
    let parts = [condition];
    if accept_op(p, ",") {
        parts.push(parse_expr(p));
    }
    if parenthesised {
        expect_op(p, ")");
    }
    expect_op(p, ";");
    return node("assert", parts);
}

fn parse_statement(p: Parser) -> String {
    if at_kw(p, "let") {
        return parse_let(p);
    }
    if at_kw(p, "if") {
        return parse_if(p);
    }
    if at_kw(p, "while") {
        return parse_while(p);
    }
    if at_kw(p, "for") {
        return parse_for(p);
    }
    if at_kw(p, "return") {
        return parse_return(p);
    }
    if at_kw(p, "break") {
        advance(p);
        expect_op(p, ";");
        return node("break", []);
    }
    if at_kw(p, "continue") {
        advance(p);
        expect_op(p, ";");
        return node("continue", []);
    }
    if at_kw(p, "capability") {
        return parse_capability(p);
    }
    if at_kw(p, "try") {
        return parse_try(p);
    }
    if at_kw(p, "throw") {
        return parse_throw(p);
    }
    if at_kw(p, "assert") {
        return parse_assert(p);
    }
    if at_op(p, "{") {
        return parse_block(p);
    }

    let expr = parse_expr(p);
    if at_op(p, "=") or at_op(p, "+=") or at_op(p, "-=") or at_op(p, "*=") or at_op(p, "/=") or at_op(p, "%=") {
        let op = advance(p).text;
        let value = parse_expr(p);
        expect_op(p, ";");
        return node("assign", [op, expr, value]);
    }
    expect_op(p, ";");
    return node("expr", [expr]);
}

fn parse_block(p: Parser) -> String {
    expect_op(p, "{");
    let statements: List<String> = [];
    while not at_op(p, "}") and not at_kind(p, "eof") {
        if accept_op(p, ";") {
            continue;
        }
        statements.push(parse_statement(p));
    }
    expect_op(p, "}");
    return node("block", statements);
}

// ---------------------------------------------------------------------------
// Declarations
// ---------------------------------------------------------------------------

fn parse_use(p: Parser) -> String {
    advance(p);
    let mut path = expect_ident(p, "a module name after 'use'").text;
    while accept_op(p, ".") {
        path = path + "." + expect_ident(p, "a module path component").text;
    }
    let parts = [path];
    if at_kw(p, "as") {
        error_here(p, "module aliases ('as') are not implemented in 0.1");
    }
    accept_op(p, ";");
    return node("use", parts);
}

fn parse_struct(p: Parser) -> String {
    advance(p);
    let name = expect_ident(p, "a struct name").text;
    expect_op(p, "{");
    let parts = [name];
    while not at_op(p, "}") and not at_kind(p, "eof") {
        let field_name = expect_ident(p, "a struct field name").text;
        expect_op(p, ":");
        let ty = parse_type(p);
        parts.push(node("field", [field_name, ty]));
        accept_op(p, ",");
        accept_op(p, ";");
    }
    expect_op(p, "}");
    return node("struct", parts);
}

fn parse_function(p: Parser) -> String {
    advance(p);
    let name = expect_ident(p, "a function name after 'fn'").text;
    let params = parse_params(p);
    let mut ret = node("t", ["Unit"]);
    if accept_op(p, "->") {
        ret = parse_type(p);
    }
    let body = parse_block(p);
    return node("fn", [name, params, node("ret", [ret]), body]);
}

fn parse_layer(p: Parser) -> String {
    let name = expect_ident(p, "a layer name").text;
    expect_op(p, "(");
    let args: List<String> = [];
    if not at_op(p, ")") {
        while true {
            let arg_name = expect_ident(p, "a layer argument name").text;
            expect_op(p, ":");
            let parts = [arg_name];
            if at_kind(p, "id") and (peek_at(p, 1).kind == "op") and (peek_at(p, 1).text == "," or peek_at(p, 1).text == ")") {
                let sym = advance(p).text;
                parts.push(node("sym", [sym]));
            } else {
                parts.push(parse_expr(p));
            }
            args.push(node("arg", parts));
            if not accept_op(p, ",") {
                break;
            }
            if at_op(p, ")") {
                break;
            }
        }
    }
    expect_op(p, ")");
    let parts = [name];
    for arg in args {
        parts.push(arg);
    }
    return node("layer", parts);
}

fn parse_model(p: Parser) -> String {
    advance(p);
    let name = expect_ident(p, "a model name").text;
    expect_op(p, "{");
    let inputs: List<String> = [];
    let outputs: List<String> = [];
    let layers: List<String> = [];
    while not at_op(p, "}") and not at_kind(p, "eof") {
        let section = peek(p);
        if section.kind == "id" and (section.text == "input" or section.text == "output") {
            advance(p);
            let field_name = expect_ident(p, "a model field name").text;
            expect_op(p, ":");
            let ty = parse_type(p);
            if section.text == "input" {
                inputs.push(node("input", [field_name, ty]));
            } else {
                outputs.push(node("output", [field_name, ty]));
            }
            continue;
        }
        if section.kind == "id" and section.text == "stack" {
            advance(p);
            expect_op(p, "{");
            while not at_op(p, "}") and not at_kind(p, "eof") {
                layers.push(parse_layer(p));
            }
            expect_op(p, "}");
            continue;
        }
        error_here(p, "expected 'input', 'output' or 'stack' in model body");
    }
    expect_op(p, "}");
    let parts = [name];
    for field in inputs {
        parts.push(field);
    }
    for field in outputs {
        parts.push(field);
    }
    parts.push(node("stack", layers));
    return node("model", parts);
}

fn parse_training(p: Parser) -> String {
    advance(p);
    let name = expect_ident(p, "a training name").text;
    expect_op(p, "{");
    let options: List<String> = [];
    while not at_op(p, "}") and not at_kind(p, "eof") {
        let field_name = expect_ident(p, "a training option name").text;
        expect_op(p, ":");
        let value = parse_expr(p);
        options.push(node("opt", [field_name, value]));
        accept_op(p, ",");
        accept_op(p, ";");
    }
    expect_op(p, "}");
    let parts = [name];
    for option in options {
        parts.push(option);
    }
    return node("training", parts);
}

fn parse_program(p: Parser) -> Unit {
    let mut module_name = "";
    if at_kw(p, "module") {
        advance(p);
        module_name = expect_ident(p, "a module name after 'module'").text;
        accept_op(p, ";");
    }
    let uses: List<String> = [];
    let structs: List<String> = [];
    let functions: List<String> = [];
    let models: List<String> = [];
    let trainings: List<String> = [];

    while not at_kind(p, "eof") {
        if at_kw(p, "use") {
            uses.push(parse_use(p));
            continue;
        }
        if at_kw(p, "fn") {
            functions.push(parse_function(p));
            continue;
        }
        if at_kw(p, "struct") {
            structs.push(parse_struct(p));
            continue;
        }
        if at_kw(p, "model") {
            models.push(parse_model(p));
            continue;
        }
        if at_kw(p, "training") {
            trainings.push(parse_training(p));
            continue;
        }
        if at_kw(p, "module") {
            error_here(p, "the 'module' declaration must appear once, before all items");
        }
        error_here(p, "expected a declaration (fn, struct, use), found " + describe_token(peek(p)));
    }

    print("(module " + module_name + ")");
    for u in uses {
        print(u);
    }
    for s in structs {
        print(s);
    }
    for f in functions {
        print(f);
    }
    for m in models {
        print(m);
    }
    for tr in trainings {
        print(tr);
    }
}

fn main() -> Unit {
    capability fs;
    let args = process.args();
    if args.len() < 1 {
        print("usage: parser.pac <path.pac>");
        return;
    }
    let path = args.get(0);
    let source = fs.read_text(path);
    let tokens = lex(source);
    let p = Parser(tokens, 0, source);
    parse_program(p);
}
