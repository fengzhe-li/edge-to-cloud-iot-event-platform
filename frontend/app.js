// Local preview gate only. It provides no authentication or authorization.
function checkLogin() {
    const previewOpen = sessionStorage.getItem('previewOpen') === 'true';
    document.getElementById('login-overlay').style.display = previewOpen ? 'none' : '';
    document.getElementById('app-content').style.display = previewOpen ? '' : 'none';
}
function handleLogin() {
    sessionStorage.setItem('previewOpen', 'true');
    checkLogin();
}
function handleLogout() {
    sessionStorage.removeItem('previewOpen');
    checkLogin();
}
checkLogin();

// ===== API Config =====
const STATUS_API_BASE = window.APP_CONFIG?.STATUS_API_BASE || "";
const EMAIL_API_BASE = window.APP_CONFIG?.EMAIL_API_BASE || "";

// ===== Fetch latest status =====
async function fetchLatestStatus(sensorId) {
    try {
        const url = `${STATUS_API_BASE}?sensor_id=${sensorId}`;
        console.log("Fetching:", url);

        const res = await fetch(url, {
            method: "GET",
            mode: "cors",
            cache: "no-store"
        });

        console.log("Status:", res.status);

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }

        const raw = await res.json();
        const data = typeof raw.body === 'string' ? JSON.parse(raw.body) : raw;
        console.log("Data:", data);

        // The lambda returns a `{ ok: true, sensor: { status: "..." } }` object
        const sData = data.sensor || data;
        const rawStatus = (sData.status ?? sData.state ?? "unknown").toString().toLowerCase();

        // updated_ts is a bigint (Unix ms) from the Lambda
        const updatedAt = sData.updated_ts ? new Date(Number(sData.updated_ts)) : null;

        return { status: rawStatus, updatedAt };
    } catch (err) {
        console.error(`Sensor ${sensorId} fetch failed:`, err);
        addLog(`⚠ API error for Sensor ${sensorId}: ${err.message}`, 'log-system');
        return { status: "unknown", updatedAt: null };
    }
}

// ===== Fetch Latest RFID Tap =====
let lastProcessedRfidTs = Math.floor(Date.now() / 1000); // Process only new taps

async function fetchLatestRFIDTaps() {
    try {
        const url = `${STATUS_API_BASE}?device_id=Arduino2`;
        const res = await fetch(url, { method: "GET", mode: "cors", cache: "no-store" });

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }

        const raw = await res.json();
        const data = typeof raw.body === 'string' ? JSON.parse(raw.body) : raw;

        if (data.rfid && data.rfid.found) {
            const scan = data.rfid;
            const isNew = Number(scan.scan_timestamp) > Number(lastProcessedRfidTs);

            if (isNew) {
                console.log("New Tap Detected via API!", scan);
                handleRFIDTap(scan.rfid_uid);
                lastProcessedRfidTs = Number(scan.scan_timestamp);
            }
        }
    } catch (err) {
        console.error("RFID poll failed:", err);
        addLog(` RFID poll failed: ${err.message}`, 'log-system');
    }
}

// ===== Poll all sensors every 2 s =====
function pollAllSensors() {
    [0, 1, 2, 3, 4, 5].forEach(async (id) => {
        // Skip updating visually if the sensor has been marked inactive via IoT config
        if (!sensorActiveMap[id]) return;

        const result = await fetchLatestStatus(id);

        // Prevent WET status from overwriting HANDLING status
        if (sensorStates[id] === 'handling' && result.status === 'wet') {
            return;
        }

        if ((result.status === 'wet' || result.status === 'dry') && result.status !== sensorStates[id]) {
            setStatus(id, result.status, result.updatedAt);
        }
    });
}

// ===== Zone & Employee Data =====
// Zone 1: 4 employees;  Zone 2: 2 employees;  Zone 3: 2 employees
const zones = {
    1: { name: "Zone 1", desc: "Beverages & Dairy", color: "#6C63FF", cls: "z1", employeeIds: [1, 2, 3, 4] },
    2: { name: "Zone 2", desc: "Electronics & General", color: "#00c6ff", cls: "z2", employeeIds: [5, 6] },
    3: { name: "Zone 3", desc: "Produce & Fresh", color: "#00d68f", cls: "z3", employeeIds: [7, 8] },
};

const sensorZoneMap = { 0: 1, 1: 1, 2: 2, 3: 3, 4: 3, 5: 2 };

const employees = [
    { id: 1, name: "Ruben", role: "Zone 1 Staff", available: true, color: "#6C63FF", email: "operations@example.com" },
    { id: 2, name: "Jan", role: "Zone 1 Staff", available: true, color: "#8b84ff", email: "operations@example.com" },
    { id: 3, name: "Chloe", role: "Zone 1 Staff", available: true, color: "#a29bfe", email: "operations@example.com" },
    { id: 4, name: "Lee", role: "Zone 1 Staff", available: true, color: "#fd79a8", email: "operations@example.com" },
    { id: 5, name: "Wu", role: "Zone 2 Staff", available: true, color: "#00c6ff", email: "operations@example.com" },
    { id: 6, name: "Chang", role: "Zone 2 Staff", available: true, color: "#55c1ff", email: "operations@example.com" },
    { id: 7, name: "Joker", role: "Zone 3 Staff", available: true, color: "#00d68f", email: "operations@example.com" },
    { id: 8, name: "Tom", role: "Zone 3 Staff", available: true, color: "#55efc4", email: "operations@example.com" },
];

