// auth.js - Handles client-side authentication simulation using LocalStorage

const USERS_KEY = 'awd_users';
const SESSION_KEY = 'awd_session';

// Initialize default admin user if no users exist
function initDB() {
    let users = localStorage.getItem(USERS_KEY);
    if (!users) {
        users = [{ username: 'admin', password: 'admin' }];
        localStorage.setItem(USERS_KEY, JSON.stringify(users));
    }
}

// Check if user is logged in
function isAuthenticated() {
    return sessionStorage.getItem(SESSION_KEY) !== null;
}

// Protect routes that require authentication
function requireAuth() {
    if (!isAuthenticated()) {
        window.location.href = 'login.html';
    }
}

// Redirect away from auth pages if already logged in
function redirectIfAuth() {
    if (isAuthenticated()) {
        window.location.href = 'dashboard.html';
    }
}

// Handle Login
function login(username, password) {
    const users = JSON.parse(localStorage.getItem(USERS_KEY) || '[]');
    const user = users.find(u => u.username === username && u.password === password);
    
    if (user) {
        sessionStorage.setItem(SESSION_KEY, username);
        return true;
    }
    return false;
}

// Handle Registration
function register(username, password) {
    const users = JSON.parse(localStorage.getItem(USERS_KEY) || '[]');
    const exists = users.find(u => u.username === username);
    
    if (exists) {
        return false; // User already exists
    }
    
    users.push({ username, password });
    localStorage.setItem(USERS_KEY, JSON.stringify(users));
    return true;
}

// Handle Logout
function logout() {
    sessionStorage.removeItem(SESSION_KEY);
    window.location.href = 'login.html';
}

// Initialize the "Database"
initDB();
