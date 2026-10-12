const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let me = null;

async function api(url, method = "GET", body) {
  const r = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || "Something went wrong.");
  return data;
}

function note(text, bad) {
  $("#msg").innerHTML = text ? `<div class="note ${bad ? "bad" : "ok"}">${esc(text)}</div>` : "";
}

const L = ["librarian"], ALL = ["librarian", "student", "member"];
const pages = {
  dashboard: { label: "Dashboard", roles: ALL, render: dashboard },
  "add-book": { label: "Add book", roles: L, render: addBook },
  books: { label: "Search books", roles: ALL, render: books },
  "add-user": { label: "Add student / user", roles: L, render: addUser },
  issue: { label: "Issue book", roles: L, render: issue },
  "return": { label: "Return book", roles: L, render: returnBook },
  status: { label: "Book availability", roles: ALL, render: status },
};

function show(key) {
  note("");
  document.querySelectorAll("#nav button").forEach(b => b.classList.toggle("on", b.dataset.k === key));
  $("#title").textContent = pages[key].label;
  $("#page").innerHTML = "";
  $("#page").onclick = null;
  pages[key].render().catch(e => note(e.message, true));
}

function start(user) {
  me = user;
  $("#login-view").classList.add("hidden");
  $("#app-view").classList.remove("hidden");
  $("#who").textContent = `${user.name} (${user.role})`;
  $("#nav").innerHTML = Object.entries(pages).filter(([, p]) => p.roles.includes(user.role))
    .map(([k, p]) => `<button data-k="${k}">${p.label}</button>`).join("");
  show("dashboard");
}

$("#nav").onclick = e => e.target.dataset.k && show(e.target.dataset.k);

$("#login-form").onsubmit = async e => {
  e.preventDefault();
  const btn = $("#login-btn");
  $("#login-error").textContent = "";
  btn.disabled = true; btn.textContent = "Logging in...";
  try {
    start(await api("/api/login", "POST", Object.fromEntries(new FormData(e.target))));
    e.target.reset();
  } catch (err) {
    $("#login-error").textContent = err.message;
    e.target.password.value = ""; e.target.password.focus();
  }
  btn.disabled = false; btn.textContent = "Log in";
};

$("#toggle-pw").onclick = e => {
  const p = $("#login-form").password, show = p.type === "password";
  p.type = show ? "text" : "password";
  e.target.textContent = show ? "Hide" : "Show";
};

$("#logout").onclick = async () => { await api("/api/logout", "POST"); location.reload(); };

api("/api/me").then(start).catch(() => {});

function form(fields, label, onSubmit) {
  $("#page").innerHTML = `<form class="card" id="f">${fields.map(f =>
    `<label>${f.label}${f.html || `<input name="${f.name}" type="${f.type || "text"}" ${f.optional ? "" : "required"} ${f.attr || ""}>`}</label>`).join("")}<button>${label}</button></form>`;
  $("#f").onsubmit = async e => {
    e.preventDefault();
    try { await onSubmit(Object.fromEntries(new FormData(e.target))); } catch (err) { note(err.message, true); }
  };
}

function loanTable(rows, withReturn) {
  if (!rows.length) return `<p class="empty">No books are issued right now.</p>`;
  return `<div class="table-wrap"><table><tr><th>Book</th><th>Borrower</th><th>Issued</th><th>Due</th>${withReturn ? "<th></th>" : ""}</tr>${rows.map(r =>
    `<tr><td>${esc(r.title)}</td><td>${esc(r.full_name)}</td><td>${r.issue_date}</td><td>${r.due_date} ${r.overdue ? '<span class="tag bad">Overdue</span>' : ""}</td>${withReturn ? `<td><button class="small" data-return="${r.id}">Return</button></td>` : ""}</tr>`).join("")}</table></div>`;
}

function bookTable(rows) {
  if (!rows.length) return `<p class="empty">No books match.</p>`;
  return `<div class="table-wrap"><table><tr><th>Title</th><th>Author</th><th>ISBN</th><th>Category</th><th>Copies</th><th>Status</th></tr>${rows.map(b =>
    `<tr><td>${esc(b.title)}</td><td>${esc(b.author)}</td><td>${esc(b.isbn)}</td><td>${esc(b.category)}</td><td>${b.available_copies} of ${b.total_copies}</td><td><span class="tag ${b.available_copies ? "" : "bad"}">${b.available_copies ? "Available" : "All issued"}</span></td></tr>`).join("")}</table></div>`;
}

