#include <stdio.h>
#include <stdlib.h>
#include <dirent.h>
#include <ctype.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>

#define MAX_PID 32768
#define MAX_PROCESS 32768
#define TOP_PROCESS 20
#define MAX_HISTORY 32768

#define CPU_ALERT_THRESHOLD 80.0

#define HISTORY_FILE "process_history.dat"
#define ACTIVITY_LOG "process_activity.log"

typedef struct {
    int pid;
    char name[256];
    char state[64];
    unsigned long ram;
    double cpu;
} Process;

typedef struct {
    int pid;
    char name[256];
    double max_cpu;
    unsigned long max_ram;
} History;

/* =========================================
   GLOBAL MEMORY
   ========================================= */

Process processes[MAX_PROCESS];
Process previous_processes[MAX_PROCESS];

History history[MAX_HISTORY];

int previous_count = 0;
int history_count = 0;
int first_scan = 1;


/* =========================================
   PROCESS CPU
   ========================================= */

double get_process_cpu(int pid, unsigned long *total_time)
{
    char path[256];
    char line[1024];

    unsigned long utime = 0;
    unsigned long stime = 0;

    snprintf(path, sizeof(path), "/proc/%d/stat", pid);

    FILE *fp = fopen(path, "r");

    if (!fp)
        return 0.0;

    if (!fgets(line, sizeof(line), fp)) {
        fclose(fp);
        return 0.0;
    }

    fclose(fp);

    char *end_name = strrchr(line, ')');

    if (!end_name)
        return 0.0;

    char *ptr = end_name + 2;

    char state;

    int result = sscanf(
        ptr,
        "%c "
        "%*d %*d %*d %*d %*d %*d "
        "%*u %*u %*u %*u "
        "%lu %lu",
        &state,
        &utime,
        &stime
    );

    if (result != 3)
        return 0.0;

    *total_time = utime + stime;

    return (double)(utime + stime);
}


/* =========================================
   SYSTEM CPU
   ========================================= */

unsigned long long get_total_cpu()
{
    FILE *fp = fopen("/proc/stat", "r");

    if (!fp)
        return 0;

    char line[512];

    if (!fgets(line, sizeof(line), fp)) {
        fclose(fp);
        return 0;
    }

    fclose(fp);

    unsigned long long user, nice, system, idle;
    unsigned long long iowait, irq, softirq, steal;

    sscanf(
        line,
        "cpu %llu %llu %llu %llu %llu %llu %llu %llu",
        &user,
        &nice,
        &system,
        &idle,
        &iowait,
        &irq,
        &softirq,
        &steal
    );

    return user + nice + system + idle +
           iowait + irq + softirq + steal;
}


unsigned long long get_cpu_idle()
{
    FILE *fp = fopen("/proc/stat", "r");

    if (!fp)
        return 0;

    char line[512];

    if (!fgets(line, sizeof(line), fp)) {
        fclose(fp);
        return 0;
    }

    fclose(fp);

    unsigned long long user, nice, system, idle;
    unsigned long long iowait, irq, softirq, steal;

    sscanf(
        line,
        "cpu %llu %llu %llu %llu %llu %llu %llu %llu",
        &user,
        &nice,
        &system,
        &idle,
        &iowait,
        &irq,
        &softirq,
        &steal
    );

    return idle + iowait;
}


/* =========================================
   MEMORY
   ========================================= */

unsigned long get_memory_total()
{
    FILE *fp = fopen("/proc/meminfo", "r");

    if (!fp)
        return 0;

    char line[256];
    unsigned long total = 0;

    while (fgets(line, sizeof(line), fp)) {

        if (sscanf(line, "MemTotal: %lu kB", &total) == 1)
            break;
    }

    fclose(fp);

    return total;
}


unsigned long get_memory_available()
{
    FILE *fp = fopen("/proc/meminfo", "r");

    if (!fp)
        return 0;

    char line[256];
    unsigned long available = 0;

    while (fgets(line, sizeof(line), fp)) {

        if (sscanf(line, "MemAvailable: %lu kB", &available) == 1)
            break;
    }

    fclose(fp);

    return available;
}


/* =========================================
   UPTIME
   ========================================= */

double get_uptime()
{
    FILE *fp = fopen("/proc/uptime", "r");

    if (!fp)
        return 0;

    double uptime = 0;

    fscanf(fp, "%lf", &uptime);

    fclose(fp);

    return uptime;
}


