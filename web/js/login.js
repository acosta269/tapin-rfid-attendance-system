/* =========================================================
    DEMO ONLY — replace this whole block with a real backend call.

    In production:
    1. Send { username, password } to your server (e.g. POST /api/login).
    2. Server checks the credentials against the database and looks up
        the user's role (admin / hr / employee) stored in that record.
    3. Server responds with the role (or a session token that encodes it).
    4. Redirect based on the role THE SERVER returned — never trust
        a role guessed only from the username on the client side.

    The lookup table below just simulates step 2 so you can see the
    redirect logic working before your backend is ready.
========================================================= */

const demoUserDirectory = {
"admin":      { role: "admin",    redirect: "admin-dashboard.html" },
"jsantos":    { role: "hr",       redirect: "hr-dashboard.html" },
"hr.manager": { role: "hr",       redirect: "hr-dashboard.html" },
"emp001":     { role: "employee", redirect: "employee-dashboard.html" },
"emp002":     { role: "employee", redirect: "employee-dashboard.html" }
};

const form = document.getElementById('loginForm');
const message = document.getElementById('formMessage');

form.addEventListener('submit', (e) => {
e.preventDefault();
const username = form.username.value.trim();
const pass = form.password.value;

if (!username || !pass) {
    message.textContent = 'Please enter both username and password.';
    message.className = 'form-message error';
    return;
}

message.textContent = 'Checking credentials…';
message.className = 'form-message pending';

// Simulated lookup delay — this is where your real fetch() call goes.
setTimeout(() => {
    const match = demoUserDirectory[username.toLowerCase()];

    if (!match) {
    message.textContent = 'Username not found or password incorrect.';
    message.className = 'form-message error';
    return;
    }

    message.textContent = `Welcome — signing in as ${match.role}…`;
    message.className = 'form-message pending';

    setTimeout(() => {
    window.location.href = match.redirect;
    }, 700);
}, 600);
});