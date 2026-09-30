const CONFIG = {
    SYSTEM_CSV_URL: "https://docs.google.com/spreadsheets/d/1HoiUuAfxN8kIdVCbGVNYUPz1p8fFHhN2B5vWP53avc0/export?format=csv&gid=0",
    PLOTS_CSV_URL: "https://docs.google.com/spreadsheets/d/1HoiUuAfxN8kIdVCbGVNYUPz1p8fFHhN2B5vWP53avc0/export?format=csv&gid=1001",
    MEASUREMENTS_CSV_URL: "https://docs.google.com/spreadsheets/d/1HoiUuAfxN8kIdVCbGVNYUPz1p8fFHhN2B5vWP53avc0/export?format=csv&gid=1002",
    // Set to 300s (5 minutes) so static test data doesn't immediately grey out
    STALE_AFTER_S: 300
};

const POLL_INTERVAL_MS = 5000; // 5 seconds

let lastFetchTime = null;

// Robust CSV parser handling quoted fields
function parseCSV(csvText) {
    if (!csvText) return [];
    const rows = [];
    let currentRow = [];
    let currentCell = '';
    let inQuotes = false;

    for (let i = 0; i < csvText.length; i++) {
        const char = csvText[i];
        const nextChar = csvText[i + 1];

        if (inQuotes) {
            if (char === '"' && nextChar === '"') {
                currentCell += '"';
                i++;
            } else if (char === '"') {
                inQuotes = false;
            } else {
                currentCell += char;
            }
        } else {
            if (char === '"') {
                inQuotes = true;
            } else if (char === ',') {
                currentRow.push(currentCell);
                currentCell = '';
            } else if (char === '\n' || char === '\r') {
                currentRow.push(currentCell);
                rows.push(currentRow);
                currentRow = [];
                currentCell = '';
                if (char === '\r' && nextChar === '\n') i++;
            } else {
                currentCell += char;
            }
        }
    }
    if (currentRow.length > 0 || currentCell) {
        currentRow.push(currentCell);
        rows.push(currentRow);
    }

    if (rows.length < 2) return [];

    const headers = rows[0].map(h => h.trim());
    const data = [];
    for (let i = 1; i < rows.length; i++) {
        // Skip empty rows (all cells empty or just one empty cell)
        if (rows[i].length === 0 || rows[i].every(c => c === undefined || c.trim() === '')) continue;

        const rowObj = {};
        headers.forEach((header, index) => {
            rowObj[header] = rows[i][index] !== undefined ? rows[i][index].trim() : '';
        });
        data.push(rowObj);
    }
    return data;
}

function updateTimeAgo() {
    const timeEl = document.getElementById('last-updated');
    if (!window.lastDataEpoch) return;

    const nowS = Date.now() / 1000;
    const diffSeconds = Math.max(0, Math.floor(nowS - window.lastDataEpoch));

    if (diffSeconds < 2) {
        timeEl.innerText = "Live";
    } else if (diffSeconds < 60) {
        timeEl.innerText = `Updated ${diffSeconds}s ago`;
    } else if (diffSeconds < 3600) {
        const m = Math.floor(diffSeconds / 60);
        timeEl.innerText = `Updated ${m}m ago`;
    } else if (diffSeconds < 86400) {
        const h = Math.floor(diffSeconds / 3600);
        const m = Math.floor((diffSeconds % 3600) / 60);
        timeEl.innerText = `Updated ${h}h ${m}m ago`;
    } else {
        const d = Math.floor(diffSeconds / 86400);
        timeEl.innerText = `Updated ${d} days ago`;
    }
}

function renderEmptyState() {
    const container = document.getElementById('dashboard-content');
    container.innerHTML = `
        <div class="empty-state text-center" style="padding: 60px 20px; background: white; border-radius: 12px; border: 1px dashed rgba(0,0,0,0.1);">
            <i data-lucide="database" style="width: 48px; height: 48px; color: var(--color-grey); margin-bottom: 20px;"></i>
            <h3 style="color: var(--color-dark-green); margin-bottom: 10px;">Awaiting Data Source Configuration</h3>
            <p style="color: var(--color-grey); max-width: 400px; margin: 0 auto;">
                Please configure the CSV URLs in app.js (CONFIG) to view live telemetry.
            </p>
        </div>
    `;
    if (typeof lucide !== 'undefined') lucide.createIcons({ root: container });
}

function renderWaitingState() {
    const container = document.getElementById('dashboard-content');
    container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--color-grey);">Waiting for live data...</div>';
}