void print_uptime()
{
    double seconds = get_uptime();

    int days = (int)(seconds / 86400);

    seconds -= days * 86400;

    int hours = (int)(seconds / 3600);

    seconds -= hours * 3600;

    int minutes = (int)(seconds / 60);

    printf(
        "Uptime     : %d hari %d jam %d menit\n",
        days,
        hours,
        minutes
    );
}


/* =========================================
   PROCESS INFORMATION
   ========================================= */

int get_process_info(int pid, Process *p)
{
    char path[256];
    char line[512];

    snprintf(
        path,
        sizeof(path),
        "/proc/%d/status",
        pid
    );

    FILE *fp = fopen(path, "r");

    if (!fp)
        return 0;

    p->pid = pid;

    p->name[0] = '\0';
    p->state[0] = '\0';

    p->ram = 0;
    p->cpu = 0;

    while (fgets(line, sizeof(line), fp)) {

        if (strncmp(line, "Name:", 5) == 0) {

            sscanf(
                line,
                "Name:\t%255[^\n]",
                p->name
            );
        }

        else if (strncmp(line, "State:", 6) == 0) {

            sscanf(
                line,
                "State:\t%63[^\n]",
                p->state
            );
        }

        else if (strncmp(line, "VmRSS:", 6) == 0) {

            sscanf(
                line,
                "VmRSS:\t%lu",
                &p->ram
            );
        }
    }

    fclose(fp);

    unsigned long cpu_time = 0;

    p->cpu = get_process_cpu(
        pid,
        &cpu_time
    );

    return 1;
}


/* =========================================
   HISTORY
   ========================================= */

void update_history(Process *p)
{
    int index = -1;

    for (int i = 0; i < history_count; i++) {

        if (history[i].pid == p->pid) {

            index = i;
            break;
        }
    }

    if (index == -1) {

        if (history_count >= MAX_HISTORY)
            return;

        index = history_count;

        history[index].pid = p->pid;

        strcpy(
            history[index].name,
            p->name
        );

        history[index].max_cpu = p->cpu;
        history[index].max_ram = p->ram;

        history_count++;
    }

    else {

        if (p->cpu > history[index].max_cpu)
            history[index].max_cpu = p->cpu;

        if (p->ram > history[index].max_ram)
            history[index].max_ram = p->ram;

        strcpy(
            history[index].name,
            p->name
        );
    }
}


void save_history()
{
    FILE *fp = fopen(
        HISTORY_FILE,
        "wb"
    );

    if (!fp)
        return;

    fwrite(
        &history_count,
        sizeof(int),
        1,
        fp
    );

    fwrite(
        history,
        sizeof(History),
        history_count,
        fp
    );

    fclose(fp);
}


void load_history()
{
    FILE *fp = fopen(
        HISTORY_FILE,
        "rb"
    );

    if (!fp)
        return;

    fread(
        &history_count,
        sizeof(int),
        1,
        fp
    );

    if (history_count > MAX_HISTORY)
        history_count = MAX_HISTORY;

    fread(
        history,
        sizeof(History),
        history_count,
        fp
    );

    fclose(fp);
}


/* =========================================
   ACTIVITY LOG
   ========================================= */

void write_activity_log(
    const char *action,
    Process *p
)
{
    FILE *fp = fopen(
        ACTIVITY_LOG,
        "a"
    );

    if (!fp)
        return;

    time_t now = time(NULL);

    struct tm *t = localtime(&now);

    fprintf(
        fp,
        "[%04d-%02d-%02d %02d:%02d:%02d] "
        "%-10s PID=%d NAME=%s CPU=%.2f%% RAM=%lu KB\n",

        t->tm_year + 1900,
        t->tm_mon + 1,
        t->tm_mday,

        t->tm_hour,
        t->tm_min,
        t->tm_sec,

        action,

        p->pid,
        p->name,
        p->cpu,
        p->ram
    );

    fclose(fp);
}


/* =========================================
   ACTIVITY DETECTION
   ========================================= */

int find_previous_process(int pid)
{
    for (int i = 0; i < previous_count; i++) {

        if (previous_processes[i].pid == pid)
            return i;
    }

    return -1;
}


int find_current_process(
    int count,
    int pid
)
{
    for (int i = 0; i < count; i++) {

        if (processes[i].pid == pid)
            return i;
    }

    return -1;
}


