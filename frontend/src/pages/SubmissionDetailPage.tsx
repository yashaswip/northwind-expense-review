import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  api,
  type LineItem,
  type SubmissionDetail,
  type Verdict,
} from "../api";
import VerdictBadge from "../components/VerdictBadge";

function OverrideModal({
  item,
  onClose,
  onSaved,
}: {
  item: LineItem;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [verdict, setVerdict] = useState<Verdict>(item.effective_verdict);
  const [comment, setComment] = useState("");
  const [err, setErr] = useState("");

  const save = async () => {
    if (!comment.trim()) {
      setErr("Comment is required for audit trail.");
      return;
    }
    try {
      await api.override(item.id, { new_verdict: verdict, comment });
      onSaved();
      onClose();
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Override verdict</h3>
        <p className="muted">{item.filename}</p>
        <div className="field">
          <label>New verdict</label>
          <select
            value={verdict}
            onChange={(e) => setVerdict(e.target.value as Verdict)}
          >
            <option value="compliant">Compliant</option>
            <option value="flagged">Flagged</option>
            <option value="rejected">Rejected</option>
            <option value="needs_review">Needs review</option>
          </select>
        </div>
        <div className="field">
          <label>Reviewer comment (required)</label>
          <textarea
            rows={4}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </div>
        {err && <p className="error">{err}</p>}
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button className="btn" onClick={save}>
            Save override
          </button>
          <button className="btn secondary" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SubmissionDetailPage() {
  const { id } = useParams();
  const [sub, setSub] = useState<SubmissionDetail | null>(null);
  const [files, setFiles] = useState<FileList | null>(null);
  const [loading, setLoading] = useState(false);
  const [overrideItem, setOverrideItem] = useState<LineItem | null>(null);
  const [error, setError] = useState("");
  const [sampleFolder, setSampleFolder] = useState("01_clean_denver");

  const load = useCallback(() => {
    if (!id) return;
    api.submission(Number(id)).then(setSub).catch((e) => setError(String(e)));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const upload = async () => {
    if (!files?.length || !sub) return;
    setLoading(true);
    try {
      await api.uploadReceipts(sub.id, files);
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const loadSample = async () => {
    if (!sub) return;
    setLoading(true);
    try {
      const r = await fetch(
        `/api/submissions/${sub.id}/load-sample?folder=${sampleFolder}`,
        { method: "POST" }
      );
      if (!r.ok) throw new Error(await r.text());
      await r.json();
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const review = async () => {
    if (!sub) return;
    setLoading(true);
    try {
      const updated = await api.review(sub.id);
      setSub(updated);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  if (!sub) return <p className="muted">Loading…</p>;

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>
          {sub.employee.name}{" "}
          <span className="muted">({sub.employee.employee_id})</span>
        </h2>
        <p>
          <strong>Trip:</strong> {sub.trip_dates}
          <br />
          {sub.trip_purpose}
        </p>
        <p>
          <strong>Status:</strong> {sub.status} · Grade {sub.employee.grade}
        </p>
      </div>

      {sub.status === "draft" && (
        <div className="card">
          <h3>Upload receipts</h3>
          <p className="muted">
            PDF, JPG, PNG, or TXT — one file per line item.
          </p>
          <input
            type="file"
            multiple
            accept=".pdf,.jpg,.jpeg,.png,.txt,image/*,application/pdf,text/plain"
            onChange={(e) => setFiles(e.target.files)}
          />
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
            <button className="btn" disabled={loading || !files?.length} onClick={upload}>
              Upload
            </button>
          </div>

          <hr style={{ borderColor: "var(--border)", margin: "1.5rem 0" }} />
          <h4>Or load sample receipts (dev/demo)</h4>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <select
              value={sampleFolder}
              onChange={(e) => setSampleFolder(e.target.value)}
            >
              <option value="01_clean_denver">01 Clean Denver</option>
              <option value="02_clean_boston_conf">02 Boston conference</option>
              <option value="03_dinner_over_cap">03 Dinner over cap</option>
              <option value="04_alcohol_solo_travel">04 Alcohol solo</option>
              <option value="05_receipt_mismatch">05 Receipt mismatch</option>
            </select>
            <button className="btn secondary" disabled={loading} onClick={loadSample}>
              Load sample folder
            </button>
          </div>
        </div>
      )}

      {sub.status === "draft" && (
        <div className="card">
          <button className="btn" disabled={loading} onClick={review}>
            {loading ? "Processing…" : "Run AI pre-review"}
          </button>
          <p className="muted" style={{ marginTop: "0.5rem" }}>
            Upload or load sample receipts first, then run pre-review.
          </p>
        </div>
      )}

      {sub.line_items.length > 0 && (
        <>
          {sub.status === "draft" && (
            <button className="btn" disabled={loading} onClick={review} style={{ marginBottom: "1rem" }}>
              Re-run pre-review
            </button>
          )}
          <h3>Line items ({sub.line_items.length})</h3>
          {sub.line_items.map((item) => (
            <div
              key={item.id}
              className={`card line-item ${item.effective_verdict}`}
            >
              <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
                <div>
                  <strong>{item.filename}</strong>
                  <br />
                  <span className="muted">
                    {item.category}
                    {item.vendor ? ` · ${item.vendor}` : ""}
                    {item.amount != null ? ` · $${item.amount.toFixed(2)}` : ""}
                  </span>
                </div>
                <div>
                  <VerdictBadge verdict={item.effective_verdict} />
                  {item.has_override && (
                    <span className="muted" style={{ marginLeft: "0.5rem" }}>
                      (overridden)
                    </span>
                  )}
                  <div className="confidence">
                    Confidence: {(item.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
              <p style={{ marginTop: "0.75rem" }}>{item.reasoning}</p>
              {item.policy_citations.map((c, i) => (
                <div key={i} className="citation">
                  <strong>
                    {c.document_id}
                    {c.section ? ` §${c.section}` : ""}
                  </strong>
                  <br />
                  "{c.quote}"
                </div>
              ))}
              {item.overrides.length > 0 && (
                <div style={{ marginTop: "1rem" }}>
                  <strong>Override history</strong>
                  {item.overrides.map((o) => (
                    <div key={o.id} className="citation">
                      {o.reviewer}: {o.previous_verdict} → {o.new_verdict}
                      <br />
                      {o.comment}
                      <br />
                      <span className="muted">
                        {new Date(o.created_at).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <button
                className="btn secondary"
                style={{ marginTop: "0.75rem" }}
                onClick={() => setOverrideItem(item)}
              >
                Override verdict
              </button>
            </div>
          ))}
        </>
      )}

      {error && <p className="error">{error}</p>}

      {overrideItem && (
        <OverrideModal
          item={overrideItem}
          onClose={() => setOverrideItem(null)}
          onSaved={load}
        />
      )}
    </>
  );
}
