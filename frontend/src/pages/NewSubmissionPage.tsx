import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Employee } from "../api";

export default function NewSubmissionPage() {
  const nav = useNavigate();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [mode, setMode] = useState<"pick" | "new">("pick");
  const [employeeId, setEmployeeId] = useState("");
  const [tripPurpose, setTripPurpose] = useState("");
  const [tripDates, setTripDates] = useState("");
  const [newEmp, setNewEmp] = useState({
    employee_id: "",
    name: "",
    grade: 5,
    title: "",
    department: "",
    manager_id: "",
    home_base: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.employees().then((list) => {
      setEmployees(list);
      if (list[0]) setEmployeeId(String(list[0].id));
    });
  }, []);

  const submit = async () => {
    setError("");
    setLoading(true);
    try {
      let empId = Number(employeeId);
      if (mode === "new") {
        const created = await api.createEmployee(newEmp);
        empId = created.id;
      }
      const sub = await api.createSubmission({
        employee_id: empId,
        trip_purpose: tripPurpose,
        trip_dates: tripDates,
      });
      nav(`/submissions/${sub.id}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>New expense submission</h2>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button
          className={`btn ${mode === "pick" ? "" : "secondary"}`}
          onClick={() => setMode("pick")}
        >
          Existing employee
        </button>
        <button
          className={`btn ${mode === "new" ? "" : "secondary"}`}
          onClick={() => setMode("new")}
        >
          New employee
        </button>
      </div>

      {mode === "pick" ? (
        <div className="field">
          <label>Employee</label>
          <select
            value={employeeId}
            onChange={(e) => setEmployeeId(e.target.value)}
          >
            {employees.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} — Grade {e.grade}, {e.department}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className="grid-2">
          {(
            [
              ["employee_id", "Employee ID"],
              ["name", "Name"],
              ["title", "Title"],
              ["department", "Department"],
              ["manager_id", "Manager ID"],
              ["home_base", "Home base"],
            ] as const
          ).map(([key, label]) => (
            <div className="field" key={key}>
              <label>{label}</label>
              <input
                value={newEmp[key]}
                onChange={(e) =>
                  setNewEmp({ ...newEmp, [key]: e.target.value })
                }
              />
            </div>
          ))}
          <div className="field">
            <label>Grade</label>
            <input
              type="number"
              min={1}
              max={10}
              value={newEmp.grade}
              onChange={(e) =>
                setNewEmp({ ...newEmp, grade: Number(e.target.value) })
              }
            />
          </div>
        </div>
      )}

      <div className="field">
        <label>Trip purpose</label>
        <textarea
          rows={3}
          value={tripPurpose}
          onChange={(e) => setTripPurpose(e.target.value)}
        />
      </div>
      <div className="field">
        <label>Trip dates (e.g. 2025-04-14 to 2025-04-16)</label>
        <input
          value={tripDates}
          onChange={(e) => setTripDates(e.target.value)}
        />
      </div>

      {error && <p className="error">{error}</p>}

      <button className="btn" disabled={loading} onClick={submit}>
        {loading ? "Creating…" : "Continue to upload receipts"}
      </button>
    </div>
  );
}
