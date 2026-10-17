// PEACOCK-native IR, optimizer and bytecode verification kernel (migration stage 4).
//
// Models linear PIR instructions, register def-before-use invariants, slot range
// verification, control-flow label validation, balanced try/catch scopes,
// constant folding, and bytecode jump-target validation in genuine .pac source.

module selfhost_ir_model

struct IRInstr {
    op: String,
    dst: Int,
    slot: Int,
    src_a: Int,
    src_b: Int,
    label_a: String,
    label_b: String,
    int_val: Int
}

fn ir_const_int(dst: Int, value: Int) -> IRInstr {
    return IRInstr("const_int", dst, -1, -1, -1, "", "", value);
}

fn ir_slot_get(dst: Int, slot: Int) -> IRInstr {
    return IRInstr("slot_get", dst, slot, -1, -1, "", "", 0);
}

fn ir_slot_set(slot: Int, src: Int) -> IRInstr {
    return IRInstr("slot_set", -1, slot, src, -1, "", "", 0);
}

fn ir_binop(op_name: String, dst: Int, left: Int, right: Int) -> IRInstr {
    return IRInstr("binop", dst, -1, left, right, op_name, "", 0);
}

fn ir_label(name: String) -> IRInstr {
    return IRInstr("label", -1, -1, -1, -1, name, "", 0);
}

fn ir_jump(target: String) -> IRInstr {
    return IRInstr("jump", -1, -1, -1, -1, target, "", 0);
}

fn ir_branch(cond: Int, then_label: String, else_label: String) -> IRInstr {
    return IRInstr("branch", -1, -1, cond, -1, then_label, else_label, 0);
}

fn ir_try_begin(catch_label: String, end_label: String) -> IRInstr {
    return IRInstr("try_begin", -1, -1, -1, -1, catch_label, end_label, 0);
}

fn ir_try_end() -> IRInstr {
    return IRInstr("try_end", -1, -1, -1, -1, "", "", 0);
}

fn ir_return(src: Int) -> IRInstr {
    return IRInstr("return", -1, -1, src, -1, "", "", 0);
}

fn verify_ir(instrs: List<IRInstr>, slot_count: Int) -> String {
    if len(instrs) == 0 {
        return "missing_terminator";
    }
    let mut labels: List<String> = [];
    let mut i = 0;
    while i < len(instrs) {
        let ins = instrs.get(i);
        if ins.op == "label" {
            if ins.label_a == "" or labels.contains(ins.label_a) {
                return "duplicate_label";
            }
            labels.push(ins.label_a);
        }
        i += 1;
    }

    let mut defined_regs: List<Int> = [];
    let mut try_depth = 0;
    i = 0;
    while i < len(instrs) {
        let ins = instrs.get(i);
        if ins.op == "slot_get" or ins.op == "slot_set" {
            if ins.slot < 0 or ins.slot >= slot_count {
                return "bad_slot";
            }
        }
        if ins.src_a >= 0 and not defined_regs.contains(ins.src_a) {
            return "undefined_reg";
        }
        if ins.src_b >= 0 and not defined_regs.contains(ins.src_b) {
            return "undefined_reg";
        }
        if ins.dst >= 0 {
            if not defined_regs.contains(ins.dst) {
                defined_regs.push(ins.dst);
            }
        }
        if ins.op == "jump" {
            if not labels.contains(ins.label_a) {
                return "unknown_label";
            }
        } else if ins.op == "branch" {
            if not labels.contains(ins.label_a) or not labels.contains(ins.label_b) {
                return "unknown_label";
            }
        } else if ins.op == "try_begin" {
            if not labels.contains(ins.label_a) or not labels.contains(ins.label_b) {
                return "unknown_label";
            }
            try_depth += 1;
        } else if ins.op == "try_end" {
            if try_depth <= 0 {
                return "unbalanced_try";
            }
            try_depth -= 1;
        }
        i += 1;
    }

    if try_depth != 0 {
        return "unbalanced_try";
    }
    let last = instrs.get(len(instrs) - 1);
    if last.op != "return" and last.op != "jump" and last.op != "branch" and last.op != "throw" {
        return "missing_terminator";
    }
    return "ok";
}

