// PEACOCK-native semantic kernel (migration stage 3).
//
// This file is executed by PEACOCK itself. It contains a recursive type
// descriptor, type relations, expression result rules, a lexical symbol table,
// declaration/assignment checks and user-function signature checks. The Python
// bootstrap remains authoritative; `compile_source(..., semantic_mode="shadow")`
// translates real parsed/typed AST nodes into probes executed by this kernel.
//
// Scope is intentionally explicit: this is not yet a complete semantic
// analyser and it does not emit PEACOCK diagnostics or IR.

module selfhost_type_model

struct TypeDesc {
    tag: String,
    name: String,
    shape_known: Bool,
    dims: List<Int>,
    elements: List<TypeDesc>
}

struct Binding {
    name: String,
    ty: TypeDesc,
    mutable: Bool,
    scope: Int
}

struct FunctionSignature {
    name: String,
    parameter_names: List<String>,
    parameter_types: List<TypeDesc>,
    result: TypeDesc
}

struct StructSignature {
    name: String,
    field_names: List<String>,
    field_types: List<TypeDesc>
}

fn primitive(name: String) -> TypeDesc {
    return TypeDesc("primitive", name, false, [], []);
}

fn error_type() -> TypeDesc {
    return primitive("<error>");
}

fn tensor_type(dtype: String, known: Bool, dims: List<Int>) -> TypeDesc {
    return TypeDesc("tensor", dtype, known, dims, []);
}

fn list_type(element: TypeDesc) -> TypeDesc {
    return TypeDesc("list", "", false, [], [element]);
}

fn nominal_type(type_name: String) -> TypeDesc {
    return TypeDesc("nominal", type_name, false, [], []);
}

fn opaque_type(type_name: String) -> TypeDesc {
    return TypeDesc("opaque", type_name, false, [], []);
}

fn range_type() -> TypeDesc {
    return opaque_type("Range");
}

fn is_error(ty: TypeDesc) -> Bool {
    return ty.name == "<error>";
}

fn is_numeric(ty: TypeDesc) -> Bool {
    return ty.tag == "primitive" and (ty.name == "Int" or ty.name == "Float");
}

fn type_equal(left: TypeDesc, right: TypeDesc) -> Bool {
    if left.tag != right.tag or left.name != right.name {
        return false;
    }
    if left.shape_known != right.shape_known {
        return false;
    }
    if left.shape_known {
        if len(left.dims) != len(right.dims) {
            return false;
        }
        let mut i = 0;
        while i < len(left.dims) {
            if left.dims.get(i) != right.dims.get(i) {
                return false;
            }
            i += 1;
        }
    }
    if len(left.elements) != len(right.elements) {
        return false;
    }
    let mut i = 0;
    while i < len(left.elements) {
        if not type_equal(left.elements.get(i), right.elements.get(i)) {
            return false;
        }
        i += 1;
    }
    return true;
}

fn type_key(ty: TypeDesc) -> String {
    if ty.tag == "list" {
        if len(ty.elements) != 1 {
            return "list<?>";
        }
        return "list<" + type_key(ty.elements.get(0)) + ">";
    }
    if ty.tag == "tensor" {
        let mut key = "tensor<" + ty.name + ",";
        if not ty.shape_known {
            return key + "?>";
        }
        key = key + "[";
        let mut i = 0;
        while i < len(ty.dims) {
            if i > 0 {
                key = key + ",";
            }
            key = key + str(ty.dims.get(i));
            i += 1;
        }
        return key + "]>";
    }
    return ty.tag + ":" + ty.name;
}

// `source` may flow to `target` under the v0.1 assignment rules.
fn is_assignable(source: TypeDesc, target: TypeDesc) -> Bool {
    if is_error(source) or is_error(target) {
        return true;
    }
    if source.tag == "primitive" and source.name == "Never" {
        return true;
    }
    if source.tag == "tensor" and target.tag == "tensor" {
        if source.name != target.name {
            return false;
        }
        if not target.shape_known {
            return true;
        }
        return source.shape_known and type_equal(source, target);
    }
    return type_equal(source, target);
}

