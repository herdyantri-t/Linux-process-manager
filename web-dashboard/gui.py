import tkinter as tk
from tkinter import ttk, messagebox
import os
import time
import signal
import platform
from collections import deque


# ============================================================
# CONFIGURATION
# ============================================================

REFRESH_INTERVAL = 2000
CPU_ALERT = 80.0
MAX_HISTORY = 40

BG = "#0b0f14"
PANEL = "#111820"
PANEL2 = "#151e28"
BORDER = "#263442"
TEXT = "#e6edf3"
MUTED = "#8b9aaa"
ACCENT = "#38bdf8"
GREEN = "#22c55e"
YELLOW = "#f59e0b"
RED = "#ef4444"


# ============================================================
# PROCESS DATA
# ============================================================

class ProcessManager:

    def __init__(self):
        self.previous_cpu = {}
        self.previous_total = None

    def read_processes(self):

        processes = []

        try:
            cpu_count = os.cpu_count() or 1

            # System CPU
            with open("/proc/stat", "r") as f:
                line = f.readline()

            parts = line.split()
            system_total = sum(int(x) for x in parts[1:])

            if self.previous_total is None:
                total_delta = 1
            else:
                total_delta = system_total - self.previous_total

            self.previous_total = system_total

            # Processes
            for pid in os.listdir("/proc"):

                if not pid.isdigit():
                    continue

                try:

                    status_path = f"/proc/{pid}/status"
                    stat_path = f"/proc/{pid}/stat"

                    name = pid
                    state = "?"

                    ram = 0

                    with open(status_path, "r") as f:

                        for line in f:

                            if line.startswith("Name:"):
                                name = line.split(":", 1)[1].strip()

                            elif line.startswith("State:"):
                                state = line.split(":", 1)[1].strip().split()[0]

                            elif line.startswith("VmRSS:"):
                                ram = int(line.split()[1])

                    with open(stat_path, "r") as f:
                        stat_line = f.read()

                    closing = stat_line.rfind(")")

                    if closing == -1:
                        continue

                    stat_data = stat_line[closing + 2:].split()

                    utime = int(stat_data[11])
                    stime = int(stat_data[12])

                    process_cpu = utime + stime

                    previous = self.previous_cpu.get(pid, process_cpu)

                    cpu_delta = process_cpu - previous

                    self.previous_cpu[pid] = process_cpu

                    if total_delta > 0:
                        cpu = (
                            cpu_delta /
                            total_delta *
                            100 *
                            cpu_count
                        )
                    else:
                        cpu = 0

                    processes.append({
                        "pid": int(pid),
                        "name": name,
                        "state": state,
                        "ram": ram,
                        "cpu": max(0, cpu)
                    })

                except (FileNotFoundError,
                        ProcessLookupError,
                        PermissionError,
                        ValueError,
                        IndexError):
                    continue

        except Exception:
            pass

        return processes

    def system_info(self):

        cpu = self.get_cpu_usage()

        memory = self.get_memory()

        uptime = self.get_uptime()

        return cpu, memory, uptime

    def get_cpu_usage(self):

        try:

            with open("/proc/stat", "r") as f:
                line = f.readline()

            values = list(map(int, line.split()[1:]))

            idle = values[3] + values[4]

            total = sum(values)

            if not hasattr(self, "last_idle"):
                self.last_idle = idle
                self.last_total = total
                return 0

            idle_delta = idle - self.last_idle
            total_delta = total - self.last_total

            self.last_idle = idle
            self.last_total = total

            if total_delta <= 0:
                return 0

            return (1 - idle_delta / total_delta) * 100

        except Exception:
            return 0

    def get_memory(self):

        total = 0
        available = 0

        try:

            with open("/proc/meminfo", "r") as f:

                for line in f:

                    if line.startswith("MemTotal:"):
                        total = int(line.split()[1])

                    elif line.startswith("MemAvailable:"):
                        available = int(line.split()[1])

            used = total - available

            return total, used, available

        except Exception:
            return 0, 0, 0

    def get_uptime(self):

        try:

            with open("/proc/uptime", "r") as f:
                seconds = int(float(f.read().split()[0]))

            days = seconds // 86400
            seconds %= 86400

            hours = seconds // 3600
            seconds %= 3600

            minutes = seconds // 60

            return f"{days}d {hours}h {minutes}m"

        except Exception:
            return "-"