// ===== State =====
// States: 'dry' | 'wet' | 'handling' | 'inactive' (greyed out)
const sensorStates = { 0: 'dry', 1: 'dry', 2: 'dry', 3: 'dry', 4: 'dry', 5: 'dry' };
const sensorActiveMap = { 0: true, 1: true, 2: true, 3: true, 4: true, 5: true };
const sensorChangedAt = { 0: null, 1: null, 2: null, 3: null, 4: null, 5: null };
const sensorHandledBy = { 0: null, 1: null, 2: null, 3: null, 4: null, 5: null }; // employeeId when handling
let activeSensorId = null;
let activeZoneId = null;
let selectedEmployee = null;
let activeTapSensorId = null;

// ===== Clock =====
function updateClock() {
    document.getElementById('clock').textContent =
        new Date().toLocaleTimeString('en-US', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ===== Start polling =====
pollAllSensors();
setInterval(pollAllSensors, 2000);

// Poll for RFIDs separate from Sensors because Lambda requires explicit query param
setInterval(fetchLatestRFIDTaps, 2000);

// ===== Poll for System Statuses =====
function updateArduinoStatusUI(displayId, isOnline) {
    const el = document.getElementById(displayId);
    if (!el) return;

    if (isOnline) {
        el.className = 'arduino-status online';
        el.querySelector('.status-text').textContent = displayId === 'arduino-status-1' ? 'System 1 Online' : 'System 2 Online';
    } else {
        el.className = 'arduino-status offline';
        el.querySelector('.status-text').textContent = displayId === 'arduino-status-1' ? 'System 1 Offline' : 'System 2 Offline';
    }
}

async function pollArduinoSystems() {
    try {
        const fetchSystem1 = fetch(`${STATUS_API_BASE}?device_id=Arduino1`, {
    method: "GET",
    mode: "cors",
    cache: "no-store"
})
            .then(async res => {
    if (!res.ok) return null;
    const raw = await res.json();
    const data = typeof raw.body === 'string' ? JSON.parse(raw.body) : raw;
    return data;
})
            .then(data => {
                const isOnline = data && data.system && data.system.online;
                updateArduinoStatusUI('arduino-status-1', Boolean(isOnline));
            })
            .catch(err => {
                console.error('Error fetching System 1:', err);
                updateArduinoStatusUI('arduino-status-1', false);
            });

        const fetchSystem2 = fetch(`${STATUS_API_BASE}?device_id=Arduino2`, {
    method: "GET",
    mode: "cors",
    cache: "no-store"
})
            .then(async res => {
    if (!res.ok) return null;
    const raw = await res.json();
    const data = typeof raw.body === 'string' ? JSON.parse(raw.body) : raw;
    return data;
})
            .then(data => {
                const isOnline = data && data.system && data.system.online;
                updateArduinoStatusUI('arduino-status-2', Boolean(isOnline));
            })
            .catch(err => {
                console.error('Error fetching System 2:', err);
                updateArduinoStatusUI('arduino-status-2', false);
            });

        // Run both fetches concurrently so System 2 doesn't wait for System 1
        await Promise.all([fetchSystem1, fetchSystem2]);
    } catch (err) {
        console.error('Error in pollArduinoSystems:', err);
    }
}

pollArduinoSystems();
setInterval(pollArduinoSystems, 5000);

// ===== Log =====
function addLog(msg, cls = 'log-system') {
    const list = document.getElementById('log-list');
    if (!list) return;
    const div = document.createElement('div');
    div.className = `log-entry ${cls}`;
    const t = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    div.innerHTML = `<span class="log-time">${t}</span><span>${msg}</span>`;
    list.prepend(div);
}
function clearLog() {
    const list = document.getElementById('log-list');
    if (list) list.innerHTML = '';
}

// ===== Download Helpers =====
function downloadCSV(filename, csvContent) {
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function downloadActivityLog() {
    const entries = document.querySelectorAll('#log-list .log-entry');
    if (!entries.length) { alert('No activity log entries to download.'); return; }
    const rows = [['Time', 'Message']];
    entries.forEach(entry => {
        const time = entry.querySelector('.log-time')?.textContent?.trim() || '';
        const spans = entry.querySelectorAll('span');
        const msg = spans.length > 1 ? spans[1].textContent.trim() : '';
        rows.push([time, msg]);
    });
    const csv = rows.map(r => r.map(c => `"${c.replace(/"/g, '""')}"`).join(',')).join('\n');
    const now = new Date();
    const ts = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;
    downloadCSV(`activity_log_${ts}.csv`, csv);
}

function downloadAuditLog() {
    const rows_el = document.querySelectorAll('#audit-tbody .audit-row');
    if (!rows_el.length) { alert('No audit events to download.'); return; }
    const rows = [['Time', 'Sensor', 'Zone', 'Event Type', 'Details', 'Actor']];
    rows_el.forEach(tr => {
        const cells = tr.querySelectorAll('td');
        const row = [];
        cells.forEach(td => {
            row.push(td.textContent.trim());
        });
        rows.push(row);
    });
    const csv = rows.map(r => r.map(c => `"${c.replace(/"/g, '""')}"`).join(',')).join('\n');
    const now = new Date();
    const ts = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;
    downloadCSV(`audit_log_${ts}.csv`, csv);
}

// ===== Audit Table =====
function addAuditRow({ time, sensorId, zoneId, eventType, details, actor }) {
    const tbody = document.getElementById('audit-tbody');
    if (!tbody) return;
    const empty = tbody.querySelector('.audit-empty-row');
    if (empty) empty.remove();
    const ts = time ? time.toLocaleTimeString('en-US', { hour12: false }) : '--';
    const zone = zoneId ? zones[zoneId] : null;
    const TYPE_META = {
        'state-change': { label: 'State Change', cls: 'at-state' },
        'manual': { label: 'Manual Op', cls: 'at-manual' },
        'tap': { label: 'Employee Tap', cls: 'at-tap' },
        'assign': { label: 'Assignment', cls: 'at-assign' },
        'email': { label: 'Email Sent', cls: 'at-email' },
    };
    const meta = TYPE_META[eventType] || { label: eventType, cls: '' };
    const tr = document.createElement('tr');
    tr.className = `audit-row`;
    tr.innerHTML = `
        <td class="at-time">${ts}</td>
        <td class="at-sensor">${sensorId != null ? 'S' + sensorId : '—'}</td>
        <td class="at-zone">${zone ? zone.name : '—'}</td>
        <td><span class="at-badge ${meta.cls}">${meta.label}</span></td>
        <td class="at-details">${details}</td>
        <td class="at-actor">${actor || 'System'}</td>
    `;
    tbody.prepend(tr);
}
function clearAuditTable() {
    const tbody = document.getElementById('audit-tbody');
    if (tbody) tbody.innerHTML = '<tr class="audit-empty-row"><td colspan="6">No events recorded yet</td></tr>';
}

// ===== Stats =====
function updateStats() {
    const vals = Object.values(sensorStates);
    const wet = vals.filter(s => s === 'wet').length;
    const handling = vals.filter(s => s === 'handling').length;
    const dry = vals.filter(s => s === 'dry').length;
    const inactive = vals.filter(s => s === 'inactive').length;

    // Only count zones that have an active alert or handling state
    const zonesAffected = new Set(
        Object.entries(sensorStates)
            .filter(([, v]) => v === 'wet' || v === 'handling')
            .map(([k]) => sensorZoneMap[+k])
    ).size;

    const summaryText = `${dry} Dry · ${wet} Wet · ${handling} Handling · ${zonesAffected} Zone${zonesAffected !== 1 ? 's' : ''} Affected`;

    // Update all summary elements 
    document.querySelectorAll('#stat-summary, .stat-summary').forEach(el => {
        el.textContent = summaryText;
    });
}

// ===== Zone status update =====
function updateZoneState(zoneId) {
    const zone = zones[zoneId];
    const sensors = Object.entries(sensorZoneMap).filter(([, z]) => z === zoneId).map(([s]) => +s);
    const hasWet = sensors.some(s => sensorStates[s] === 'wet');
    const hasHandling = sensors.some(s => sensorStates[s] === 'handling');
    const el = document.getElementById(`mzone-${zoneId}`);
    const chip = document.getElementById(`zchip-${zoneId}`);
    el.classList.remove('zone-wet', 'zone-handling', zone.cls);
    chip.classList.remove('alert', 'handling');
    if (hasWet) {
        el.classList.add('zone-wet', zone.cls);
        chip.textContent = '⚠ Alert';
        chip.classList.add('alert');
    } else if (hasHandling) {
        el.classList.add('zone-handling', zone.cls);
        chip.textContent = '🔧 Handling';
        chip.classList.add('handling');
    } else {
        chip.textContent = '✓ Clear';
    }
    if (typeof window.updateMapZoneState === 'function') {
        window.updateMapZoneState(zoneId, hasWet || hasHandling);
    }
}

// ===== Helpers =====
function fmtTime(d) {
    return d ? d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : 'No changes yet';
}

// ===== Control panel row =====
function updateControlPanel(id, status, time) {
    const badge = document.getElementById(`ctrl-badge-${id}`);
    const timeEl = document.getElementById(`ctrl-time-${id}`);
    const dryBtn = document.getElementById(`ctrl-dry-${id}`);
    const wetBtn = document.getElementById(`ctrl-wet-${id}`);
    if (!badge) return;
    badge.textContent = status === 'handling' ? 'HANDLING' : status.toUpperCase();
    badge.className = 'ctrl-status-badge' +
        (status === 'wet' ? ' wet' : status === 'handling' ? ' handling' : status === 'inactive' ? ' inactive' : '');
    if (timeEl) timeEl.textContent = time ? `Last changed: ${fmtTime(time)}` : '—';
    if (dryBtn) dryBtn.classList.toggle('active', status === 'dry');
    if (wetBtn) wetBtn.classList.toggle('active', status === 'wet');
}

// ===== Set sensor status (API-driven) =====
function setStatus(id, status, dbTimestamp) {
    if (sensorStates[id] === status) return;
    const prev = sensorStates[id];
    sensorStates[id] = status;
    // Use database timestamp when available, fallback to browser time
    const eventTime = dbTimestamp ? new Date(dbTimestamp) : new Date();
    sensorChangedAt[id] = eventTime;
    const zoneId = sensorZoneMap[id];
    const node = document.getElementById(`snode-${id}`);

    // First, remove inactive if it was there before to avoid lingering grey CSS
    if (node) {
        if (status !== 'inactive') node.classList.remove('inactive');
    }

    if (status === 'inactive') {
        if (node) {
            node.classList.remove('wet', 'handling');
            node.classList.add('inactive');
        }
    } else if (status === 'wet') {
        if (node) {
            node.classList.remove('handling');
            node.classList.add('wet');
        }
        addLog(`⚠ Sensor ${id} (Zone ${zoneId}) — WET detected at ${fmtTime(eventTime)}`, 'log-wet');
        addAuditRow({ time: eventTime, sensorId: id, zoneId, eventType: 'state-change', details: `${prev.toUpperCase()} → WET`, actor: 'System (API)' });
        openCautionModal(id, zoneId);
    } else if (status === 'dry') {
        sensorHandledBy[id] = null;
        if (node) {
            node.classList.remove('wet', 'handling');
        }
        addLog(`Sensor ${id} (Zone ${zoneId}) — returned to DRY at ${fmtTime(eventTime)}`, 'log-dry');
        addAuditRow({ time: eventTime, sensorId: id, zoneId, eventType: 'state-change', details: `${prev.toUpperCase()} → DRY`, actor: 'System (API)' });

        // Auto-close tap handler active modal if sensor turns DRY
        if (activeTapSensorId == id) {
            activeTapSensorId = null;
            document.getElementById('active-handling-modal').style.display = 'none';
        }
    }
    updateControlPanel(id, status, eventTime);
    updateZoneState(zoneId);
    updateStats();
}

// ===== Sensor Popover =====
let popoverSensorId = null;

function openSensorPopover(event, sensorId) {
    event.stopPropagation();
    popoverSensorId = sensorId;
    const zoneId = sensorZoneMap[sensorId];
    const zone = zones[zoneId];
    const state = sensorStates[sensorId];
    const handlerEmpId = sensorHandledBy[sensorId];

    document.getElementById('spop-name').textContent = `Sensor ${sensorId}`;
    document.getElementById('spop-zone').textContent = `${zone.name} · ${zone.desc}`;

    const badge = document.getElementById('spop-badge');
    badge.textContent = state === 'handling' ? 'HANDLING' : state.toUpperCase();
    badge.className = 'spop-badge' +
        (state === 'wet' ? ' wet' : state === 'handling' ? ' handling' : '');

    document.getElementById('spop-time').textContent =
        sensorChangedAt[sensorId] ? `Last changed: ${fmtTime(sensorChangedAt[sensorId])}` : 'No changes yet';

    // Handler info line
    const handlerDiv = document.getElementById('spop-handler');
    if (state === 'handling' && handlerEmpId !== null) {
        const emp = employees.find(e => e.id === handlerEmpId);
        handlerDiv.textContent = `🔧 ${emp?.name || 'Employee'} is currently handling this`;
        handlerDiv.style.display = '';
    } else {
        handlerDiv.style.display = 'none';
    }

    // Button visibility
    document.getElementById('spop-assign-btn').style.display = state === 'wet' ? '' : 'none';

    // Position
    const pop = document.getElementById('sensor-popover');
    pop.style.display = 'block';
    let rect;
    try {
        rect = (event.currentTarget || event.target).getBoundingClientRect();
    } catch (_) {
        rect = { top: 200, bottom: 220, left: 300, right: 330, width: 30 };
    }
    const popW = 250, popH = 180;
    let left = rect.left + (rect.width || 30) / 2 - popW / 2;
    let top = rect.bottom + 10;
    if (left + popW > window.innerWidth - 10) left = window.innerWidth - popW - 10;
    if (left < 10) left = 10;
    if (top + popH > window.innerHeight - 10) top = rect.top - popH - 10;
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';
    document.getElementById('popover-backdrop').style.display = 'block';
}

function closeSensorPopover() {
    document.getElementById('sensor-popover').style.display = 'none';
    document.getElementById('popover-backdrop').style.display = 'none';
    popoverSensorId = null;
}

function openAssignFromPopover() {
    const id = popoverSensorId;
    closeSensorPopover();
    activeSensorId = id;
    activeZoneId = sensorZoneMap[id];
    openEmployeeModal(activeZoneId);
}

// ===== Caution Modal (wet alert) =====
function openCautionModal(sensorId, zoneId) {
    activeSensorId = sensorId;
    activeZoneId = zoneId;
    const zone = zones[zoneId];
    document.getElementById('caution-sensor-name').textContent = `Sensor ${sensorId}`;
    document.getElementById('caution-zone-name').textContent = zone.name;
    const card = document.getElementById('caution-zone-card');
    card.className = `caution-zone-card ${zone.cls}`;
    document.getElementById('czc-name').textContent = zone.name;
    const staffCount = employees.filter(e => zone.employeeIds.includes(e.id) && e.available).length;
    document.getElementById('czc-info').textContent = `${zone.desc} · ${staffCount} staff available`;
    document.getElementById('caution-modal').style.display = 'flex';
}
function closeCautionModal() {
    document.getElementById('caution-modal').style.display = 'none';
}
function openEmployeeModalFromCaution() {
    closeCautionModal();
    openEmployeeModal(activeZoneId);
}

// ===== Employee Assignment Modal =====
function openEmployeeModal(zoneId) {
    selectedEmployee = null;
    activeZoneId = zoneId;
    const zone = zones[zoneId];
    document.getElementById('emp-zone-label').textContent = zone.name;
    document.getElementById('emp-search').value = '';
    document.getElementById('confirm-btn').disabled = true;
    renderEmployees('');
    document.getElementById('employee-modal').style.display = 'flex';
}
function closeEmployeeModal() {
    document.getElementById('employee-modal').style.display = 'none';
    if (activeSensorId && sensorStates[activeSensorId] === 'wet') {
        openCautionModal(activeSensorId, activeZoneId);
    }
}

function renderEmployees(filter) {
    const zone = zones[activeZoneId];
    const list = document.getElementById('employee-list');
    list.innerHTML = '';
    const pool = employees.filter(e =>
        zone.employeeIds.includes(e.id) &&
        (e.name.toLowerCase().includes(filter.toLowerCase()) || e.role.toLowerCase().includes(filter.toLowerCase()))
    );
    if (!pool.length) {
        list.innerHTML = `<div style="text-align:center;color:var(--muted);padding:20px;font-size:0.82rem;">No employees found.</div>`;
        return;
    }
    pool.forEach(emp => {
        const initials = emp.name.split(' ').map(n => n[0]).join('');
        const div = document.createElement('div');
        div.className = 'emp-item' + (selectedEmployee?.id === emp.id ? ' selected' : '');
        div.id = `emp-${emp.id}`;
        div.onclick = () => selectEmployee(emp);
        div.innerHTML = `
            <div class="emp-avatar" style="background:${emp.color}">${initials}</div>
            <div class="emp-info">
                <div class="emp-name">${emp.name}</div>
                <div class="emp-role">${emp.role}</div>
            </div>
            <span class="emp-avail ${emp.available ? 'avail-yes' : 'avail-busy'}">${emp.available ? 'Available' : 'Busy'}</span>
        `;
        list.appendChild(div);
    });
}
function filterEmployees() { renderEmployees(document.getElementById('emp-search').value); }

function selectEmployee(emp) {
    selectedEmployee = emp;
    document.querySelectorAll('.emp-item').forEach(el => el.classList.remove('selected'));
    document.getElementById(`emp-${emp.id}`)?.classList.add('selected');
    document.getElementById('confirm-btn').disabled = false;
    const emailInput = document.getElementById('emp-email-display');
    const emailBtn = document.getElementById('send-email-btn');
    if (emailInput) emailInput.value = emp.email || '';
    if (emailBtn) emailBtn.disabled = !emp.email;
}

// ===== Send Email =====
async function sendEmailToSelected() {
    if (!selectedEmployee) return;
    const emp = selectedEmployee;
    const sensorId = activeSensorId;
    const zoneId = activeZoneId;
    const zone = zones[zoneId] || {};
    const wetTime = sensorId && sensorChangedAt[sensorId] ? fmtTime(sensorChangedAt[sensorId]) : 'unknown time';

    const subject = `[Alert] Moisture detected — Sensor ${sensorId ?? '?'} (${zone.name ?? 'Unknown Zone'})`;
    const message =
        `Hi ${emp.name},\n\n` +
        `A wet condition was detected by Sensor ${sensorId ?? '?'} in ${zone.name ?? 'Unknown Zone'} (${zone.desc ?? ''}) at ${wetTime}.\n\n` +
        `Please respond to the affected area as soon as possible.\n\nSensorWatch Dashboard`;

    const sendBtn = document.getElementById('send-email-btn');
    if (sendBtn) { sendBtn.disabled = true; sendBtn.textContent = 'Sending…'; }

    try {
        const res = await fetch(EMAIL_API_BASE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ to: [emp.email], subject, message }),
        });

        const rawText = await res.text();
        console.log("Email API URL:", EMAIL_API_BASE);
        console.log("Email API status:", res.status);
        console.log("Email API response:", rawText);

        let data = {};
        try {
            data = JSON.parse(rawText);
        } catch (e) { }

        if (!res.ok) {
            throw new Error(data.error || rawText || `HTTP ${res.status}`);
        }
        addLog(`✉ Email sent to ${emp.name} (${emp.email})`, 'log-assign');
        addAuditRow({ time: new Date(), sensorId: activeSensorId, zoneId: activeZoneId, eventType: 'email', details: `Email sent to ${emp.name} ‹${emp.email}›`, actor: 'Manager (UI)' });
    } catch (err) {
        addLog(`✉ Email failed for ${emp.name}: ${err.message}`, 'log-system');
    } finally {
        if (sendBtn) { sendBtn.disabled = false; sendBtn.textContent = '✉ Send Email'; }
    }
}