fn same_shape(left: TypeDesc, right: TypeDesc) -> Bool {
    if left.tag != "tensor" or right.tag != "tensor" {
        return false;
    }
    if left.shape_known != right.shape_known {
        return false;
    }
    if not left.shape_known {
        return true;
    }
    if len(left.dims) != len(right.dims) {
        return false;
    }
    let mut i = 0;
    while i < len(left.dims) {
        if left.dims.get(i) != right.dims.get(i) {
            return false;
        }
        i += 1;
    }
    return true;
}

// NumPy-style, right-aligned shape compatibility. Unknown shapes are
// conservatively compatible, matching the bootstrap type rules.
fn broadcastable(left: TypeDesc, right: TypeDesc) -> Bool {
    if left.tag != "tensor" or right.tag != "tensor" {
        return false;
    }
    if not left.shape_known or not right.shape_known {
        return true;
    }
    let mut rank = len(left.dims);
    if len(right.dims) > rank {
        rank = len(right.dims);
    }
    let mut i = 1;
    while i <= rank {
        let mut a = 1;
        let mut b = 1;
        if i <= len(left.dims) {
            a = left.dims.get(len(left.dims) - i);
        }
        if i <= len(right.dims) {
            b = right.dims.get(len(right.dims) - i);
        }
        if a != b and a != 1 and b != 1 {
            return false;
        }
        i += 1;
    }
    return true;
}

fn tensor_binary_type(op: String, left: TypeDesc, right: TypeDesc) -> TypeDesc {
    if op != "+" and op != "-" and op != "*" and op != "/" and op != "**" {
        return error_type();
    }
    if left.tag == "tensor" and right.tag == "tensor" {
        if left.name != right.name or not broadcastable(left, right) {
            return error_type();
        }
        if not left.shape_known or not right.shape_known {
            return tensor_type(left.name, false, []);
        }
        let mut rank = len(left.dims);
        if len(right.dims) > rank {
            rank = len(right.dims);
        }
        let dims: List<Int> = [];
        let mut offset = 0;
        while offset < rank {
            let mut a = 1;
            let mut b = 1;
            if offset < len(left.dims) {
                a = left.dims.get(len(left.dims) - 1 - offset);
            }
            if offset < len(right.dims) {
                b = right.dims.get(len(right.dims) - 1 - offset);
            }
            if a == 1 {
                dims.push(b);
            } else {
                dims.push(a);
            }
            offset += 1;
        }
        dims.reverse();
        return tensor_type(left.name, true, dims);
    }
    let mut tensor = left;
    let mut scalar = right;
    if right.tag == "tensor" {
        tensor = right;
        scalar = left;
    }
    if tensor.tag != "tensor" or not is_numeric(scalar) {
        return error_type();
    }
    if op == "**" and scalar.name != "Int" {
        return error_type();
    }
    return tensor;
}

fn infer_binary(op: String, left: TypeDesc, right: TypeDesc) -> TypeDesc {
    if is_error(left) or is_error(right) {
        return error_type();
    }
    if op == "and" or op == "or" {
        if left.tag == "primitive" and right.tag == "primitive" and left.name == "Bool" and right.name == "Bool" {
            return primitive("Bool");
        }
        return error_type();
    }
    if op == "==" or op == "!=" {
        if type_equal(left, right) and left.tag == "primitive" and
            (left.name == "Int" or left.name == "Float" or left.name == "Bool" or left.name == "String") {
            return primitive("Bool");
        }
        return error_type();
    }
    if op == "<" or op == "<=" or op == ">" or op == ">=" {
        if type_equal(left, right) and left.tag == "primitive" and
            (left.name == "Int" or left.name == "Float" or left.name == "String") {
            return primitive("Bool");
        }
        return error_type();
    }
    if left.tag == "tensor" or right.tag == "tensor" {
        return tensor_binary_type(op, left, right);
    }
    if op == "+" and type_equal(left, right) and left.tag == "primitive" and
        (left.name == "Int" or left.name == "Float" or left.name == "String") {
        return left;
    }
    if (op == "-" or op == "*" or op == "/") and type_equal(left, right) and
        left.tag == "primitive" and (left.name == "Int" or left.name == "Float") {
        return left;
    }
    if op == "%" and type_equal(left, right) and left.tag == "primitive" and left.name == "Int" {
        return left;
    }
    if op == "**" and type_equal(left, right) and left.tag == "primitive" and
        (left.name == "Int" or left.name == "Float") {
        return left;
    }
    return error_type();
}

