#ifndef PEACOCK_NATIVE_RUNTIME_H
#define PEACOCK_NATIVE_RUNTIME_H

#include <stddef.h>
#include <stdint.h>
#include <setjmp.h>

#define P_MAX_STACK 1024
#define P_MAX_CALL_DEPTH 128
#define P_MAX_OUTPUT (1024 * 1024)

typedef enum {
    P_UNINIT, P_UNIT, P_INT, P_FLOAT, P_BOOL, P_STRING, P_LIST, P_RANGE
} PType;

typedef struct PValue PValue;
typedef struct { size_t length; char *data; } PString;
typedef struct { size_t length, capacity; PValue *items; } PList;

struct PValue {
    PType type;
    union {
        int64_t integer;
        double floating;
        int boolean;
        PString *string;
        PList *list;
        struct { int64_t start, end; } range;
    } as;
};

typedef struct { PValue items[P_MAX_STACK]; int length; } PStack;

extern int64_t p_steps;
extern int64_t p_max_steps;
extern int p_call_depth;
extern size_t p_output_chars;

/* Optional single-entry embedding boundary used by native host shells. */
typedef int (*POutputCallback)(const char *data, size_t length, void *userdata);
extern jmp_buf p_error_target;
extern int p_error_target_active;
void p_set_output_callback(POutputCallback callback, void *userdata);
const char *p_last_error(void);

void p_tick(void);
void p_enter(void);
void p_leave(void);
void p_fail(const char *code, const char *message) __attribute__((noreturn));
void *p_alloc(size_t size);
void *p_realloc(void *pointer, size_t size);
void p_free(void *pointer);
void p_runtime_cleanup(void);
size_t p_runtime_allocation_count(void);

PValue p_unit(void);
PValue p_int(int64_t value);
PValue p_float(double value);
PValue p_bool(int value);
PValue p_string(const char *data, size_t length);
PValue p_cstring(const char *data);
PValue p_list(size_t length, PValue *items);
PValue p_range(int64_t start, int64_t end);

void p_push(PStack *stack, PValue value);
PValue p_pop(PStack *stack);
PValue p_read_slot(PValue value);
int64_t p_require_int(PValue value, const char *what);
double p_require_float(PValue value, const char *what);
PString *p_require_string(PValue value, const char *what);
PList *p_require_list(PValue value, const char *what);

PValue p_binary(const char *op, PValue left, PValue right);
PValue p_unary(const char *op, PValue value);
PValue p_index_get(PValue base, PValue index);
void p_index_set(PValue base, PValue index, PValue value);
PValue p_len(PValue value);
PValue p_assert(PValue condition, PValue message);
PValue p_throw(PValue message);

PValue p_native(const char *name, int argc, PValue *args);
PValue p_method(const char *name, int argc, PValue *args);
void p_format(PValue value, int newline);
void p_runtime_init(int64_t max_steps);

#endif
