import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Employee, type SubmissionSummary } from "../api";
export default function HistoryPage() {
  const [subs, setSubs] = useState<SubmissionSummary[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeeId, setEmployeeId] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const load = () => {
    const params: Record<string, string> = {};
    if (employeeId) params.employee_id = employeeId;
    if (status) params.status = status;
    api
      .submissions(params)
      .then(setSubs)
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    api.employees().then(setEmployees);
    load();
  }, []);

  return (
    <>
      <div className="filters card">
        <div>
          <label>Employee</label>
          <select
            value={employeeId}
            onChange={(e) => setEmployeeId(e.target.value)}
          >
            <option value="">All</option>
            {employees.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} ({e.employee_id})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label>Status</label>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="processing">Processing</option>
            <option value="reviewed">Reviewed</option>
          </select>
        </div>
        <div style={{ alignSelf: "end" }}>
          <button className="btn secondary" onClick={load}>
            Apply filters
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Employee</th>
              <th>Trip</th>
              <th>Status</th>
              <th>Items</th>
              <th>Flagged</th>
            </tr>
          </thead>
          <tbody>
            {subs.length === 0 ? (
              <tr>
                <td colSpan={6} className="muted">
                  No submissions yet.{" "}
                  <Link to="/new">Create one</Link>.
                </td>
              </tr>
            ) : (
              subs.map((s) => (
                <tr key={s.id}>
                  <td>{new Date(s.created_at).toLocaleDateString()}</td>
                  <td>
                    <Link to={`/submissions/${s.id}`}>{s.employee_name}</Link>
                    <br />
                    <span className="muted">{s.employee_code}</span>
                  </td>
                  <td>
                    {s.trip_dates}
                    <br />
                    <span className="muted">{s.trip_purpose.slice(0, 60)}…</span>
                  </td>
                  <td>{s.status}</td>
                  <td>{s.line_count}</td>
                  <td>
                    {s.flagged_count > 0 ? (
                      <span style={{ color: "var(--flagged)" }}>
                        {s.flagged_count}
                      </span>
                    ) : (
                      "0"
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