fn infer_unary(op: String, operand: TypeDesc) -> TypeDesc {
    if is_error(operand) {
        return error_type();
    }
    if op == "-" and (is_numeric(operand) or operand.tag == "tensor") {
        return operand;
    }
    if op == "not" and operand.tag == "primitive" and operand.name == "Bool" {
        return primitive("Bool");
    }
    return error_type();
}

fn valid_range_bounds(start: TypeDesc, end: TypeDesc) -> Bool {
    return start.tag == "primitive" and start.name == "Int" and
        end.tag == "primitive" and end.name == "Int";
}

fn infer_list(elements: List<TypeDesc>, has_expected: Bool, expected_element: TypeDesc) -> TypeDesc {
    if len(elements) == 0 {
        if has_expected {
            return list_type(expected_element);
        }
        return error_type();
    }
    let first = elements.get(0);
    if is_error(first) {
        return error_type();
    }
    let mut i = 1;
    while i < len(elements) {
        if not type_equal(first, elements.get(i)) {
            return error_type();
        }
        i += 1;
    }
    return list_type(first);
}

fn infer_index(base: TypeDesc, index: TypeDesc) -> TypeDesc {
    if is_error(base) or is_error(index) {
        return error_type();
    }
    if index.tag != "primitive" or index.name != "Int" {
        return error_type();
    }
    if base.tag == "list" and len(base.elements) == 1 {
        return base.elements.get(0);
    }
    if base.tag == "primitive" and base.name == "String" {
        return primitive("String");
    }
    return error_type();
}

fn lookup_index(bindings: List<Binding>, scope_stack: List<Int>, name: String) -> Int {
    let mut scope_index = scope_stack.len() - 1;
    while scope_index >= 0 {
        let current_scope = scope_stack.get(scope_index);
        let mut binding_index = bindings.len() - 1;
        while binding_index >= 0 {
            let binding = bindings.get(binding_index);
            if binding.scope == current_scope and binding.name == name {
                return binding_index;
            }
            binding_index -= 1;
        }
        scope_index -= 1;
    }
    return -1;
}

fn declare(bindings: List<Binding>, scope_stack: List<Int>, name: String, ty: TypeDesc, mutable: Bool) -> Bool {
    let current_scope = scope_stack.get(scope_stack.len() - 1);
    let duplicate = lookup_index(bindings, scope_stack, name) >= 0 and
        bindings.get(lookup_index(bindings, scope_stack, name)).scope == current_scope;
    if name != "_" {
        // Keep the latest duplicate just as the bootstrap's recovery path does;
        // the false result still exposes the duplicate to differential checks.
        bindings.push(Binding(name, ty, mutable, current_scope));
    }
    return not duplicate;
}

fn resolved_type(bindings: List<Binding>, scope_stack: List<Int>, name: String) -> TypeDesc {
    let index = lookup_index(bindings, scope_stack, name);
    if index < 0 {
        return error_type();
    }
    return bindings.get(index).ty;
}

fn assignment_status(bindings: List<Binding>, scope_stack: List<Int>, name: String, value: TypeDesc, op: String) -> String {
    let index = lookup_index(bindings, scope_stack, name);
    if index < 0 {
        return "unknown";
    }
    let binding = bindings.get(index);
    if not binding.mutable {
        return "immutable";
    }
    if op == "=" {
        if is_assignable(value, binding.ty) {
            return "ok";
        }
        return "type";
    }
    let result = infer_binary(op, binding.ty, value);
    if is_error(result) or not is_assignable(result, binding.ty) {
        return "type";
    }
    return "ok";
}

fn signature_index(signatures: List<FunctionSignature>, name: String) -> Int {
    let mut i = signatures.len() - 1;
    while i >= 0 {
        if signatures.get(i).name == name {
            return i;
        }
        i -= 1;
    }
    return -1;
}

fn check_call(signatures: List<FunctionSignature>, name: String, arguments: List<TypeDesc>) -> TypeDesc {
    let index = signature_index(signatures, name);
    if index < 0 {
        return error_type();
    }
    let signature = signatures.get(index);
    if len(arguments) != len(signature.parameter_types) {
        return error_type();
    }
    let mut i = 0;
    while i < len(arguments) {
        if not is_assignable(arguments.get(i), signature.parameter_types.get(i)) {
            return error_type();
        }
        i += 1;
    }
    return signature.result;
}

