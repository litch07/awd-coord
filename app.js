// Google Sheet CSV URL
const SHEET_URL = "";
const POLL_INTERVAL_MS = 5000; // 5 seconds

let lastFetchTime = null;

function parseCSV(csvText) {
    const lines = csvText.trim().split('\n');
    if (lines.length < 2) return null;

    const headers = lines[0].split(',').map(h => h.trim());
    const values = lines[1].split(',').map(v => v.trim());

    const data = {};
    headers.forEach((header, index) => {
        data[header] = values[index];
    });

    return data;
}

function updateTimeAgo() {
    const timeEl = document.getElementById('last-updated');
    if (!lastFetchTime) return;

    const now = new Date();
    const diffSeconds = Math.floor((now - lastFetchTime) / 1000);

    if (diffSeconds < 2) {
        timeEl.innerText = "Live";
    } else {
        timeEl.innerText = `Updated ${diffSeconds}s ago`;
    }
}

function renderDashboard(data) {
    const container = document.getElementById('dashboard-content');

    if (!data || Object.keys(data).length === 0) {
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--color-grey);">Waiting for live data...</div>';
        return;
    }

    // Pulse indicator
    const indicator = document.querySelector('.live-indicator');
    if (indicator) indicator.classList.add('active');

    const getBadgeClass = (status) => {
        status = (status || '').toLowerCase();
        if (status.includes('irrigating')) return 'irrigating';
        if (status.includes('alert')) return 'alert';
        if (status.includes('waiting')) return 'waiting';
        return 'not-connected';
    };

    const savedPercent = data.percent_saved ? parseFloat(data.percent_saved) : 0;

    const template = document.getElementById('dashboard-template');
    if (!template) {
        console.error("Dashboard template not found!");
        return;
    }

    const clone = template.content.cloneNode(true);
    
    clone.getElementById('tpl-water-saved').textContent = savedPercent + '%';
    clone.getElementById('tpl-water-saved-bar').style.width = Math.min(savedPercent, 100) + '%';
    clone.getElementById('tpl-awd-usage').textContent = (data.litres_used_awd || 0) + ' L';
    clone.getElementById('tpl-flood-baseline').textContent = (data.litres_used_flood_baseline || 0) + ' L';
    clone.getElementById('tpl-system-status').textContent = data.system_status || 'Unknown';
    
    const p1Status = clone.getElementById('tpl-plot1-status');
    p1Status.textContent = data.plot_1_status || '--';
    p1Status.className = 'status-badge ' + getBadgeClass(data.plot_1_status);
    
    const p2Status = clone.getElementById('tpl-plot2-status');
    p2Status.textContent = data.plot_2_status || '--';
    p2Status.className = 'status-badge ' + getBadgeClass(data.plot_2_status);
    
    const p3Status = clone.getElementById('tpl-plot3-status');
    p3Status.textContent = data.plot_3_status || '--';
    p3Status.className = 'status-badge ' + getBadgeClass(data.plot_3_status);
    
    const modularStatus = clone.getElementById('tpl-modular-status');
    modularStatus.textContent = data.plot_modular_status || '--';
    modularStatus.className = 'status-badge ' + getBadgeClass(data.plot_modular_status);
    
    clone.getElementById('tpl-serving').textContent = data.active_plot || 'None';
    clone.getElementById('tpl-packet-id').textContent = data.timestamp || '--';
    
    container.innerHTML = '';
    container.appendChild(clone);
    
    if (typeof lucide !== 'undefined') {
        lucide.createIcons({ root: container });
    }
}

function renderEmptyState() {
    const container = document.getElementById('dashboard-content');
    container.innerHTML = `
        <div class="empty-state text-center" style="padding: 60px 20px; background: white; border-radius: 12px; border: 1px dashed rgba(0,0,0,0.1);">
            <i data-lucide="database" style="width: 48px; height: 48px; color: var(--color-grey); margin-bottom: 20px;"></i>
            <h3 style="color: var(--color-dark-green); margin-bottom: 10px;">Awaiting Data Source Configuration</h3>
            <p style="color: var(--color-grey); max-width: 400px; margin: 0 auto;">
                The backend SHEET_URL is currently empty. Please configure the data source in app.js to view live telemetry.
            </p>
        </div>
    `;
    if (typeof lucide !== 'undefined') lucide.createIcons({ root: container });
}

async function fetchData() {
    if (!SHEET_URL) {
        renderEmptyState();
        return;
    }

    try {
        const response = await fetch(SHEET_URL + "?t=" + new Date().getTime());
        if (!response.ok) throw new Error("Network response was not ok");

        const csvText = await response.text();
        const data = parseCSV(csvText);

        if (data) {
            lastFetchTime = new Date();
            renderDashboard(data);
            updateTimeAgo();
        }
    } catch (error) {
        console.error("Error fetching live data:", error);
    }
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    fetchData();
    if (SHEET_URL) {
        setInterval(fetchData, POLL_INTERVAL_MS);
    }
    setInterval(updateTimeAgo, 1000);
});
