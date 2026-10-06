// Config (written by Terraform to /config.json), Cognito auth via its public JSON API, and API calls.
let config = null;

export async function loadConfig() {
  if (!config) {
    const res = await fetch("/config.json", { cache: "no-store" });
    if (!res.ok) throw new Error("config.json missing - copy public/config.example.json to public/config.json");
    config = await res.json();
  }
  return config;
}

// ---------------- Cognito (no SDK needed) ----------------
const TOKENS = "phytro.tokens";

async function cognito(action, body) {
  const res = await fetch(`https://cognito-idp.${config.region}.amazonaws.com/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-amz-json-1.1",
      "X-Amz-Target": `AWSCognitoIdentityProviderService.${action}`,
    },
    body: JSON.stringify({ ClientId: config.clientId, ...body }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const friendly = {
      UserNotConfirmedException: "Please confirm your email first - check your inbox for the code.",
      NotAuthorizedException: "Incorrect email or password.",
      UsernameExistsException: "An account with this email already exists. Try signing in.",
      CodeMismatchException: "That code doesn't match. Check the latest email.",
      InvalidPasswordException: "Password needs 8+ characters with upper-case, lower-case and a number.",
      LimitExceededException: "Too many attempts. Wait a few minutes and try again.",
    };
    const type = (data.__type || "").split("#").pop();
    const err = new Error(friendly[type] || data.message || "Sign-in service error");
    err.type = type;
    throw err;
  }
  return data;
}

function decode(jwt) {
  const b = jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(b));
}

function saveTokens(result, refresh) {
  const t = {
    idToken: result.IdToken,
    refreshToken: result.RefreshToken || refresh,
    expires: Date.now() + (result.ExpiresIn - 60) * 1000,
  };
  localStorage.setItem(TOKENS, JSON.stringify(t));
  return t;
}

export const auth = {
  user() {
    const t = JSON.parse(localStorage.getItem(TOKENS) || "null");
    if (!t) return null;
    const claims = decode(t.idToken);
    return { email: claims.email, sub: claims.sub };
  },
  async signIn(email, password) {
    const r = await cognito("InitiateAuth", {
      AuthFlow: "USER_PASSWORD_AUTH",
      AuthParameters: { USERNAME: email, PASSWORD: password },
    });
    saveTokens(r.AuthenticationResult);
  },
  signUp: (email, password) =>
    cognito("SignUp", { Username: email, Password: password, UserAttributes: [{ Name: "email", Value: email }] }),
  confirm: (email, code) => cognito("ConfirmSignUp", { Username: email, ConfirmationCode: code }),
  resend: (email) => cognito("ResendConfirmationCode", { Username: email }),
  forgot: (email) => cognito("ForgotPassword", { Username: email }),
  reset: (email, code, password) =>
    cognito("ConfirmForgotPassword", { Username: email, ConfirmationCode: code, Password: password }),
  signOut() {
    localStorage.removeItem(TOKENS);
  },
  async token() {
    let t = JSON.parse(localStorage.getItem(TOKENS) || "null");
    if (!t) throw new Error("signed out");
    if (Date.now() > t.expires) {
      try {
        const r = await cognito("InitiateAuth", {
          AuthFlow: "REFRESH_TOKEN_AUTH",
          AuthParameters: { REFRESH_TOKEN: t.refreshToken },
        });
        t = saveTokens(r.AuthenticationResult, t.refreshToken);
      } catch {
        auth.signOut();
        window.location.assign("/");
        throw new Error("Session expired - please sign in again.");
      }
    }
    return t.idToken;
  },
};

// ---------------- PhyTro API ----------------
async function call(method, path, body) {
  const token = await auth.token();
  const res = await fetch(`${config.apiUrl}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) {
    auth.signOut();
    window.location.assign("/");
  }
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

export const api = {
  meta: () => call("GET", "/meta"),
  profile: () => call("GET", "/profile"),
  saveProfile: (p) => call("PUT", "/profile", p),
  browse: (store, category) =>
    call("GET", `/browse?store=${encodeURIComponent(store)}&category=${encodeURIComponent(category)}`),
  search: (q, store) => call("GET", `/search?q=${encodeURIComponent(q)}&store=${encodeURIComponent(store)}`),
  product: (code) => call("GET", `/products/${code}`),
  list: () => call("GET", "/list"),
  saveItem: (item) => call("PUT", `/list/${item.barcode}`, item),
  removeItem: (code) => call("DELETE", `/list/${code}`),
  analyze: (barcode, store, autoAdd) => call("POST", "/analyze", { barcode, store, auto_add: autoAdd }),
  job: (id) => call("GET", `/jobs/${id}`),
};
