const API_URL = 'https://tapin-api.up.railway.app/api/get-latest-rfid';
const POLL_INTERVAL = 2000;

const $ = (sel) => document.querySelector(sel);
const scannedAt = $('#scannedAt');
const employeeCard = $('#employeeCard');
const noData = $('#noData');
const statusDot = $('#statusDot');
const statusText = $('#statusText');
const lastUpdated = $('#lastUpdated');
const logoContainer = $('#logoContainer');
const emptyAvatar = $('#emptyAvatar');
const profileIconPlaceholder = $('#profileIconPlaceholder');

let currentData = null;
let isFirstLoad = true;
let currentRfid = null;

function loadLogo() {
    const logoPaths = [
        'storage/assets/tapin_logo.png',
        'storage/assets/tapin_logo.jpg',
        'assets/tapin_logo.png',
        'assets/tapin_logo.jpg',
        'tapin_logo.png',
        'tapin_logo.jpg'
    ];

    for (const path of logoPaths) {
        const img = new Image();
        img.onload = function() {
            logoContainer.innerHTML = '';
            logoContainer.appendChild(img);
        };
        img.src = path;
    }
}

function loadProfileIcon() {
    const iconPaths = [
        'storage/assets/profile_icon.png',
        'storage/assets/profile_icon.jpg',
        'assets/profile_icon.png',
        'assets/profile_icon.jpg',
        'profile_icon.png',
        'profile_icon.jpg'
    ];

    for (const path of iconPaths) {
        const img = new Image();
        img.onload = function() {
            profileIconPlaceholder.src = path;
        };
        img.src = path;
    }
}

function formatDate(isoString) {
    if (!isoString) return 'Waiting for scan...';
    try {
        const d = new Date(isoString);
        return 'Scanned: ' + d.toLocaleString('en-PH', { 
            month: 'short', day: 'numeric', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            hour12: true
        });
    } catch {
        return isoString;
    }
}

function formatTime(isoString) {
    if (!isoString) return '--';
    try {
        const d = new Date(isoString);
        return d.toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch {
        return isoString;
    }
}

function getInitials(firstname, lastname) {
    const f = (firstname || '').charAt(0).toUpperCase();
    const l = (lastname || '').charAt(0).toUpperCase();
    return f + l || '?';
}

function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
}

function render(data) {
    currentData = data;
    const isFound = data.found === true;
    const hasEmployee = data.employee !== null && data.employee !== undefined;

    // Update scanned time (always update)
    if (data.scanned_at) {
        scannedAt.textContent = formatDate(data.scanned_at);
    } else {
        scannedAt.textContent = 'Waiting for scan...';
    }

    // Update last updated time
    lastUpdated.textContent = 'Updated: ' + new Date().toLocaleTimeString('en-PH', { hour12: true });

    // Check if RFID changed or if we need to switch states
    const rfidChanged = (data.rfid !== currentRfid);
    const stateChanged = (isFound && hasEmployee) !== employeeCard.classList.contains('visible');

    if (rfidChanged || stateChanged || isFirstLoad) {
        currentRfid = data.rfid;

        if (isFound && hasEmployee) {
            renderEmployee(data.employee);
            employeeCard.classList.add('visible');
            noData.style.display = 'none';
        } else if (data.rfid && !isFound) {
            renderUnknownEmployee(data.rfid, data.scanned_at);
            employeeCard.classList.add('visible');
            noData.style.display = 'none';
        } else {
            employeeCard.classList.remove('visible');
            noData.style.display = 'flex';
        }

        // Update status
        if (isFound && hasEmployee) {
            statusDot.className = 'status-dot online';
            statusText.textContent = 'Employee registered';
        } else if (data.rfid && !isFound) {
            statusDot.className = 'status-dot unknown';
            statusText.textContent = 'Employee not registered';
        } else {
            statusDot.className = 'status-dot offline';
            statusText.textContent = 'Waiting for scan';
        }

        isFirstLoad = false;
    }
}

