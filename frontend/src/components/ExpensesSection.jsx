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
      <div className="card-heading">
        <div>
          <span className="eyebrow">Expenses</span>
          <h2>Search and manage transactions</h2>
        </div>
      </div>

      <div className="toolbar-grid">
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

      <div className="actions-row">
        <button className="primary-button" type="button" onClick={refreshExpenses}>
          Apply filters
        </button>
      </div>

      <div className="data-grid">
        {expenses.map((expense) => (
          <article className="data-card" key={expense.id}>
            <div>
              <p className="eyebrow">{expense.categoryName}</p>
              <h3>{expense.description}</h3>
              <p className="muted">
                {formatDate(expense.expenseDate)} . {humanize(expense.paymentMethod)}
              </p>
            </div>
            <div className="data-card__footer">
              <strong>{formatCurrency(expense.amount)}</strong>
              <button className="text-button" type="button" onClick={() => handleDeleteExpense(expense.id)}>
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
