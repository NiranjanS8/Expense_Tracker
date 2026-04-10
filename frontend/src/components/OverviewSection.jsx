import { ChevronLeft, ChevronRight, DollarSign, Receipt, Tag, TrendingUp } from "lucide-react";
import { DateField, SelectField } from "./Controls";
import { formatCurrency, formatDate, humanize } from "../lib";

function SummaryCard({ icon: Icon, label, value, detail }) {
  return (
    <article className="summary-card">
      <div className="summary-card__icon">
        <Icon size={18} />
      </div>
      <div>
        <p className="eyebrow">{label}</p>
        <h3>{value}</h3>
        <p className="muted">{detail}</p>
      </div>
    </article>
  );
}

export default function OverviewSection({
  loading,
  summary,
  categoryBreakdown,
  expenses,
  expensesPage,
  setOverviewExpensePage,
  categories,
  expenseForm,
  setExpenseForm,
  expenseError,
  expenseMessage,
  handleExpenseSubmit,
  paymentMethods,
  monthLabel,
  onPreviousMonth,
  onNextMonth,
  canMoveToNextMonth,
}) {
  const topCategory = [...(categoryBreakdown || [])].sort(
    (left, right) => Number(right.totalAmount || 0) - Number(left.totalAmount || 0),
  )[0];
  const maxCategoryValue = Math.max(
    1,
    ...categoryBreakdown.map((item) => Number(item.totalAmount || 0)),
  );

  return (
    <>
      <section className="page-intro">
        <div>
          <h2>Overview</h2>
        </div>
        <div className="month-switcher month-switcher--page">
          <button type="button" onClick={onPreviousMonth}>
            <ChevronLeft size={16} />
          </button>
          <span>{monthLabel}</span>
          <button type="button" onClick={onNextMonth} disabled={!canMoveToNextMonth}>
            <ChevronRight size={16} />
          </button>
        </div>
      </section>

      <section className="summary-grid">
        <SummaryCard
          icon={DollarSign}
          label="Monthly total"
          value={formatCurrency(summary?.monthlyTotal)}
          detail={`${summary?.transactionCount || 0} transactions`}
        />
        <SummaryCard
          icon={TrendingUp}
          label="Avg. transaction"
          value={formatCurrency(
            summary?.transactionCount
              ? Number(summary.monthlyTotal || 0) / Number(summary.transactionCount || 1)
              : 0,
          )}
          detail={loading ? "Refreshing live data" : "Average per expense this month"}
        />
        <SummaryCard
          icon={Tag}
          label="Top category"
          value={topCategory?.categoryName || "No category yet"}
          detail={formatCurrency(topCategory?.totalAmount)}
        />
        <SummaryCard
          icon={Receipt}
          label="Transactions"
          value={String(summary?.transactionCount || 0)}
          detail="Captured this month"
        />
      </section>

      <section className="content-grid">
        <article className="glass-panel feature-card">
          <div className="card-heading">
            <div>
              <span className="eyebrow">Quick add</span>
              <h2>Quick Add Expense</h2>
            </div>
          </div>

          <form className="expense-form" onSubmit={handleExpenseSubmit}>
            <div className="field-row">
              <label>
                Amount
                <input
                  min="0"
                  step="0.01"
                  type="number"
                  value={expenseForm.amount}
                  onChange={(event) =>
                    setExpenseForm((current) => ({ ...current, amount: event.target.value }))
                  }
                  required
                />
              </label>
              <DateField
                label="Date"
                value={expenseForm.expenseDate}
                onChange={(nextValue) =>
                  setExpenseForm((current) => ({
                    ...current,
                    expenseDate: nextValue,
                  }))
                }
              />
            </div>

            <div className="field-row">
              <SelectField
                label="Category"
                value={expenseForm.categoryId}
                onChange={(nextValue) =>
                  setExpenseForm((current) => ({
                    ...current,
                    categoryId: String(nextValue),
                  }))
                }
                options={categories.map((category) => ({
                  value: String(category.id),
                  label: category.name,
                }))}
                placeholder="Choose category"
              />
              <SelectField
                label="Payment method"
                value={expenseForm.paymentMethod}
                onChange={(nextValue) =>
                  setExpenseForm((current) => ({
                    ...current,
                    paymentMethod: String(nextValue),
                  }))
                }
                options={paymentMethods.map((method) => ({
                  value: method,
                  label: humanize(method),
                }))}
              />
            </div>

            <label>
              Description
              <textarea
                rows="3"
                value={expenseForm.description}
                onChange={(event) =>
                  setExpenseForm((current) => ({
                    ...current,
                    description: event.target.value,
                  }))
                }
                required
              />
            </label>

            {expenseError && <p className="form-error">{expenseError}</p>}
            {expenseMessage && <p className="form-success">{expenseMessage}</p>}

            <button className="primary-button" type="submit">
              Save expense
            </button>
          </form>
        </article>

        <article className="glass-panel feature-card">
          <div className="card-heading">
            <div>
              <span className="eyebrow">Spending mix</span>
              <h2>Category Breakdown</h2>
            </div>
          </div>

          <div className="category-list">
            {categoryBreakdown.length === 0 && (
              <p className="muted">No category spending available for this month yet.</p>
            )}
            {categoryBreakdown.map((item) => (
              <div className="category-item" key={item.categoryName}>
                <div className="category-item__meta">
                  <strong>{item.categoryName}</strong>
                  <span>{formatCurrency(item.totalAmount)}</span>
                </div>
                <div className="category-bar">
                  <span
                    style={{
                      width: `${(Number(item.totalAmount || 0) / maxCategoryValue) * 100}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="glass-panel feature-card">
          <div className="card-heading">
            <div>
              <span className="eyebrow">Recent activity</span>
              <h2>Latest transactions</h2>
            </div>
            <div className="pagination-meta">
              <span className="muted">
                Page {(expensesPage?.page || 0) + 1} of {Math.max(expensesPage?.totalPages || 1, 1)}
              </span>
            </div>
          </div>

        <div className="transactions">
          {expenses.length === 0 && <p className="muted">No expenses captured yet.</p>}
          {expenses.map((expense) => (
            <article className="transaction-item" key={expense.id}>
              <div>
                <strong>{expense.description}</strong>
                <p className="muted">
                  {expense.categoryName} . {humanize(expense.paymentMethod)}
                </p>
              </div>
              <div className="transaction-item__right">
                <strong>{formatCurrency(expense.amount)}</strong>
                <p className="muted">{formatDate(expense.expenseDate)}</p>
              </div>
            </article>
          ))}
        </div>

        <div className="pagination-row">
          <button
            className="ghost-button icon-only"
            type="button"
            disabled={expensesPage?.first}
            onClick={() => setOverviewExpensePage((current) => Math.max(current - 1, 0))}
          >
            <ChevronLeft size={16} />
          </button>
          <span className="muted">
            Page {(expensesPage?.page || 0) + 1} of {Math.max(expensesPage?.totalPages || 1, 1)}
          </span>
          <button
            className="ghost-button icon-only"
            type="button"
            disabled={expensesPage?.last || expensesPage?.totalPages === 0}
            onClick={() =>
              setOverviewExpensePage((current) =>
                Math.min(current + 1, Math.max((expensesPage?.totalPages || 1) - 1, 0)),
              )
            }
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </section>
    </>
  );
}