# ============================================================
# MAIN APPLICATION
# ============================================================

class LinuxProcessManager:

    def __init__(self, root):

        self.root = root

        self.root.title("Linux Process Manager")
        self.root.geometry("1250x760")
        self.root.minsize(1050, 650)
        self.root.configure(bg=BG)

        self.manager = ProcessManager()

        self.processes = []

        self.cpu_history = deque(maxlen=MAX_HISTORY)
        self.ram_history = deque(maxlen=MAX_HISTORY)

        self.sort_column = "cpu"
        self.sort_reverse = True

        self.search_text = ""

        self.create_styles()
        self.create_interface()

        self.update_data()

    # ========================================================
    # STYLE
    # ========================================================

    def create_styles(self):

        style = ttk.Style()

        style.theme_use("clam")

        style.configure(
            "Treeview",
            background=PANEL,
            foreground=TEXT,
            fieldbackground=PANEL,
            borderwidth=0,
            rowheight=34,
            font=("Segoe UI", 10)
        )

        style.configure(
            "Treeview.Heading",
            background=PANEL2,
            foreground=MUTED,
            borderwidth=0,
            font=("Segoe UI", 9, "bold")
        )

        style.map(
            "Treeview",
            background=[
                ("selected", "#1d4ed8")
            ],
            foreground=[
                ("selected", "#ffffff")
            ]
        )

    # ========================================================
    # INTERFACE
    # ========================================================

    def create_interface(self):

        # HEADER
        header = tk.Frame(
            self.root,
            bg=BG,
            height=75
        )

        header.pack(
            fill="x",
            padx=25,
            pady=(20, 5)
        )

        title = tk.Label(
            header,
            text="LINUX PROCESS MANAGER",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 22, "bold")
        )

        title.pack(side="left")

        subtitle = tk.Label(
            header,
            text="  •  Debian System Monitor",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 10)
        )

        subtitle.pack(side="left", pady=(10, 0))

        self.status_label = tk.Label(
            header,
            text="● SYSTEM ONLINE",
            bg=BG,
            fg=GREEN,
            font=("Segoe UI", 10, "bold")
        )

        self.status_label.pack(
            side="right",
            pady=10
        )

        # CARDS
        cards = tk.Frame(
            self.root,
            bg=BG
        )

        cards.pack(
            fill="x",
            padx=25,
            pady=10
        )

        self.cpu_card = self.create_card(
            cards,
            "CPU USAGE",
            "0%",
            ACCENT
        )

        self.ram_card = self.create_card(
            cards,
            "MEMORY",
            "0%",
            GREEN
        )

        self.process_card = self.create_card(
            cards,
            "PROCESSES",
            "0",
            YELLOW
        )

        self.uptime_card = self.create_card(
            cards,
            "UPTIME",
            "-",
            "#a78bfa"
        )

        # CHART + ALERT AREA
        middle = tk.Frame(
            self.root,
            bg=BG
        )

        middle.pack(
            fill="x",
            padx=25,
            pady=5
        )

        # CHART
        chart_panel = tk.Frame(
            middle,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        chart_panel.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 8)
        )

        tk.Label(
            chart_panel,
            text="SYSTEM PERFORMANCE",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 11, "bold")
        ).pack(
            anchor="w",
            padx=15,
            pady=(12, 0)
        )

        self.chart = tk.Canvas(
            chart_panel,
            height=150,
            bg=PANEL,
            highlightthickness=0
        )

        self.chart.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=5
        )

        # ALERT
        alert_panel = tk.Frame(
            middle,
            bg=PANEL,
            width=280,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        alert_panel.pack(
            side="right",
            fill="y"
        )

        tk.Label(
            alert_panel,
            text="⚠ CPU ALERT",
            bg=PANEL,
            fg=RED,
            font=("Segoe UI", 11, "bold")
        ).pack(
            anchor="w",
            padx=15,
            pady=(12, 8)
        )

        self.alert_text = tk.Label(
            alert_panel,
            text="No high CPU process",
            bg=PANEL,
            fg=MUTED,
            justify="left",
            anchor="nw",
            font=("Segoe UI", 9)
        )

        self.alert_text.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=5
        )

        # TOOLBAR
        toolbar = tk.Frame(
            self.root,
            bg=BG
        )

        toolbar.pack(
            fill="x",
            padx=25,
            pady=(15, 5)
        )

        search_frame = tk.Frame(
            toolbar,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        search_frame.pack(
            side="left"
        )

        tk.Label(
            search_frame,
            text="🔍",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 11)
        ).pack(
            side="left",
            padx=(10, 4)
        )

        self.search_entry = tk.Entry(
            search_frame,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            width=30,
            font=("Segoe UI", 10)
        )

        self.search_entry.pack(
            side="left",
            padx=5,
            pady=8
        )

        self.search_entry.bind(
            "<KeyRelease>",
            self.search_process
        )

        self.make_button(
            toolbar,
            "⟳ Refresh",
            self.manual_refresh,
            ACCENT
        ).pack(
            side="right",
            padx=4
        )

        self.make_button(
            toolbar,
            "▣ Details",
            self.show_detail,
            "#64748b"
        ).pack(
            side="right",
            padx=4
        )

        self.make_button(
            toolbar,
            "⚠ Terminate",
            self.terminate_process,
            RED
        ).pack(
            side="right",
            padx=4
        )

        self.make_button(
            toolbar,
            "☷ Activity",
            self.show_activity,
            "#8b5cf6"
        ).pack(
            side="right",
            padx=4
        )

        # TABLE
        table_frame = tk.Frame(
            self.root,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        table_frame.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=(5, 20)
        )

        columns = (
            "pid",
            "name",
            "state",
            "cpu",
            "ram"
        )

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings"
        )

        headings = {
            "pid": "PID",
            "name": "PROCESS",
            "state": "STATE",
            "cpu": "CPU %",
            "ram": "RAM"
        }

        widths = {
            "pid": 80,
            "name": 400,
            "state": 120,
            "cpu": 110,
            "ram": 130
        }

        for column in columns:

            self.tree.heading(
                column,
                text=headings[column],
                command=lambda c=column:
                self.sort_by(c)
            )

            self.tree.column(
                column,
                width=widths[column],
                anchor="w"
            )

        self.tree.tag_configure(
            "high",
            foreground=RED
        )

        self.tree.tag_configure(
            "normal",
            foreground=TEXT
        )

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.tree.pack(
            side="left",
            fill="both",
            expand=True
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

    # ========================================================
    # CARDS
    # ========================================================

    def create_card(
        self,
        parent,
        title,
        value,
        accent
    ):

        frame = tk.Frame(
            parent,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5
        )

        tk.Label(
            frame,
            text=title,
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9, "bold")
        ).pack(
            anchor="w",
            padx=15,
            pady=(12, 2)
        )

        value_label = tk.Label(
            frame,
            text=value,
            bg=PANEL,
            fg=accent,
            font=("Segoe UI", 22, "bold")
        )

        value_label.pack(
            anchor="w",
            padx=15,
            pady=(0, 12)
        )

        return value_label

    # ========================================================
    # BUTTON
    # ========================================================

    def make_button(
        self,
        parent,
        text,
        command,
        color
    ):

        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=PANEL2,
            fg=TEXT,
            activebackground=color,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=14,
            pady=7,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )

    # ========================================================
    # UPDATE DATA
    # ========================================================

    def update_data(self):

        self.processes = self.manager.read_processes()

        cpu, memory, uptime = self.manager.system_info()

        total, used, available = memory

        if total > 0:
            ram_percent = used / total * 100
        else:
            ram_percent = 0

        self.cpu_history.append(cpu)
        self.ram_history.append(ram_percent)

        # Cards
        self.cpu_card.config(
            text=f"{cpu:.1f}%"
        )

        self.ram_card.config(
            text=f"{ram_percent:.1f}%"
        )

        self.process_card.config(
            text=str(len(self.processes))
        )

        self.uptime_card.config(
            text=uptime
        )

        self.update_table()

        self.update_alerts()

        self.draw_chart()

        self.root.after(
            REFRESH_INTERVAL,
            self.update_data
        )

    # ========================================================
    # TABLE
    # ========================================================

    def update_table(self):

        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self.search_text.lower()

        filtered = []

        for p in self.processes:

            if search:

                if (
                    search not in p["name"].lower()
                    and search not in str(p["pid"])
                ):
                    continue

            filtered.append(p)

        reverse = self.sort_reverse

        if self.sort_column == "name":

            filtered.sort(
                key=lambda x: x["name"].lower(),
                reverse=reverse
            )

        else:

            filtered.sort(
                key=lambda x: x[self.sort_column],
                reverse=reverse
            )

        for p in filtered:

            tag = (
                "high"
                if p["cpu"] >= CPU_ALERT
                else "normal"
            )

            self.tree.insert(
                "",
                "end",
                values=(
                    p["pid"],
                    p["name"],
                    p["state"],
                    f"{p['cpu']:.1f}%",
                    f"{p['ram']:,} KB"
                ),
                tags=(tag,)
            )

    # ========================================================
    # SEARCH
    # ========================================================

    def search_process(self, event=None):

        self.search_text = (
            self.search_entry
            .get()
            .strip()
        )

        self.update_table()

    # ========================================================
    # SORT
    # ========================================================

    def sort_by(self, column):

        if column == "pid":
            key = "pid"

        elif column == "name":
            key = "name"

        elif column == "state":
            key = "state"

        elif column == "cpu":
            key = "cpu"

        elif column == "ram":
            key = "ram"

        else:
            return

        if self.sort_column == key:
            self.sort_reverse = not self.sort_reverse

        else:
            self.sort_column = key
            self.sort_reverse = True

        self.update_table()

    # ========================================================
    # ALERT
    # ========================================================

    def update_alerts(self):

        alerts = [
            p for p in self.processes
            if p["cpu"] >= CPU_ALERT
        ]

        alerts.sort(
            key=lambda x: x["cpu"],
            reverse=True
        )

        if not alerts:

            self.alert_text.config(
                text="✓ No high CPU process",
                fg=GREEN
            )

            return

        text = ""

        for p in alerts[:5]:

            text += (
                f"PID {p['pid']}  "
                f"{p['name'][:18]}\n"
                f"CPU {p['cpu']:.1f}%\n\n"
            )

        self.alert_text.config(
            text=text,
            fg=RED
        )

    # ========================================================
    # CHART
    # ========================================================

    def draw_chart(self):

        self.chart.delete("all")

        width = self.chart.winfo_width()
        height = self.chart.winfo_height()

        if width <= 10:
            return

        # Grid
        for i in range(1, 5):

            y = i * height / 5

            self.chart.create_line(
                0,
                y,
                width,
                y,
                fill=BORDER
            )

        # CPU
        self.draw_line(
            list(self.cpu_history),
            width,
            height,
            ACCENT
        )

        # RAM
        self.draw_line(
            list(self.ram_history),
            width,
            height,
            GREEN
        )

        self.chart.create_text(
            10,
            10,
            text="CPU",
            anchor="nw",
            fill=ACCENT,
            font=("Segoe UI", 8, "bold")
        )

        self.chart.create_text(
            55,
            10,
            text="RAM",
            anchor="nw",
            fill=GREEN,
            font=("Segoe UI", 8, "bold")
        )

    def draw_line(
        self,
        values,
        width,
        height,
        color
    ):

        if len(values) < 2:
            return

        points = []

        step = width / (MAX_HISTORY - 1)

        for i, value in enumerate(values):

            x = i * step

            value = min(
                100,
                max(0, value)
            )

            y = height - (
                value / 100 * height
            )

            points.extend(
                [x, y]
            )

        if len(points) >= 4:

            self.chart.create_line(
                *points,
                fill=color,
                width=2,
                smooth=True
            )

    # ========================================================
    # MANUAL REFRESH
    # ========================================================

    def manual_refresh(self):

        self.processes = self.manager.read_processes()

        self.update_table()

    # ========================================================
    # DETAIL
    # ========================================================

    def show_detail(self):

        selected = self.tree.selection()

        if not selected:

            messagebox.showinfo(
                "Process Detail",
                "Pilih process terlebih dahulu."
            )

            return

        values = self.tree.item(
            selected[0]
        )["values"]

        pid = int(values[0])

        process = None

        for p in self.processes:

            if p["pid"] == pid:
                process = p
                break

        if not process:
            return

        window = tk.Toplevel(
            self.root
        )

        window.title(
            f"Process Detail - {process['name']}"
        )

        window.geometry(
            "450x350"
        )

        window.configure(
            bg=BG
        )

        tk.Label(
            window,
            text=process["name"],
            bg=BG,
            fg=ACCENT,
            font=("Segoe UI", 20, "bold")
        ).pack(
            pady=(25, 20)
        )

        details = [
            ("PID", process["pid"]),
            ("Process Name", process["name"]),
            ("State", process["state"]),
            ("CPU Usage", f"{process['cpu']:.2f}%"),
            ("RAM", f"{process['ram']:,} KB"),
            ("Linux", platform.release())
        ]

        for label, value in details:

            row = tk.Frame(
                window,
                bg=BG
            )

            row.pack(
                fill="x",
                padx=40,
                pady=7
            )

            tk.Label(
                row,
                text=label,
                bg=BG,
                fg=MUTED,
                width=18,
                anchor="w"
            ).pack(
                side="left"
            )

            tk.Label(
                row,
                text=str(value),
                bg=BG,
                fg=TEXT,
                anchor="w"
            ).pack(
                side="left"
            )

    # ========================================================
    # TERMINATE
    # ========================================================

    def terminate_process(self):

        selected = self.tree.selection()

        if not selected:

            messagebox.showwarning(
                "Terminate",
                "Pilih process terlebih dahulu."
            )

            return

        values = self.tree.item(
            selected[0]
        )["values"]

        pid = int(values[0])
        name = values[1]

        if pid <= 1:

            messagebox.showerror(
                "Tidak diizinkan",
                "Process sistem utama tidak boleh dihentikan."
            )

            return

        confirm = messagebox.askyesno(
            "Terminate Process",
            f"Hentikan process?\n\n"
            f"PID  : {pid}\n"
            f"Name : {name}"
        )

        if not confirm:
            return

        try:

            os.kill(
                pid,
                signal.SIGTERM
            )

            self.write_log(
                f"TERMINATE PID={pid} NAME={name}"
            )

            messagebox.showinfo(
                "Terminate",
                f"SIGTERM berhasil dikirim ke PID {pid}."
            )

        except ProcessLookupError:

            messagebox.showerror(
                "Error",
                "Process sudah tidak berjalan."
            )

        except PermissionError:

            messagebox.showerror(
                "Permission denied",
                "Tidak punya permission untuk menghentikan process ini."
            )

        except Exception as e:

            messagebox.showerror(
                "Error",
                str(e)
            )

    # ========================================================
    # ACTIVITY LOG
    # ========================================================

    def write_log(self, text):

        try:

            with open(
                "process_activity.log",
                "a"
            ) as f:

                f.write(
                    f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"{text}\n"
                )

        except Exception:
            pass

    def show_activity(self):

        window = tk.Toplevel(
            self.root
        )

        window.title(
            "Process Activity Log"
        )

        window.geometry(
            "750x500"
        )

        window.configure(
            bg=BG
        )

        text = tk.Text(
            window,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 10)
        )

        text.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=20
        )

        try:

            with open(
                "process_activity.log",
                "r"
            ) as f:

                content = f.read()

            if content:
                text.insert(
                    "1.0",
                    content
                )

            else:

                text.insert(
                    "1.0",
                    "No activity recorded."
                )

        except FileNotFoundError:

            text.insert(
                "1.0",
                "No activity recorded."
            )

        text.config(
            state="disabled"
        )


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = LinuxProcessManager(
        root
    )

    root.mainloop()
