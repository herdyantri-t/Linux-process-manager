let processes = [];
let cpuHistory = [];
let ramHistory = [];

const MAX_HISTORY = 20;
const CPU_ALERT_THRESHOLD = 80;

let currentPage = "dashboard";


// =========================================================
// DASHBOARD
// =========================================================

async function loadDashboard() {

    try {

        const response =
            await fetch("/api/dashboard");

        if (!response.ok) {
            throw new Error("Gagal mengambil dashboard");
        }

        const data =
            await response.json();

        updateSystemCards(data.system);

        processes = data.processes;

        updateProcessTable();

        updateChart(
            data.system.cpu,
            data.system.memory.percent
        );

        setConnectionStatus(true);

    } catch (error) {

        console.error(error);

        setConnectionStatus(false);
    }
}


// =========================================================
// SYSTEM CARDS
// =========================================================

function updateSystemCards(system) {

    document.getElementById(
        "cpu-value"
    ).textContent =
        system.cpu + "%";

    document.getElementById(
        "memory-value"
    ).textContent =
        system.memory.percent + "%";

    document.getElementById(
        "process-value"
    ).textContent =
        system.processes;

    document.getElementById(
        "uptime-value"
    ).textContent =
        system.uptime;

    document.getElementById(
        "cpu-cores"
    ).textContent =
        system.cores + " CPU cores";

    document.getElementById(
        "memory-detail"
    ).textContent =
        formatMemory(
            system.memory.used
        )
        +
        " / "
        +
        formatMemory(
            system.memory.total
        );
}


// =========================================================
// CONNECTION STATUS
// =========================================================

function setConnectionStatus(online) {

    const status =
        document.getElementById(
            "connection-status"
        );

    if (online) {

        status.textContent =
            "● SYSTEM ONLINE";

        status.style.color =
            "#4ade80";

    } else {

        status.textContent =
            "● CONNECTION ERROR";

        status.style.color =
            "#f87171";
    }
}


// =========================================================
// PROCESS TABLE
// =========================================================

function updateProcessTable() {

    const searchInput =
        document.getElementById(
            "search"
        );

    if (!searchInput) {
        return;
    }

    const keyword =
        searchInput.value
            .toLowerCase();

    const tableBody =
        document.getElementById(
            "process-table"
        );

    if (!tableBody) {
        return;
    }

    let filtered =
        processes.filter(
            process => {

                return (

                    process.name
                        .toLowerCase()
                        .includes(keyword)

                    ||

                    String(process.pid)
                        .includes(keyword)
                );
            }
        );

    filtered.sort(
        (a, b) =>
            b.cpu - a.cpu
    );

    tableBody.innerHTML = "";

    filtered.forEach(
        process => {

            const row =
                document.createElement(
                    "tr"
                );

            const cpuClass =
                process.cpu >=
                CPU_ALERT_THRESHOLD
                    ? "cpu-high"
                    : "cpu-normal";

            row.innerHTML = `

                <td>
                    ${process.pid}
                </td>

                <td>
                    ${escapeHTML(
                        process.name
                    )}
                </td>

                <td class="state">
                    ${escapeHTML(
                        process.state
                    )}
                </td>

                <td class="${cpuClass}">
                    ${process.cpu}%
                </td>

                <td>
                    ${formatMemory(
                        process.ram
                    )}
                </td>

            `;

            row.style.cursor =
                "pointer";

            row.addEventListener(
                "dblclick",
                () => {
                    showProcessDetail(
                        process.pid
                    );
                }
            );

            tableBody.appendChild(
                row
            );
        }
    );
}


// =========================================================
// SEARCH
// =========================================================

const searchInput =
    document.getElementById(
        "search"
    );

if (searchInput) {

    searchInput.addEventListener(
        "input",
        updateProcessTable
    );
}


// =========================================================
// MEMORY FORMAT
// =========================================================

function formatMemory(kb) {

    if (!kb || kb < 1024) {

        return (
            (kb || 0)
            + " KB"
        );
    }

    const mb =
        kb / 1024;

    if (mb < 1024) {

        return (
            mb.toFixed(1)
            + " MB"
        );
    }

    const gb =
        mb / 1024;

    return (
        gb.toFixed(2)
        + " GB"
    );
}


// =========================================================
// PROCESS DETAIL
// =========================================================

async function showProcessDetail(pid) {

    try {

        const response =
            await fetch(
                `/api/process/${pid}`
            );

        const data =
            await response.json();

        if (!response.ok) {

            alert(
                data.error ||
                "Process tidak ditemukan"
            );

            return;
        }

        const message = `

PID          : ${data.pid}

Name         : ${data.name}

State        : ${data.state}

RAM          : ${formatMemory(data.ram)}

Threads      : ${data.threads}

Parent PID   : ${data.ppid}

Executable   : ${data.executable}

Command      : ${data.command}

        `;

        const terminate =
            confirm(
                message
                +
                "\n\nKlik OK untuk TERMINATE process ini."
                +
                "\nKlik Cancel untuk kembali."
            );

        if (terminate) {

            await terminateProcess(
                pid
            );
        }

    } catch (error) {

        alert(
            "Gagal mengambil detail process."
        );
    }
}


