"""Recursive-descent parser for PEACOCK 0.3.

The grammar implemented here is exactly the grammar in ``SPECIFICATION.md`` §4.
Features that are reserved for later phases produce targeted diagnostics rather
than generic syntax errors.
"""

from __future__ import annotations

from .ast_nodes import (
    AssertStmt,
    AssignStmt,
    Binary,
    Block,
    BoolLit,
    BreakStmt,
    Call,
    CapabilityStmt,
    ContinueStmt,
    Expr,
    ExprStmt,
    Field,
    FloatLit,
    ForStmt,
    FunctionDecl,
    IfStmt,
    Index,
    IntLit,
    LayerArg,
    LayerDecl,
    LetStmt,
    ListLit,
    ListTypeExpr,
    ModelDecl,
    Module,
    Name,
    NamedTypeExpr,
    Param,
    RangeExpr,
    ReturnStmt,
    Stmt,
    StringLit,
    StructDecl,
    StructField,
    TensorTypeExpr,
    ThrowStmt,
    TrainingDecl,
    TrainingField,
    TryStmt,
    TypeExpr,
    Unary,
    UseDecl,
    WhileStmt,
)
from .diagnostics import DiagnosticBag, ParseError, Span
from .tokens import RESERVED_FUTURE, Token, TokenKind

_FUTURE_MESSAGES = {
    TokenKind.ENUM: "सूचीभेद declarations are reserved for a future version; 0.3 supports संघटन only",
    TokenKind.MATCH: "मिलान expressions are reserved for a future version",
    TokenKind.IMPL: "कार्यान्वयन blocks are reserved for a future version",
    TokenKind.PUB: "सार्वजनिक visibility modifiers are reserved; all 0.3 declarations are module-local",
    TokenKind.CONST: "स्थिर declarations are reserved for a future version; use 'स्थापय'",
    TokenKind.IMPORT: "आयात statements are reserved; 0.3 has no file imports",
    TokenKind.ASYNC: "असामकालिक functions are reserved; 0.3 is single-threaded",
    TokenKind.AWAIT: "प्रतीक्षा is reserved; 0.3 is single-threaded",
    TokenKind.SPAWN: "जनय is reserved; concurrency is not implemented in 0.3",
    TokenKind.YIELD: "उत्पादय is reserved; generators are not implemented in 0.3",
}

_ITEM_STARTERS = {
    TokenKind.FN,
    TokenKind.STRUCT,
    TokenKind.MODEL,
    TokenKind.TRAINING,
    TokenKind.USE,
    TokenKind.MODULE,
}

_ASSIGN_OPS = {
    TokenKind.ASSIGN: "=",
    TokenKind.PLUS_ASSIGN: "+=",
    TokenKind.MINUS_ASSIGN: "-=",
    TokenKind.STAR_ASSIGN: "*=",
    TokenKind.SLASH_ASSIGN: "/=",
    TokenKind.PERCENT_ASSIGN: "%=",
}


