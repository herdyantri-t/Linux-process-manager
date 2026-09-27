#include <stdio.h>

int main() {
    FILE *file;
    char line[256];

    file = fopen("/proc/1/status", "r");

    if (file == NULL) {
        printf("Gagal membuka file\n");
        return 1;
    }

    while (fgets(line, sizeof(line), file)) {
        if (sscanf(line, "VmRSS: %s", line) == 1) {
            printf("RAM: %s kB\n", line);
            break;
        }
    }

    fclose(file);

    return 0;
}
