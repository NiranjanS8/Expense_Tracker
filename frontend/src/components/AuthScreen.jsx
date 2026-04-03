import { Eye, EyeOff } from "lucide-react";

export default function AuthScreen({
  mode,
  setMode,
  authForm,
  setAuthForm,
  showPassword,
  setShowPassword,
  authError,
  authMessage,
  handleAuthSubmit,
}) {
  return (
    <main className="shell shell--auth">
      <section className="auth-hero glass-panel">
        <span className="eyebrow">Expense Tracker</span>
        <h1>Mindful money, designed to feel calm.</h1>
        <p>
          Track spending, budgets, recurring habits, insights, and exports in one quiet
          workspace inspired by the Figma concept.
        </p>
        <div className="hero-notes">
          <div>
            <strong>Full finance hub</strong>
            <span>Dashboard, budgets, goals, automation, and reports.</span>
          </div>
          <div>
            <strong>Quick capture</strong>
            <span>Add expenses before they slip away.</span>
          </div>
          <div>
            <strong>Grounded insights</strong>
            <span>Understand patterns without the noise.</span>
          </div>
        </div>
      </section>

      <section className="auth-card glass-panel">
        <div className="auth-switch">
          <button
            className={mode === "login" ? "is-active" : ""}
            onClick={() => setMode("login")}
            type="button"
          >
            Login
          </button>
          <button
            className={mode === "register" ? "is-active" : ""}
            onClick={() => setMode("register")}
            type="button"
          >
            Sign up
          </button>
        </div>

        <div className="auth-copy">
          <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p>
            {mode === "login"
              ? "Sign in to open the full expense tracker workspace."
              : "Create an account and start managing the whole app, not just the dashboard."}
          </p>
        </div>

        <form className="auth-form" onSubmit={handleAuthSubmit}>
          {mode === "register" && (
            <label>
              Full name
              <input
                value={authForm.fullName}
                onChange={(event) =>
                  setAuthForm((current) => ({ ...current, fullName: event.target.value }))
                }
                placeholder="Niranjan"
                required
              />
            </label>
          )}

          <label>
            Email
            <input
              type="email"
              value={authForm.email}
              onChange={(event) =>
                setAuthForm((current) => ({ ...current, email: event.target.value }))
              }
              placeholder="demo@expensetracker.com"
              required
            />
          </label>

          <label>
            Password
            <div className="password-field">
              <input
                type={showPassword ? "text" : "password"}
                value={authForm.password}
                onChange={(event) =>
                  setAuthForm((current) => ({ ...current, password: event.target.value }))
                }
                placeholder="Password@123"
                required
              />
              <button type="button" onClick={() => setShowPassword((value) => !value)}>
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </label>

          {authError && <p className="form-error">{authError}</p>}
          {authMessage && <p className="form-success">{authMessage}</p>}

          <button className="primary-button" type="submit">
            {mode === "login" ? "Enter app" : "Create account"}
          </button>
        </form>

        <button
          className="secondary-link"
          onClick={() =>
            setAuthForm({
              email: "demo@expensetracker.com",
              password: "Password@123",
              fullName: "Demo User",
            })
          }
          type="button"
        >
          Use demo account
        </button>
      </section>
    </main>
  );
}
