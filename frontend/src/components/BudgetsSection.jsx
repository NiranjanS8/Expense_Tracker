import { formatCurrency, humanize } from "../lib";
import { MonthField } from "./Controls";

export default function BudgetsSection({
  budgetForm,
  setBudgetForm,
  handleBudgetSubmit,
  budgetCurrent,
  budgetHistory,
  budgetMessage,
  budgetError,
}) {
  return (
    <div className="stack-grid">
      <section className="glass-panel feature-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">Budget</span>
            <h2>Set your monthly limit</h2>
          </div>
        </div>

        <form className="toolbar-grid" onSubmit={handleBudgetSubmit}>
          <MonthField
            label="Budget month"
            value={budgetForm.budgetMonth}
            onChange={(nextValue) =>
              setBudgetForm((current) => ({ ...current, budgetMonth: nextValue }))
            }
          />
          <label>
            Amount
            <input
              min="0"
              step="0.01"
              type="number"
              value={budgetForm.amount}
              onChange={(event) =>
                setBudgetForm((current) => ({ ...current, amount: event.target.value }))
              }
              required
            />
          </label>
          <div className="actions-row actions-row--align-end">
            <button className="primary-button" type="submit">
              Save budget
            </button>
          </div>
        </form>
        {budgetError && <p className="form-error">{budgetError}</p>}
        {budgetMessage && <p className="form-success">{budgetMessage}</p>}
      </section>

      <section className="summary-grid summary-grid--three">
        <article className="summary-card">
          <div>
            <p className="eyebrow">Current budget</p>
            <h3>{formatCurrency(budgetCurrent?.budgetAmount)}</h3>
            <p className="muted">{budgetCurrent?.budgetMonth || "No month selected"}</p>
          </div>
        </article>
        <article className="summary-card">
          <div>
            <p className="eyebrow">Spent</p>
            <h3>{formatCurrency(budgetCurrent?.spentAmount)}</h3>
            <p className="muted">{humanize(budgetCurrent?.status || "ON_TRACK")}</p>
          </div>
        </article>
        <article className="summary-card">
          <div>
            <p className="eyebrow">Remaining</p>
            <h3>{formatCurrency(budgetCurrent?.remainingAmount)}</h3>
            <p className="muted">{budgetCurrent?.alertMessage || "No alerts"}</p>
          </div>
        </article>
      </section>

      <section className="glass-panel feature-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">History</span>
            <h2>Monthly budget summaries</h2>
          </div>
        </div>
        <div className="data-grid">
          {budgetHistory.map((budget) => (
            <article className="data-card" key={budget.budgetMonth}>
              <div>
                <p className="eyebrow">{budget.budgetMonth}</p>
                <h3>{formatCurrency(budget.budgetAmount)}</h3>
                <p className="muted">
                  Spent {formatCurrency(budget.spentAmount)} . {humanize(budget.status)}
                </p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