async function dashboard() {
  const [s, loans] = await Promise.all([api("/api/stats"), api("/api/issues")]);
  const tiles = [["Book titles", s.titles], ["Copies available", s.available], ["Books issued", s.issued], ["Overdue", s.overdue], ["Members", s.members]];
  $("#page").innerHTML = `<div class="tiles">${tiles.map(([l, v]) =>
    `<div class="tile ${l === "Overdue" && v > 0 ? "warn" : ""}"><b>${v}</b><span>${l}</span></div>`).join("")}</div>
    <h3>${me.role === "librarian" ? "Books currently issued" : "Your books"}</h3>${loanTable(loans)}`;
}

async function addBook() {
  form([
    { label: "Title", name: "title" },
    { label: "Author", name: "author" },
    { label: "ISBN", name: "isbn", optional: true },
    { label: "Category", name: "category", optional: true },
    { label: "Number of copies", name: "copies", type: "number", attr: 'value="1" min="1"' },
  ], "Add book", async d => { await api("/api/books", "POST", d); note("Book added."); $("#f").reset(); });
}

async function books() {
  $("#page").innerHTML = `<input id="q" class="search" placeholder="Search by title, author, ISBN or category"><div id="res"></div>`;
  const load = async () => { $("#res").innerHTML = bookTable(await api("/api/books?q=" + encodeURIComponent($("#q").value))); };
  $("#q").oninput = () => load().catch(e => note(e.message, true));
  await load();
}

async function addUser() {
  form([
    { label: "Full name", name: "full_name" },
    { label: "Username", name: "username" },
    { label: "Email", name: "email", type: "email", optional: true },
    { label: "Password", name: "password", type: "password", attr: 'minlength="6"' },
    { label: "User type", html: `<select name="role"><option value="student">Student</option><option value="member">Member</option><option value="librarian">Librarian</option></select>` },
  ], "Add user", async d => { await api("/api/users", "POST", d); note("User added."); $("#f").reset(); });
}

async function issue() {
  const [bk, us] = await Promise.all([api("/api/books?q="), api("/api/users")]);
  const avail = bk.filter(b => b.available_copies > 0);
  const people = us.filter(u => u.role !== "librarian");
  if (!avail.length || !people.length) {
    $("#page").innerHTML = `<p class="empty">${!avail.length ? "No copies are available to issue." : "Add a student or member first."}</p>`;
    return;
  }
  form([
    { label: "Book", html: `<select name="book_id">${avail.map(b => `<option value="${b.id}">${esc(b.title)} (${b.available_copies} left)</option>`).join("")}</select>` },
    { label: "Borrower", html: `<select name="user_id">${people.map(u => `<option value="${u.id}">${esc(u.full_name)} (${esc(u.username)})</option>`).join("")}</select>` },
    { label: "Loan period (days)", name: "days", type: "number", attr: 'value="14" min="1" max="90"' },
  ], "Issue book", async d => { await api("/api/issue", "POST", d); await issue(); note("Book issued."); });
}

async function returnBook() {
  const rows = await api("/api/issues");
  $("#page").innerHTML = loanTable(rows, true);
  $("#page").onclick = async e => {
    const id = e.target.dataset.return;
    if (!id) return;
    try { await api("/api/return", "POST", { issue_id: id }); await returnBook(); note("Book returned."); }
    catch (err) { note(err.message, true); }
  };
}

async function status() {
  $("#page").innerHTML = `<label style="max-width:240px">Show<select id="flt"><option value="all">All books</option><option value="in">Available</option><option value="out">All issued</option></select></label><div id="res"></div>`;
  const rows = await api("/api/books?q=");
  const draw = () => {
    const f = $("#flt").value;
    $("#res").innerHTML = bookTable(rows.filter(b => f === "all" || (f === "in") === b.available_copies > 0));
  };
  $("#flt").onchange = draw;
  draw();
}
