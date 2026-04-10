import { formatCurrency, formatDate, humanize } from "../lib";
import { DateField, SelectField } from "./Controls";

export default function ExpensesSection({
  expenses,
  categories,
  filters,
  setFilters,
  refreshExpenses,
  handleDeleteExpense,
}) {
  return (
    <section className="glass-panel feature-card">
      <section className="page-intro page-intro--inside">
        <span className="eyebrow">Expenses</span>
        <h2>Search and manage transactions</h2>
      </section>

      <div className="toolbar-grid toolbar-grid--filters">
        <label>
          Search
          <input
            value={filters.search}
            onChange={(event) =>
              setFilters((current) => ({ ...current, search: event.target.value }))
            }
            placeholder="Search description"
          />
        </label>
        <SelectField
          label="Category"
          value={filters.categoryId}
          onChange={(nextValue) =>
            setFilters((current) => ({ ...current, categoryId: String(nextValue) }))
          }
          options={[
            { value: "", label: "All categories" },
            ...categories.map((category) => ({
              value: String(category.id),
              label: category.name,
            })),
          ]}
        />
        <DateField
          label="Start date"
          value={filters.startDate}
          onChange={(nextValue) =>
            setFilters((current) => ({ ...current, startDate: nextValue }))
          }
        />
        <DateField
          label="End date"
          value={filters.endDate}
          onChange={(nextValue) =>
            setFilters((current) => ({ ...current, endDate: nextValue }))
          }
        />
      </div>

      <div className="actions-row actions-row--filters">
        <button className="primary-button" type="button" onClick={refreshExpenses}>
          Apply filters
        </button>
      </div>

      <div className="expense-list">
        {expenses.map((expense) => (
          <article className="expense-row" key={expense.id}>
            <div className="expense-row__content">
              <p className="eyebrow">{expense.categoryName}</p>
              <h3>{expense.description}</h3>
              <p className="muted">
                {formatDate(expense.expenseDate)} . {humanize(expense.paymentMethod)}
              </p>
            </div>
            <div className="expense-row__actions">
              <strong>{formatCurrency(expense.amount)}</strong>
              <button
                className="text-button text-button--danger"
                type="button"
                onClick={() => handleDeleteExpense(expense.id)}
              >
                Delete
              </button>
            </div>
          </article>
        ))}
        {expenses.length === 0 && <p className="muted">No expenses match the current filters.</p>}
      </div>
    </section>
  );
}
