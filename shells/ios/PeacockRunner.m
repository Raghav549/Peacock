#import "PeacockRunner.h"
#import "program.h"
#include <stdlib.h>
#include <string.h>

#define I_OUTPUT_LIMIT (4 * 1024 * 1024 + 4096)
typedef struct { char *data; size_t length, capacity; int failed; } IBuffer;

static int append_output(IBuffer *buffer, const char *data, size_t length) {
    if (buffer->failed || length > I_OUTPUT_LIMIT - buffer->length) {
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
    return append_output((IBuffer *)userdata, data, length);
}

@implementation PeacockRunner
+ (NSData *)runWithError:(NSError **)error {
    @synchronized(self) {
        IBuffer buffer = {0};
        const char *native_error = NULL;
        int status = peacock_run(2000000, collect_output, &buffer, &native_error);
        if (status && error && native_error) {
            NSString *message = [NSString stringWithUTF8String:native_error] ?: @"PEACOCK native fault";
            *error = [NSError errorWithDomain:@"org.peacock.native" code:status
                                     userInfo:@{NSLocalizedDescriptionKey: message}];
        }
        NSData *result = buffer.length ? [NSData dataWithBytes:buffer.data length:buffer.length] : [NSData data];
        free(buffer.data);
        return result;
    }
}
@end