function confirmAssignment() {
    if (!selectedEmployee || !activeSensorId) return;
    const emp = selectedEmployee;
    const sensorId = activeSensorId;
    const zoneId = activeZoneId;
    const now = new Date();
    document.getElementById('employee-modal').style.display = 'none';
    addLog(`✓ ${emp.name} assigned to Sensor ${sensorId} (${zones[zoneId].name}) at ${fmtTime(now)}`, 'log-assign');
    addAuditRow({ time: now, sensorId, zoneId, eventType: 'assign', details: `${emp.name} assigned to respond`, actor: 'Manager (UI)' });
    activeSensorId = null;
    activeZoneId = null;
    selectedEmployee = null;
}



// ===== RFID Auto-Handling Workflow =====

// Call this from the polling function when a tap is detected
function handleRFIDTap(rfidUid) {
    const emp = getEmployeeByRfid(rfidUid);
    if (!emp) return;

    // Find the sensor that has been in the 'wet' state the longest.
    let targetSensorId = null;
    let oldestTime = null;

    for (const [id, state] of Object.entries(sensorStates)) {
        if (state === 'wet') {
            const changedTime = sensorChangedAt[id];
            if (!oldestTime || (changedTime && changedTime < oldestTime)) {
                oldestTime = changedTime;
                targetSensorId = id;
            }
        }
    }

    if (targetSensorId === null) return;

    const id = targetSensorId;
    const now = new Date();
    const zoneId = sensorZoneMap[id];
    const node = document.getElementById(`snode-${id}`);

    // 1. Close WET Caution Modal
    closeCautionModal();

    // 2. Turn Sensor Yellow (handling state)
    sensorStates[id] = 'handling';
    sensorHandledBy[id] = emp.id;
    sensorChangedAt[id] = now;
    node.classList.remove('wet');
    node.classList.add('handling');
    addLog(`🔧 [RFID] ${emp.name} is handling Sensor ${id} (Zone ${zoneId}) — at ${fmtTime(now)}`, 'log-assign');
    addAuditRow({ time: now, sensorId: id, zoneId, eventType: 'tap', details: `[RFID] ${emp.name} auto-assigned — WET → HANDLING`, actor: emp.name });
    addAuditRow({ time: now, sensorId: id, zoneId, eventType: 'state-change', details: `WET → HANDLING`, actor: emp.name });
    updateControlPanel(id, 'handling', now);
    updateZoneState(zoneId);
    updateStats();

    // 3. Open new Employee Tap Notification Modal
    activeTapSensorId = id;
    document.getElementById('ahm-emp-name').textContent = emp.name;
    document.getElementById('ahm-sensor-name').textContent = `Sensor ${id}`;
    document.getElementById('ahm-zone-name').textContent = zones[zoneId].name;
    document.getElementById('active-handling-modal').style.display = 'flex';
}

