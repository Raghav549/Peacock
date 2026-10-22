#include "runtime.h"

#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int64_t p_steps = 0;
int64_t p_max_steps = 2000000;
int p_call_depth = 0;
size_t p_output_chars = 0;

jmp_buf p_error_target;
int p_error_target_active = 0;
static POutputCallback p_output_callback = NULL;
static void *p_output_userdata = NULL;
static char p_error_text[2048];

typedef struct PAllocation {
    void *pointer;
    struct PAllocation *next;
} PAllocation;

static PAllocation *p_allocations = NULL;
static size_t p_live_allocations = 0;

size_t p_runtime_allocation_count(void) { return p_live_allocations; }

void p_runtime_cleanup(void) {
    PAllocation *current = p_allocations;
    p_allocations = NULL;
    p_live_allocations = 0;
    while (current) {
        PAllocation *next = current->next;
        free(current->pointer);
        free(current);
        current = next;
    }
}

void p_set_output_callback(POutputCallback callback, void *userdata) {
    p_output_callback = callback;
    p_output_userdata = userdata;
}

const char *p_last_error(void) { return p_error_text; }

void p_fail(const char *code, const char *message) {
    snprintf(p_error_text, sizeof(p_error_text), "%s: %s", code, message);
    if (p_error_target_active) longjmp(p_error_target, 1);
    fprintf(stderr, "%s\n", p_error_text);
    exit(3);
}

void *p_alloc(size_t size) {
    void *result = calloc(1, size ? size : 1);
    if (!result) p_fail("PE4003", "native allocation failed");
    PAllocation *node = (PAllocation *)malloc(sizeof(*node));
    if (!node) {
        free(result);
        p_fail("PE4003", "native allocation tracking failed");
    }
    node->pointer = result;
    node->next = p_allocations;
    p_allocations = node;
    p_live_allocations++;
    return result;
}

static PAllocation *p_find_allocation(void *pointer, PAllocation **previous) {
    PAllocation *prior = NULL;
    PAllocation *current = p_allocations;
    while (current && current->pointer != pointer) {
        prior = current;
        current = current->next;
    }
    if (!current) p_fail("PE4999", "invalid native allocation ownership");
    if (previous) *previous = prior;
    return current;
}

void *p_realloc(void *pointer, size_t size) {
    if (!pointer) return p_alloc(size);
    PAllocation *node = p_find_allocation(pointer, NULL);
    void *result = realloc(pointer, size ? size : 1);
    if (!result) p_fail("PE4003", "native allocation failed");
    node->pointer = result;
    return result;
}

void p_free(void *pointer) {
    if (!pointer) return;
    PAllocation *previous = NULL;
    PAllocation *node = p_find_allocation(pointer, &previous);
    if (previous) previous->next = node->next;
    else p_allocations = node->next;
    free(node->pointer);
    free(node);
    p_live_allocations--;
}

void p_tick(void) {
    p_steps++;
    if (p_steps > p_max_steps) p_fail("PE4003", "program exceeded the native step limit");
}

void p_enter(void) {
    if (p_call_depth >= P_MAX_CALL_DEPTH) p_fail("PE4003", "native call depth exceeded");
    p_call_depth++;
}

void p_leave(void) { p_call_depth--; }

PValue p_unit(void) { PValue v; memset(&v, 0, sizeof(v)); v.type = P_UNIT; return v; }
PValue p_int(int64_t x) { PValue v = p_unit(); v.type = P_INT; v.as.integer = x; return v; }
PValue p_float(double x) { PValue v = p_unit(); v.type = P_FLOAT; v.as.floating = x; return v; }
PValue p_bool(int x) { PValue v = p_unit(); v.type = P_BOOL; v.as.boolean = !!x; return v; }

PValue p_string(const char *data, size_t length) {
    PValue v = p_unit();
    PString *s = p_alloc(sizeof(*s));
    s->data = p_alloc(length + 1);
    if (length) memcpy(s->data, data, length);
    s->data[length] = '\0';
    s->length = length;
    v.type = P_STRING;
    v.as.string = s;
    return v;
}