fn can_fold_int_binop(op: String, left: Int, right: Int) -> Bool {
    if op == "/" or op == "%" {
        return right != 0 and not (left == -9223372036854775807 - 1 and right == -1);
    }
    if op == "**" {
        return right >= 0 and right <= 30;
    }
    return op == "+" or op == "-" or op == "*";
}

fn fold_int_binop(op: String, left: Int, right: Int) -> Int {
    if op == "+" {
        return left + right;
    }
    if op == "-" {
        return left - right;
    }
    if op == "*" {
        return left * right;
    }
    if op == "/" {
        return left / right;
    }
    if op == "%" {
        return left % right;
    }
    if op == "**" {
        return left ** right;
    }
    return 0;
}

fn verify_bytecode_jumps(instruction_count: Int, jump_targets: List<Int>) -> Bool {
    if instruction_count <= 0 {
        return false;
    }
    let mut i = 0;
    while i < len(jump_targets) {
        let target = jump_targets.get(i);
        if target < 0 or target >= instruction_count {
            return false;
        }
        i += 1;
    }
    return true;
}

fn run_ir_checks() -> Int {
    let mut checks = 0;
    let valid_fn: List<IRInstr> = [
        ir_const_int(0, 10),
        ir_const_int(1, 32),
        ir_binop("+", 2, 0, 1),
        ir_slot_set(0, 2),
        ir_slot_get(3, 0),
        ir_return(3)
    ];
    assert(verify_ir(valid_fn, 1) == "ok");
    assert(verify_ir(valid_fn, 0) == "bad_slot");
    checks += 2;

    let undef_reg: List<IRInstr> = [
        ir_binop("+", 1, 0, 0),
        ir_return(1)
    ];
    assert(verify_ir(undef_reg, 1) == "undefined_reg");
    checks += 1;

    let dup_label: List<IRInstr> = [
        ir_label("entry"),
        ir_label("entry"),
        ir_const_int(0, 1),
        ir_return(0)
    ];
    assert(verify_ir(dup_label, 1) == "duplicate_label");
    checks += 1;

    let bad_jump: List<IRInstr> = [
        ir_jump("missing")
    ];
    assert(verify_ir(bad_jump, 1) == "unknown_label");
    checks += 1;

    let bad_try: List<IRInstr> = [
        ir_label("catch_lbl"),
        ir_label("end_lbl"),
        ir_try_begin("catch_lbl", "end_lbl"),
        ir_const_int(0, 1),
        ir_return(0)
    ];
    assert(verify_ir(bad_try, 1) == "unbalanced_try");
    checks += 1;

    let good_try: List<IRInstr> = [
        ir_try_begin("catch_lbl", "end_lbl"),
        ir_const_int(0, 7),
        ir_try_end(),
        ir_jump("end_lbl"),
        ir_label("catch_lbl"),
        ir_const_int(0, 0),
        ir_label("end_lbl"),
        ir_return(0)
    ];
    assert(verify_ir(good_try, 1) == "ok");
    checks += 1;

    assert(can_fold_int_binop("+", 20, 22));
    assert(fold_int_binop("+", 20, 22) == 42);
    assert(not can_fold_int_binop("/", 10, 0));
    assert(can_fold_int_binop("/", -7, 2));
    assert(fold_int_binop("/", -7, 2) == -3);
    assert(verify_bytecode_jumps(6, [0, 3, 5]));
    assert(not verify_bytecode_jumps(6, [0, 6]));
    assert(not verify_bytecode_jumps(6, [-1]));
    checks += 8;

    return checks;
}

fn main() -> Unit {
    let total = run_ir_checks();
    print("PEACOCK IR-model checks passed (" + str(total) + " assertions)");
}
