export const API_BASE = "/api";
export const SESSION_KEY = "expense-tracker-react-session";
export const paymentMethods = [
  "CASH",
  "CARD",
  "UPI",
  "BANK_TRANSFER",
  "WALLET",
  "OTHER",
];
export const recurringFrequencies = ["WEEKLY", "MONTHLY"];
export const exportTypes = ["CSV", "PDF"];

export const initialAuth = {
  email: "",
  password: "",
  fullName: "",
};

export const initialExpense = {
  amount: "",
  expenseDate: new Date().toISOString().slice(0, 10),
  categoryId: "",
  paymentMethod: "UPI",
  description: "",
};

export const initialBudget = {
  amount: "",
  budgetMonth: new Date().toISOString().slice(0, 7),
};

export const initialGoal = {
  name: "",
  targetAmount: "",
  currentAmount: "",
  targetDate: "",
};

export const initialRecurring = {
  categoryId: "",
  amount: "",
  startDate: new Date().toISOString().slice(0, 10),
  description: "",
  paymentMethod: "UPI",
  frequency: "MONTHLY",
};

export const initialRule = {
  keyword: "",
  categoryId: "",
  active: true,
};

export const initialExportRequest = {
  type: "CSV",
  search: "",
  startDate: "",
  endDate: "",
};

export function loadSession() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
  } catch {
    return null;
  }
}

export function saveSession(session) {
  if (!session?.token) {
    localStorage.removeItem(SESSION_KEY);
    return;
  }

  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export function formatDate(value) {
  if (!value) {
    return "No date";
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export function humanize(value) {
  return String(value || "")
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function shiftMonth(month, direction) {
  const [year, monthValue] = month.split("-").map(Number);
  const date = new Date(year, monthValue - 1 + direction, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export function extractErrorMessage(error) {
  if (typeof error === "string") {
    return error;
  }

  if (error?.message) {
    return error.message;
  }

  return "Something went wrong. Please try again.";
}

export async function apiRequest(path, { method = "GET", token, body } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const errorBody = await response.json();
      throw new Error(
        errorBody.message || errorBody.error || errorBody.details || "Request failed",
      );
    }

    throw new Error(await response.text());
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}