function renderDashboard(systemData, plotsData, measurementsData) {
    const container = document.getElementById('dashboard-content');

    if (!systemData || systemData.length === 0) {
        renderWaitingState();
        return;
    }

    const sys = systemData[0]; // Tab 1 has exactly one row

    // Pulse indicator
    const indicator = document.querySelector('.live-indicator');
    if (indicator) indicator.classList.add('active');

    const template = document.getElementById('dashboard-template');
    if (!template) return;

    const clone = template.content.cloneNode(true);

    // 1. Data Age Check (Staleness)
    const updatedEpoch = parseInt(sys.updated_at_epoch_s, 10);
    window.lastDataEpoch = updatedEpoch;

    const ageS = Math.max(0, Date.now() / 1000 - updatedEpoch);
    const isStale = isNaN(updatedEpoch) || ageS > CONFIG.STALE_AFTER_S;

    if (isStale) {
        const offlineBanner = clone.getElementById('offline-banner');
        offlineBanner.classList.remove('hidden');

        const offlineSecs = Math.floor(ageS);
        if (offlineSecs < 60) {
            clone.getElementById('offline-seconds').textContent = `${offlineSecs} seconds ago`;
        } else {
            const m = Math.floor(offlineSecs / 60);
            const s = offlineSecs % 60;
            clone.getElementById('offline-seconds').textContent = `${m}m ${s}s ago`;
        }

        // Grey out panels
        const panelsContainer = clone.getElementById('panels-container');
        panelsContainer.style.opacity = '0.5';
        panelsContainer.style.pointerEvents = 'none';

        if (indicator) indicator.classList.remove('active');
        clone.getElementById('tpl-link-status').textContent = "OFFLINE";
        clone.getElementById('tpl-link-status').style.color = "var(--color-danger)";
    } else {
        clone.getElementById('tpl-link-status').textContent = "ONLINE";
        clone.getElementById('tpl-link-status').style.color = "var(--color-success)";
    }

    // 2. Measurements (Calculated dynamically from live telemetry)
    let totalSeconds = 0;
    let onlineNodes = 0;
    if (plotsData && plotsData.length > 0) {
        plotsData.forEach(plot => {
            if (plot.online === 'TRUE') onlineNodes++;
            const secs = parseFloat(plot.irrigation_seconds_total);
            if (!isNaN(secs)) totalSeconds += secs;
        });
    }

    // Assuming mini submersible pump flows at ~0.5 Liters per second
    const estLiters = (totalSeconds * 0.5).toFixed(1);

    clone.getElementById('tpl-water-pumped').textContent = estLiters + " L (est.)";
    clone.getElementById('tpl-nodes-online').textContent = onlineNodes + " / " + (plotsData ? plotsData.length : 0);

    // pump on/off, a red FAULT banner when pump_fault is true
    const pumpOn = sys.pump_on === 'TRUE';
    clone.getElementById('tpl-pump-status').textContent = sys.pump_on ? (pumpOn ? "ON" : "OFF") : "--";
    if (pumpOn) clone.getElementById('tpl-pump-status').style.color = 'var(--color-success)';

    let reasonText = "System is idle";
    const mode = sys.system_mode || "IDLE";
    if (mode === "IRRIGATING") {
        reasonText = `Irrigating Plot ${sys.active_plot || '?'}.`;
    } else if (mode === "ARMING") {
        reasonText = `Preparing to irrigate Plot ${sys.active_plot || '?'}.`;
    } else if (mode === "WATER_CONFIRM") {
        reasonText = `Confirming flow to Plot ${sys.active_plot || '?'}.`;
    } else if (mode === "RESELECT_COOLDOWN") {
        reasonText = "Cooling down before next plot selection.";
    } else if (mode === "IDLE") {
        if (pumpOn) reasonText = "Manual override active or shutting down.";
        else reasonText = "All plots are hydrated. Pump is off.";
    } else {
        reasonText = `Status: ${mode}`;
    }
    
    const reasonEl = clone.getElementById('tpl-pump-reason');
    if (reasonEl) reasonEl.textContent = reasonText;

    const pumpFault = sys.pump_fault === 'TRUE';
    if (pumpFault) {
        clone.getElementById('fault-banner').classList.remove('hidden');
    }

    clone.getElementById('tpl-pump-voltage').textContent = sys.pump_voltage || '--';
    clone.getElementById('tpl-pump-current').textContent = sys.pump_current_ma || '--';
    clone.getElementById('tpl-pump-power').textContent = sys.pump_power_mw || '--';

    // Format timestamp nicely to local time
    if (sys.updated_at_iso_utc) {
        const d = new Date(sys.updated_at_iso_utc);
        clone.getElementById('tpl-timestamp').textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } else {
        clone.getElementById('tpl-timestamp').textContent = '--';
    }

    // 4. Plots
    const plotsContainer = clone.getElementById('plots-container');
    const plotTemplate = document.getElementById('plot-row-template');

    if (plotsData && plotsData.length > 0 && plotTemplate) {
        plotsData.forEach(plot => {
            const plotClone = plotTemplate.content.cloneNode(true);
            plotClone.querySelector('.plot-id-text').textContent = plot.node_id || '--';

            // Build status string
            let statusBadge = plotClone.querySelector('.plot-status-badge');

            const isOnline = plot.online === 'TRUE';
            const valveOpen = plot.valve_open === 'TRUE';

            let statusText = "UNKNOWN";
            let badgeClass = "not-connected";

            if (!isOnline) {
                statusText = "OFFLINE";
                badgeClass = "not-connected";
            } else if (valveOpen) {
                statusText = "IRRIGATING";
                badgeClass = "irrigating";
            } else {
                statusText = "WAITING";
                badgeClass = "waiting";
            }

            // Allow override texts if we had any logic for it, but for now just use these basics
            if (plot.water_present === 'TRUE' && statusText === "WAITING") {
                statusText = "SATURATED";
                badgeClass = "irrigating"; // Greenish
            }

            // Populate the beautiful new grid UI
            plotClone.querySelector('.plot-depth').textContent = plot.depth_cm ? plot.depth_cm + ' cm' : '--';
            plotClone.querySelector('.plot-stage').textContent = plot.stage || '--';

            const valveEl = plotClone.querySelector('.plot-valve');
            if (valveOpen) {
                valveEl.textContent = 'OPEN';
                valveEl.style.color = 'var(--color-success)';
            } else {
                valveEl.textContent = 'CLOSED';
                valveEl.style.color = '#64748b';
            }

            const waterEl = plotClone.querySelector('.plot-water');
            if (plot.water_present === 'TRUE') {
                waterEl.textContent = 'Flowing';
                waterEl.style.color = '#0284c7'; // Blue
            } else {
                waterEl.textContent = 'Not Flowing';
                waterEl.style.color = '#64748b';
            }

            if (plot.override === 'TRUE') {
                plotClone.querySelector('.override-badge').style.display = 'inline-block';
                statusText = "MANUAL CONTROL";
                badgeClass = "waiting";
            }

            statusBadge.textContent = statusText;
            statusBadge.classList.add(badgeClass);

            const reasonEl = plotClone.querySelector('.plot-reason');
            if (reasonEl) {
                if (!isOnline) {
                    reasonEl.textContent = "Node is offline.";
                } else if (plot.override === 'TRUE') {
                    reasonEl.textContent = "Forced open by manual switch.";
                } else if (valveOpen) {
                    if (parseFloat(plot.depth_cm) < 15) {
                        reasonEl.textContent = plot.stage === "FLOWERING" ? "Depth < 5cm (Critical Stage)" : "Depth < 15cm (Vegetative)";
                    } else {
                        reasonEl.textContent = "Soil is dry (Analog > 1500).";
                    }
                } else {
                    if (plot.water_present === 'TRUE' || (parseFloat(plot.depth_cm) >= 15 && parseFloat(plot.soil) <= 1500)) {
                        reasonEl.textContent = "Plot is adequately hydrated.";
                    } else {
                        reasonEl.textContent = "Waiting for turn in queue.";
                    }
                }
            }

            plotsContainer.appendChild(plotClone);
        });
    } else {
        plotsContainer.innerHTML = '<div style="color: var(--color-grey); font-size: 0.9rem; padding: 10px;">No field nodes connected.</div>';
    }

    container.innerHTML = '';
    container.appendChild(clone);

    if (typeof lucide !== 'undefined') {
        lucide.createIcons({ root: container });
    }
}

