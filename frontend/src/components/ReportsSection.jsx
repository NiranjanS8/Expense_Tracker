import { formatCurrency, formatDate, humanize } from "../lib";
import { DateField, SelectField } from "./Controls";

export default function ReportsSection({
  insights,
  exportRequest,
  setExportRequest,
  handleExportSubmit,
  exportJobs,
  handleDownloadExport,
  exportMessage,
  exportError,
  emailPreference,
  setEmailPreference,
  handleEmailPreferenceSubmit,
  handleSendEmailReport,
  emailMessage,
  emailError,
  exportTypes,
}) {
  return (
    <div className="stack-grid">
      <section className="glass-panel feature-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">Insights</span>
            <h2>Monthly interpretation</h2>
          </div>
        </div>

        <section className="summary-grid summary-grid--three">
          <article className="summary-card">
            <div>
              <p className="eyebrow">Current month</p>
              <h3>{formatCurrency(insights?.currentMonthTotal)}</h3>
              <p className="muted">{String(insights?.month || "")}</p>
            </div>
          </article>
          <article className="summary-card">
            <div>
              <p className="eyebrow">Previous month</p>
              <h3>{formatCurrency(insights?.previousMonthTotal)}</h3>
              <p className="muted">{formatCurrency(insights?.absoluteChange)} change</p>
            </div>
          </article>
          <article className="summary-card">
            <div>
              <p className="eyebrow">Top category</p>
              <h3>{insights?.topCategory?.categoryName || "No category"}</h3>
              <p className="muted">{formatCurrency(insights?.topCategory?.totalAmount)}</p>
            </div>
          </article>
        </section>

        <div className="data-grid">
          {(insights?.insights || []).map((item, index) => (
            <article className="data-card" key={`${item.title}-${index}`}>
              <div>
                <p className="eyebrow">{item.type || "Insight"}</p>
                <h3>{item.title}</h3>
                <p className="muted">{item.message}</p>
              </div>
            </article>
          ))}
          {insights?.largestExpense && (
            <article className="data-card">
              <div>
                <p className="eyebrow">Largest expense</p>
                <h3>{insights.largestExpense.description}</h3>
                <p className="muted">
                  {formatCurrency(insights.largestExpense.amount)} on{" "}
                  {formatDate(insights.largestExpense.expenseDate)}
                </p>
              </div>
            </article>
          )}
        </div>
      </section>

      <section className="glass-panel feature-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">Exports</span>
            <h2>Create CSV and PDF jobs</h2>
          </div>
        </div>
        <form className="toolbar-grid" onSubmit={handleExportSubmit}>
          <SelectField
            label="Type"
            value={exportRequest.type}
            onChange={(nextValue) =>
              setExportRequest((current) => ({ ...current, type: String(nextValue) }))
            }
            options={exportTypes.map((type) => ({ value: type, label: type }))}
          />
          <label>
            Search
            <input
              value={exportRequest.search}
              onChange={(event) =>
                setExportRequest((current) => ({ ...current, search: event.target.value }))
              }
            />
          </label>
          <DateField
            label="Start date"
            value={exportRequest.startDate}
            onChange={(nextValue) =>
              setExportRequest((current) => ({ ...current, startDate: nextValue }))
            }
          />
          <DateField
            label="End date"
            value={exportRequest.endDate}
            onChange={(nextValue) =>
              setExportRequest((current) => ({ ...current, endDate: nextValue }))
            }
          />
          <div className="actions-row actions-row--align-end">
            <button className="primary-button" type="submit">
              Queue export
            </button>
          </div>
        </form>
        {exportError && <p className="form-error">{exportError}</p>}
        {exportMessage && <p className="form-success">{exportMessage}</p>}

        <div className="data-grid">
          {exportJobs.map((job) => (
            <article className="data-card" key={job.id}>
              <div>
                <p className="eyebrow">{job.type}</p>
                <h3>{humanize(job.status)}</h3>
                <p className="muted">{job.fileName || "File pending"}</p>
              </div>
              <div className="data-card__footer">
                <strong>{job.downloadReady ? "Ready" : "Processing"}</strong>
                {job.downloadReady ? (
                  <button className="text-button" type="button" onClick={() => handleDownloadExport(job.id)}>
                    Download
                  </button>
                ) : (
                  <span className="muted">{job.errorMessage || "Background worker running"}</span>
                )}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="glass-panel feature-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">Email reports</span>
            <h2>Scheduled summary settings</h2>
          </div>
        </div>
        <form className="toolbar-grid" onSubmit={handleEmailPreferenceSubmit}>
          <label>
            Report email
            <input
              type="email"
              value={emailPreference.email}
              onChange={(event) =>
                setEmailPreference((current) => ({ ...current, email: event.target.value }))
              }
              required
            />
          </label>
          <SelectField
            label="Enabled"
            value={String(emailPreference.enabled)}
            onChange={(nextValue) =>
              setEmailPreference((current) => ({
                ...current,
                enabled: String(nextValue) === "true",
              }))
            }
            options={[
              { value: "true", label: "Enabled" },
              { value: "false", label: "Disabled" },
            ]}
          />
          <div className="actions-row actions-row--align-end">
            <button className="primary-button" type="submit">
              Save preference
            </button>
            <button className="ghost-button" type="button" onClick={handleSendEmailReport}>
              Send now
            </button>
          </div>
        </form>
        {emailError && <p className="form-error">{emailError}</p>}
        {emailMessage && <p className="form-success">{emailMessage}</p>}
      </section>
    </div>
  );
}
