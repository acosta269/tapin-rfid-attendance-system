const authApiBaseUrl = window.TAPIN_API_URL || 'http://localhost:5000';

function redirectToLogin() {
    localStorage.removeItem('tapinUser');
    window.location.replace('../login.html');
}

async function verifySession() {
    try {
        const response = await fetch(`${authApiBaseUrl}/api/session`, {
            credentials: 'include',
            cache: 'no-store'
        });
        if (!response.ok) {
            redirectToLogin();
        }
    } catch (error) {
        redirectToLogin();
    }
}

history.replaceState({ dashboard: true }, '', window.location.href);
window.addEventListener('popstate', () => {
    history.pushState({ dashboard: true }, '', window.location.href);
});
window.addEventListener('pageshow', verifySession);

const logoutLink = document.getElementById('tapinLogout');
if (logoutLink) {
    logoutLink.addEventListener('click', async (event) => {
        event.preventDefault();
        try {
            await fetch(`${authApiBaseUrl}/api/logout`, {
                method: 'POST',
                credentials: 'include'
            });
        } finally {
            redirectToLogin();
        }
    });
}