PValue p_cstring(const char *data) { return p_string(data, strlen(data)); }

PValue p_list(size_t length, PValue *items) {
    PValue v = p_unit();
    PList *list = p_alloc(sizeof(*list));
    list->length = list->capacity = length;
    list->items = p_alloc((length ? length : 1) * sizeof(PValue));
    if (length) memcpy(list->items, items, length * sizeof(PValue));
    v.type = P_LIST;
    v.as.list = list;
    return v;
}

PValue p_range(int64_t start, int64_t end) {
    PValue v = p_unit(); v.type = P_RANGE; v.as.range.start = start; v.as.range.end = end; return v;
}

void p_push(PStack *stack, PValue value) {
    if (stack->length >= P_MAX_STACK) p_fail("PE4003", "native operand stack limit exceeded");
    stack->items[stack->length++] = value;
}

PValue p_pop(PStack *stack) {
    if (stack->length <= 0) p_fail("PE4999", "native operand stack underflow");
    return stack->items[--stack->length];
}

PValue p_read_slot(PValue value) {
    if (value.type == P_UNINIT) p_fail("PE4002", "read of an uninitialised local variable");
    return value;
}

int64_t p_require_int(PValue value, const char *what) {
    if (value.type != P_INT) p_fail("PE4002", what);
    return value.as.integer;
}

double p_require_float(PValue value, const char *what) {
    if (value.type != P_FLOAT) p_fail("PE4002", what);
    return value.as.floating;
}

PString *p_require_string(PValue value, const char *what) {
    if (value.type != P_STRING) p_fail("PE4002", what);
    return value.as.string;
}

PList *p_require_list(PValue value, const char *what) {
    if (value.type != P_LIST) p_fail("PE4002", what);
    return value.as.list;
}

static int64_t p_checked(__int128 value) {
    if (value > INT64_MAX || value < INT64_MIN) p_fail("PE4004", "integer overflow");
    return (int64_t)value;
}

static int p_same_type(PValue a, PValue b) { return a.type == b.type; }

static int p_equal(PValue a, PValue b) {
    if (!p_same_type(a, b)) p_fail("PE4006", "cannot compare values of different types");
    switch (a.type) {
        case P_INT: return a.as.integer == b.as.integer;
        case P_FLOAT: return a.as.floating == b.as.floating;
        case P_BOOL: return a.as.boolean == b.as.boolean;
        case P_STRING: {
            PString *x = a.as.string, *y = b.as.string;
            return x->length == y->length && (!x->length || !memcmp(x->data, y->data, x->length));
        }
        default: p_fail("PE4006", "equality is not defined for this native value");
    }
    return 0;
}

static int64_t p_division(int64_t a, int64_t b) {
    if (!b) p_fail("PE4005", "division by zero");
    if (a == INT64_MIN && b == -1) p_fail("PE4004", "integer overflow in division");
    return a / b;
}