fn return_compatible(actual: TypeDesc, expected: TypeDesc, has_value: Bool) -> Bool {
    if expected.tag == "primitive" and expected.name == "Unit" {
        return not has_value;
    }
    if not has_value {
        return false;
    }
    return is_assignable(actual, expected);
}

fn variable_initializer_compatible(actual: TypeDesc, expected: TypeDesc) -> Bool {
    if expected.tag == "primitive" and expected.name == "Unit" {
        return false;
    }
    return is_assignable(actual, expected);
}

fn condition_compatible(actual: TypeDesc) -> Bool {
    return is_assignable(actual, primitive("Bool"));
}

fn iterable_supported(actual: TypeDesc) -> Bool {
    // Match the analyser's ErrorType recovery: an upstream error owns the
    // diagnostic and must not produce a second, misleading iterable error.
    return is_error(actual) or actual.tag == "list" or (actual.tag == "opaque" and actual.name == "Range");
}

fn struct_index(structs: List<StructSignature>, name: String) -> Int {
    let mut i = structs.len() - 1;
    while i >= 0 {
        if structs.get(i).name == name {
            return i;
        }
        i -= 1;
    }
    return -1;
}

fn check_struct_init(structs: List<StructSignature>, name: String, arguments: List<TypeDesc>) -> TypeDesc {
    let index = struct_index(structs, name);
    if index < 0 {
        return error_type();
    }
    let st = structs.get(index);
    if len(arguments) != len(st.field_types) {
        return error_type();
    }
    let mut i = 0;
    while i < len(arguments) {
        if not is_assignable(arguments.get(i), st.field_types.get(i)) {
            return error_type();
        }
        i += 1;
    }
    return nominal_type(name);
}

fn resolve_struct_field(structs: List<StructSignature>, base: TypeDesc, field_name: String) -> TypeDesc {
    if is_error(base) {
        return error_type();
    }
    if base.tag != "nominal" {
        return error_type();
    }
    let index = struct_index(structs, base.name);
    if index < 0 {
        return error_type();
    }
    let st = structs.get(index);
    let mut i = 0;
    while i < len(st.field_names) {
        if st.field_names.get(i) == field_name {
            return st.field_types.get(i);
        }
        i += 1;
    }
    return error_type();
}

fn resolve_property(base: TypeDesc, prop_name: String) -> TypeDesc {
    if is_error(base) {
        return error_type();
    }
    if base.tag == "tensor" {
        if prop_name == "rank" or prop_name == "size" {
            return primitive("Int");
        }
        if prop_name == "shape" {
            return list_type(primitive("Int"));
        }
        if prop_name == "dtype" {
            return primitive("String");
        }
        if prop_name == "requires_grad" {
            return primitive("Bool");
        }
        if prop_name == "grad" {
            return tensor_type(base.name, false, []);
        }
        return error_type();
    }
    if base.tag == "opaque" and base.name == "Canvas" {
        if prop_name == "width" or prop_name == "height" {
            return primitive("Int");
        }
        return error_type();
    }
    if base.tag == "opaque" and base.name == "Model" {
        if prop_name == "parameter_count" {
            return primitive("Int");
        }
        return error_type();
    }
    if base.tag == "opaque" and base.name == "Dataset" {
        if prop_name == "size" {
            return primitive("Int");
        }
        if prop_name == "features" or prop_name == "labels" {
            return tensor_type("Float32", false, []);
        }
        return error_type();
    }
    return error_type();
}

