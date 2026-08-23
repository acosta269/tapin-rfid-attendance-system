const employeeApiBaseUrl = window.TAPIN_API_URL || 'https://tapin-api.up.railway.app';

function employeeLoginRedirect() {
    localStorage.removeItem('tapinUser');
    window.location.replace('../login.html');
}

function setEmployeeText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value || '--';
}

async function loadEmployeeDashboard() {
    try {
        const sessionResponse = await fetch(`${employeeApiBaseUrl}/api/session`, { credentials: 'include', cache: 'no-store' });
        if (!sessionResponse.ok) {
            employeeLoginRedirect();
            return;
        }
        const sessionData = await sessionResponse.json();
        const user = sessionData.user;
        if ((user.role || '').toLowerCase() !== 'employee') {
            window.location.replace('./dashboard.html#admin-dashboard');
            return;
        }

        setEmployeeText('dashboardUserName', user.fullname || user.username);
        setEmployeeText('dashboardUserRole', 'EMPLOYEE');
        setEmployeeText('employeeUid', user.uid);
        setEmployeeText('employeeId', user.employeeid);
        setEmployeeText('employeeRfid', user.rfid);
        setEmployeeText('employeeRole', user.role);
        setEmployeeText('profileName', user.fullname || user.username);

        const dataResponse = await fetch(`${employeeApiBaseUrl}/api/get-latest-rfid`, { credentials: 'include', cache: 'no-store' });
        if (!dataResponse.ok) return;
        const data = await dataResponse.json();
        const latest = data.employee;
        const isMyScan = latest && latest.rfid === user.rfid;
        setEmployeeText('employeeLatestScan', isMyScan ? data.scanned_at : 'None');
        setEmployeeText('employeeStatus', isMyScan ? 'Present' : 'Absent');
        setEmployeeText('employeeActivity', isMyScan ? `RFID scan recorded at ${data.scanned_at}.` : 'No RFID scan received today.');
        setEmployeeText('attendanceMessage', isMyScan ? `Your latest scan was recorded at ${data.scanned_at}.` : 'Your attendance has not been recorded today.');
    } catch (error) {
        employeeLoginRedirect();
    }
}

const logoutLink = document.getElementById('tapinLogout');
if (logoutLink) {
    logoutLink.addEventListener('click', async (event) => {
        event.preventDefault();
        try {
            await fetch(`${employeeApiBaseUrl}/api/logout`, { method: 'POST', credentials: 'include' });
        } finally {
            employeeLoginRedirect();
        }
    });
}

function updateEmployeeClock() {
    const now = new Date();
    setEmployeeText('dashboardDate', now.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }));
    setEmployeeText('dashboardTime', now.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short' }));
}

history.replaceState({ employeeDashboard: true }, '', window.location.href);
window.addEventListener('popstate', () => history.pushState({ employeeDashboard: true }, '', window.location.href));
setInterval(updateEmployeeClock, 1000);
setInterval(loadEmployeeDashboard, 2000);
updateEmployeeClock();
loadEmployeeDashboard();
