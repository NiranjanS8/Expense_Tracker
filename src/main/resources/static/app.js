const API_BASE = "/api";
const STORAGE_KEY = "expense-tracker-ui-session";

const state = {
    authMode: "login",
    token: null,
    user: null,
    month: new Date().toISOString().slice(0, 7),
    categories: [],
    summary: null,
    categoryInsights: [],
    expenses: []
};

const elements = {
    authCard: document.getElementById("authCard"),
    appPanel: document.getElementById("appPanel"),
    authTitle: document.getElementById("authTitle"),
    authSubtitle: document.getElementById("authSubtitle"),
    authForm: document.getElementById("authForm"),
    fullNameField: document.getElementById("fullNameField"),
    fullName: document.getElementById("fullName"),
    email: document.getElementById("email"),
    password: document.getElementById("password"),
    authSubmit: document.getElementById("authSubmit"),
    authToggle: document.getElementById("authToggle"),
    demoFill: document.getElementById("demoFill"),
    authMessage: document.getElementById("authMessage"),
    monthFilter: document.getElementById("monthFilter"),
    welcomeTitle: document.getElementById("welcomeTitle"),
    welcomeMeta: document.getElementById("welcomeMeta"),
    refreshButton: document.getElementById("refreshButton"),
    logoutButton: document.getElementById("logoutButton"),
    monthlyTotal: document.getElementById("monthlyTotal"),
    transactionCount: document.getElementById("transactionCount"),
    topCategory: document.getElementById("topCategory"),
    topCategoryAmount: document.getElementById("topCategoryAmount"),
    budgetSignal: document.getElementById("budgetSignal"),
    budgetSignalFoot: document.getElementById("budgetSignalFoot"),
    categoryBreakdown: document.getElementById("categoryBreakdown"),
    expensesList: document.getElementById("expensesList"),
    loadExpensesButton: document.getElementById("loadExpensesButton"),
    expenseForm: document.getElementById("expenseForm"),
    amount: document.getElementById("amount"),
    expenseDate: document.getElementById("expenseDate"),
    categoryId: document.getElementById("categoryId"),
    paymentMethod: document.getElementById("paymentMethod"),
    description: document.getElementById("description"),
    expenseMessage: document.getElementById("expenseMessage")
};

function init() {
    restoreSession();
    bindEvents();
    elements.monthFilter.value = state.month;
    elements.expenseDate.value = new Date().toISOString().slice(0, 10);
    updateAuthMode();
    renderShell();
    if (state.token) {
        bootAuthenticatedView();
    }
}

function bindEvents() {
    elements.authToggle.addEventListener("click", () => {
        state.authMode = state.authMode === "login" ? "register" : "login";
        updateAuthMode();
        clearMessage(elements.authMessage);
    });

    elements.demoFill.addEventListener("click", () => {
        elements.email.value = "demo@expensetracker.com";
        elements.password.value = "Password@123";
        state.authMode = "login";
        updateAuthMode();
    });

    elements.authForm.addEventListener("submit", handleAuthSubmit);
    elements.expenseForm.addEventListener("submit", handleExpenseSubmit);
    elements.refreshButton.addEventListener("click", () => loadDashboardData(true));
    elements.loadExpensesButton.addEventListener("click", () => loadExpenses(true));
    elements.logoutButton.addEventListener("click", logout);
    elements.monthFilter.addEventListener("change", async (event) => {
        state.month = event.target.value;
        persistSession();
        await loadDashboardData(false);
    });
}

function updateAuthMode() {
    const isRegister = state.authMode === "register";
    elements.fullNameField.classList.toggle("hidden", !isRegister);
    elements.authTitle.textContent = isRegister ? "Create your account" : "Welcome back";
    elements.authSubtitle.textContent = isRegister
        ? "Set up your workspace and start logging expenses."
        : "Sign in to load your dashboard.";
    elements.authSubmit.textContent = isRegister ? "Create account" : "Sign in";
    elements.authToggle.textContent = isRegister
        ? "Already have an account? Sign in"
        : "Need an account? Register";
}

function renderShell() {
    const isAuthenticated = Boolean(state.token);
    elements.authCard.classList.toggle("hidden", isAuthenticated);
    elements.appPanel.classList.toggle("hidden", !isAuthenticated);
}

