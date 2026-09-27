#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

unsigned long get_process_cpu(int pid) {

    char path[100];
    unsigned long utime;
    unsigned long stime;

    snprintf(path, sizeof(path), "/proc/%d/stat", pid);

    FILE *file = fopen(path, "r");

    if (file == NULL) {
        return 0;
    }

    fscanf(file,
           "%*d %*s %*c %*d %*d %*d %*d %*d %*d %*d %*d %*d %*d %lu %lu",
           &utime, &stime);

    fclose(file);

    return utime + stime;
}

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

int main(int argc, char *argv[]) {

    if (argc != 2) {
        printf("Cara pakai: ./cpu <PID>\n");
        return 1;
    }

    int pid = atoi(argv[1]);

    unsigned long process1;
    unsigned long process2;

    unsigned long system1;
    unsigned long system2;

    process1 = get_process_cpu(pid);
    system1 = get_total_cpu();

    sleep(1);

    process2 = get_process_cpu(pid);
    system2 = get_total_cpu();

    unsigned long process_diff = process2 - process1;
    unsigned long system_diff = system2 - system1;

    long cpu_count = sysconf(_SC_NPROCESSORS_ONLN);

    double cpu_usage = 0;

    if (system_diff > 0) {
    	cpu_usage = ((double)process_diff * cpu_count * 100) / system_diff;
}
    printf("PID        : %d\n", pid);
    printf("CPU awal   : %lu\n", process1);
    printf("CPU akhir  : %lu\n", process2);
    printf("CPU count  : %ld\n", cpu_count);
    printf("CPU usage  : %.2f%%\n", cpu_usage);
    return 0;
}