void detect_activity(int count)
{
    if (first_scan) {

        previous_count = 0;

        for (int i = 0; i < count; i++) {

            previous_processes[
                previous_count++
            ] = processes[i];
        }

        first_scan = 0;

        return;
    }


    /* Proses baru */

    for (int i = 0; i < count; i++) {

        if (
            find_previous_process(
                processes[i].pid
            ) == -1
        ) {

            write_activity_log(
                "START",
                &processes[i]
            );
        }
    }


    /* Proses selesai */

    for (int i = 0; i < previous_count; i++) {

        if (
            find_current_process(
                count,
                previous_processes[i].pid
            ) == -1
        ) {

            write_activity_log(
                "EXIT",
                &previous_processes[i]
            );
        }
    }


    /* Simpan kondisi sekarang */

    previous_count = 0;

    for (int i = 0; i < count; i++) {

        previous_processes[
            previous_count++
        ] = processes[i];
    }
}


/* =========================================
   SCAN PROCESS
   ========================================= */

int scan_processes()
{
    DIR *dir = opendir("/proc");

    if (!dir)
        return 0;

    struct dirent *entry;

    int count = 0;

    while (
        (entry = readdir(dir)) != NULL
    ) {

        if (!isdigit(entry->d_name[0]))
            continue;

        int pid = atoi(entry->d_name);

        if (
            pid <= 0 ||
            pid >= MAX_PID
        )
            continue;

        if (count >= MAX_PROCESS)
            break;

        Process p;

        if (get_process_info(pid, &p)) {

            processes[count] = p;

            update_history(
                &processes[count]
            );

            count++;
        }
    }

    closedir(dir);

    detect_activity(count);

    save_history();

    return count;
}


/* =========================================
   SORT CPU
   ========================================= */

int compare_cpu(
    const void *a,
    const void *b
)
{
    const Process *p1 =
        (const Process *)a;

    const Process *p2 =
        (const Process *)b;

    if (p1->cpu < p2->cpu)
        return 1;

    if (p1->cpu > p2->cpu)
        return -1;

    return 0;
}


/* =========================================
   SHOW PROCESS
   ========================================= */

void show_processes()
{
    int count = scan_processes();

    if (count <= 0) {

        printf(
            "Tidak ada proses ditemukan.\n"
        );

        return;
    }

    qsort(
        processes,
        count,
        sizeof(Process),
        compare_cpu
    );

    printf("\n");

    printf(
        "===============================================================\n"
    );

    printf(
        "                     PROCESS LIST\n"
    );

    printf(
        "===============================================================\n"
    );

    printf(
        "%-3s %-7s %-20s %-15s %-10s %-10s\n",
        "",
        "PID",
        "NAME",
        "STATE",
        "RAM(KB)",
        "CPU%"
    );

    printf(
        "---------------------------------------------------------------\n"
    );

    int limit =
        count < TOP_PROCESS
        ? count
        : TOP_PROCESS;

    int alert_count = 0;

    for (int i = 0; i < limit; i++) {

        if (
            processes[i].cpu >=
            CPU_ALERT_THRESHOLD
        ) {

            printf(
                "!! %-7d %-20s %-15s %-10lu %-10.2f\n",

                processes[i].pid,
                processes[i].name,
                processes[i].state,
                processes[i].ram,
                processes[i].cpu
            );

            alert_count++;
        }

        else {

            printf(
                "   %-7d %-20s %-15s %-10lu %-10.2f\n",

                processes[i].pid,
                processes[i].name,
                processes[i].state,
                processes[i].ram,
                processes[i].cpu
            );
        }
    }

    printf(
        "===============================================================\n"
    );

    if (alert_count > 0) {

        printf("\n");
        printf("!!! PROCESS ALERT !!!\n");

        printf(
            "%d proses menggunakan CPU >= %.0f%%\n",
            alert_count,
            CPU_ALERT_THRESHOLD
        );
    }

    printf(
        "\nTotal proses terdeteksi : %d\n",
        count
    );
}


/* =========================================
   SEARCH
   ========================================= */

