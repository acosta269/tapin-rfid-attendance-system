const dashboardApiBaseUrl = window.TAPIN_API_URL || 'https://tapin-api.up.railway.app';

function redirectToLogin() {
    localStorage.removeItem('tapinUser');
    window.location.replace('../login.html');
}

function updateUserDisplay(user) {
    const name = document.getElementById('dashboardUserName');
    const role = document.getElementById('dashboardUserRole');
    if (name) name.textContent = user.fullname || user.username || 'User';
    if (role) role.textContent = (user.role || 'employee').toUpperCase();
}

function updateDeviceDisplay(devices) {
    const indicator = document.getElementById('readerStatusIndicator');
    const statusText = document.getElementById('readerStatusText');
    const online = devices.length > 0;

    if (indicator) {
        indicator.className = `status-indicator ${online ? 'status-online' : 'status-offline'}`;
    }
    if (statusText) {
        statusText.className = `status-text ${online ? 'text-online' : 'text-offline'}`;
        statusText.innerHTML = online
            ? '<i class="fa-solid fa-circle-check"></i> Online'
            : '<i class="fa-solid fa-circle-xmark"></i> Offline';
    }
}

function updateClock() {
    const now = new Date();
    const date = document.getElementById('dashboardDate');
    const time = document.getElementById('dashboardTime');
    if (date) date.textContent = now.toLocaleDateString(undefined, {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
    if (time) time.textContent = now.toLocaleTimeString(undefined, {
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
}

async function loadDashboardData() {
    try {
        const response = await fetch(`${dashboardApiBaseUrl}/api/get-latest-rfid`, {
            credentials: 'include',
            cache: 'no-store'
        });
        if (response.status === 401) {
            redirectToLogin();
            return;
        }
        if (!response.ok) throw new Error('Dashboard data unavailable');

        const data = await response.json();
        updateDeviceDisplay(data.devices || []);

        const latestScanTime = document.getElementById('latestScanTime');
        if (latestScanTime) {
            latestScanTime.textContent = data.scanned_at
                ? `${data.scanned_at}${data.employee ? ` - ${data.employee.firstname} ${data.employee.lastname}` : ''}`
                : 'No scan received';
        }
    } catch (error) {
        updateDeviceDisplay([]);
    }
}

async function verifyDashboardSession() {
    try {
        const response = await fetch(`${dashboardApiBaseUrl}/api/session`, {
            credentials: 'include',
            cache: 'no-store'
        });
        if (!response.ok) {
            redirectToLogin();
            return;
        }
        const data = await response.json();
        updateUserDisplay(data.user);
        await loadDashboardData();
    } catch (error) {
        redirectToLogin();
    }
}

const logoutLink = document.getElementById('tapinLogout');
if (logoutLink) {
    logoutLink.addEventListener('click', async (event) => {
        event.preventDefault();
        try {
            await fetch(`${dashboardApiBaseUrl}/api/logout`, {
                method: 'POST',
                credentials: 'include'
            });
        } finally {
            redirectToLogin();
        }
    });
}

history.replaceState({ dashboard: true }, '', window.location.href);
window.addEventListener('popstate', () => {
    history.pushState({ dashboard: true }, '', window.location.href);
});
window.addEventListener('pageshow', verifyDashboardSession);
setInterval(updateClock, 1000);
setInterval(loadDashboardData, 5000);
updateClock();
verifyDashboardSession();
