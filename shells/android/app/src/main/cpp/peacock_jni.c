#include "program.h"
#include <jni.h>
#include <stdlib.h>
#include <string.h>

#define J_OUTPUT_LIMIT (4 * 1024 * 1024 + 4096)

typedef struct { char *data; size_t length, capacity; int failed; } JBuffer;

static int append_bytes(JBuffer *buffer, const char *data, size_t length) {
    if (buffer->failed || length > J_OUTPUT_LIMIT - buffer->length) {
        buffer->failed = 1;
        return 1;
    }
    size_t needed = buffer->length + length;
    if (needed > buffer->capacity) {
        size_t capacity = buffer->capacity ? buffer->capacity : 4096;
        while (capacity < needed) capacity *= 2;
        char *resized = (char *)realloc(buffer->data, capacity);
        if (!resized) { buffer->failed = 1; return 1; }
        buffer->data = resized;
        buffer->capacity = capacity;
    }
    if (length) memcpy(buffer->data + buffer->length, data, length);
    buffer->length = needed;
    return 0;
}

static int collect_output(const char *data, size_t length, void *userdata) {
    return append_bytes((JBuffer *)userdata, data, length);
}

JNIEXPORT jbyteArray JNICALL Java_org_peacock_shell_MainActivity_runPeacock(
    JNIEnv *environment, jobject activity
) {
    (void)activity;
    JBuffer buffer = {0};
    const char *error = NULL;
    int status = peacock_run(2000000, collect_output, &buffer, &error);
    if (status && error) {
        append_bytes(&buffer, "\n", 1);
        append_bytes(&buffer, error, strlen(error));
    }
    if (buffer.failed) {
        free(buffer.data);
        buffer.data = NULL;
        buffer.length = buffer.capacity = 0;
        buffer.failed = 0;
        const char message[] = "PE5002: Android output buffer failed";
        append_bytes(&buffer, message, sizeof(message) - 1);
    }
    jbyteArray result = (*environment)->NewByteArray(environment, (jsize)buffer.length);
    if (result && buffer.length) {
        (*environment)->SetByteArrayRegion(environment, result, 0, (jsize)buffer.length, (const jbyte *)buffer.data);
    }
    free(buffer.data);
    return result;
}
