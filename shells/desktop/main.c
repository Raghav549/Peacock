#include "program.h"
#include <stdio.h>

static int write_output(const char *data, size_t length, void *userdata) {
    (void)userdata;
    return length && fwrite(data, 1, length, stdout) != length;
}

int main(void) {
    const char *error = NULL;
    int status = peacock_run(2000000, write_output, NULL, &error);
    if (status && error) fprintf(stderr, "%s\n", error);
    return status;
}