fn resolve_method(base: TypeDesc, method_name: String, arguments: List<TypeDesc>) -> TypeDesc {
    if is_error(base) {
        return error_type();
    }
    if base.tag == "list" and len(base.elements) == 1 {
        let elem = base.elements.get(0);
        if method_name == "len" and len(arguments) == 0 {
            return primitive("Int");
        }
        if method_name == "push" and len(arguments) == 1 and is_assignable(arguments.get(0), elem) {
            return primitive("Unit");
        }
        if method_name == "pop" and len(arguments) == 0 {
            return elem;
        }
        if method_name == "get" and len(arguments) == 1 and is_assignable(arguments.get(0), primitive("Int")) {
            return elem;
        }
        if method_name == "contains" and len(arguments) == 1 and is_assignable(arguments.get(0), elem) {
            return primitive("Bool");
        }
        if method_name == "index_of" and len(arguments) == 1 and is_assignable(arguments.get(0), elem) {
            return primitive("Int");
        }
        if method_name == "join" and len(arguments) == 1 and is_assignable(arguments.get(0), primitive("String")) {
            if is_error(elem) or (elem.tag == "primitive" and elem.name == "String") {
                return primitive("String");
            }
            return error_type();
        }
        if method_name == "sort" and len(arguments) == 0 {
            if is_error(elem) or is_numeric(elem) {
                return primitive("Unit");
            }
            return error_type();
        }
        if method_name == "reverse" and len(arguments) == 0 {
            return primitive("Unit");
        }
        return error_type();
    }
    if base.tag == "primitive" and base.name == "String" {
        if method_name == "len" and len(arguments) == 0 {
            return primitive("Int");
        }
        if (method_name == "upper" or method_name == "lower" or method_name == "trim") and len(arguments) == 0 {
            return primitive("String");
        }
        if (method_name == "contains" or method_name == "starts_with" or method_name == "ends_with") and len(arguments) == 1 and is_assignable(arguments.get(0), primitive("String")) {
            return primitive("Bool");
        }
        if method_name == "split" and len(arguments) == 1 and is_assignable(arguments.get(0), primitive("String")) {
            return list_type(primitive("String"));
        }
        if method_name == "replace" and len(arguments) == 2 and is_assignable(arguments.get(0), primitive("String")) and is_assignable(arguments.get(1), primitive("String")) {
            return primitive("String");
        }
        if method_name == "substring" and len(arguments) == 2 and is_assignable(arguments.get(0), primitive("Int")) and is_assignable(arguments.get(1), primitive("Int")) {
            return primitive("String");
        }
        return error_type();
    }
    if base.tag == "tensor" {
        if (method_name == "sum" or method_name == "mean" or method_name == "max" or method_name == "min" or method_name == "item") and len(arguments) == 0 {
            return primitive("Float");
        }
        if (method_name == "exp" or method_name == "log" or method_name == "sqrt" or method_name == "abs" or method_name == "relu" or method_name == "gelu" or method_name == "layer_norm" or method_name == "tanh" or method_name == "sigmoid" or method_name == "softmax") and len(arguments) == 0 {
            return base;
        }
        if method_name == "reshape" and len(arguments) == 1 and is_assignable(arguments.get(0), list_type(primitive("Int"))) {
            return tensor_type(base.name, false, []);
        }
        if method_name == "transpose" and len(arguments) == 0 {
            if not base.shape_known {
                return tensor_type(base.name, false, []);
            }
            let rev: List<Int> = [];
            let mut i = len(base.dims) - 1;
            while i >= 0 {
                rev.push(base.dims.get(i));
                i -= 1;
            }
            return tensor_type(base.name, true, rev);
        }
        if method_name == "matmul" and len(arguments) == 1 {
            let rhs = arguments.get(0);
            if rhs.tag != "tensor" or rhs.name != base.name {
                return error_type();
            }
            if not base.shape_known or not rhs.shape_known {
                return tensor_type(base.name, false, []);
            }
            if len(base.dims) != 2 or len(rhs.dims) != 2 or base.dims.get(1) != rhs.dims.get(0) {
                return error_type();
            }
            return tensor_type(base.name, true, [base.dims.get(0), rhs.dims.get(1)]);
        }
        if (method_name == "backward" or method_name == "zero_grad") and len(arguments) == 0 {
            return primitive("Unit");
        }
        return error_type();
    }
    if base.tag == "opaque" and base.name == "Range" and method_name == "len" and len(arguments) == 0 {
        return primitive("Int");
    }
    if base.tag == "opaque" and base.name == "Color" {
        if method_name == "css" and len(arguments) == 0 {
            return primitive("String");
        }
        if method_name == "luminance" and len(arguments) == 0 {
            return primitive("Float");
        }
        return error_type();
    }
    if base.tag == "opaque" and base.name == "Canvas" and method_name == "save" and len(arguments) == 1 and is_assignable(arguments.get(0), primitive("String")) {
        return primitive("Unit");
    }
    if base.tag == "opaque" and base.name == "Model" {
        if method_name == "summary" and len(arguments) == 0 {
            return primitive("String");
        }
        if method_name == "predict" and len(arguments) == 1 and arguments.get(0).tag == "tensor" {
            return tensor_type("Float32", false, []);
        }
        return error_type();
    }
    if base.tag == "opaque" and base.name == "Dataset" {
        if method_name == "size" and len(arguments) == 0 {
            return primitive("Int");
        }
        if (method_name == "features" or method_name == "labels") and len(arguments) == 0 {
            return tensor_type("Float32", false, []);
        }
        return error_type();
    }
    return error_type();
}

