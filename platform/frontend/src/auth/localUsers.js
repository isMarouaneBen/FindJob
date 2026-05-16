// Prototype-only credential store. PASSWORDS ARE STORED IN PLAIN TEXT in
// localStorage — replace with a real backend (POST /auth/register,
// /auth/login returning a JWT) before shipping.

const USERS_KEY = "findjob.users";

const readUsers = () => {
  try { return JSON.parse(localStorage.getItem(USERS_KEY) || "[]"); }
  catch { return []; }
};

const writeUsers = (users) =>
  localStorage.setItem(USERS_KEY, JSON.stringify(users));

export function registerLocal({ email, password, fullName }) {
  email = email.trim().toLowerCase();
  const users = readUsers();
  if (users.find((u) => u.email === email)) {
    throw new Error("An account with this email already exists.");
  }
  const user = {
    id: crypto.randomUUID(),
    email,
    fullName: fullName?.trim() || email,
    password,            // prototype only — never do this in production
    provider: "local",
    createdAt: new Date().toISOString(),
  };
  users.push(user);
  writeUsers(users);
  return toPublicUser(user);
}

export function loginLocal({ email, password }) {
  email = email.trim().toLowerCase();
  const user = readUsers().find((u) => u.email === email);
  if (!user || user.password !== password) {
    throw new Error("Invalid email or password.");
  }
  return toPublicUser(user);
}

function toPublicUser(u) {
  return {
    id: u.id,
    email: u.email,
    fullName: u.fullName,
    provider: u.provider,
    picture: u.picture || null,
  };
}
