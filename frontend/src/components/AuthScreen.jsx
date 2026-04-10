import { Eye, EyeOff, Shield, TrendingUp, Zap } from "lucide-react";

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
  const capabilities = [
    {
      icon: TrendingUp,
      title: "Track smarter",
      text: "Track every expense with intelligent categorization.",
    },
    {
      icon: Shield,
      title: "Plan ahead",
      text: "Set budgets and receive proactive insights.",
    },
    {
      icon: Zap,
      title: "Automate habits",
      text: "Automate recurring expenses and smart rules.",
    },
  ];

  return (
    <main className="shell shell--auth">
      <section className="auth-hero">
        <div>
          <span className="eyebrow">Expense Tracker</span>
          <h1>Finova</h1>
          <p>
            A premium expense tracking platform designed for clarity, control, and confidence
            in your personal finances.
          </p>
        </div>

        <div className="capability-list">
          {capabilities.map((capability) => {
            const Icon = capability.icon;
            return (
              <div className="capability-item" key={capability.title}>
                <div className="capability-item__icon">
                  <Icon size={18} />
                </div>
                <div>
                  <strong>{capability.title}</strong>
                  <span>{capability.text}</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="auth-card glass-panel">
        <div className="auth-mobile-brand">
          <h1>Finova</h1>
        </div>

        <div className="auth-switch">
          <button
            className={mode === "login" ? "is-active" : ""}
            onClick={() => setMode("login")}
            type="button"
          >
            Log In
          </button>
          <button
            className={mode === "register" ? "is-active" : ""}
            onClick={() => setMode("register")}
            type="button"
          >
            Sign Up
          </button>
        </div>

        <div className="auth-copy">
          <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p>
            {mode === "login"
              ? "Sign in to your finance workspace."
              : "Create an account to access budgets, automation, and reports."}
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
            {mode === "login" ? "Log In" : "Create Account"}
          </button>
        </form>

        {mode === "login" && <button className="text-link" type="button">Forgot password?</button>}

        <div className="auth-footer">
          <span>{mode === "login" ? "Don't have an account?" : "Already have an account?"}</span>
          <button className="text-link" onClick={() => setMode(mode === "login" ? "register" : "login")} type="button">
            {mode === "login" ? "Sign up" : "Log in"}
          </button>
        </div>

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