async function handleAuthSubmit(event) {
    event.preventDefault();
    setMessage(elements.authMessage, "Working...", false);

    const payload = {
        email: elements.email.value.trim(),
        password: elements.password.value
    };

    if (state.authMode === "register") {
        payload.fullName = elements.fullName.value.trim();
    }

    try {
        const endpoint = state.authMode === "register" ? "/auth/register" : "/auth/login";
        const response = await apiRequest(endpoint, {
            method: "POST",
            body: JSON.stringify(payload)
        }, false);

        state.token = response.accessToken;
        state.user = response.user;
        persistSession();
        renderShell();
        clearMessage(elements.authMessage);
        await bootAuthenticatedView();
    } catch (error) {
        setMessage(elements.authMessage, extractErrorMessage(error), true);
    }
}

async function bootAuthenticatedView() {
    try {
        await loadCategories();
        await loadCurrentUser();
        await loadDashboardData(false);
        await loadExpenses(false);
    } catch (error) {
        if (error.status === 401 || error.status === 403) {
            logout();
            setMessage(elements.authMessage, "Your session expired. Please sign in again.", true);
            return;
        }
        setMessage(elements.authMessage, extractErrorMessage(error), true);
    }
}

async function loadCurrentUser() {
    const user = await apiRequest("/users/me");
    state.user = user;
    persistSession();
    elements.welcomeTitle.textContent = `${user.fullName.split(" ")[0]}'s spending overview`;
    elements.welcomeMeta.textContent = `${user.email} | ${state.month}`;
}