PValue p_binary(const char *op, PValue a, PValue b) {
    if (!strcmp(op, "==") || !strcmp(op, "!=")) {
        int equal = p_equal(a, b);
        return p_bool(!strcmp(op, "==") ? equal : !equal);
    }
    if (!strcmp(op, "and") || !strcmp(op, "or")) {
        if (a.type != P_BOOL || b.type != P_BOOL) p_fail("PE4006", "boolean operator requires सत्यता operands");
        return p_bool(!strcmp(op, "and") ? (a.as.boolean && b.as.boolean) : (a.as.boolean || b.as.boolean));
    }
    if (!strcmp(op, "+") && a.type == P_STRING && b.type == P_STRING) {
        PString *x = a.as.string, *y = b.as.string;
        if (x->length > SIZE_MAX - y->length) p_fail("PE4003", "string size overflow");
        char *data = p_alloc(x->length + y->length + 1);
        memcpy(data, x->data, x->length);
        memcpy(data + x->length, y->data, y->length);
        PValue result = p_string(data, x->length + y->length);
        p_free(data);
        return result;
    }
    if (a.type == P_STRING && b.type == P_STRING && (!strcmp(op, "<") || !strcmp(op, "<=") || !strcmp(op, ">") || !strcmp(op, ">="))) {
        PString *x = a.as.string, *y = b.as.string;
        size_t common = x->length < y->length ? x->length : y->length;
        int comparison = common ? memcmp(x->data, y->data, common) : 0;
        if (!comparison) comparison = x->length < y->length ? -1 : (x->length > y->length ? 1 : 0);
        if (!strcmp(op, "<")) return p_bool(comparison < 0);
        if (!strcmp(op, "<=")) return p_bool(comparison <= 0);
        if (!strcmp(op, ">")) return p_bool(comparison > 0);
        return p_bool(comparison >= 0);
    }
    if (a.type == P_INT && b.type == P_INT) {
        int64_t x = a.as.integer, y = b.as.integer;
        if (!strcmp(op, "+")) return p_int(p_checked((__int128)x + y));
        if (!strcmp(op, "-")) return p_int(p_checked((__int128)x - y));
        if (!strcmp(op, "*")) return p_int(p_checked((__int128)x * y));
        if (!strcmp(op, "/")) return p_int(p_division(x, y));
        if (!strcmp(op, "%")) {
            int64_t q = p_division(x, y);
            return p_int(p_checked((__int128)x - (__int128)q * y));
        }
        if (!strcmp(op, "**")) {
            if (y < 0) p_fail("PE4004", "integer exponent must be non-negative");
            if (y > 63 && (x > 1 || x < -1)) p_fail("PE4004", "integer overflow in exponentiation");
            __int128 result = 1, base = x;
            int64_t exponent = y;
            while (exponent) {
                if (exponent & 1) result = p_checked(result * base);
                exponent >>= 1;
                if (exponent) base = p_checked(base * base);
            }
            return p_int(p_checked(result));
        }
        if (!strcmp(op, "<")) return p_bool(x < y);
        if (!strcmp(op, "<=")) return p_bool(x <= y);
        if (!strcmp(op, ">")) return p_bool(x > y);
        if (!strcmp(op, ">=")) return p_bool(x >= y);
    }
    if (a.type == P_FLOAT && b.type == P_FLOAT) {
        double x = a.as.floating, y = b.as.floating;
        if (!strcmp(op, "+")) return p_float(x + y);
        if (!strcmp(op, "-")) return p_float(x - y);
        if (!strcmp(op, "*")) return p_float(x * y);
        if (!strcmp(op, "/")) { if (y == 0.0) p_fail("PE4005", "float division by zero"); return p_float(x / y); }
        if (!strcmp(op, "**")) {
            errno = 0;
            double result = pow(x, y);
            if (errno || isnan(result)) p_fail("PE4004", "invalid float exponentiation");
            return p_float(result);
        }
        if (!strcmp(op, "<")) return p_bool(x < y);
        if (!strcmp(op, "<=")) return p_bool(x <= y);
        if (!strcmp(op, ">")) return p_bool(x > y);
        if (!strcmp(op, ">=")) return p_bool(x >= y);
    }
    p_fail("PE4006", "operator is not defined for these native value types");
    return p_unit();
}

PValue p_unary(const char *op, PValue value) {
    if (!strcmp(op, "not")) {
        if (value.type != P_BOOL) p_fail("PE4006", "'न' requires सत्यता");
        return p_bool(!value.as.boolean);
    }
    if (!strcmp(op, "-")) {
        if (value.type == P_INT) return p_int(p_checked(-(__int128)value.as.integer));
        if (value.type == P_FLOAT) return p_float(-value.as.floating);
    }
    p_fail("PE4006", "unary operator is not defined for this native value");
    return p_unit();
}

static size_t p_utf8_length(PString *s) {
    size_t count = 0;
    for (size_t i = 0; i < s->length; i++) if (((unsigned char)s->data[i] & 0xc0) != 0x80) count++;
    return count;
}

