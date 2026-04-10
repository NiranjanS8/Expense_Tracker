import { useEffect, useMemo, useState } from "react";
import {
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  Receipt,
  Target,
  Wallet,
  X,
  Zap,
} from "lucide-react";
import AuthScreen from "./components/AuthScreen";
import AutomationSection from "./components/AutomationSection";
import BudgetsSection from "./components/BudgetsSection";
import ExpensesSection from "./components/ExpensesSection";
import GoalsSection from "./components/GoalsSection";
import OverviewSection from "./components/OverviewSection";
import ReportsSection from "./components/ReportsSection";
import {
  apiRequest,
  exportTypes,
  extractErrorMessage,
  initialAuth,
  initialBudget,
  initialExpense,
  initialExportRequest,
  initialGoal,
  initialRecurring,
  initialRule,
  loadSession,
  paymentMethods,
  recurringFrequencies,
  saveSession,
  shiftMonth,
} from "./lib";

const sections = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "expenses", label: "Expenses", icon: Receipt },
  { id: "budgets", label: "Budgets", icon: Wallet },
  { id: "goals", label: "Goals", icon: Target },
  { id: "automation", label: "Automation", icon: Zap },
  { id: "reports", label: "Reports", icon: FileText },
];

export default function App() {
  const session = loadSession();
  const [mode, setMode] = useState("login");
  const [showPassword, setShowPassword] = useState(false);
  const [authForm, setAuthForm] = useState(initialAuth);
  const [authMessage, setAuthMessage] = useState("");
  const [authError, setAuthError] = useState("");
  const [token, setToken] = useState(session?.token || "");
  const [user, setUser] = useState(session?.user || null);
  const [month, setMonth] = useState(session?.month || new Date().toISOString().slice(0, 7));
  const [activeSection, setActiveSection] = useState("overview");
  const [isMobile, setIsMobile] = useState(window.innerWidth < 1024);
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth >= 1024);
  const [loading, setLoading] = useState(false);
  const [globalMessage, setGlobalMessage] = useState("");

  const [categories, setCategories] = useState([]);
  const [summary, setSummary] = useState(null);
  const [categoryBreakdown, setCategoryBreakdown] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [expensesPage, setExpensesPage] = useState({
    page: 0,
    size: 5,
    totalElements: 0,
    totalPages: 0,
    first: true,
    last: true,
    empty: true,
  });
  const [expenseForm, setExpenseForm] = useState(initialExpense);
  const [expenseError, setExpenseError] = useState("");
  const [expenseMessage, setExpenseMessage] = useState("");
  const [expenseFilters, setExpenseFilters] = useState({
    search: "",
    categoryId: "",
    startDate: "",
    endDate: "",
  });
  const [overviewExpensePage, setOverviewExpensePage] = useState(0);

  const [budgetForm, setBudgetForm] = useState(initialBudget);
  const [budgetCurrent, setBudgetCurrent] = useState(null);
  const [budgetHistory, setBudgetHistory] = useState([]);
  const [budgetError, setBudgetError] = useState("");
  const [budgetMessage, setBudgetMessage] = useState("");

  const [goalForm, setGoalForm] = useState(initialGoal);
  const [goals, setGoals] = useState([]);
  const [goalError, setGoalError] = useState("");
  const [goalMessage, setGoalMessage] = useState("");

  const [recurringForm, setRecurringForm] = useState(initialRecurring);
  const [recurringRules, setRecurringRules] = useState([]);
  const [recurringError, setRecurringError] = useState("");
  const [recurringMessage, setRecurringMessage] = useState("");
  const [recurringGenerationMessage, setRecurringGenerationMessage] = useState("");

  const [ruleForm, setRuleForm] = useState(initialRule);
  const [smartRules, setSmartRules] = useState([]);
  const [ruleError, setRuleError] = useState("");
  const [ruleMessage, setRuleMessage] = useState("");

  const [insights, setInsights] = useState(null);
  const [exportRequest, setExportRequest] = useState(initialExportRequest);
  const [exportJobs, setExportJobs] = useState([]);
  const [exportError, setExportError] = useState("");
  const [exportMessage, setExportMessage] = useState("");
  const [emailPreference, setEmailPreference] = useState({
    email: session?.user?.email || "",
    enabled: true,
  });
  const [emailError, setEmailError] = useState("");
  const [emailMessage, setEmailMessage] = useState("");

  const monthLabel = useMemo(() => {
    const [year, monthValue] = month.split("-").map(Number);
    return new Intl.DateTimeFormat("en-IN", {
      month: "long",
      year: "numeric",
    }).format(new Date(year, monthValue - 1, 1));
  }, [month]);

  const canMoveToNextMonth = useMemo(() => {
    const currentMonth = new Date().toISOString().slice(0, 7);
    return month < currentMonth;
  }, [month]);

  useEffect(() => {
    saveSession({ token, user, month });
  }, [token, user, month]);

  useEffect(() => {
    function handleResize() {
      const mobile = window.innerWidth < 1024;
      setIsMobile(mobile);
      setSidebarOpen(!mobile);
    }

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!token) {
      return;
    }

    void bootApp();
  }, [token]);

  useEffect(() => {
    if (!token) {
      return;
    }

    void loadOverview();
  }, [month, overviewExpensePage]);

  useEffect(() => {
    if (!token) {
      return;
    }

    void loadSection(activeSection);
  }, [activeSection, token]);

  async function bootApp() {
    try {
      setLoading(true);
      const [profile, categoryList] = await Promise.all([
        apiRequest("/users/me", { token }),
        apiRequest("/categories", { token }),
      ]);

      setUser(profile);
      setCategories(categoryList);
      setEmailPreference((current) => ({
        ...current,
        email: current.email || profile.email || "",
      }));
      if (!expenseForm.categoryId && categoryList.length > 0) {
        setExpenseForm((current) => ({ ...current, categoryId: String(categoryList[0].id) }));
        setRecurringForm((current) => ({ ...current, categoryId: String(categoryList[0].id) }));
        setRuleForm((current) => ({ ...current, categoryId: String(categoryList[0].id) }));
      }

      await Promise.all([loadOverview(), loadBudgets(), loadGoals(), loadAutomation(), loadReports()]);
    } catch (error) {
      handleSessionExpiry(error);
    } finally {
      setLoading(false);
    }
  }

  async function loadSection(sectionId) {
    if (sectionId === "overview" || sectionId === "expenses") {
      await loadOverview();
      return;
    }
    if (sectionId === "budgets") {
      await loadBudgets();
      return;
    }
    if (sectionId === "goals") {
      await loadGoals();
      return;
    }
    if (sectionId === "automation") {
      await loadAutomation();
      return;
    }
    if (sectionId === "reports") {
      await loadReports();
    }
  }

  async function loadOverview() {
    try {
      const query = new URLSearchParams({
        page: String(overviewExpensePage),
        size: "5",
        sortBy: "expenseDate",
        sortDir: "desc",
      });
      if (expenseFilters.search) query.set("search", expenseFilters.search);
      if (expenseFilters.categoryId) query.set("categoryId", expenseFilters.categoryId);
      if (expenseFilters.startDate) query.set("startDate", expenseFilters.startDate);
      if (expenseFilters.endDate) query.set("endDate", expenseFilters.endDate);

      const [summaryResponse, categoryResponse, expenseResponse] = await Promise.all([
        apiRequest(`/dashboard/summary?month=${month}&recentLimit=6`, { token }),
        apiRequest(`/dashboard/categories?month=${month}`, { token }),
        apiRequest(`/expenses?${query.toString()}`, { token }),
      ]);
      setSummary(summaryResponse);
      setCategoryBreakdown(categoryResponse);
      setExpenses(expenseResponse.content || []);
      setExpensesPage({
        page: expenseResponse.page,
        size: expenseResponse.size,
        totalElements: expenseResponse.totalElements,
        totalPages: expenseResponse.totalPages,
        first: expenseResponse.first,
        last: expenseResponse.last,
        empty: expenseResponse.empty,
      });
    } catch (error) {
      handleSessionExpiry(error);
    }
  }

  async function loadBudgets() {
    try {
      const [currentBudget, history] = await Promise.all([
        apiRequest("/budgets/current", { token }),
        apiRequest("/budgets", { token }),
      ]);
      setBudgetCurrent(currentBudget);
      setBudgetHistory(history);
    } catch (error) {
      setBudgetError(extractErrorMessage(error));
    }
  }

  async function loadGoals() {
    try {
      setGoals(await apiRequest("/goals", { token }));
    } catch (error) {
      setGoalError(extractErrorMessage(error));
    }
  }

  async function loadAutomation() {
    try {
      const [recurring, rules] = await Promise.all([
        apiRequest("/recurring-expenses", { token }),
        apiRequest("/smart-category-rules", { token }),
      ]);
      setRecurringRules(recurring);
      setSmartRules(rules);
    } catch (error) {
      setRecurringError(extractErrorMessage(error));
    }
  }

  async function loadReports() {
    try {
      const [insightsResponse, jobs, preference] = await Promise.all([
        apiRequest(`/insights/summary?month=${month}`, { token }),
        apiRequest("/exports/jobs", { token }),
        apiRequest("/email-reports/preference", { token }),
      ]);
      setInsights(insightsResponse);
      setExportJobs(jobs);
      setEmailPreference(preference);
    } catch (error) {
      setExportError(extractErrorMessage(error));
    }
  }

  function handleSessionExpiry(error) {
    const message = extractErrorMessage(error);
    if (message.toLowerCase().includes("token") || message.toLowerCase().includes("unauthorized")) {
      logout("Your session expired. Please log in again.");
      return;
    }
    setGlobalMessage(message);
  }

  async function handleAuthSubmit(event) {
    event.preventDefault();
    setAuthError("");
    setAuthMessage("");
    try {
      const payload =
        mode === "register"
          ? authForm
          : { email: authForm.email, password: authForm.password };

      const response = await apiRequest(`/auth/${mode}`, { method: "POST", body: payload });
      setToken(response.accessToken);
      setUser(response.user);
      setAuthForm(initialAuth);
      setAuthMessage(mode === "register" ? "Account created." : "Welcome back.");
    } catch (error) {
      setAuthError(extractErrorMessage(error));
    }
  }

  async function handleExpenseSubmit(event) {
    event.preventDefault();
    setExpenseError("");
    setExpenseMessage("");
    try {
      await apiRequest("/expenses", {
        method: "POST",
        token,
        body: {
          ...expenseForm,
          amount: Number(expenseForm.amount),
          categoryId: Number(expenseForm.categoryId),
        },
      });
      setExpenseMessage("Expense added successfully.");
      setExpenseForm((current) => ({ ...initialExpense, categoryId: current.categoryId }));
      setOverviewExpensePage(0);
      await Promise.all([loadOverview(), loadBudgets(), loadReports()]);
    } catch (error) {
      setExpenseError(extractErrorMessage(error));
    }
  }

  async function handleDeleteExpense(id) {
    try {
      await apiRequest(`/expenses/${id}`, { method: "DELETE", token });
      await Promise.all([loadOverview(), loadBudgets(), loadReports()]);
    } catch (error) {
      setExpenseError(extractErrorMessage(error));
    }
  }

  async function handleBudgetSubmit(event) {
    event.preventDefault();
    setBudgetError("");
    setBudgetMessage("");
    try {
      await apiRequest(`/budgets/${budgetForm.budgetMonth}`, {
        method: "PUT",
        token,
        body: { amount: Number(budgetForm.amount), budgetMonth: budgetForm.budgetMonth },
      });
      setBudgetMessage("Budget saved.");
      await loadBudgets();
    } catch {
      try {
        await apiRequest("/budgets", {
          method: "POST",
          token,
          body: { amount: Number(budgetForm.amount), budgetMonth: budgetForm.budgetMonth },
        });
        setBudgetMessage("Budget created.");
        await loadBudgets();
      } catch (error) {
        setBudgetError(extractErrorMessage(error));
      }
    }
  }

  async function handleGoalSubmit(event) {
    event.preventDefault();
    setGoalError("");
    setGoalMessage("");
    try {
      await apiRequest("/goals", {
        method: "POST",
        token,
        body: {
          ...goalForm,
          targetAmount: Number(goalForm.targetAmount),
          currentAmount: Number(goalForm.currentAmount),
        },
      });
      setGoalForm(initialGoal);
      setGoalMessage("Goal saved.");
      await loadGoals();
    } catch (error) {
      setGoalError(extractErrorMessage(error));
    }
  }

  async function handleDeleteGoal(id) {
    try {
      await apiRequest(`/goals/${id}`, { method: "DELETE", token });
      await loadGoals();
    } catch (error) {
      setGoalError(extractErrorMessage(error));
    }
  }

  async function handleRecurringSubmit(event) {
    event.preventDefault();
    setRecurringError("");
    setRecurringMessage("");
    try {
      await apiRequest("/recurring-expenses", {
        method: "POST",
        token,
        body: {
          ...recurringForm,
          categoryId: Number(recurringForm.categoryId),
          amount: Number(recurringForm.amount),
        },
      });
      setRecurringForm((current) => ({ ...initialRecurring, categoryId: current.categoryId }));
      setRecurringMessage("Recurring rule saved.");
      await loadAutomation();
    } catch (error) {
      setRecurringError(extractErrorMessage(error));
    }
  }

  async function handleToggleRecurring(rule) {
    try {
      await apiRequest(`/recurring-expenses/${rule.id}/status`, {
        method: "PATCH",
        token,
        body: { active: !rule.active },
      });
      await loadAutomation();
    } catch (error) {
      setRecurringError(extractErrorMessage(error));
    }
  }

  async function handleGenerateRecurring() {
    try {
      const response = await apiRequest(`/recurring-expenses/generate?runDate=${new Date().toISOString().slice(0, 10)}`, {
        method: "POST",
        token,
      });
      setRecurringGenerationMessage(
        `${response.expensesGenerated} expenses generated from ${response.recurringRulesProcessed} recurring rules.`,
      );
      await Promise.all([loadAutomation(), loadOverview(), loadBudgets(), loadReports()]);
    } catch (error) {
      setRecurringError(extractErrorMessage(error));
    }
  }

  async function handleRuleSubmit(event) {
    event.preventDefault();
    setRuleError("");
    setRuleMessage("");
    try {
      await apiRequest("/smart-category-rules", {
        method: "POST",
        token,
        body: {
          ...ruleForm,
          categoryId: Number(ruleForm.categoryId),
          active: Boolean(ruleForm.active),
        },
      });
      setRuleForm((current) => ({ ...initialRule, categoryId: current.categoryId }));
      setRuleMessage("Smart category rule saved.");
      await loadAutomation();
    } catch (error) {
      setRuleError(extractErrorMessage(error));
    }
  }

  async function handleDeleteRule(id) {
    try {
      await apiRequest(`/smart-category-rules/${id}`, { method: "DELETE", token });
      await loadAutomation();
    } catch (error) {
      setRuleError(extractErrorMessage(error));
    }
  }

  async function handleExportSubmit(event) {
    event.preventDefault();
    setExportError("");
    setExportMessage("");
    try {
      await apiRequest("/exports/jobs", {
        method: "POST",
        token,
        body: {
          ...exportRequest,
          search: exportRequest.search || null,
          startDate: exportRequest.startDate || null,
          endDate: exportRequest.endDate || null,
        },
      });
      setExportMessage("Export job queued.");
      await loadReports();
    } catch (error) {
      setExportError(extractErrorMessage(error));
    }
  }

  async function handleDownloadExport(jobId) {
    const response = await fetch(`/api/exports/jobs/${jobId}/download`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `expense-export-${jobId}`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function handleEmailPreferenceSubmit(event) {
    event.preventDefault();
    setEmailError("");
    setEmailMessage("");
    try {
      const response = await apiRequest("/email-reports/preference", {
        method: "PUT",
        token,
        body: emailPreference,
      });
      setEmailPreference(response);
      setEmailMessage("Email preference saved.");
    } catch (error) {
      setEmailError(extractErrorMessage(error));
    }
  }

  async function handleSendEmailReport() {
    try {
      const response = await apiRequest(`/email-reports/send?month=${month}`, {
        method: "POST",
        token,
      });
      setEmailMessage(response.message);
    } catch (error) {
      setEmailError(extractErrorMessage(error));
    }
  }

  function logout(message = "") {
    setToken("");
    setUser(null);
    setActiveSection("overview");
    setGlobalMessage(message);
  }

  if (!token) {
    return (
      <AuthScreen
        mode={mode}
        setMode={setMode}
        authForm={authForm}
        setAuthForm={setAuthForm}
        showPassword={showPassword}
        setShowPassword={setShowPassword}
        authError={authError || globalMessage}
        authMessage={authMessage}
        handleAuthSubmit={handleAuthSubmit}
      />
    );
  }

  return (
    <main className="shell app-shell">
      {isMobile && sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      <aside className={`glass-panel sidebar ${sidebarOpen ? "is-open" : ""}`}>
        <div className="sidebar__brand">
          <span className="eyebrow">Expense Tracker</span>
          <h2>Finova</h2>
          <p className="muted">{user?.email}</p>
        </div>

        <nav className="sidebar__nav">
          {sections.map((section) => {
            const Icon = section.icon;
            return (
              <button
                key={section.id}
                className={`nav-button ${activeSection === section.id ? "is-active" : ""}`}
                type="button"
                onClick={() => {
                  setActiveSection(section.id);
                  if (isMobile) {
                    setSidebarOpen(false);
                  }
                }}
              >
                <Icon size={16} />
                {section.label}
              </button>
            );
          })}
        </nav>

        <div className="sidebar__footer muted">
          <button className="ghost-button sidebar__logout" type="button" onClick={() => logout()}>
            <LogOut size={16} />
            Logout
          </button>
          <p>© 2026 Finova</p>
        </div>
      </aside>

      <section className="dashboard-shell">
        {isMobile && (
          <header className="dashboard-header glass-panel">
            <div className="header-left">
              <button className="ghost-button icon-only" type="button" onClick={() => setSidebarOpen((value) => !value)}>
                {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
              </button>
              <span className="dashboard-header__title">{sections.find((section) => section.id === activeSection)?.label || "Overview"}</span>
            </div>
          </header>
        )}

        {globalMessage && <p className="form-success">{globalMessage}</p>}

        {activeSection === "overview" && (
          <OverviewSection
            loading={loading}
            summary={summary}
            categoryBreakdown={categoryBreakdown}
            expenses={expenses}
            expensesPage={expensesPage}
            setOverviewExpensePage={setOverviewExpensePage}
            categories={categories}
            expenseForm={expenseForm}
            setExpenseForm={setExpenseForm}
            expenseError={expenseError}
            expenseMessage={expenseMessage}
            handleExpenseSubmit={handleExpenseSubmit}
            paymentMethods={paymentMethods}
            monthLabel={monthLabel}
            onPreviousMonth={() => setMonth((current) => shiftMonth(current, -1))}
            onNextMonth={() => setMonth((current) => shiftMonth(current, 1))}
            canMoveToNextMonth={canMoveToNextMonth}
          />
        )}

        {activeSection === "expenses" && (
          <ExpensesSection
            expenses={expenses}
            categories={categories}
            filters={expenseFilters}
            setFilters={setExpenseFilters}
            refreshExpenses={loadOverview}
            handleDeleteExpense={handleDeleteExpense}
          />
        )}

        {activeSection === "budgets" && (
          <BudgetsSection
            budgetForm={budgetForm}
            setBudgetForm={setBudgetForm}
            handleBudgetSubmit={handleBudgetSubmit}
            budgetCurrent={budgetCurrent}
            budgetHistory={budgetHistory}
            budgetMessage={budgetMessage}
            budgetError={budgetError}
          />
        )}

        {activeSection === "goals" && (
          <GoalsSection
            goalForm={goalForm}
            setGoalForm={setGoalForm}
            handleGoalSubmit={handleGoalSubmit}
            goals={goals}
            goalMessage={goalMessage}
            goalError={goalError}
            handleDeleteGoal={handleDeleteGoal}
          />
        )}

        {activeSection === "automation" && (
          <AutomationSection
            recurringForm={recurringForm}
            setRecurringForm={setRecurringForm}
            handleRecurringSubmit={handleRecurringSubmit}
            recurringRules={recurringRules}
            handleToggleRecurring={handleToggleRecurring}
            handleGenerateRecurring={handleGenerateRecurring}
            recurringMessage={recurringMessage}
            recurringError={recurringError}
            recurringGenerationMessage={recurringGenerationMessage}
            categories={categories}
            paymentMethods={paymentMethods}
            recurringFrequencies={recurringFrequencies}
            ruleForm={ruleForm}
            setRuleForm={setRuleForm}
            handleRuleSubmit={handleRuleSubmit}
            smartRules={smartRules}
            handleDeleteRule={handleDeleteRule}
            ruleMessage={ruleMessage}
            ruleError={ruleError}
          />
        )}

        {activeSection === "reports" && (
          <ReportsSection
            insights={insights}
            exportRequest={exportRequest}
            setExportRequest={setExportRequest}
            handleExportSubmit={handleExportSubmit}
            exportJobs={exportJobs}
            handleDownloadExport={handleDownloadExport}
            exportMessage={exportMessage}
            exportError={exportError}
            emailPreference={emailPreference}
            setEmailPreference={setEmailPreference}
            handleEmailPreferenceSubmit={handleEmailPreferenceSubmit}
            handleSendEmailReport={handleSendEmailReport}
            emailMessage={emailMessage}
            emailError={emailError}
            exportTypes={exportTypes}
          />
        )}
      </section>
    </main>
  );
}
