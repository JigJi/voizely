const TOKEN_KEY = 'token';
const USER_KEY = 'user';

function getStorage(remember) {
  return remember ? localStorage : sessionStorage;
}

function getBothStorages() {
  return [localStorage, sessionStorage];
}

export function setToken(token, remember = true) {
  getStorage(remember).setItem(TOKEN_KEY, token);
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
}

export function setUser(user, remember = true) {
  getStorage(remember).setItem(USER_KEY, JSON.stringify(user));
}

export function getUser() {
  const raw = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function logout() {
  for (const s of getBothStorages()) {
    s.removeItem(TOKEN_KEY);
    s.removeItem(USER_KEY);
  }
  window.location.href = '/login';
}

export function isLoggedIn() {
  return !!getToken();
}

export async function login(username, password) {
  const form = new URLSearchParams();
  form.append('username', username);
  form.append('password', password);

  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Login failed');
  }

  return res.json();
}