static size_t p_utf8_offset(PString *s, int64_t index) {
    int64_t current = 0;
    size_t offset = 0;
    while (offset < s->length && current < index) {
        unsigned char c = (unsigned char)s->data[offset++];
        size_t extra = c < 0x80 ? 0 : ((c & 0xe0) == 0xc0 ? 1 : ((c & 0xf0) == 0xe0 ? 2 : 3));
        if (offset + extra > s->length) p_fail("PE4002", "invalid UTF-8 string boundary");
        offset += extra;
        current++;
    }
    if (current != index) p_fail("PE4002", "string index out of bounds");
    return offset;
}

PValue p_index_get(PValue base, PValue index) {
    int64_t i = p_require_int(index, "index must be a पूर्णाङ्क");
    if (base.type == P_LIST) {
        PList *list = base.as.list;
        if (i < 0 || (uint64_t)i >= list->length) p_fail("PE4002", "list index out of bounds");
        return list->items[i];
    }
    if (base.type == P_STRING) {
        PString *s = base.as.string;
        if (i < 0 || (uint64_t)i >= p_utf8_length(s)) p_fail("PE4002", "string index out of bounds");
        size_t start = p_utf8_offset(s, i), end = p_utf8_offset(s, i + 1);
        return p_string(s->data + start, end - start);
    }
    p_fail("PE4002", "value is not indexable in the native backend");
    return p_unit();
}

void p_index_set(PValue base, PValue index, PValue value) {
    PList *list = p_require_list(base, "indexed assignment requires a सूची");
    int64_t i = p_require_int(index, "index must be a पूर्णाङ्क");
    if (i < 0 || (uint64_t)i >= list->length) p_fail("PE4002", "list index out of bounds");
    list->items[i] = value;
}

PValue p_len(PValue value) {
    if (value.type == P_LIST) return p_int((int64_t)value.as.list->length);
    if (value.type == P_STRING) return p_int((int64_t)p_utf8_length(value.as.string));
    if (value.type == P_RANGE) {
        int64_t length = value.as.range.end > value.as.range.start ? value.as.range.end - value.as.range.start : 0;
        return p_int(length);
    }
    p_fail("PE4002", "दैर्घ्य() is not defined for this native value");
    return p_unit();
}

/* A small formatting buffer is shared by print, str() and nested list display. */
typedef struct { char *data; size_t length, capacity; } PBuffer;
static void p_buffer_add(PBuffer *b, const char *data, size_t length) {
    if (b->length + length + 1 > b->capacity) {
        size_t capacity = b->capacity ? b->capacity : 64;
        while (capacity < b->length + length + 1) capacity *= 2;
        b->data = p_realloc(b->data, capacity); b->capacity = capacity;
    }
    if (length) memcpy(b->data + b->length, data, length);
    b->length += length; b->data[b->length] = '\0';
}
static void p_buffer_cstr(PBuffer *b, const char *text) { p_buffer_add(b, text, strlen(text)); }
static void p_buffer_value(PBuffer *b, PValue value, int nested) {
    char number[128];
    switch (value.type) {
        case P_UNINIT: p_fail("PE4999", "attempt to format an uninitialised native value"); break;
        case P_UNIT: p_buffer_cstr(b, "एकक"); break;
        case P_BOOL: p_buffer_cstr(b, value.as.boolean ? "सत्य" : "असत्य"); break;
        case P_INT: snprintf(number, sizeof(number), "%lld", (long long)value.as.integer); p_buffer_cstr(b, number); break;
        case P_FLOAT: {
            double x = value.as.floating;
            if (isnan(x)) p_buffer_cstr(b, "NaN");
            else if (isinf(x)) p_buffer_cstr(b, x > 0 ? "Infinity" : "-Infinity");
            else {
                for (int precision = 1; precision <= 17; precision++) {
                    snprintf(number, sizeof(number), "%.*g", precision, x);
                    char *end = NULL;
                    double roundtrip = strtod(number, &end);
                    if (end && !*end && roundtrip == x) break;
                }
                p_buffer_cstr(b, number);
                if (!strchr(number, '.') && !strchr(number, 'e') && !strchr(number, 'E')) p_buffer_cstr(b, ".0");
            }
            break;
        }
        case P_STRING: {
            PString *s = value.as.string;
            if (nested) p_buffer_cstr(b, "\"");
            for (size_t i = 0; i < s->length; i++) {
                char c = s->data[i];
                if (nested && c == '\\') p_buffer_cstr(b, "\\\\");
                else if (nested && c == '"') p_buffer_cstr(b, "\\\"");
                else if (nested && c == '\n') p_buffer_cstr(b, "\\n");
                else if (nested && c == '\t') p_buffer_cstr(b, "\\t");
                else p_buffer_add(b, &c, 1);
            }
            if (nested) p_buffer_cstr(b, "\"");
            break;
        }
        case P_LIST:
            p_buffer_cstr(b, "[");
            for (size_t i = 0; i < value.as.list->length; i++) {
                if (i) p_buffer_cstr(b, ", ");
                p_buffer_value(b, value.as.list->items[i], 1);
            }
            p_buffer_cstr(b, "]"); break;
        case P_RANGE:
            snprintf(number, sizeof(number), "सीमा(%lld..%lld)", (long long)value.as.range.start, (long long)value.as.range.end);
            p_buffer_cstr(b, number); break;
    }
}

