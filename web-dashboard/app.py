from flask import Flask, jsonify, render_template, request
import os
import signal
import time
import socket
import platform

app = Flask(__name__)

# =========================================================
# CONFIGURATION
# =========================================================

CPU_ALERT_THRESHOLD = 80.0

previous_system_cpu = None
previous_process_cpu = {}

ACTIVITY_LOG_PATHS = [
    "/home/vboxuser/project-os/process_activity.log",
    "/home/vboxuser/process_activity.log"
]


# =========================================================
# CPU MONITOR
# =========================================================

def read_system_cpu():
    try:
        with open("/proc/stat", "r") as f:
            line = f.readline()

        parts = line.split()

        if not parts or parts[0] != "cpu":
            return 0, 0

        values = list(map(int, parts[1:]))

        total = sum(values)
        idle = values[3]

        return total, idle

    except Exception:
        return 0, 0


def calculate_system_cpu():
    global previous_system_cpu

    current_total, current_idle = read_system_cpu()

    if previous_system_cpu is None:
        previous_system_cpu = (
            current_total,
            current_idle
        )

        return 0.0

    old_total, old_idle = previous_system_cpu

    total_diff = current_total - old_total
    idle_diff = current_idle - old_idle

    previous_system_cpu = (
        current_total,
        current_idle
    )

    if total_diff <= 0:
        return 0.0

    usage = (
        (1 - idle_diff / total_diff)
        * 100
    )

    return round(usage, 1)


# =========================================================
# PROCESS MONITOR
# =========================================================

def get_processes():

    global previous_process_cpu

    processes = []
    current_process_cpu = {}

    clock_tick = os.sysconf(
        os.sysconf_names["SC_CLK_TCK"]
    )

    current_time = time.time()

    for pid_name in os.listdir("/proc"):

        if not pid_name.isdigit():
            continue

        try:

            pid = int(pid_name)

            # -------------------------------------------------
            # PROCESS STATUS
            # -------------------------------------------------

            with open(
                f"/proc/{pid}/status",
                "r"
            ) as f:
                status = f.read()

            name = "Unknown"
            state = "Unknown"
            ram = 0

            for line in status.splitlines():

                if line.startswith("Name:"):
                    name = line.split(
                        ":", 1
                    )[1].strip()

                elif line.startswith("State:"):
                    state = line.split(
                        ":", 1
                    )[1].strip()

                elif line.startswith("VmRSS:"):

                    try:
                        ram = int(
                            line.split()[1]
                        )
                    except ValueError:
                        ram = 0

            # -------------------------------------------------
            # PROCESS CPU
            # -------------------------------------------------

            with open(
                f"/proc/{pid}/stat",
                "r"
            ) as f:
                stat = f.read()

            close_paren = stat.rfind(")")

            if close_paren == -1:
                continue

            after_name = (
                stat[
                    close_paren + 2:
                ].split()
            )

            utime = int(after_name[11])
            stime = int(after_name[12])

            process_time = (
                utime + stime
            )

            current_process_cpu[pid] = (
                process_time,
                current_time
            )

            cpu_percent = 0.0

            if pid in previous_process_cpu:

                old_process_time, old_time = (
                    previous_process_cpu[pid]
                )

                process_diff = (
                    process_time
                    - old_process_time
                )

                time_diff = (
                    current_time
                    - old_time
                )

                if time_diff > 0:

                    cpu_percent = (
                        process_diff
                        /
                        (
                            time_diff
                            * clock_tick
                        )
                    ) * 100

                    cpu_percent *= (
                        os.cpu_count() or 1
                    )

            processes.append({
                "pid": pid,
                "name": name,
                "state": state,
                "ram": ram,
                "cpu": round(
                    cpu_percent,
                    1
                )
            })

        except (
            FileNotFoundError,
            PermissionError,
            ValueError,
            IndexError
        ):
            continue

    previous_process_cpu = (
        current_process_cpu
    )

    processes.sort(
        key=lambda x: x["cpu"],
        reverse=True
    )

    return processes


# =========================================================
# MEMORY
# =========================================================

def get_memory():

    total = 0
    available = 0

    try:

        with open(
            "/proc/meminfo",
            "r"
        ) as f:

            for line in f:

                if line.startswith(
                    "MemTotal:"
                ):

                    total = int(
                        line.split()[1]
                    )

                elif line.startswith(
                    "MemAvailable:"
                ):

                    available = int(
                        line.split()[1]
                    )

    except Exception:
        pass

    used = total - available

    percent = 0

    if total > 0:

        percent = (
            used / total
        ) * 100

    return {
        "total": total,
        "used": used,
        "available": available,
        "percent": round(
            percent,
            1
        )
    }


# =========================================================
# UPTIME
# =========================================================

def get_uptime():

    try:

        with open(
            "/proc/uptime",
            "r"
        ) as f:

            seconds = float(
                f.read().split()[0]
            )

        days = int(
            seconds // 86400
        )

        hours = int(
            (seconds % 86400) // 3600
        )

        minutes = int(
            (seconds % 3600) // 60
        )

        return f"{days}d {hours}h {minutes}m"

    except Exception:

        return "Unknown"


# =========================================================
# PROCESS DETAIL
# =========================================================