void search_process()
{
    char keyword[256];

    printf(
        "\nMasukkan nama proses: "
    );

    scanf(
        "%255s",
        keyword
    );

    int count = scan_processes();

    int found = 0;

    printf("\nHasil pencarian:\n\n");

    printf(
        "%-7s %-25s %-15s %-10s %-10s\n",
        "PID",
        "NAME",
        "STATE",
        "RAM(KB)",
        "CPU%"
    );

    printf(
        "-------------------------------------------------------------\n"
    );

    for (int i = 0; i < count; i++) {

        if (
            strstr(
                processes[i].name,
                keyword
            ) != NULL
        ) {

            printf(
                "%-7d %-25s %-15s %-10lu %-10.2f\n",

                processes[i].pid,
                processes[i].name,
                processes[i].state,
                processes[i].ram,
                processes[i].cpu
            );

            found++;
        }
    }

    if (!found)
        printf(
            "Proses tidak ditemukan.\n"
        );
}


/* =========================================
   DETAIL
   ========================================= */

void process_detail()
{
    int pid;

    printf(
        "\nMasukkan PID: "
    );

    scanf(
        "%d",
        &pid
    );

    Process p;

    if (!get_process_info(pid, &p)) {

        printf(
            "PID tidak ditemukan.\n"
        );

        return;
    }

    printf("\n");

    printf(
        "=====================================\n"
    );

    printf(
        "          PROCESS DETAIL\n"
    );

    printf(
        "=====================================\n"
    );

    printf(
        "PID       : %d\n",
        p.pid
    );

    printf(
        "Name      : %s\n",
        p.name
    );

    printf(
        "State     : %s\n",
        p.state
    );

    printf(
        "RAM       : %lu KB\n",
        p.ram
    );

    printf(
        "CPU       : %.2f%%\n",
        p.cpu
    );

    for (int i = 0; i < history_count; i++) {

        if (history[i].pid == pid) {

            printf(
                "\nHistorical Maximum:\n"
            );

            printf(
                "Max CPU   : %.2f%%\n",
                history[i].max_cpu
            );

            printf(
                "Max RAM   : %lu KB\n",
                history[i].max_ram
            );

            break;
        }
    }

    printf(
        "=====================================\n"
    );
}


/* =========================================
   TERMINATE
   ========================================= */

void terminate_process()
{
    int pid;

    printf(
        "\nMasukkan PID yang ingin dihentikan: "
    );

    scanf(
        "%d",
        &pid
    );

    if (pid <= 1) {

        printf(
            "PID tersebut tidak boleh dihentikan.\n"
        );

        return;
    }

    if (kill(pid, 0) != 0) {

        printf(
            "Proses tidak ditemukan atau tidak memiliki izin.\n"
        );

        return;
    }

    Process p;

    if (!get_process_info(pid, &p)) {

        printf(
            "Informasi proses tidak dapat dibaca.\n"
        );

        return;
    }

    printf("\nProses ditemukan:\n");

    printf(
        "PID  : %d\n",
        p.pid
    );

    printf(
        "Name : %s\n",
        p.name
    );

    char confirm;

    printf(
        "\nYakin ingin terminate proses ini? (y/n): "
    );

    scanf(
        " %c",
        &confirm
    );

    if (
        confirm != 'y' &&
        confirm != 'Y'
    ) {

        printf(
            "Dibatalkan.\n"
        );

        return;
    }

    if (kill(pid, SIGTERM) == 0) {

        printf(
            "SIGTERM berhasil dikirim ke PID %d.\n",
            pid
        );

        write_activity_log(
            "TERMINATE",
            &p
        );
    }

    else {

        perror(
            "Gagal terminate"
        );
    }
}


/* =========================================
   SYSTEM INFO
   ========================================= */

void show_system_info()
{
    unsigned long total =
        get_memory_total();

    unsigned long available =
        get_memory_available();

    unsigned long used =
        total - available;

    printf("\n");

    printf(
        "=====================================\n"
    );

    printf(
        "          SYSTEM INFORMATION\n"
    );

    printf(
        "=====================================\n"
    );

    printf(
        "Jumlah CPU : %ld Core\n",
        sysconf(_SC_NPROCESSORS_ONLN)
    );

    printf(
        "RAM Total  : %lu MB\n",
        total / 1024
    );

    printf(
        "RAM Used   : %lu MB\n",
        used / 1024
    );

    printf(
        "RAM Free   : %lu MB\n",
        available / 1024
    );

    print_uptime();

    printf(
        "CPU Alert  : %.0f%%\n",
        CPU_ALERT_THRESHOLD
    );

    printf(
        "=====================================\n"
    );
}