static void p_write(const char *data, size_t length) {
    size_t characters = 0;
    for (size_t i = 0; i < length; i++) if (((unsigned char)data[i] & 0xc0) != 0x80) characters++;
    if (p_output_chars + characters > P_MAX_OUTPUT) p_fail("PE4003", "native output limit exceeded");
    p_output_chars += characters;
    if (p_output_callback) {
        if (length && p_output_callback(data, length, p_output_userdata)) p_fail("PE5002", "native output callback failed");
    } else if (length && fwrite(data, 1, length, stdout) != length) p_fail("PE5002", "native stdout write failed");
}

void p_format(PValue value, int newline) {
    PBuffer b = {0}; p_buffer_value(&b, value, 0); p_write(b.data, b.length);
    if (newline) p_write("\n", 1);
    p_free(b.data);
}

PValue p_assert(PValue condition, PValue message) {
    if (condition.type != P_BOOL || !condition.as.boolean) {
        if (message.type == P_STRING) {
            PString *s = message.as.string;
            char *text = p_alloc(s->length + 1); memcpy(text, s->data, s->length); text[s->length] = '\0';
            p_fail("PE4010", text);
        }
        p_fail("PE4010", "assertion failed");
    }
    return p_unit();
}

PValue p_throw(PValue message) {
    if (message.type != P_STRING) p_fail("PE4002", "क्षिप requires an अक्षरमाला message");
    p_fail("PE4020", message.as.string->data);
    return p_unit();
}

static int p_value_compare(PValue a, PValue b) {
    if (a.type != b.type || (a.type != P_INT && a.type != P_FLOAT)) p_fail("PE4002", "क्रमय() requires homogeneous numeric lists");
    if (a.type == P_INT) return a.as.integer < b.as.integer ? -1 : (a.as.integer > b.as.integer);
    return a.as.floating < b.as.floating ? -1 : (a.as.floating > b.as.floating);
}

