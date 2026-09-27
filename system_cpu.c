#include <stdio.h>
#include <unistd.h>

unsigned long get_total_cpu() {

    FILE *file;
    char line[256];

    unsigned long cpu[10];
    unsigned long total = 0;

    file = fopen("/proc/stat", "r");

    if (file == NULL) {
        return 0;
    }

    fgets(line, sizeof(line), file);

    sscanf(line,
           "cpu %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu",
           &cpu[0], &cpu[1], &cpu[2], &cpu[3],
           &cpu[4], &cpu[5], &cpu[6], &cpu[7],
           &cpu[8], &cpu[9]);

    fclose(file);

    for (int i = 0; i < 10; i++) {
        total += cpu[i];
    }

    return total;
}

int main() {

    unsigned long cpu1;
    unsigned long cpu2;

    cpu1 = get_total_cpu();

    sleep(1);

    cpu2 = get_total_cpu();

    printf("CPU awal  : %lu\n", cpu1);
    printf("CPU akhir : %lu\n", cpu2);
    printf("Selisih   : %lu\n", cpu2 - cpu1);

    return 0;
}
