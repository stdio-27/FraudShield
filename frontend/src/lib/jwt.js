/**
 * Read the (unverified) claims of a JWT for UI purposes only: showing who is
 * signed in and disabling controls the server would reject anyway.
 * Authorisation is always enforced by the API.
 */
export function decodeJwt(token) {
  try {
    const payload = token.split('.')[1];
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
        .join(''),
    );
    const claims = JSON.parse(json);
    return {
      email: claims.sub ?? null,
      role: claims.role ?? null,
      expiresAt: typeof claims.exp === 'number' ? claims.exp * 1000 : null,
    };
  } catch {
    return null;
  }
}