async function loadCategories() {
    const categories = await apiRequest("/categories");
    state.categories = categories;
    const options = categories
        .map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`)
        .join("");
    elements.categoryId.innerHTML = options || `<option value="">No categories found</option>`;
}

async function loadDashboardData(showInlineMessage) {
    try {
        const [summary, categoryInsights] = await Promise.all([
            apiRequest(`/dashboard/summary?month=${encodeURIComponent(state.month)}&recentLimit=5`),
            apiRequest(`/dashboard/categories?month=${encodeURIComponent(state.month)}`)
        ]);

        state.summary = summary;
        state.categoryInsights = categoryInsights;
        renderMetrics();
        renderCategoryBreakdown();

        if (showInlineMessage) {
            setMessage(elements.expenseMessage, "Dashboard refreshed.", false);
        }
    } catch (error) {
        if (showInlineMessage) {
            setMessage(elements.expenseMessage, extractErrorMessage(error), true);
        }
    }
}

async function loadExpenses(showInlineMessage) {
    try {
        const expenses = await apiRequest("/expenses?page=0&size=8&sortBy=expenseDate&sortDir=desc");
        state.expenses = expenses.content || [];
        renderExpenses();
        if (showInlineMessage) {
            setMessage(elements.expenseMessage, "Expense list refreshed.", false);
        }
    } catch (error) {
        if (showInlineMessage) {
            setMessage(elements.expenseMessage, extractErrorMessage(error), true);
        }
    }
}

function renderMetrics() {
    const summary = state.summary;
    elements.monthlyTotal.textContent = formatCurrency(summary?.monthlyTotal ?? 0);
    elements.transactionCount.textContent = String(summary?.transactionCount ?? 0);

    const topCategory = state.categoryInsights[0];
    if (topCategory) {
        elements.topCategory.textContent = topCategory.categoryName;
        elements.topCategoryAmount.textContent = formatCurrency(topCategory.totalAmount);
        elements.budgetSignal.textContent = Number(topCategory.totalAmount) > 5000 ? "Heavy month" : "In control";
        elements.budgetSignalFoot.textContent = `${topCategory.categoryName} leads this month`;
    } else {
        elements.topCategory.textContent = "No data";
        elements.topCategoryAmount.textContent = "Add expenses to see trends";
        elements.budgetSignal.textContent = "In control";
        elements.budgetSignalFoot.textContent = "Waiting for more data";
    }
}

function renderCategoryBreakdown() {
    if (!state.categoryInsights.length) {
        elements.categoryBreakdown.className = "bar-list empty-state";
        elements.categoryBreakdown.textContent = "No category data yet.";
        return;
    }

    elements.categoryBreakdown.className = "bar-list";
    const maxAmount = Number(state.categoryInsights[0].totalAmount || 0) || 1;

    elements.categoryBreakdown.innerHTML = state.categoryInsights
        .slice(0, 6)
        .map((item) => {
            const width = Math.max(8, (Number(item.totalAmount) / maxAmount) * 100);
            return `
                <div class="bar-row">
                    <div class="bar-header">
                        <strong>${escapeHtml(item.categoryName)}</strong>
                        <span>${formatCurrency(item.totalAmount)}</span>
                    </div>
                    <div class="bar-track">
                        <div class="bar-fill" style="width:${width}%"></div>
                    </div>
                </div>
            `;
        })
        .join("");
}

function renderExpenses() {
    if (!state.expenses.length) {
        elements.expensesList.className = "expense-list empty-state";
        elements.expensesList.textContent = "No expenses yet.";
        return;
    }

    elements.expensesList.className = "expense-list";
    elements.expensesList.innerHTML = state.expenses.map((expense) => `
        <article class="expense-item">
            <div class="expense-main">
                <p class="expense-title">${escapeHtml(expense.description || expense.categoryName)}</p>
                <p class="expense-meta">${escapeHtml(expense.categoryName)} | ${formatDate(expense.expenseDate)}</p>
            </div>
            <strong class="expense-amount">${formatCurrency(expense.amount)}</strong>
            <span class="pill">${humanizePaymentMethod(expense.paymentMethod)}</span>
        </article>
    `).join("");
}

async function handleExpenseSubmit(event) {
    event.preventDefault();
    setMessage(elements.expenseMessage, "Saving expense...", false);

    const payload = {
        categoryId: Number(elements.categoryId.value),
        amount: Number(elements.amount.value).toFixed(2),
        expenseDate: elements.expenseDate.value,
        description: elements.description.value.trim() || null,
        paymentMethod: elements.paymentMethod.value
    };

    try {
        await apiRequest("/expenses", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        elements.expenseForm.reset();
        elements.expenseDate.value = new Date().toISOString().slice(0, 10);
        if (state.categories.length) {
            elements.categoryId.value = String(state.categories[0].id);
        }
        elements.paymentMethod.value = "CARD";
        setMessage(elements.expenseMessage, "Expense saved successfully.", false);

        await Promise.all([loadDashboardData(false), loadExpenses(false)]);
    } catch (error) {
        setMessage(elements.expenseMessage, extractErrorMessage(error), true);
    }
}

function logout() {
    state.token = null;
    state.user = null;
    state.summary = null;
    state.categoryInsights = [];
    state.expenses = [];
    window.localStorage.removeItem(STORAGE_KEY);
    renderShell();
    elements.authForm.reset();
    elements.expenseForm.reset();
    elements.expenseDate.value = new Date().toISOString().slice(0, 10);
    clearMessage(elements.authMessage);
    clearMessage(elements.expenseMessage);
}

async function apiRequest(path, options = {}, requiresAuth = true) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (requiresAuth && state.token) {
        headers.Authorization = `Bearer ${state.token}`;
    }

    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
        ? await response.json().catch(() => ({}))
        : await response.text();

    if (!response.ok) {
        const error = new Error(typeof payload === "string" ? payload : payload.message || "Request failed");
        error.status = response.status;
        error.payload = payload;
        throw error;
    }

    return payload;
}

function persistSession() {
    if (!state.token || !state.user) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        token: state.token,
        user: state.user,
        month: state.month
    }));
}

function restoreSession() {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;

    try {
        const session = JSON.parse(raw);
        state.token = session.token || null;
        state.user = session.user || null;
        state.month = session.month || state.month;
    } catch (error) {
        window.localStorage.removeItem(STORAGE_KEY);
    }
}

function setMessage(element, message, isError) {
    element.textContent = message;
    element.style.color = isError ? "#8b2f2f" : "#628141";
}

function clearMessage(element) {
    element.textContent = "";
}

function formatCurrency(value) {
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2
    }).format(Number(value || 0));
}

function formatDate(value) {
    return new Date(value).toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric"
    });
}

function humanizePaymentMethod(value) {
    return String(value || "")
        .toLowerCase()
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function extractErrorMessage(error) {
    if (error?.payload?.details?.length) {
        return error.payload.details.join(" | ");
    }
    return error?.payload?.message || error.message || "Something went wrong.";
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll("\"", "&quot;")
        .replaceAll("'", "&#39;");
}

init();