function renderEmployee(emp) {
    const fullname = (emp.firstname || '') + ' ' + (emp.lastname || '');
    const initials = getInitials(emp.firstname, emp.lastname);
    const role = emp.role || 'employee';
    const roleLabel = role.charAt(0).toUpperCase() + role.slice(1);
    const scannedTime = currentData.scanned_at ? formatTime(currentData.scanned_at) : '--';
    const currentTime = getCurrentTime();

    // Only rebuild HTML if employee data changed
    const currentHtml = employeeCard.innerHTML;
    const newHtml = `
        <div class="profile-section">
            <div class="profile-avatar">
                ${emp.image ? `<img src="${emp.image}" alt="${fullname}" onerror="this.style.display='none';this.parentElement.textContent='${initials}';">` : `<span class="initials-text">${initials}</span>`}
            </div>
            <div class="profile-info">
                <div class="fullname">${fullname || 'Unknown'}</div>
                <span class="role-badge">${roleLabel}</span>
                <div class="id-row">
                    <span>
                        <span class="label">Employee ID:</span>
                        <span class="value">${emp.employeeid || 'N/A'}</span>
                    </span>
                    <span>
                        <span class="label">RFID:</span>
                        <span class="value">${emp.rfid || 'N/A'}</span>
                    </span>
                </div>
            </div>
        </div>
        <div class="time-section">
            <div class="time-item">
                <div class="label">Time In</div>
                <div class="value clock-in" id="timeInValue">${scannedTime}</div>
            </div>
            <div class="time-item">
                <div class="label">Current Time</div>
                <div class="value" id="currentTimeDisplay">${currentTime}</div>
            </div>
        </div>
    `;

    // Only update if HTML changed
    if (currentHtml !== newHtml) {
        employeeCard.innerHTML = newHtml;
    } else {
        // Just update the time values without re-rendering
        const timeInElem = document.getElementById('timeInValue');
        const currentTimeElem = document.getElementById('currentTimeDisplay');
        if (timeInElem) timeInElem.textContent = scannedTime;
        if (currentTimeElem) currentTimeElem.textContent = currentTime;
    }

    // Keep current time updating
    const currentTimeDisplay = document.getElementById('currentTimeDisplay');
    if (currentTimeDisplay) {
        if (window._timeInterval) {
            clearInterval(window._timeInterval);
        }
        window._timeInterval = setInterval(() => {
            const elem = document.getElementById('currentTimeDisplay');
            if (elem) elem.textContent = getCurrentTime();
        }, 1000);
    }
}

function renderUnknownEmployee(rfid, scannedAtTime) {
    const scannedTime = scannedAtTime ? formatTime(scannedAtTime) : '--';
    const currentTime = getCurrentTime();

    const currentHtml = employeeCard.innerHTML;
    const newHtml = `
        <div class="profile-section">
            <div class="profile-avatar unknown-avatar">
                <span class="initials-text">❓</span>
            </div>
            <div class="profile-info">
                <div class="fullname unknown-name">Unknown</div>
                <span class="role-badge unknown">Unknown</span>
                <div class="id-row">
                    <span>
                        <span class="label">Employee ID:</span>
                        <span class="value unknown-value">—</span>
                    </span>
                    <span>
                        <span class="label">RFID:</span>
                        <span class="value unknown-value">${rfid || 'N/A'}</span>
                    </span>
                </div>
            </div>
        </div>
        <div class="time-section">
            <div class="time-item">
                <div class="label">Time In</div>
                <div class="value clock-in" id="timeInValueUnknown">${scannedTime}</div>
            </div>
            <div class="time-item">
                <div class="label">Current Time</div>
                <div class="value" id="currentTimeDisplayUnknown">${currentTime}</div>
            </div>
        </div>
    `;

    if (currentHtml !== newHtml) {
        employeeCard.innerHTML = newHtml;
    } else {
        const timeInElem = document.getElementById('timeInValueUnknown');
        const currentTimeElem = document.getElementById('currentTimeDisplayUnknown');
        if (timeInElem) timeInElem.textContent = scannedTime;
        if (currentTimeElem) currentTimeElem.textContent = currentTime;
    }

    const currentTimeDisplay = document.getElementById('currentTimeDisplayUnknown');
    if (currentTimeDisplay) {
        if (window._timeInterval) {
            clearInterval(window._timeInterval);
        }
        window._timeInterval = setInterval(() => {
            const elem = document.getElementById('currentTimeDisplayUnknown');
            if (elem) elem.textContent = getCurrentTime();
        }, 1000);
    }
}

async function fetchData() {
    try {
        const response = await fetch(API_URL, {
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'success') {
            render(data);
        } else {
            console.warn('API returned non-success status:', data);
        }
    } catch (error) {
        console.error('Fetch error:', error);
        statusDot.className = 'status-dot offline';
        statusText.textContent = 'Connection error';
        if (isFirstLoad) {
            scannedAt.textContent = 'Unable to connect to server';
        }
    }
}

function startPolling() {
    loadLogo();
    loadProfileIcon();
    fetchData();
    setInterval(fetchData, POLL_INTERVAL);
}

document.addEventListener('DOMContentLoaded', startPolling);

document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        fetchData();
    }
});