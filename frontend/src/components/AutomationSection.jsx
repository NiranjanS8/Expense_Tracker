import { formatCurrency, formatDate, humanize } from "../lib";
import { DateField, SelectField } from "./Controls";

export default function AutomationSection({
  recurringForm,
  setRecurringForm,
  handleRecurringSubmit,
  recurringRules,
  handleToggleRecurring,
  handleGenerateRecurring,
  recurringMessage,
  recurringError,
  recurringGenerationMessage,
  categories,
  paymentMethods,
  recurringFrequencies,
  ruleForm,
  setRuleForm,
  handleRuleSubmit,
  smartRules,
  handleDeleteRule,
  ruleMessage,
  ruleError,
}) {
  return (
    <div className="stack-grid">
      <section className="glass-panel feature-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">Recurring</span>
            <h2>Automate repeating expenses</h2>
          </div>
          <button className="ghost-button" type="button" onClick={handleGenerateRecurring}>
            Generate due items
          </button>
        </div>

        <form className="toolbar-grid" onSubmit={handleRecurringSubmit}>
          <SelectField
            label="Category"
            value={recurringForm.categoryId}
            onChange={(nextValue) =>
              setRecurringForm((current) => ({ ...current, categoryId: String(nextValue) }))
            }
            options={[
              { value: "", label: "Choose category" },
              ...categories.map((category) => ({
                value: String(category.id),
                label: category.name,
              })),
            ]}
          />
          <label>
            Amount
            <input
              min="0"
              step="0.01"
              type="number"
              value={recurringForm.amount}
              onChange={(event) =>
                setRecurringForm((current) => ({ ...current, amount: event.target.value }))
              }
              required
            />
          </label>
          <DateField
            label="Start date"
            value={recurringForm.startDate}
            onChange={(nextValue) =>
              setRecurringForm((current) => ({ ...current, startDate: nextValue }))
            }
          />
          <SelectField
            label="Frequency"
            value={recurringForm.frequency}
            onChange={(nextValue) =>
              setRecurringForm((current) => ({ ...current, frequency: String(nextValue) }))
            }
            options={recurringFrequencies.map((frequency) => ({
              value: frequency,
              label: humanize(frequency),
            }))}
          />
          <SelectField
            label="Payment method"
            value={recurringForm.paymentMethod}
            onChange={(nextValue) =>
              setRecurringForm((current) => ({
                ...current,
                paymentMethod: String(nextValue),
              }))
            }
            options={paymentMethods.map((method) => ({
              value: method,
              label: humanize(method),
            }))}
          />
          <label className="toolbar-grid__wide">
            Description
            <input
              value={recurringForm.description}
              onChange={(event) =>
                setRecurringForm((current) => ({ ...current, description: event.target.value }))
              }
            />
          </label>
          <div className="actions-row actions-row--align-end">
            <button className="primary-button" type="submit">
              Save recurring rule
            </button>
          </div>
        </form>
        {recurringError && <p className="form-error">{recurringError}</p>}
        {(recurringMessage || recurringGenerationMessage) && (
          <p className="form-success">{recurringGenerationMessage || recurringMessage}</p>
        )}

        <div className="data-grid">
          {recurringRules.map((rule) => (
            <article className="data-card" key={rule.id}>
              <div>
                <p className="eyebrow">{humanize(rule.frequency)}</p>
                <h3>{rule.description || rule.categoryName}</h3>
                <p className="muted">
                  {formatCurrency(rule.amount)} . Next run {formatDate(rule.nextExecutionDate)}
                </p>
              </div>
              <div className="data-card__footer">
                <strong>{rule.active ? "Active" : "Paused"}</strong>
                <button className="text-button" type="button" onClick={() => handleToggleRecurring(rule)}>
                  {rule.active ? "Pause" : "Resume"}
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="glass-panel feature-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">Smart category</span>
            <h2>Auto-map descriptions to categories</h2>
          </div>
        </div>
        <form className="toolbar-grid" onSubmit={handleRuleSubmit}>
          <label>
            Keyword
            <input
              value={ruleForm.keyword}
              onChange={(event) =>
                setRuleForm((current) => ({ ...current, keyword: event.target.value }))
              }
              required
            />
          </label>
          <SelectField
            label="Category"
            value={ruleForm.categoryId}
            onChange={(nextValue) =>
              setRuleForm((current) => ({ ...current, categoryId: String(nextValue) }))
            }
            options={[
              { value: "", label: "Choose category" },
              ...categories.map((category) => ({
                value: String(category.id),
                label: category.name,
              })),
            ]}
          />
          <SelectField
            label="Status"
            value={String(ruleForm.active)}
            onChange={(nextValue) =>
              setRuleForm((current) => ({ ...current, active: String(nextValue) === "true" }))
            }
            options={[
              { value: "true", label: "Active" },
              { value: "false", label: "Inactive" },
            ]}
          />
          <div className="actions-row actions-row--align-end">
            <button className="primary-button" type="submit">
              Save rule
            </button>
          </div>
        </form>
        {ruleError && <p className="form-error">{ruleError}</p>}
        {ruleMessage && <p className="form-success">{ruleMessage}</p>}

        <div className="data-grid">
          {smartRules.map((rule) => (
            <article className="data-card" key={rule.id}>
              <div>
                <p className="eyebrow">{rule.active ? "Active" : "Inactive"}</p>
                <h3>{rule.keyword}</h3>
                <p className="muted">Maps to {rule.categoryName}</p>
              </div>
              <div className="data-card__footer">
                <strong>{rule.categoryName}</strong>
                <button className="text-button" type="button" onClick={() => handleDeleteRule(rule.id)}>
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