/* =========================================
   HISTORY DISPLAY
   ========================================= */

void show_history()
{
    printf("\n");

    printf(
        "================================================\n"
    );

    printf(
        "               PROCESS HISTORY\n"
    );

    printf(
        "================================================\n"
    );

    if (history_count == 0) {

        printf(
            "Belum ada history.\n"
        );

        return;
    }

    printf(
        "%-7s %-25s %-12s %-12s\n",
        "PID",
        "NAME",
        "MAX CPU%",
        "MAX RAM(KB)"
    );

    printf(
        "------------------------------------------------\n"
    );

    for (int i = 0; i < history_count; i++) {

        printf(
            "%-7d %-25s %-12.2f %-12lu\n",

            history[i].pid,
            history[i].name,
            history[i].max_cpu,
            history[i].max_ram
        );
    }

    printf(
        "\nTotal history : %d proses\n",
        history_count
    );
}


/* =========================================
   ACTIVITY LOG DISPLAY
   ========================================= */

void show_activity_log()
{
    FILE *fp = fopen(
        ACTIVITY_LOG,
        "r"
    );

    if (!fp) {

        printf(
            "\nBelum ada aktivitas yang tercatat.\n"
        );

        return;
    }

    char line[512];

    printf("\n");

    printf(
        "===============================================================\n"
    );

    printf(
        "                    PROCESS ACTIVITY LOG\n"
    );

    printf(
        "===============================================================\n"
    );

    while (
        fgets(
            line,
            sizeof(line),
            fp
        )
    ) {

        printf(
            "%s",
            line
        );
    }

    printf(
        "===============================================================\n"
    );

    fclose(fp);
}


/* =========================================
   AUTO REFRESH
   ========================================= */

void auto_refresh()
{
    printf(
        "\nAuto refresh aktif.\n"
    );

    printf(
        "Tekan Ctrl+C untuk menghentikan refresh.\n"
    );

    while (1) {

        system("clear");

        printf(
            "===============================================================\n"
        );

        printf(
            "             LINUX PROCESS MANAGER - LIVE\n"
        );

        printf(
            "===============================================================\n"
        );

        show_processes();

        printf("\n");

        show_system_info();

        printf("\n");

        printf(
            "Activity logging : AKTIF\n"
        );

        printf(
            "CPU alert        : %.0f%%\n",
            CPU_ALERT_THRESHOLD
        );

        printf(
            "\nRefresh setiap 2 detik...\n"
        );

        sleep(2);
    }
}


/* =========================================
   MAIN
   ========================================= */

int main()
{
    load_history();

    int choice;

    while (1) {

        printf("\n");

        printf(
            "=========================================\n"
        );

        printf(
            "         LINUX PROCESS MANAGER v7.1\n"
        );

        printf(
            "=========================================\n"
        );

        printf(
            "CPU              : %ld Core\n",
            sysconf(_SC_NPROCESSORS_ONLN)
        );

        printf(
            "History Process  : %d\n",
            history_count
        );

        printf(
            "Alert Threshold  : %.0f%% CPU\n",
            CPU_ALERT_THRESHOLD
        );

        printf(
            "=========================================\n"
        );

        printf(
            "1. Lihat proses\n"
        );

        printf(
            "2. Cari proses\n"
        );

        printf(
            "3. Detail proses\n"
        );

        printf(
            "4. Terminate proses\n"
        );

        printf(
            "5. Auto refresh + system monitor\n"
        );

        printf(
            "6. System information\n"
        );

        printf(
            "7. Process history\n"
        );

        printf(
            "8. Process activity log\n"
        );

        printf(
            "0. Keluar\n"
        );

        printf(
            "=========================================\n"
        );

        printf(
            "Pilih menu: "
        );

        scanf(
            "%d",
            &choice
        );

        switch (choice) {

            case 1:
                show_processes();
                break;

            case 2:
                search_process();
                break;

            case 3:
                process_detail();
                break;

            case 4:
                terminate_process();
                break;

            case 5:
                auto_refresh();
                break;

            case 6:
                show_system_info();
                break;

            case 7:
                show_history();
                break;

            case 8:
                show_activity_log();
                break;

            case 0:

                printf(
                    "\nLinux Process Manager selesai.\n"
                );

                return 0;

            default:

                printf(
                    "Pilihan tidak tersedia.\n"
                );
        }
    }

    return 0;
}