def get_process_detail(pid):

    try:

        if not os.path.isdir(
            f"/proc/{pid}"
        ):
            return None

        name = "Unknown"
        state = "Unknown"
        ram = 0
        threads = 0
        ppid = 0

        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        with open(
            f"/proc/{pid}/status",
            "r"
        ) as f:

            status = f.read()

        for line in status.splitlines():

            if line.startswith("Name:"):

                name = line.split(
                    ":",
                    1
                )[1].strip()

            elif line.startswith("State:"):

                state = line.split(
                    ":",
                    1
                )[1].strip()

            elif line.startswith("VmRSS:"):

                try:

                    ram = int(
                        line.split()[1]
                    )

                except ValueError:
                    ram = 0

            elif line.startswith("Threads:"):

                try:

                    threads = int(
                        line.split()[1]
                    )

                except ValueError:
                    threads = 0

            elif line.startswith("PPid:"):

                try:

                    ppid = int(
                        line.split()[1]
                    )

                except ValueError:
                    ppid = 0

        # -------------------------------------------------
        # CMDLINE
        # -------------------------------------------------

        try:

            with open(
                f"/proc/{pid}/cmdline",
                "r"
            ) as f:

                raw_cmdline = f.read()

            command = raw_cmdline.replace(
                "\x00",
                " "
            ).strip()

        except Exception:

            command = name

        # -------------------------------------------------
        # EXE
        # -------------------------------------------------

        try:

            executable = os.readlink(
                f"/proc/{pid}/exe"
            )

        except Exception:

            executable = "Unavailable"

        return {
            "pid": pid,
            "name": name,
            "state": state,
            "ram": ram,
            "threads": threads,
            "ppid": ppid,
            "command": command,
            "executable": executable
        }

    except (
        FileNotFoundError,
        PermissionError
    ):

        return None


# =========================================================
# ACTIVITY LOG
# =========================================================

def get_activity_log():

    for path in ACTIVITY_LOG_PATHS:

        if os.path.exists(path):

            try:

                with open(
                    path,
                    "r",
                    errors="replace"
                ) as f:

                    lines = f.readlines()

                lines.reverse()

                return [
                    line.rstrip()
                    for line in lines[:200]
                ]

            except Exception:

                continue

    return []


# =========================================================
# SYSTEM INFORMATION
# =========================================================

def get_system_information():

    memory = get_memory()

    try:

        hostname = socket.gethostname()

    except Exception:

        hostname = "Unknown"

    try:

        kernel = platform.release()

    except Exception:

        kernel = "Unknown"

    try:

        architecture = platform.machine()

    except Exception:

        architecture = "Unknown"

    return {
        "hostname": hostname,
        "kernel": kernel,
        "architecture": architecture,
        "cpu_cores": os.cpu_count() or 1,
        "cpu_usage": calculate_system_cpu(),
        "memory": memory,
        "uptime": get_uptime()
    }


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# =========================================================
# DASHBOARD API
# =========================================================

@app.route("/api/dashboard")
def dashboard():

    processes = get_processes()

    cpu = calculate_system_cpu()

    memory = get_memory()

    uptime = get_uptime()

    return jsonify({

        "system": {

            "cpu": cpu,

            "memory": memory,

            "processes": len(
                processes
            ),

            "uptime": uptime,

            "cores": os.cpu_count() or 1
        },

        "processes": processes
    })


# =========================================================
# PROCESSES
# =========================================================

@app.route("/api/processes")
def processes_api():

    return jsonify(
        get_processes()
    )


# =========================================================
# PROCESS DETAIL
# =========================================================

@app.route(
    "/api/process/<int:pid>"
)
def process_detail(pid):

    detail = get_process_detail(
        pid
    )

    if detail is None:

        return jsonify({
            "error":
            "Process tidak ditemukan"
        }), 404

    return jsonify(detail)


# =========================================================
# TERMINATE PROCESS
# =========================================================

@app.route(
    "/api/terminate",
    methods=["POST"]
)
def terminate_process():

    data = request.get_json(
        silent=True
    ) or {}

    try:

        pid = int(
            data.get("pid")
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({
            "success": False,
            "message":
            "PID tidak valid"
        }), 400

    # Jangan izinkan terminate PID 1
    if pid <= 1:

        return jsonify({
            "success": False,
            "message":
            "PID ini tidak boleh dihentikan"
        }), 400

    try:

        os.kill(
            pid,
            signal.SIGTERM
        )

        return jsonify({
            "success": True,
            "message":
            f"SIGTERM dikirim ke PID {pid}"
        })

    except ProcessLookupError:

        return jsonify({
            "success": False,
            "message":
            "Process sudah tidak ada"
        }), 404

    except PermissionError:

        return jsonify({
            "success": False,
            "message":
            "Permission ditolak"
        }), 403

    except Exception as e:

        return jsonify({
            "success": False,
            "message":
            str(e)
        }), 500


# =========================================================
# ALERTS
# =========================================================

@app.route("/api/alerts")
def alerts():

    processes = get_processes()

    alert_processes = [

        process

        for process in processes

        if process["cpu"]
        >= CPU_ALERT_THRESHOLD
    ]

    return jsonify({

        "threshold":
        CPU_ALERT_THRESHOLD,

        "count":
        len(alert_processes),

        "processes":
        alert_processes
    })


# =========================================================
# ACTIVITY
# =========================================================

@app.route("/api/activity")
def activity():

    return jsonify({
        "activities":
        get_activity_log()
    })


# =========================================================
# SYSTEM
# =========================================================

@app.route("/api/system")
def system():

    return jsonify(
        get_system_information()
    )


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
