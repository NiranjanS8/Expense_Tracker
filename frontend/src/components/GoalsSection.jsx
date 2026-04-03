import { formatCurrency, formatDate, humanize } from "../lib";
import { DateField } from "./Controls";

export default function GoalsSection({
  goalForm,
  setGoalForm,
  handleGoalSubmit,
  goals,
  goalMessage,
  goalError,
  handleDeleteGoal,
}) {
  return (
    <div className="stack-grid">
      <section className="glass-panel feature-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">Goals</span>
            <h2>Track savings targets</h2>
          </div>
        </div>
        <form className="toolbar-grid" onSubmit={handleGoalSubmit}>
          <label>
            Goal name
            <input
              value={goalForm.name}
              onChange={(event) =>
                setGoalForm((current) => ({ ...current, name: event.target.value }))
              }
              required
            />
          </label>
          <label>
            Target amount
            <input
              min="0"
              step="0.01"
              type="number"
              value={goalForm.targetAmount}
              onChange={(event) =>
                setGoalForm((current) => ({ ...current, targetAmount: event.target.value }))
              }
              required
            />
          </label>
          <label>
            Current amount
            <input
              min="0"
              step="0.01"
              type="number"
              value={goalForm.currentAmount}
              onChange={(event) =>
                setGoalForm((current) => ({ ...current, currentAmount: event.target.value }))
              }
              required
            />
          </label>
          <DateField
            label="Target date"
            value={goalForm.targetDate}
            onChange={(nextValue) =>
              setGoalForm((current) => ({ ...current, targetDate: nextValue }))
            }
          />
          <div className="actions-row actions-row--align-end">
            <button className="primary-button" type="submit">
              Save goal
            </button>
          </div>
        </form>
        {goalError && <p className="form-error">{goalError}</p>}
        {goalMessage && <p className="form-success">{goalMessage}</p>}
      </section>

      <section className="glass-panel feature-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">Saved goals</span>
            <h2>Progress overview</h2>
          </div>
        </div>
        <div className="data-grid">
          {goals.map((goal) => (
            <article className="data-card" key={goal.id}>
              <div>
                <p className="eyebrow">{humanize(goal.status)}</p>
                <h3>{goal.name}</h3>
                <p className="muted">Target {formatDate(goal.targetDate)}</p>
                <p className="muted">
                  {formatCurrency(goal.currentAmount)} saved of {formatCurrency(goal.targetAmount)}
                </p>
                <p className="muted">
                  Progress {Number(goal.progressPercentage || 0).toFixed(1)}% . Remaining{" "}
                  {formatCurrency(goal.remainingAmount)}
                </p>
              </div>
              <div className="data-card__footer">
                <strong>{formatCurrency(goal.requiredMonthlyContribution)}</strong>
                <button className="text-button" type="button" onClick={() => handleDeleteGoal(goal.id)}>
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
