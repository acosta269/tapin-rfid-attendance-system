const form = document.getElementById('loginForm');
const message = document.getElementById('formMessage');
const apiBaseUrl = window.TAPIN_API_URL || 'http://localhost:5000';
const submitButton = form ? form.querySelector('button[type="submit"]') : null;
const rememberInput = form ? form.querySelector('input[name="remember"]') : null;

if (form) {
const rememberedUsername = localStorage.getItem('tapinRememberedUsername');
if (rememberedUsername) {
    form.username.value = rememberedUsername;
    rememberInput.checked = true;
}

form.addEventListener('submit', async (e) => {
e.preventDefault();
const username = form.username.value.trim();
const pass = form.password.value;

if (!username || !pass) {
    message.textContent = 'Please enter both username and password.';
    message.className = 'form-message error';
    return;
}

message.textContent = 'Checking credentials...';
message.className = 'form-message pending';
submitButton.disabled = true;

try {
    const response = await fetch(`${apiBaseUrl}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username, password: pass })
    });
    const result = await response.json();

    if (!response.ok || result.status !== 'success') {
        throw new Error(result.message || 'Username or password is incorrect.');
    }

    localStorage.setItem('tapinUser', JSON.stringify(result.user));
    if (rememberInput.checked) {
        localStorage.setItem('tapinRememberedUsername', username);
    } else {
        localStorage.removeItem('tapinRememberedUsername');
    }
    window.location.href = result.redirect;
} catch (error) {
    message.textContent = error.message || 'Unable to connect to the server.';
    message.className = 'form-message error';
    submitButton.disabled = false;
}
});
}