PValue p_method(const char *name, int argc, PValue *args) {
    if (argc < 1) p_fail("PE4999", "method has no receiver");
    PValue receiver = args[0];
    if (receiver.type == P_LIST) {
        PList *list = receiver.as.list;
        if (!strcmp(name, "len") && argc == 1) return p_int((int64_t)list->length);
        if (!strcmp(name, "push") && argc == 2) {
            if (list->length == list->capacity) {
                list->capacity = list->capacity ? list->capacity * 2 : 4;
                list->items = p_realloc(list->items, list->capacity * sizeof(PValue));
            }
            list->items[list->length++] = args[1]; return p_unit();
        }
        if (!strcmp(name, "pop") && argc == 1) {
            if (!list->length) p_fail("PE4002", "निष्कासय() on an empty सूची");
            return list->items[--list->length];
        }
        if (!strcmp(name, "get") && argc == 2) return p_index_get(receiver, args[1]);
        if ((!strcmp(name, "contains") || !strcmp(name, "index_of")) && argc == 2) {
            for (size_t i = 0; i < list->length; i++) {
                if (p_equal(list->items[i], args[1])) return !strcmp(name, "contains") ? p_bool(1) : p_int((int64_t)i);
            }
            return !strcmp(name, "contains") ? p_bool(0) : p_int(-1);
        }
        if (!strcmp(name, "join") && argc == 2) {
            PString *separator = p_require_string(args[1], "join separator must be a string");
            PBuffer b = {0};
            for (size_t i = 0; i < list->length; i++) {
                if (list->items[i].type != P_STRING) p_fail("PE4002", "संयोजय() requires सूची<अक्षरमाला>");
                if (i) p_buffer_add(&b, separator->data, separator->length);
                PString *item = list->items[i].as.string; p_buffer_add(&b, item->data, item->length);
            }
PValue result = p_string(b.data ? b.data : "", b.length); p_free(b.data); return result;
        }
        if (!strcmp(name, "sort") && argc == 1) {
            for (size_t i = 1; i < list->length; i++) {
                PValue item = list->items[i]; size_t j = i;
                while (j && p_value_compare(item, list->items[j - 1]) < 0) { list->items[j] = list->items[j - 1]; j--; }
                list->items[j] = item;
            }
            return p_unit();
        }
        if (!strcmp(name, "reverse") && argc == 1) {
            for (size_t i = 0; i < list->length / 2; i++) {
                PValue item = list->items[i]; list->items[i] = list->items[list->length - 1 - i]; list->items[list->length - 1 - i] = item;
            }
            return p_unit();
        }
    }
    if (receiver.type == P_STRING) {
        PString *s = receiver.as.string;
        if (!strcmp(name, "len") && argc == 1) return p_int((int64_t)p_utf8_length(s));
        if ((!strcmp(name, "contains") || !strcmp(name, "starts_with") || !strcmp(name, "ends_with")) && argc == 2) {
            PString *part = p_require_string(args[1], "string argument required");
            int found = 0;
            if (!strcmp(name, "contains")) {
                if (!part->length) found = 1;
                else for (size_t i = 0; i + part->length <= s->length; i++) if (!memcmp(s->data + i, part->data, part->length)) { found = 1; break; }
            } else if (!strcmp(name, "starts_with")) found = part->length <= s->length && !memcmp(s->data, part->data, part->length);
            else found = part->length <= s->length && !memcmp(s->data + s->length - part->length, part->data, part->length);
            return p_bool(found);
        }
        if (!strcmp(name, "substring") && argc == 3) {
            int64_t start = p_require_int(args[1], "substring start"), end = p_require_int(args[2], "substring end");
            if (start < 0 || end < start || (uint64_t)end > p_utf8_length(s)) p_fail("PE4002", "substring bounds invalid");
            size_t a = p_utf8_offset(s, start), b = p_utf8_offset(s, end); return p_string(s->data + a, b - a);
        }
    }
    p_fail("PE4002", "method is not implemented by the native backend for this receiver");
    return p_unit();
}

PValue p_native(const char *name, int argc, PValue *args) {
    if (!strcmp(name, "print") && argc == 1) { p_format(args[0], 1); return p_unit(); }
    if (!strcmp(name, "str") && argc == 1) {
        PBuffer b = {0}; p_buffer_value(&b, args[0], 0); PValue result = p_string(b.data ? b.data : "", b.length); p_free(b.data); return result;
    }
    if (!strcmp(name, "len") && argc == 1) return p_len(args[0]);
    p_fail("PE4002", "native function is not implemented by the AOT backend");
    return p_unit();
}

void p_runtime_init(int64_t max_steps) {
    p_runtime_cleanup();
    p_steps = 0;
    p_call_depth = 0;
    p_output_chars = 0;
    p_error_text[0] = '\0';
    p_max_steps = max_steps > 0 ? max_steps : 2000000;
}