fn capability_declared(declared: List<String>, required: String) -> Bool {
    if required == "" {
        return true;
    }
    return declared.contains(required);
}

fn diagnostic_code_for_violation(violation: String) -> String {
    if violation == "duplicate_decl" {
        return "PE3001";
    }
    if violation == "unknown_name" {
        return "PE3002";
    }
    if violation == "type_mismatch" {
        return "PE3003";
    }
    if violation == "arity_mismatch" {
        return "PE3004";
    }
    if violation == "invalid_capability" {
        return "PE3005";
    }
    if violation == "unimported_namespace" {
        return "PE3006";
    }
    if violation == "immutable_assign" {
        return "PE3007";
    }
    if violation == "bad_return" {
        return "PE3008";
    }
    if violation == "missing_capability" {
        return "PE3011";
    }
    if violation == "unknown_field" {
        return "PE3015";
    }
    return "PE3012";
}

fn run_builtin_checks() -> Int {
    let int_ty = primitive("Int");
    let float_ty = primitive("Float");
    let bool_ty = primitive("Bool");
    let string_ty = primitive("String");
    let never_ty = primitive("Never");
    let err_ty = error_type();
    let mut cases = 0;

    assert(is_assignable(int_ty, int_ty));
    assert(not is_assignable(int_ty, float_ty));
    assert(is_assignable(never_ty, primitive("Unit")));
    assert(is_assignable(err_ty, string_ty));
    assert(type_equal(list_type(list_type(int_ty)), list_type(list_type(primitive("Int")))));
    assert(not is_assignable(list_type(int_ty), list_type(float_ty)));
    assert(is_assignable(nominal_type("Point"), nominal_type("Point")));
    assert(not is_assignable(nominal_type("Point"), nominal_type("Other")));
    assert(is_assignable(opaque_type("Color"), opaque_type("Color")));
    cases += 9;

    let concrete = tensor_type("Float32", true, [2, 3]);
    let dynamic = tensor_type("Float32", false, []);
    assert(is_assignable(concrete, dynamic));
    assert(not is_assignable(dynamic, concrete));
    assert(not is_assignable(concrete, tensor_type("Float64", false, [])));
    assert(is_assignable(concrete, tensor_type("Float32", true, [2, 3])));
    assert(not is_assignable(concrete, tensor_type("Float32", true, [3, 2])));
    assert(broadcastable(tensor_type("Float32", true, [2, 1]), tensor_type("Float32", true, [1, 3])));
    assert(broadcastable(tensor_type("Float32", true, [3]), tensor_type("Float32", true, [2, 3])));
    assert(not broadcastable(tensor_type("Float32", true, [2]), tensor_type("Float32", true, [3])));
    assert(not broadcastable(int_ty, concrete));
    cases += 9;

    assert(type_equal(infer_binary("+", int_ty, int_ty), int_ty));
    assert(type_equal(infer_binary("+", string_ty, string_ty), string_ty));
    assert(type_equal(infer_binary("and", bool_ty, bool_ty), bool_ty));
    assert(type_equal(infer_binary("<", int_ty, int_ty), bool_ty));
    assert(is_error(infer_binary("+", int_ty, float_ty)));
    assert(type_equal(infer_unary("-", concrete), concrete));
    assert(type_equal(infer_unary("not", bool_ty), bool_ty));
    assert(is_error(infer_index(list_type(int_ty), float_ty)));
    assert(type_equal(infer_index(list_type(int_ty), int_ty), int_ty));
    assert(type_equal(infer_list([int_ty, int_ty], false, err_ty), list_type(int_ty)));
    assert(is_error(infer_list([int_ty, float_ty], false, err_ty)));
    assert(is_error(infer_list([], false, err_ty)));
    assert(type_equal(infer_list([], true, int_ty), list_type(int_ty)));
    cases += 13;

    let mut bindings: List<Binding> = [];
    let mut active_scopes: List<Int> = [0];
    assert(declare(bindings, active_scopes, "value", int_ty, true));
    assert(resolved_type(bindings, active_scopes, "value").name == "Int");
    assert(assignment_status(bindings, active_scopes, "value", float_ty, "=") == "type");
    assert(assignment_status(bindings, active_scopes, "value", int_ty, "=") == "ok");
    assert(not declare(bindings, active_scopes, "value", float_ty, false));
    assert(resolved_type(bindings, active_scopes, "value").name == "Float");
    assert(assignment_status(bindings, active_scopes, "value", float_ty, "=") == "immutable");
    active_scopes.push(1);
    assert(declare(bindings, active_scopes, "value", string_ty, false));
    assert(resolved_type(bindings, active_scopes, "value").name == "String");
    active_scopes.pop();
    assert(resolved_type(bindings, active_scopes, "value").name == "Float");
    assert(lookup_index(bindings, active_scopes, "missing") == -1);
    cases += 12;

    let mut signatures: List<FunctionSignature> = [];
    signatures.push(FunctionSignature("sum", ["left", "right"], [int_ty, int_ty], int_ty));
    assert(type_equal(check_call(signatures, "sum", [int_ty, int_ty]), int_ty));
    assert(is_error(check_call(signatures, "sum", [int_ty])));
    assert(is_error(check_call(signatures, "sum", [int_ty, float_ty])));
    assert(is_error(check_call(signatures, "absent", [])));
    assert(return_compatible(int_ty, int_ty, true));
    assert(not return_compatible(int_ty, float_ty, true));
    assert(not return_compatible(int_ty, int_ty, false));
    assert(return_compatible(primitive("Unit"), primitive("Unit"), false));
    assert(not return_compatible(primitive("Unit"), primitive("Unit"), true));
    assert(variable_initializer_compatible(int_ty, int_ty));
    assert(not variable_initializer_compatible(int_ty, primitive("Unit")));
    assert(condition_compatible(bool_ty));
    assert(not condition_compatible(int_ty));
    assert(iterable_supported(range_type()));
    assert(iterable_supported(list_type(int_ty)));
    assert(not iterable_supported(int_ty));
    assert(iterable_supported(err_ty));
    cases += 13;

    let mut structs: List<StructSignature> = [];
    structs.push(StructSignature("Point", ["x", "y"], [int_ty, float_ty]));
    assert(type_equal(check_struct_init(structs, "Point", [int_ty, float_ty]), nominal_type("Point")));
    assert(is_error(check_struct_init(structs, "Point", [int_ty])));
    assert(is_error(check_struct_init(structs, "Point", [float_ty, float_ty])));
    assert(type_equal(resolve_struct_field(structs, nominal_type("Point"), "x"), int_ty));
    assert(type_equal(resolve_struct_field(structs, nominal_type("Point"), "y"), float_ty));
    assert(is_error(resolve_struct_field(structs, nominal_type("Point"), "z")));
    assert(type_equal(resolve_property(concrete, "rank"), int_ty));
    assert(type_equal(resolve_property(concrete, "shape"), list_type(int_ty)));
    assert(type_equal(resolve_property(opaque_type("Canvas"), "width"), int_ty));
    assert(type_equal(resolve_method(list_type(int_ty), "get", [int_ty]), int_ty));
    assert(type_equal(resolve_method(list_type(string_ty), "join", [string_ty]), string_ty));
    assert(is_error(resolve_method(list_type(int_ty), "join", [string_ty])));
    assert(type_equal(resolve_method(string_ty, "split", [string_ty]), list_type(string_ty)));
    assert(type_equal(resolve_method(concrete, "transpose", []), tensor_type("Float32", true, [3, 2])));
    assert(type_equal(resolve_method(concrete, "matmul", [tensor_type("Float32", true, [3, 4])]), tensor_type("Float32", true, [2, 4])));
    assert(capability_declared(["fs", "compute"], "fs"));
    assert(not capability_declared(["fs"], "ui"));
    assert(diagnostic_code_for_violation("unknown_field") == "PE3015");
    cases += 18;

    return cases;
}

fn main() -> Unit {
    let checks = run_builtin_checks();
    print("PEACOCK type-model checks passed (" + str(checks) + " assertions)");
}