// =========================================================
// TERMINATE PROCESS
// =========================================================

async function terminateProcess(pid) {

    const confirmed =
        confirm(
            `Yakin ingin menghentikan PID ${pid}?`
        );

    if (!confirmed) {
        return;
    }

    try {

        const response =
            await fetch(
                "/api/terminate",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        pid: pid
                    })
                }
            );

        const data =
            await response.json();

        alert(
            data.message
        );

        if (data.success) {

            await loadDashboard();
        }

    } catch (error) {

        alert(
            "Gagal mengirim perintah terminate."
        );
    }
}


// =========================================================
// REFRESH BUTTON
// =========================================================

const refreshButton =
    document.getElementById(
        "refresh"
    );

if (refreshButton) {

    refreshButton.addEventListener(
        "click",
        () => {

            loadDashboard();

            if (
                currentPage ===
                "alerts"
            ) {

                loadAlerts();

            } else if (
                currentPage ===
                "activity"
            ) {

                loadActivity();

            } else if (
                currentPage ===
                "system"
            ) {

                loadSystemPage();

            } else if (
                currentPage ===
                "processes"
            ) {

                loadProcessesPage();
            }
        }
    );
}


// =========================================================
// ALERTS
// =========================================================

async function loadAlerts() {

    currentPage = "alerts";

    const content =
        document.querySelector(
            ".content"
        );

    content.innerHTML = `

        <div class="panel">

            <div class="panel-header">

                <div class="panel-title">
                    Process Alerts
                </div>

            </div>

            <div class="panel-body">

                <p>
                    Loading alerts...
                </p>

            </div>

        </div>
    `;

    try {

        const response =
            await fetch(
                "/api/alerts"
            );

        const data =
            await response.json();

        let rows = "";

        if (
            data.processes.length === 0
        ) {

            rows = `

                <tr>

                    <td colspan="4">
                        Tidak ada process
                        dengan CPU ≥
                        ${data.threshold}%.
                    </td>

                </tr>
            `;

        } else {

            data.processes
                .forEach(
                    process => {

                        rows += `

                            <tr>

                                <td>
                                    ${process.pid}
                                </td>

                                <td>
                                    ${escapeHTML(
                                        process.name
                                    )}
                                </td>

                                <td class="cpu-high">
                                    ${process.cpu}%
                                </td>

                                <td>
                                    ${formatMemory(
                                        process.ram
                                    )}
                                </td>

                            </tr>
                        `;
                    }
                );
        }

        content.innerHTML = `

            <div class="panel">

                <div class="panel-header">

                    <div class="panel-title">
                        🚨 Process Alerts
                    </div>

                </div>

                <div class="panel-body">

                    <p style="
                        margin-bottom:20px;
                        color:#9ca3af;
                    ">
                        CPU alert threshold:
                        ${data.threshold}%
                    </p>

                    <div class="table-container">

                        <table>

                            <thead>

                                <tr>

                                    <th>PID</th>
                                    <th>PROCESS</th>
                                    <th>CPU</th>
                                    <th>RAM</th>

                                </tr>

                            </thead>

                            <tbody>

                                ${rows}

                            </tbody>

                        </table>

                    </div>

                </div>

            </div>
        `;

    } catch (error) {

        showError(
            "Gagal mengambil data alerts."
        );
    }
}


// =========================================================
// ACTIVITY
// =========================================================

async function loadActivity() {

    currentPage = "activity";

    const content =
        document.querySelector(
            ".content"
        );

    content.innerHTML = `

        <div class="panel">

            <div class="panel-header">

                <div class="panel-title">
                    Process Activity
                </div>

            </div>

            <div class="panel-body">

                Loading...

            </div>

        </div>
    `;

    try {

        const response =
            await fetch(
                "/api/activity"
            );

        const data =
            await response.json();

        let activityHTML = "";

        if (
            data.activities.length === 0
        ) {

            activityHTML = `

                <p style="
                    color:#9ca3af;
                ">
                    Belum ada aktivitas
                    yang tercatat.
                </p>

            `;

        } else {

            activityHTML = `

                <div style="
                    font-family:monospace;
                    white-space:pre-wrap;
                    line-height:1.8;
                    color:#d1d5db;
                ">
                    ${escapeHTML(
                        data.activities.join(
                            "\n"
                        )
                    )}
                </div>
            `;
        }

        content.innerHTML = `

            <div class="panel">

                <div class="panel-header">

                    <div class="panel-title">
                        📋 Process Activity Log
                    </div>

                </div>

                <div class="panel-body">

                    ${activityHTML}

                </div>

            </div>

        `;

    } catch (error) {

        showError(
            "Gagal mengambil activity log."
        );
    }
}


