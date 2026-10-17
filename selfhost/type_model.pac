// PEACOCK-native type-algebra migration milestone (stage 3 groundwork).
//
// This module is deliberately a small, executable type-model kernel rather
// than a claim that the self-hosted semantic analyser is complete. It implements
// primitive/list/declared-nominal assignability, Never/Error recovery, tensor
// shape assignability and right-aligned broadcasting in PEACOCK. The
// Python `compiler/types.py` remains the production oracle until parity coverage
// is broad enough to replace it.
module selfhost_type_model

struct TypeDesc {
    tag: String,
    name: String,
    shape_known: Bool,
    dims: List<Int>
}

fn primitive(name: String) -> TypeDesc {
    return TypeDesc("primitive", name, false, []);
}

fn tensor_type(dtype: String, known: Bool, dims: List<Int>) -> TypeDesc {
    return TypeDesc("tensor", dtype, known, dims);
}

fn list_type(element_name: String) -> TypeDesc {
    return TypeDesc("list", element_name, false, []);
}

fn nominal_type(type_name: String) -> TypeDesc {
    return TypeDesc("nominal", type_name, false, []);
}

fn same_shape(left: TypeDesc, right: TypeDesc) -> Bool {
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

// `source` values may flow to `target` values under the v0.1 assignment rules.
fn is_assignable(source: TypeDesc, target: TypeDesc) -> Bool {
    if source.name == "<error>" or target.name == "<error>" {
        return true;
    }
    if source.tag == "primitive" and source.name == "Never" {
        return true;
    }
    if source.tag == target.tag and (source.tag == "primitive" or source.tag == "list" or source.tag == "nominal") {
        return source.name == target.name;
    }
    if source.tag == "tensor" and target.tag == "tensor" {
        if source.name != target.name {
            return false;
        }
        if not target.shape_known {
            return true;
        }
        return source.shape_known and same_shape(source, target);
    }
    return false;
}

// Whether pairwise broadcasting is valid, with dimensions aligned from the right.
fn broadcastable(left: TypeDesc, right: TypeDesc) -> Bool {
    if left.tag != "tensor" or right.tag != "tensor" {
        return false;
    }
    if not left.shape_known or not right.shape_known {
        return true;
    }
    let mut i = 1;
    let mut rank = len(left.dims);
    if len(right.dims) > rank {
        rank = len(right.dims);
    }
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

fn main() -> Unit {
    // Primitive rules and bottom/error recovery.
    assert(is_assignable(primitive("Int"), primitive("Int")));
    assert(not is_assignable(primitive("Int"), primitive("Float")));
    assert(is_assignable(primitive("Never"), primitive("Unit")));
    assert(is_assignable(primitive("<error>"), primitive("String")));
    assert(is_assignable(list_type("Int"), list_type("Int")));
    assert(not is_assignable(list_type("Int"), list_type("Float")));
    assert(is_assignable(nominal_type("Point"), nominal_type("Point")));
    assert(not is_assignable(nominal_type("Point"), nominal_type("Other")));

    // Static tensors may flow to an unknown-shape tensor of the same dtype.
    let concrete = tensor_type("Float32", true, [2, 3]);
    let dynamic = tensor_type("Float32", false, [0]);
    assert(is_assignable(concrete, dynamic));
    assert(not is_assignable(dynamic, concrete));
    assert(not is_assignable(concrete, tensor_type("Float64", false, [0])));
    assert(is_assignable(concrete, tensor_type("Float32", true, [2, 3])));
    assert(not is_assignable(concrete, tensor_type("Float32", true, [3, 2])));

    // Right-aligned broadcast rules: [2,1] with [1,3] is valid; [2] with [3] is not.
    assert(broadcastable(tensor_type("Float32", true, [2, 1]), tensor_type("Float32", true, [1, 3])));
    assert(broadcastable(tensor_type("Float32", true, [3]), tensor_type("Float32", true, [2, 3])));
    assert(not broadcastable(tensor_type("Float32", true, [2]), tensor_type("Float32", true, [3])));
    assert(not broadcastable(primitive("Int"), concrete));
    print("PEACOCK type-model checks passed");
}