// ===== Close modals on overlay click =====
document.getElementById('caution-modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeCautionModal(); });
document.getElementById('employee-modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeEmployeeModal(); });

// ===== RFID Management =====
let rfidAssignments = JSON.parse(localStorage.getItem('rfidAssignments')) || {};

function initRfidManagement() {
    // Sync local storage with employees array
    employees.forEach(e => delete e.rfidUid); // clear initial ones if any
    for (const [rfid, empId] of Object.entries(rfidAssignments)) {
        const emp = employees.find(e => e.id === Number(empId));
        if (emp) emp.rfidUid = rfid;
    }

    // Initialize selects
    const sel1 = document.getElementById('rfid-sel-1');
    const sel2 = document.getElementById('rfid-sel-2');
    if (sel1 && rfidAssignments['DEMO-RFID-01']) sel1.value = rfidAssignments['DEMO-RFID-01'];
    if (sel2 && rfidAssignments['DEMO-RFID-02']) sel2.value = rfidAssignments['DEMO-RFID-02'];

    renderRfidMappings();
}

function saveRfidAssignments() {
    const sel1 = document.getElementById('rfid-sel-1');
    const sel2 = document.getElementById('rfid-sel-2');
    const val1 = sel1 ? sel1.value : '';
    const val2 = sel2 ? sel2.value : '';

    // Validation: One RFID = One Employee, no employee assigned to multiple RFIDs
    if (val1 && val2 && val1 === val2) {
        alert('Validation Error: One employee cannot be assigned to multiple RFIDs at the same time.');
        return;
    }

    const newAssignments = {};
    if (val1) newAssignments['DEMO-RFID-01'] = val1;
    if (val2) newAssignments['DEMO-RFID-02'] = val2;

    rfidAssignments = newAssignments;
    localStorage.setItem('rfidAssignments', JSON.stringify(rfidAssignments));

    initRfidManagement(); // re-sync and re-render

    addAuditRow({
        time: new Date(),
        sensorId: null,
        zoneId: null,
        eventType: 'manual',
        details: 'RFID Assignments updated',
        actor: 'Manager (UI)'
    });

    alert('RFID Assignments Saved Successfully!');
}

function renderRfidMappings() {
    const list = document.getElementById('rfid-mapping-list');
    if (!list) return;

    list.innerHTML = '';
    const entries = Object.entries(rfidAssignments);
    if (entries.length === 0) {
        list.innerHTML = '<div class="rfid-mapping-empty">No mappings saved</div>';
        return;
    }

    entries.forEach(([rfid, empId]) => {
        const emp = employees.find(e => e.id === Number(empId));
        if (emp) {
            const div = document.createElement('div');
            div.className = 'rfid-mapping-row';
            div.innerHTML = `<strong>${rfid}</strong> ➔ ${emp.name}`;
            list.appendChild(div);
        }
    });
}

function getEmployeeByRfid(rfidUid) {
    const empId = rfidAssignments[rfidUid];
    return empId ? employees.find(e => e.id === Number(empId)) || null : null;
}

// Call init on load
initRfidManagement();

// ===== Actuator Control =====
// Simulated external state (these mimic your external Arduino variables)
let system1LedState = 'OFF';
let system2LedState = 'OFF';

// Add your API Gateway endpoint for the actuator lambda here
const ACTUATOR_API_BASE = window.APP_CONFIG?.ACTUATOR_API_BASE || "";

async function fetchActuatorState() {
    if (ACTUATOR_API_BASE === 'YOUR_ACTUATOR_API_ENDPOINT_HERE') return;

    try {
        const res = await fetch(ACTUATOR_API_BASE);
        if (res.ok) {
            const result = await res.json();
            if (result.success && result.data) {
                system1LedState = result.data.system1.toUpperCase(); // 'on' -> 'ON'
                system2LedState = result.data.system2.toUpperCase();
                renderLedStatus();
            }
        }
    } catch (err) {
        console.error('Failed to fetch actuator state:', err);
    }
}

/**
 * Update the UI variables manually and reflect the change on the DOM
 */
async function setLedState(systemId, state) {
    // Save previous state for rollback
    const prevState = systemId === 'system1' ? system1LedState : system2LedState;

    // 1. Optimistic UI Update
    if (systemId === 'system1') system1LedState = state;
    if (systemId === 'system2') system2LedState = state;
    renderLedStatus();

    addAuditRow({
        time: new Date(),
        sensorId: null,
        zoneId: null,
        eventType: 'manual',
        details: `Actuator ${systemId} toggled to ${state}`,
        actor: 'Manager (UI)'
    });

    // 2. Network Request
    try {
        const res = await fetch(ACTUATOR_API_BASE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                systemId: systemId,
                state: state.toLowerCase() // 'on' or 'off'
            })
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        // Re-sync with backend after successful update
        await fetchActuatorState();
    } catch (err) {
        console.error('Failed to update actuator state:', err);

        // Rollback UI to previous state
        if (systemId === 'system1') system1LedState = prevState;
        if (systemId === 'system2') system2LedState = prevState;

        renderLedStatus();
        showToast(`Failed to toggle ${systemId}`, 'error');
    }
}

/**
 * Handle user click on toggle button
 */
function toggleLed(systemId) {
    if (systemId === 'system1') {
        const newState = system1LedState === 'ON' ? 'OFF' : 'ON';
        setLedState('system1', newState);
    } else if (systemId === 'system2') {
        const newState = system2LedState === 'ON' ? 'OFF' : 'ON';
        setLedState('system2', newState);
    }
}

/**
 * Refresh DOM with new state
 */
function renderLedStatus() {
    // Update System 1 UI
    const badge1 = document.getElementById('actuator-state-1');
    const btn1 = document.getElementById('actuator-btn-1');
    if (badge1 && btn1) {
        badge1.textContent = `LED ${system1LedState}`;
        if (system1LedState === 'ON') {
            badge1.className = 'actuator-badge on';
            btn1.textContent = 'Turn OFF';
        } else {
            badge1.className = 'actuator-badge off';
            btn1.textContent = 'Turn ON';
        }
    }

    // Update System 2 UI
    const badge2 = document.getElementById('actuator-state-2');
    const btn2 = document.getElementById('actuator-btn-2');
    if (badge2 && btn2) {
        badge2.textContent = `LED ${system2LedState}`;
        if (system2LedState === 'ON') {
            badge2.className = 'actuator-badge on';
            btn2.textContent = 'Turn OFF';
        } else {
            badge2.className = 'actuator-badge off';
            btn2.textContent = 'Turn ON';
        }
    }
}

// Initial draw of actuator state
renderLedStatus();

// Optionally fetch the real state initially and set up polling
fetchActuatorState();
setInterval(fetchActuatorState, 5000);

// ===== IoT Sensor Config Panel =====
const IOT_API_BASE = window.APP_CONFIG?.IOT_API_BASE || "";

// Global Toaster function
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

async function fetchIotConfig() {
    const deviceId = document.getElementById('iot-device-select').value;
    const grid = document.getElementById('iot-config-grid');
    const statusBar = document.getElementById('iot-status-bar');

    grid.innerHTML = '<div style="color:var(--muted); padding: 16px;">Loading configuration...</div>';
    statusBar.textContent = `Fetching config for ${deviceId}...`;

    try {
        const res = await fetch(`${IOT_API_BASE}/config/${deviceId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        const sensors = data.sensors || [];

        grid.innerHTML = ''; // clear loading text

        if (sensors.length === 0) {
            grid.innerHTML = `<div style="color:var(--muted); padding: 16px;">No sensors found for ${deviceId}.</div>`;
            statusBar.textContent = `Loaded ${deviceId} - 0 sensors`;
            return;
        }

        sensors.forEach(sensor => {
            const card = document.createElement('div');
            card.className = 'iot-card';

            const isActive = !!sensor.active;
            const statusText = isActive ? 'Active' : 'Inactive';
            const statusColor = isActive ? 'var(--success)' : 'var(--muted)';

            // Sync with dashboard globally if it's Arduino1 or Arduino2 (assuming sensor id maps 1:1)
            const sid = parseInt(sensor.sensor_id, 10);
            if (!isNaN(sid)) {
                sensorActiveMap[sid] = isActive;
                if (!isActive) {
                    setStatus(sid, 'inactive');
                } else if (sensorStates[sid] === 'inactive') {
                    // Reset locally so poll takes over again
                    setStatus(sid, 'dry');
                }
            }

            card.innerHTML = `
                <div class="iot-card-title">Sensor ${sensor.sensor_id}</div>
                <label class="iot-switch">
                    <input type="checkbox" 
                           id="iot-toggle-${sensor.sensor_id}" 
                           ${isActive ? 'checked' : ''} 
                           onchange="handleIotToggle('${deviceId}', '${sensor.sensor_id}', this)">
                    <span class="iot-slider"></span>
                </label>
                <div class="iot-card-status" id="iot-status-text-${sensor.sensor_id}" style="color: ${statusColor}">
                    ${statusText}
                </div>
            `;
            grid.appendChild(card);
        });

        statusBar.textContent = `Loaded config for ${deviceId} (${sensors.length} sensors)`;
    } catch (err) {
        console.error('Error fetching IoT config:', err);
        grid.innerHTML = `<div style="color:var(--danger); padding: 16px;">Error loading configuration for ${deviceId}!</div>`;
        statusBar.textContent = `Error fetching config`;
        showToast('Failed to load device config', 'error');
    }
}

async function handleIotToggle(deviceId, sensorId, checkboxEl) {
    const newActiveState = checkboxEl.checked;
    const prevActiveState = !newActiveState; // stored for rollback
    const statusTextEl = document.getElementById(`iot-status-text-${sensorId}`);

    // Optimistic UI Update
    if (statusTextEl) {
        statusTextEl.textContent = newActiveState ? 'Active' : 'Inactive';
        statusTextEl.style.color = newActiveState ? 'var(--success)' : 'var(--muted)';
    }

    try {
        const res = await fetch(`${IOT_API_BASE}/config/${deviceId}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sensor_id: parseInt(sensorId, 10),
                active: newActiveState
            })
        });

        if (!res.ok) throw new Error(`HTTP error ${res.status}`);

        addAuditRow({
            time: new Date(),
            sensorId: parseInt(sensorId, 10),
            zoneId: null,
            eventType: 'manual',
            details: `IoT Sensor ${sensorId} toggled ${newActiveState ? 'ON' : 'OFF'}`,
            actor: 'Manager (UI)'
        });

        showToast(`Sensor ${sensorId} updated`);
    } catch (err) {
        console.error('Error updating sensor:', err);

        // Revert UI optimally
        checkboxEl.checked = prevActiveState;
        if (statusTextEl) {
            statusTextEl.textContent = prevActiveState ? 'Active' : 'Inactive';
            statusTextEl.style.color = prevActiveState ? 'var(--success)' : 'var(--muted)';
        }

        showToast(`Failed to update Sensor ${sensorId}`, 'error');
    }
}