// =========================================================
// SYSTEM PAGE
// =========================================================

async function loadSystemPage() {

    currentPage = "system";

    const content =
        document.querySelector(
            ".content"
        );

    content.innerHTML = `

        <div class="panel">

            <div class="panel-header">

                <div class="panel-title">
                    System Information
                </div>

            </div>

            <div class="panel-body">

                Loading...

            </div>

        </div>
    `;

    try {

        const response =
            await fetch(
                "/api/system"
            );

        const data =
            await response.json();

        content.innerHTML = `

            <div class="cards">

                <div class="card">

                    <div class="card-label">
                        Hostname
                    </div>

                    <div class="card-value">
                        ${escapeHTML(
                            data.hostname
                        )}
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        CPU
                    </div>

                    <div class="card-value">
                        ${data.cpu_usage}%
                    </div>

                    <div class="card-sub">
                        ${data.cpu_cores}
                        CPU cores
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        Memory
                    </div>

                    <div class="card-value">
                        ${data.memory.percent}%
                    </div>

                    <div class="card-sub">
                        ${formatMemory(
                            data.memory.used
                        )}
                        /
                        ${formatMemory(
                            data.memory.total
                        )}
                    </div>

                </div>


                <div class="card">

                    <div class="card-label">
                        Uptime
                    </div>

                    <div class="card-value">
                        ${data.uptime}
                    </div>

                </div>

            </div>


            <div class="panel">

                <div class="panel-header">

                    <div class="panel-title">
                        System Details
                    </div>

                </div>

                <div class="panel-body">

                    <table>

                        <tbody>

                            <tr>

                                <td>
                                    Hostname
                                </td>

                                <td>
                                    ${escapeHTML(
                                        data.hostname
                                    )}
                                </td>

                            </tr>

                            <tr>

                                <td>
                                    Kernel
                                </td>

                                <td>
                                    ${escapeHTML(
                                        data.kernel
                                    )}
                                </td>

                            </tr>

                            <tr>

                                <td>
                                    Architecture
                                </td>

                                <td>
                                    ${escapeHTML(
                                        data.architecture
                                    )}
                                </td>

                            </tr>

                            <tr>

                                <td>
                                    CPU Cores
                                </td>

                                <td>
                                    ${data.cpu_cores}
                                </td>

                            </tr>

                            <tr>

                                <td>
                                    CPU Usage
                                </td>

                                <td>
                                    ${data.cpu_usage}%
                                </td>

                            </tr>

                            <tr>

                                <td>
                                    Uptime
                                </td>

                                <td>
                                    ${data.uptime}
                                </td>

                            </tr>

                        </tbody>

                    </table>

                </div>

            </div>

        `;

    } catch (error) {

        showError(
            "Gagal mengambil informasi sistem."
        );
    }
}


// =========================================================
// PROCESSES PAGE
// =========================================================

async function loadProcessesPage() {

    currentPage = "processes";

    const content =
        document.querySelector(
            ".content"
        );

    content.innerHTML = `

        <div class="panel">

            <div class="panel-header">

                <div class="panel-title">
                    All Processes
                </div>

            </div>

            <div class="panel-body">

                Loading...

            </div>

        </div>
    `;

    try {

        const response =
            await fetch(
                "/api/processes"
            );

        const data =
            await response.json();

        let rows = "";

        data.forEach(
            process => {

                const cpuClass =
                    process.cpu >= 80
                        ? "cpu-high"
                        : "cpu-normal";

                rows += `

                    <tr
                        ondblclick="
                            showProcessDetail(
                                ${process.pid}
                            )
                        "
                        style="
                            cursor:pointer;
                        "
                    >

                        <td>
                            ${process.pid}
                        </td>

                        <td>
                            ${escapeHTML(
                                process.name
                            )}
                        </td>

                        <td>
                            ${escapeHTML(
                                process.state
                            )}
                        </td>

                        <td class="${cpuClass}">
                            ${process.cpu}%
                        </td>

                        <td>
                            ${formatMemory(
                                process.ram
                            )}
                        </td>

                    </tr>
                `;
            }
        );

        content.innerHTML = `

            <div class="panel">

                <div class="panel-header">

                    <div class="panel-title">
                        ⚙ All Processes
                    </div>

                </div>

                <div class="panel-body">

                    <p style="
                        margin-bottom:15px;
                        color:#9ca3af;
                    ">
                        Double-click a process
                        to view its details.
                    </p>

                    <div class="table-container">

                        <table>

                            <thead>

                                <tr>

                                    <th>PID</th>
                                    <th>PROCESS</th>
                                    <th>STATE</th>
                                    <th>CPU</th>
                                    <th>RAM</th>

                                </tr>

                            </thead>

                            <tbody>

                                ${rows}

                            </tbody>

                        </table>

                    </div>

                </div>

            </div>
        `;

    } catch (error) {

        showError(
            "Gagal mengambil daftar process."
        );
    }
}