class Parser:
    def __init__(self, tokens: list[Token], source: str = "", file: str = "<source>"):
        self.tokens = tokens
        self.source = source
        self.file = file
        self.index = 0
        self.diag = DiagnosticBag()

    # -- token helpers -----------------------------------------------------
    @property
    def current(self) -> Token:
        return self.tokens[min(self.index, len(self.tokens) - 1)]

    def peek(self, offset: int = 1) -> Token:
        i = min(self.index + offset, len(self.tokens) - 1)
        return self.tokens[i]

    def at(self, kind: TokenKind) -> bool:
        return self.current.kind is kind

    def advance(self) -> Token:
        tok = self.current
        if self.index < len(self.tokens) - 1:
            self.index += 1
        return tok

    def match(self, *kinds: TokenKind) -> Token | None:
        if self.current.kind in kinds:
            return self.advance()
        return None

    def expect(self, kind: TokenKind, context: str) -> Token:
        if self.at(kind):
            return self.advance()
        self.error(
            "PE2002",
            f"expected {kind.describe()} {context}, found {self.current.kind.describe()}"
            + (f" '{self.current.text}'" if self.current.text else ""),
            self.current.span,
        )
        raise ParseError("unexpected token")

    def error(self, code: str, message: str, span: Span, hint: str | None = None) -> None:
        self.diag.error(code, message, span, hint)
        raise ParseError(message, code=code, span=span)

    def _merge(self, start: Span) -> Span:
        end = self.tokens[max(0, self.index - 1)].span
        return start.merge(end)

    # -- entry point -------------------------------------------------------
    def parse_module(self) -> Module:
        start = self.current.span
        name: str | None = None
        uses: list[UseDecl] = []
        functions: list[FunctionDecl] = []
        structs: list[StructDecl] = []
        models: list[ModelDecl] = []
        trainings: list[TrainingDecl] = []

        if self.at(TokenKind.MODULE):
            mod_tok = self.advance()
            name_tok = self.expect(TokenKind.IDENT, "after 'module'")
            name = str(name_tok.value)
            self.match(TokenKind.SEMICOLON)

        while not self.at(TokenKind.EOF):
            fut = _FUTURE_MESSAGES.get(self.current.kind)
            if fut is not None:
                self.diag.error("PE2001", fut, self.current.span, hint="see SPECIFICATION.md §4 for the 0.3 subset")
                self._advance_any()
                continue
            try:
                if self.at(TokenKind.USE):
                    uses.append(self.parse_use())
                elif self.at(TokenKind.FN):
                    functions.append(self.parse_function())
                elif self.at(TokenKind.STRUCT):
                    structs.append(self.parse_struct())
                elif self.at(TokenKind.MODEL):
                    models.append(self.parse_model())
                elif self.at(TokenKind.TRAINING):
                    trainings.append(self.parse_training())
                elif self.at(TokenKind.MODULE):
                    self.error(
                        "PE2003",
                        "the 'module' declaration must appear once, before all items",
                        self.current.span,
                    )
                else:
                    self.error(
                        "PE2004",
                        f"expected a declaration (fn, struct, model, training, use), found "
                        f"{self.current.kind.describe()}",
                        self.current.span,
                    )
            except ParseError:
                self._synchronise_item()

        end = self.current.span
        return Module(name, uses, functions, structs, models, trainings, start.merge(end))

    def _advance_any(self) -> None:
        if not self.at(TokenKind.EOF):
            self.advance()

    def _synchronise_item(self) -> None:
        # Always make progress, then skip to a likely declaration boundary.
        self._advance_any()
        depth = 0
        while not self.at(TokenKind.EOF):
            if depth == 0 and self.current.kind in _ITEM_STARTERS:
                return
            if self.at(TokenKind.LBRACE):
                depth += 1
            elif self.at(TokenKind.RBRACE):
                if depth == 0:
                    self._advance_any()
                    continue
                depth -= 1
            elif depth == 0 and self.at(TokenKind.SEMICOLON):
                self._advance_any()
                if self.current.kind in _ITEM_STARTERS:
                    return
                continue
            self._advance_any()

    def _synchronise_statement(self) -> None:
        self._advance_any()
        while not self.at(TokenKind.EOF):
            if self.at(TokenKind.SEMICOLON):
                self._advance_any()
                return
            if self.at(TokenKind.RBRACE):
                return
            if self.current.kind in (TokenKind.LET, TokenKind.IF, TokenKind.WHILE, TokenKind.FOR, TokenKind.RETURN):
                return
            self._advance_any()

    # -- declarations ------------------------------------------------------
    def parse_use(self) -> UseDecl:
        start = self.advance().span
        path = [str(self.expect(TokenKind.IDENT, "after 'use'").value)]
        while self.match(TokenKind.DOT):
            path.append(str(self.expect(TokenKind.IDENT, "in module path").value))
        if self.at(TokenKind.AS):
            self.error(
                "PE2005",
                "module aliases ('रूपेण') are not implemented in 0.3",
                self.current.span,
                hint="use the canonical namespace name, e.g. 'उपयोग तन्त्रजाल;'",
            )
        # The semicolon is optional for use declarations, matching module style.
        self.match(TokenKind.SEMICOLON)
        return UseDecl(path, self._merge(start))

    def parse_function(self) -> FunctionDecl:
        start = self.advance().span
        name_tok = self.expect(TokenKind.IDENT, "after 'fn'")
        self.expect(TokenKind.LPAREN, "after function name")
        params: list[Param] = []
        if not self.at(TokenKind.RPAREN):
            while True:
                p_name = self.expect(TokenKind.IDENT, "as parameter name")
                self.expect(TokenKind.COLON, "after parameter name")
                p_type = self.parse_type()
                params.append(Param(str(p_name.value), p_type, p_name.span.merge(p_type.span)))
                if not self.match(TokenKind.COMMA):
                    break
                if self.at(TokenKind.RPAREN):
                    break
        self.expect(TokenKind.RPAREN, "after parameters")
        ret: TypeExpr | None = None
        if self.match(TokenKind.ARROW):
            ret = self.parse_type()
        body = self.parse_block()
        return FunctionDecl(
            str(name_tok.value), params, ret, body, self._merge(start), name_tok.span
        )

    def parse_struct(self) -> StructDecl:
        start = self.advance().span
        name_tok = self.expect(TokenKind.IDENT, "after 'struct'")
        self.expect(TokenKind.LBRACE, "to open struct body")
        fields: list[StructField] = []
        while not self.at(TokenKind.RBRACE) and not self.at(TokenKind.EOF):
            f_name = self.expect(TokenKind.IDENT, "as struct field name")
            self.expect(TokenKind.COLON, "after field name")
            f_type = self.parse_type()
            fields.append(StructField(str(f_name.value), f_type, f_name.span.merge(f_type.span)))
            self.match(TokenKind.COMMA, TokenKind.SEMICOLON)
        self.expect(TokenKind.RBRACE, "to close struct body")
        return StructDecl(str(name_tok.value), fields, self._merge(start), name_tok.span)

    def parse_model(self) -> ModelDecl:
        start = self.advance().span
        name_tok = self.expect(TokenKind.IDENT, "after 'model'")
        self.expect(TokenKind.LBRACE, "to open model body")
        inputs: list[StructField] = []
        outputs: list[StructField] = []
        layers: list[LayerDecl] = []
        while not self.at(TokenKind.RBRACE) and not self.at(TokenKind.EOF):
            # 'input', 'output' and 'stack' are contextual keywords: they remain
            # usable as ordinary identifiers elsewhere.
            if self.at(TokenKind.IDENT) and self.current.value in ("input", "output"):
                section = str(self.advance().value)
                f_name = self.expect(TokenKind.IDENT, f"as {section} name")
                self.expect(TokenKind.COLON, f"after {section} name")
                f_type = self.parse_type()
                target = inputs if section == "input" else outputs
                target.append(StructField(str(f_name.value), f_type, f_name.span.merge(f_type.span)))
            elif self.at(TokenKind.IDENT) and self.current.value == "stack":
                self.advance()
                self.expect(TokenKind.LBRACE, "to open stack block")
                while not self.at(TokenKind.RBRACE) and not self.at(TokenKind.EOF):
                    layers.append(self.parse_layer())
                self.expect(TokenKind.RBRACE, "to close stack block")
            else:
                self.error(
                    "PE2010",
                    "expected 'input', 'output' or 'stack' in model body",
                    self.current.span,
                    hint="model bodies contain only निवेश, निर्गम and क्रम sections in 0.3",
                )
        self.expect(TokenKind.RBRACE, "to close model body")
        if not inputs or not outputs:
            self.error(
                "PE2011",
                f"model '{name_tok.value}' must declare at least one input and one output",
                name_tok.span,
            )
        return ModelDecl(str(name_tok.value), inputs, outputs, layers, self._merge(start), name_tok.span)

    def parse_layer(self) -> LayerDecl:
        # Layer names are capitalised by convention (Dense, Dropout); accept any identifier.
        name_tok = self.expect(TokenKind.IDENT, "as layer name")
        start = name_tok.span
        self.expect(TokenKind.LPAREN, "after layer name")
        args: list[LayerArg] = []
        if not self.at(TokenKind.RPAREN):
            while True:
                a_name = self.expect(TokenKind.IDENT, "as layer argument name")
                self.expect(TokenKind.COLON, "after layer argument name")
                # Bare symbolic argument: IDENT followed by ',' or ')'.
                if self.at(TokenKind.IDENT) and self.peek().kind in (TokenKind.COMMA, TokenKind.RPAREN):
                    sym_tok = self.advance()
                    value: Expr = Name(str(sym_tok.value), sym_tok.span)
                    arg = LayerArg(str(a_name.value), value, a_name.span.merge(sym_tok.span), str(sym_tok.value))
                else:
                    value = self.parse_expr()
                    arg = LayerArg(str(a_name.value), value, a_name.span.merge(value.span), None)
                args.append(arg)
                if not self.match(TokenKind.COMMA):
                    break
                if self.at(TokenKind.RPAREN):
                    break
        self.expect(TokenKind.RPAREN, "after layer arguments")
        return LayerDecl(str(name_tok.value), args, self._merge(start))

    def parse_training(self) -> TrainingDecl:
        start = self.advance().span
        name_tok = self.expect(TokenKind.IDENT, "after 'training'")
        self.expect(TokenKind.LBRACE, "to open training body")
        fields: list[TrainingField] = []
        while not self.at(TokenKind.RBRACE) and not self.at(TokenKind.EOF):
            f_name = self.expect(TokenKind.IDENT, "as training option")
            self.expect(TokenKind.COLON, "after training option name")
            value = self.parse_expr()
            fields.append(TrainingField(str(f_name.value), value, f_name.span.merge(value.span)))
            self.match(TokenKind.COMMA, TokenKind.SEMICOLON)
        self.expect(TokenKind.RBRACE, "to close training body")
        return TrainingDecl(str(name_tok.value), fields, self._merge(start), name_tok.span)

    # -- types -------------------------------------------------------------
    def parse_type(self) -> TypeExpr:
        start = self.current.span
        if self.at(TokenKind.IDENT):
            name_tok = self.advance()
            name = str(name_tok.value)
            if name == "Tensor":
                if not self.match(TokenKind.LT):
                    self.error(
                        "PE2020",
                        "Tensor requires a dtype, e.g. Tensor<Float32> or Tensor<Float32, [2, 3]>",
                        name_tok.span,
                    )
                dtype_tok = self.expect(TokenKind.IDENT, "as tensor dtype")
                shape: list[int] | None = None
                shape_span: Span | None = None
                if self.match(TokenKind.COMMA):
                    shape_span_start = self.expect(TokenKind.LBRACKET, "before tensor shape").span
                    shape = []
                    if not self.at(TokenKind.RBRACKET):
                        while True:
                            dim_tok = self.expect(TokenKind.INT, "as tensor dimension")
                            dim = int(dim_tok.value)  # type: ignore[arg-type]
                            if dim <= 0:
                                self.error(
                                    "PE2021",
                                    "tensor dimensions must be positive integers",
                                    dim_tok.span,
                                )
                            shape.append(dim)
                            if not self.match(TokenKind.COMMA):
                                break
                    end = self.expect(TokenKind.RBRACKET, "after tensor shape").span
                    shape_span = shape_span_start.merge(end)
                self.expect(TokenKind.GT, "to close Tensor type")
                return TensorTypeExpr(
                    name_tok.span.merge(self.tokens[self.index - 1].span),
                    str(dtype_tok.value),
                    dtype_tok.span,
                    shape,
                    shape_span,
                )
            if name == "List":
                self.expect(TokenKind.LT, "after List")
                elem = self.parse_type()
                self.expect(TokenKind.GT, "to close List type")
                return ListTypeExpr(name_tok.span.merge(self.tokens[self.index - 1].span), elem)
            args: list[TypeExpr] = []
            if self.match(TokenKind.LT):
                while True:
                    args.append(self.parse_type())
                    if not self.match(TokenKind.COMMA):
                        break
                self.expect(TokenKind.GT, "to close generic type")
            return NamedTypeExpr(self._merge(start), name, args)
        self.error("PE2022", f"expected a type, found {self.current.kind.describe()}", self.current.span)
        raise ParseError("expected type")

    # -- statements --------------------------------------------------------
    def parse_block(self) -> Block:
        start = self.expect(TokenKind.LBRACE, "to open block").span
        statements: list[Stmt] = []
        while not self.at(TokenKind.RBRACE) and not self.at(TokenKind.EOF):
            if self.match(TokenKind.SEMICOLON):
                continue
            try:
                statements.append(self.parse_statement())
            except ParseError:
                self._synchronise_statement()
        end = self.expect(TokenKind.RBRACE, "to close block").span
        return Block(start.merge(end), statements)

    def parse_statement(self) -> Stmt:
        tok = self.current
        if tok.kind in _FUTURE_MESSAGES:
            msg = _FUTURE_MESSAGES[tok.kind]
            self.error("PE2001", msg, tok.span)
        if self.at(TokenKind.LET):
            return self.parse_let()
        if self.at(TokenKind.IF):
            return self.parse_if()
        if self.at(TokenKind.WHILE):
            return self.parse_while()
        if self.at(TokenKind.FOR):
            return self.parse_for()
        if self.at(TokenKind.RETURN):
            return self.parse_return()
        if self.at(TokenKind.BREAK):
            span = self.advance().span
            self.expect(TokenKind.SEMICOLON, "after 'break'")
            return BreakStmt(span)
        if self.at(TokenKind.CONTINUE):
            span = self.advance().span
            self.expect(TokenKind.SEMICOLON, "after 'continue'")
            return ContinueStmt(span)
        if self.at(TokenKind.CAPABILITY):
            return self.parse_capability()
        if self.at(TokenKind.TRY):
            return self.parse_try()
        if self.at(TokenKind.THROW):
            return self.parse_throw()
        if self.at(TokenKind.ASSERT):
            return self.parse_assert()
        if self.at(TokenKind.LBRACE):
            return self.parse_block()
        # Expression statement or assignment.
        start = self.current.span
        expr = self.parse_expr()
        if self.current.kind in _ASSIGN_OPS:
            op = _ASSIGN_OPS[self.current.kind]
            self.advance()
            value = self.parse_expr()
            if not isinstance(expr, (Name, Field, Index)):
                self.error(
                    "PE2030",
                    "the left-hand side of an assignment must be a variable, field or index",
                    expr.span,
                )
            self.expect(TokenKind.SEMICOLON, "after assignment")
            return AssignStmt(start.merge(value.span), expr, op, value)
        self.expect(TokenKind.SEMICOLON, "after expression")
        return ExprStmt(expr.span, expr)

    def parse_let(self) -> LetStmt:
        start = self.advance().span
        mutable = self.match(TokenKind.MUT) is not None
        name_tok = self.expect(TokenKind.IDENT, "as variable name")
        annotation: TypeExpr | None = None
        if self.match(TokenKind.COLON):
            annotation = self.parse_type()
        self.expect(TokenKind.ASSIGN, "in let binding")
        init = self.parse_expr()
        self.expect(TokenKind.SEMICOLON, "after let binding")
        return LetStmt(self._merge(start), str(name_tok.value), mutable, annotation, init)

    def parse_if(self) -> IfStmt:
        start = self.advance().span
        condition = self.parse_expr()
        then_block = self.parse_block()
        else_branch: Block | IfStmt | None = None
        if self.match(TokenKind.ELSE):
            if self.at(TokenKind.IF):
                else_branch = self.parse_if()
            else:
                else_branch = self.parse_block()
        return IfStmt(self._merge(start), condition, then_block, else_branch)

    def parse_while(self) -> WhileStmt:
        start = self.advance().span
        condition = self.parse_expr()
        body = self.parse_block()
        return WhileStmt(self._merge(start), condition, body)

    def parse_for(self) -> ForStmt:
        start = self.advance().span
        name_tok = self.expect(TokenKind.IDENT, "as loop variable")
        self.expect(TokenKind.IN, "in for loop")
        iterable = self.parse_expr()
        body = self.parse_block()
        return ForStmt(self._merge(start), str(name_tok.value), iterable, body)

    def parse_return(self) -> ReturnStmt:
        start = self.advance().span
        value: Expr | None = None
        if not self.at(TokenKind.SEMICOLON):
            value = self.parse_expr()
        self.expect(TokenKind.SEMICOLON, "after return")
        return ReturnStmt(start.merge(self.tokens[self.index - 1].span), value)

    def parse_capability(self) -> CapabilityStmt:
        start = self.advance().span
        names: list[str] = []
        spans: list[Span] = []
        while True:
            tok = self.expect(TokenKind.IDENT, "as capability name")
            names.append(str(tok.value))
            spans.append(tok.span)
            if not self.match(TokenKind.COMMA):
                break
        self.expect(TokenKind.SEMICOLON, "after capability declaration")
        return CapabilityStmt(self._merge(start), names, spans)

    def parse_try(self) -> TryStmt:
        start = self.advance().span
        body = self.parse_block()
        catch_name: str | None = None
        catch_body = None
        finally_body = None
        if self.match(TokenKind.CATCH):
            self.expect(TokenKind.LPAREN, "before catch binding")
            name_tok = self.expect(TokenKind.IDENT, "as catch binding")
            self.expect(TokenKind.RPAREN, "after catch binding")
            catch_name = str(name_tok.value)
            catch_body = self.parse_block()
        if self.match(TokenKind.FINALLY):
            finally_body = self.parse_block()
        if catch_body is None and finally_body is None:
            self.error("PE2028", "expected 'गृह्ण' or 'अन्ते' after try block", self.current.span)
        return TryStmt(self._merge(start), body, catch_name, catch_body, finally_body)

    def parse_throw(self) -> ThrowStmt:
        start = self.advance().span
        value = self.parse_expr()
        self.expect(TokenKind.SEMICOLON, "after throw")
        return ThrowStmt(self._merge(start), value)

    def parse_assert(self) -> AssertStmt:
        start = self.advance().span
        parenthesised = self.match(TokenKind.LPAREN) is not None
        condition = self.parse_expr()
        message = None
        if self.match(TokenKind.COMMA):
            message = self.parse_expr()
        if parenthesised:
            self.expect(TokenKind.RPAREN, "after assert arguments")
        self.expect(TokenKind.SEMICOLON, "after assert")
        return AssertStmt(self._merge(start), condition, message)

    # -- expressions -------------------------------------------------------
    def parse_expr(self) -> Expr:
        return self.parse_or()

    def parse_or(self) -> Expr:
        left = self.parse_and()
        while self.at(TokenKind.OR):
            self.advance()
            right = self.parse_and()
            left = Binary(left.span.merge(right.span), "or", left, right)
        return left

    def parse_and(self) -> Expr:
        left = self.parse_not()
        while self.at(TokenKind.AND):
            self.advance()
            right = self.parse_not()
            left = Binary(left.span.merge(right.span), "and", left, right)
        return left

    def parse_not(self) -> Expr:
        if self.at(TokenKind.NOT):
            start = self.advance().span
            operand = self.parse_not()
            return Unary(start.merge(operand.span), "not", operand)
        return self.parse_comparison()

    def parse_comparison(self) -> Expr:
        left = self.parse_range()
        op_map = {
            TokenKind.EQ: "==",
            TokenKind.NE: "!=",
            TokenKind.LT: "<",
            TokenKind.LE: "<=",
            TokenKind.GT: ">",
            TokenKind.GE: ">=",
        }
        if self.current.kind in op_map:
            op = op_map[self.advance().kind]
            right = self.parse_range()
            if self.current.kind in op_map:
                self.error(
                    "PE2031",
                    "chained comparisons are not supported",
                    self.current.span,
                    hint="combine comparisons with 'तथा', e.g. 0 <= x तथा x < 10",
                )
            return Binary(left.span.merge(right.span), op, left, right)
        return left

    def parse_range(self) -> Expr:
        left = self.parse_additive()
        if self.match(TokenKind.DOTDOT):
            right = self.parse_additive()
            return RangeExpr(left.span.merge(right.span), left, right)
        return left

    def parse_additive(self) -> Expr:
        left = self.parse_multiplicative()
        while self.current.kind in (TokenKind.PLUS, TokenKind.MINUS):
            op = "+" if self.advance().kind is TokenKind.PLUS else "-"
            right = self.parse_multiplicative()
            left = Binary(left.span.merge(right.span), op, left, right)
        return left

    def parse_multiplicative(self) -> Expr:
        left = self.parse_unary()
        while self.current.kind in (TokenKind.STAR, TokenKind.SLASH, TokenKind.PERCENT):
            kind = self.advance().kind
            op = {TokenKind.STAR: "*", TokenKind.SLASH: "/", TokenKind.PERCENT: "%"}[kind]
            right = self.parse_unary()
            left = Binary(left.span.merge(right.span), op, left, right)
        return left

    def parse_unary(self) -> Expr:
        if self.at(TokenKind.MINUS):
            start = self.advance().span
            operand = self.parse_unary()
            return Unary(start.merge(operand.span), "-", operand)
        if self.at(TokenKind.NOT):
            start = self.advance().span
            operand = self.parse_unary()
            return Unary(start.merge(operand.span), "not", operand)
        return self.parse_power()

    def parse_power(self) -> Expr:
        base = self.parse_postfix()
        if self.match(TokenKind.POWER):
            exponent = self.parse_unary()  # right-associative
            return Binary(base.span.merge(exponent.span), "**", base, exponent)
        return base

    def parse_postfix(self) -> Expr:
        expr = self.parse_primary()
        while True:
            if self.at(TokenKind.LPAREN):
                self.advance()
                args: list[Expr] = []
                arg_names: list[str | None] = []
                saw_named = False
                if not self.at(TokenKind.RPAREN):
                    while True:
                        if self.at(TokenKind.IDENT) and self.peek().kind is TokenKind.COLON:
                            name_tok = self.advance()
                            self.advance()  # ':'
                            args.append(self.parse_expr())
                            arg_names.append(str(name_tok.value))
                            saw_named = True
                        else:
                            if saw_named:
                                self.error(
                                    "PE2033",
                                    "positional arguments may not follow named arguments",
                                    self.current.span,
                                    hint="move positional arguments before named ones",
                                )
                            args.append(self.parse_expr())
                            arg_names.append(None)
                        if not self.match(TokenKind.COMMA):
                            break
                        if self.at(TokenKind.RPAREN):
                            break
                end = self.expect(TokenKind.RPAREN, "after call arguments").span
                expr = Call(expr.span.merge(end), expr, args, arg_names)
            elif self.at(TokenKind.DOT):
                self.advance()
                name_tok = self.expect(TokenKind.IDENT, "after '.'")
                expr = Field(expr.span.merge(name_tok.span), expr, str(name_tok.value), name_tok.span)
            elif self.at(TokenKind.LBRACKET):
                self.advance()
                index = self.parse_expr()
                end = self.expect(TokenKind.RBRACKET, "after index expression").span
                expr = Index(expr.span.merge(end), expr, index)
            else:
                return expr

    def parse_primary(self) -> Expr:
        tok = self.current
        if tok.kind is TokenKind.INT:
            self.advance()
            return IntLit(tok.span, int(tok.value))  # type: ignore[arg-type]
        if tok.kind is TokenKind.FLOAT:
            self.advance()
            return FloatLit(tok.span, float(tok.value))  # type: ignore[arg-type]
        if tok.kind is TokenKind.STRING:
            self.advance()
            return StringLit(tok.span, str(tok.value))
        if tok.kind is TokenKind.TRUE:
            self.advance()
            return BoolLit(tok.span, True)
        if tok.kind is TokenKind.FALSE:
            self.advance()
            return BoolLit(tok.span, False)
        if tok.kind is TokenKind.IDENT:
            self.advance()
            return Name(tok.span, str(tok.value))
        if tok.kind is TokenKind.LPAREN:
            self.advance()
            expr = self.parse_expr()
            self.expect(TokenKind.RPAREN, "after parenthesised expression")
            return expr
        if tok.kind is TokenKind.LBRACKET:
            start = self.advance().span
            elements: list[Expr] = []
            if not self.at(TokenKind.RBRACKET):
                while True:
                    elements.append(self.parse_expr())
                    if not self.match(TokenKind.COMMA):
                        break
                    if self.at(TokenKind.RBRACKET):
                        break
            end = self.expect(TokenKind.RBRACKET, "after list literal").span
            return ListLit(start.merge(end), elements)
        if tok.kind in _FUTURE_MESSAGES:
            self.error("PE2001", _FUTURE_MESSAGES[tok.kind], tok.span)
        self.error(
            "PE2032",
            f"expected an expression, found {tok.kind.describe()}"
            + (f" '{tok.text}'" if tok.text else ""),
            tok.span,
        )
        raise ParseError("expected expression")


def parse(tokens: list[Token], source: str = "", file: str = "<source>") -> tuple[Module, DiagnosticBag]:
    parser = Parser(tokens, source, file)
    module = parser.parse_module()
    return module, parser.diag