async function pushIotConfig() {
    const deviceId = document.getElementById('iot-device-select').value;
    const btn = document.getElementById('iot-push-btn');
    const statusBar = document.getElementById('iot-status-bar');

    // Set UI to loading state
    btn.disabled = true;
    const originalBtnContent = btn.innerHTML;
    btn.innerHTML = `<div class="iot-spinner"></div> Pushing...`;
    statusBar.textContent = `Pushing config to ${deviceId}...`;

    try {
        const res = await fetch(`${IOT_API_BASE}/config/push`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_id: deviceId })
        });

        if (!res.ok) throw new Error(`HTTP error ${res.status}`);

        addAuditRow({
            time: new Date(),
            sensorId: null,
            zoneId: null,
            eventType: 'manual',
            details: `IoT Config pushed to ${deviceId}`,
            actor: 'Manager (UI)'
        });

        showToast(`Config pushed to ${deviceId} successfully`);
        statusBar.textContent = `Config successfully pushed to ${deviceId}.`;

        // Immediately sync the dashboard visually with the updated toggle states
        document.querySelectorAll('.iot-switch input[type="checkbox"]').forEach(toggle => {
            const sid = parseInt(toggle.id.replace('iot-toggle-', ''), 10);
            if (!isNaN(sid)) {
                const isActive = toggle.checked;
                sensorActiveMap[sid] = isActive;
                if (!isActive) {
                    setStatus(sid, 'inactive');
                } else if (sensorStates[sid] === 'inactive') {
                    // Turn it visually to dry immediately so poll takes over 
                    setStatus(sid, 'dry');
                }
            }
        });

    } catch (err) {
        console.error('Error pushing config:', err);
        showToast(`Failed to push config to ${deviceId}`, 'error');
        statusBar.textContent = `Push failed.`;
    } finally {
        // Restore button state
        btn.disabled = false;
        btn.innerHTML = originalBtnContent;
    }
}

