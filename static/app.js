const $ = (id) => document.getElementById(id);
const tokenKey = "aviation_token";

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  const token = localStorage.getItem(tokenKey);
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(path, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Ошибка запроса");
  return data;
}

$("forecastForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    origin: $("origin").value.trim(),
    destination: $("destination").value.trim(),
    date: $("date").value,
    price: parseFloat($("price").value),
  };
  try {
    const r = await api("/api/forecast", { method: "POST", body: JSON.stringify(body) });
    $("result").hidden = false;
    $("rRoute").textContent = r.route_name;
    $("rDate").textContent = r.date;
    $("rSeats").textContent = r.seats;
    $("rWish").textContent = r.wish.toFixed(1);
    $("rBought").textContent = r.bought.toFixed(1);
    const c = await api("/api/chart", { method: "POST", body: JSON.stringify(body) });
    $("chartImg").src = c.image;
    $("chartCard").hidden = false;
  } catch (err) { alert(err.message); }
});

async function refreshAuth() {
  const token = localStorage.getItem(tokenKey);
  if (!token) return;
  try {
    const me = await api("/api/me");
    $("userLabel").textContent = " | " + me.username;
    $("logoutBtn").hidden = false;
    $("loginLink").hidden = true;
  } catch { localStorage.removeItem(tokenKey); }
}

$("logoutBtn").addEventListener("click", () => {
  localStorage.removeItem(tokenKey);
  location.reload();
});

refreshAuth();