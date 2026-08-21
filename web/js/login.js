const form = document.getElementById('loginForm');
const message = document.getElementById('formMessage');
const apiBaseUrl = window.TAPIN_API_URL || 'https://tapin-api.up.railway.app';
const submitButton = form ? form.querySelector('button[type="submit"]') : null;
const rememberInput = form ? form.querySelector('input[name="remember"]') : null;
const passwordInput = form ? form.querySelector('input[name="password"]') : null;
const passwordToggle = form ? document.getElementById('passwordToggle') : null;
const passwordToggleIcon = passwordToggle ? passwordToggle.querySelector('i') : null;

if (form) {
passwordToggle.addEventListener('click', () => {
    const showingPassword = passwordInput.type === 'text';
    passwordInput.type = showingPassword ? 'password' : 'text';
    passwordToggleIcon.className = showingPassword ? 'fa-solid fa-eye' : 'fa-solid fa-eye-slash';
    passwordToggle.setAttribute('aria-label', showingPassword ? 'Show password' : 'Hide password');
    passwordToggle.setAttribute('title', showingPassword ? 'Show password' : 'Hide password');
});

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
    submitButton.classList.add('is-loading');
    submitButton.setAttribute('aria-busy', 'true');

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
        submitButton.classList.remove('is-loading');
        submitButton.removeAttribute('aria-busy');
}
});
}