// ===== Threshold Config Panel =====
async function fetchThresholdConfig() {
    const deviceId = document.getElementById('threshold-device-select').value;
    const grid = document.getElementById('threshold-config-grid');

    grid.innerHTML = '<div style="color:var(--muted); padding: 16px;">Loading thresholds...</div>';

    try {
        const res = await fetch(`${IOT_API_BASE}/threshold/${deviceId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        const thresholds = data.thresholds || [];

        grid.innerHTML = ''; // clear loading text

        if (thresholds.length === 0) {
            grid.innerHTML = `<div style="color:var(--muted); padding: 16px;">No thresholds found for ${deviceId}.</div>`;
            return;
        }

        thresholds.forEach(t => {
            const card = document.createElement('div');
            card.className = 'iot-card threshold-card';

            card.innerHTML = `
                <div class="iot-card-title" style="margin-bottom: 8px;">Sensor ${t.sensor_id}</div>
                <div class="threshold-input-wrap">
                    <input type="number" 
                           id="threshold-input-${t.sensor_id}" 
                           class="threshold-input" 
                           value="${t.threshold_value}" />
                    <button id="threshold-save-${t.sensor_id}" 
                            class="ctrl-btn dry-btn" 
                            style="margin-left: 8px;"
                            onclick="saveThreshold('${deviceId}', '${t.sensor_id}')">Save</button>
                </div>
            `;
            grid.appendChild(card);
        });
    } catch (err) {
        console.error('Error fetching Threshold config:', err);
        grid.innerHTML = `<div style="color:var(--danger); padding: 16px;">Error loading thresholds for ${deviceId}!</div>`;
        showToast('Failed to load thresholds', 'error');
    }
}

async function saveThreshold(deviceId, sensorId) {
    const inputEl = document.getElementById(`threshold-input-${sensorId}`);
    const btnEl = document.getElementById(`threshold-save-${sensorId}`);
    const thresholdValue = parseInt(inputEl.value, 10);

    if (isNaN(thresholdValue)) {
        showToast('Invalid threshold value', 'error');
        return;
    }

    // Disable button to prevent multiple submissions
    btnEl.disabled = true;
    const originalText = btnEl.textContent;
    btnEl.textContent = 'Saving...';

    try {
        const res = await fetch(`${IOT_API_BASE}/threshold/${deviceId}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sensor_id: parseInt(sensorId, 10),
                threshold_value: thresholdValue
            })
        });

        if (!res.ok) throw new Error(`HTTP error ${res.status}`);

        showToast('Threshold updated');
    } catch (err) {
        console.error('Error updating threshold:', err);
        showToast('Update failed', 'error');
    } finally {
        btnEl.disabled = false;
        btnEl.textContent = originalText;
    }
}

async function pushThresholdConfig() {
    const deviceId = document.getElementById('threshold-device-select').value;
    const btn = document.getElementById('threshold-push-btn');

    btn.disabled = true;
    const originalBtnContent = btn.innerHTML;
    btn.innerHTML = `<div class="iot-spinner"></div> Pushing...`;

    try {
        const res = await fetch(`${IOT_API_BASE}/threshold/push`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_id: deviceId })
        });

        if (!res.ok) throw new Error(`HTTP error ${res.status}`);

        showToast('Thresholds pushed to device');
    } catch (err) {
        console.error('Error pushing thresholds:', err);
        showToast('Push failed', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalBtnContent;
    }
}

function syncDeviceSelects(deviceId) {
    document.getElementById('iot-device-select').value = deviceId;
    document.getElementById('threshold-device-select').value = deviceId;
    fetchIotConfig();
    fetchThresholdConfig();
}

// Init panels on load
window.addEventListener('DOMContentLoaded', () => {
    fetchIotConfig();
    fetchThresholdConfig();
});