// =========================================================
// NAVIGATION
// =========================================================

const navItems =
    document.querySelectorAll(
        ".nav-item"
    );

navItems.forEach(
    item => {

        item.addEventListener(
            "click",
            () => {

                navItems.forEach(
                    nav => {
                        nav.classList.remove(
                            "active"
                        );
                    }
                );

                item.classList.add(
                    "active"
                );

                const menu =
                    item.textContent
                        .trim()
                        .toLowerCase();

                if (
                    menu ===
                    "dashboard"
                ) {

                    currentPage =
                        "dashboard";

                    location.reload();

                } else if (
                    menu ===
                    "processes"
                ) {

                    loadProcessesPage();

                } else if (
                    menu ===
                    "alerts"
                ) {

                    loadAlerts();

                } else if (
                    menu ===
                    "activity"
                ) {

                    loadActivity();

                } else if (
                    menu ===
                    "system"
                ) {

                    loadSystemPage();
                }
            }
        );
    }
);


// =========================================================
// ERROR
// =========================================================

function showError(message) {

    const content =
        document.querySelector(
            ".content"
        );

    content.innerHTML = `

        <div class="panel">

            <div class="panel-body">

                <p style="
                    color:#f87171;
                ">
                    ${message}
                </p>

            </div>

        </div>
    `;
}


// =========================================================
// CHART
// =========================================================

const canvas =
    document.getElementById(
        "performance-chart"
    );

let ctx = null;

if (canvas) {

    ctx =
        canvas.getContext("2d");
}


function updateChart(cpu, ram) {

    if (!canvas || !ctx) {
        return;
    }

    cpuHistory.push(cpu);

    ramHistory.push(ram);

    if (
        cpuHistory.length >
        MAX_HISTORY
    ) {

        cpuHistory.shift();
    }

    if (
        ramHistory.length >
        MAX_HISTORY
    ) {

        ramHistory.shift();
    }

    drawChart();
}


function drawChart() {

    if (!canvas || !ctx) {
        return;
    }

    const width =
        canvas.clientWidth;

    const height =
        canvas.clientHeight;

    const dpr =
        window.devicePixelRatio ||
        1;

    canvas.width =
        width * dpr;

    canvas.height =
        height * dpr;

    ctx.setTransform(
        dpr,
        0,
        0,
        dpr,
        0,
        0
    );

    ctx.clearRect(
        0,
        0,
        width,
        height
    );

    drawGrid(
        width,
        height
    );

    drawLine(
        cpuHistory,
        width,
        height
    );

    drawLine(
        ramHistory,
        width,
        height
    );
}


function drawGrid(
    width,
    height
) {

    ctx.strokeStyle =
        "#252b38";

    ctx.lineWidth = 1;

    for (
        let i = 0;
        i <= 4;
        i++
    ) {

        const y =
            (height / 4) * i;

        ctx.beginPath();

        ctx.moveTo(
            0,
            y
        );

        ctx.lineTo(
            width,
            y
        );

        ctx.stroke();
    }
}


function drawLine(
    data,
    width,
    height
) {

    if (data.length < 2) {
        return;
    }

    ctx.beginPath();

    data.forEach(
        (value, index) => {

            const x =
                (
                    index /
                    (MAX_HISTORY - 1)
                ) * width;

            const y =
                height -
                (
                    value / 100
                ) * height;

            if (index === 0) {

                ctx.moveTo(
                    x,
                    y
                );

            } else {

                ctx.lineTo(
                    x,
                    y
                );
            }
        }
    );

    ctx.strokeStyle =
        "#4ade80";

    ctx.lineWidth = 2;

    ctx.stroke();
}


// =========================================================
// HTML ESCAPE
// =========================================================

function escapeHTML(text) {

    const div =
        document.createElement(
            "div"
        );

    div.textContent =
        text ?? "";

    return div.innerHTML;
}


// =========================================================
// WINDOW RESIZE
// =========================================================

window.addEventListener(
    "resize",
    drawChart
);


// =========================================================
// INITIAL LOAD
// =========================================================

loadDashboard();


// =========================================================
// AUTO REFRESH
// =========================================================

setInterval(
    () => {

        if (
            currentPage ===
            "dashboard"
        ) {

            loadDashboard();
        }

    },
    2000
);