async function fetchCSV(url) {
    if (!url) return [];
    try {
        const sep = url.includes('?') ? '&' : '?';
        const res = await fetch(`${url}${sep}t=${Date.now()}`);
        if (!res.ok) throw new Error("Fetch failed");
        const text = await res.text();
        return parseCSV(text);
    } catch (e) {
        console.error("Error fetching CSV:", url, e);
        return [];
    }
}

async function fetchData() {
    if (!CONFIG.SYSTEM_CSV_URL || !CONFIG.PLOTS_CSV_URL || !CONFIG.MEASUREMENTS_CSV_URL) {
        renderEmptyState();
        return;
    }

    try {
        const [sys, plots, meas] = await Promise.all([
            fetchCSV(CONFIG.SYSTEM_CSV_URL),
            fetchCSV(CONFIG.PLOTS_CSV_URL),
            fetchCSV(CONFIG.MEASUREMENTS_CSV_URL)
        ]);

        lastFetchTime = new Date();
        renderDashboard(sys, plots, meas);
        updateTimeAgo();
    } catch (error) {
        console.error("Error fetching live data:", error);
    }
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    fetchData();
    if (CONFIG.SYSTEM_CSV_URL) {
        setInterval(fetchData, POLL_INTERVAL_MS);
    }
    setInterval(updateTimeAgo, 1000);

    const refreshBtn = document.getElementById('manual-refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            refreshBtn.classList.add('spinning');
            refreshBtn.disabled = true;
            try {
                await fetchData();
            } finally {
                setTimeout(() => {
                    refreshBtn.classList.remove('spinning');
                    refreshBtn.disabled = false;
                }, 600);
            }
        });
    }
});
