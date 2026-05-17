/**
 * Per-user client-side storage helpers.
 *
 * The CV id and the form-built profile are stored in localStorage scoped by
 * the authenticated user's id (`findjob.cv:<user_id>` and
 * `findjob.profile:<user_id>`). Scoping prevents one user's data from
 * leaking to another user on the same browser.
 *
 * For unauthenticated reads (rare), we use the `"anon"` suffix.
 *
 * Migration: any legacy global keys (`findjob.cvId`, `findjob.profile`) are
 * wiped on app boot — see App.jsx / main.jsx bootstrap.
 */

const ns = (userId, slot) => `findjob.${slot}:${userId ?? "anon"}`;

export const cvKey      = (userId) => ns(userId, "cv");
export const profileKey = (userId) => ns(userId, "profile");

const safeGet = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const safeSet = (k, v) => { try { localStorage.setItem(k, v); } catch {} };
const safeDel = (k)    => { try { localStorage.removeItem(k); } catch {} };

export function getCV(userId) { return safeGet(cvKey(userId)); }
export function setCV(userId, id) { safeSet(cvKey(userId), id); }
export function clearCV(userId)   { safeDel(cvKey(userId)); }

export function getProfile(userId) {
  const raw = safeGet(profileKey(userId));
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}
export function setProfile(userId, p) { safeSet(profileKey(userId), JSON.stringify(p)); }
export function clearProfile(userId)  { safeDel(profileKey(userId)); }

export function hasCV(userId)      { return !!getCV(userId); }
export function hasProfile(userId) { return !!safeGet(profileKey(userId)); }

/**
 * Where should an authenticated user land next?
 *   - Has CV or profile → /recommendations
 *   - Otherwise         → /onboarding/cv
 */
export function nextStepFor(userId) {
  if (hasCV(userId) || hasProfile(userId)) return "/recommendations";
  return "/onboarding/cv";
}

/** Wipe legacy un-namespaced keys (called once on app boot). */
export function purgeLegacy() {
  ["findjob.cvId", "findjob.profile"].forEach(safeDel);
}
