import { useState } from "react";
import { api, type PolicyCitation } from "../api";

export default function PolicyChatPage() {
  const [question, setQuestion] = useState(
    "What is the dinner per-meal cap for solo business travel?"
  );
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<PolicyCitation[]>([]);
  const [refused, setRefused] = useState(false);
  const [refusalReason, setRefusalReason] = useState("");
  const [loading, setLoading] = useState(false);

  const ask = async () => {
    setLoading(true);
    setAnswer("");
    setCitations([]);
    try {
      const res = await api.policyAsk(question);
      setRefused(res.refused);
      setRefusalReason(res.refusal_reason || "");
      setAnswer(res.answer);
      setCitations(res.citations);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Policy library Q&A</h2>
      <p className="muted">
        Grounded answers from indexed policies only. Out-of-scope questions are refused.
      </p>
      <div className="field">
        <label>Your question</label>
        <textarea
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
      </div>
      <button className="btn" disabled={loading} onClick={ask}>
        {loading ? "Searching…" : "Ask"}
      </button>

      {refused && (
        <div className="card" style={{ marginTop: "1rem", borderColor: "var(--needs)" }}>
          <strong>Declined to answer</strong>
          <p>{refusalReason}</p>
        </div>
      )}

      {answer && (
        <div style={{ marginTop: "1rem" }}>
          <h3>Answer</h3>
          <p>{answer}</p>
          {citations.map((c, i) => (
            <div key={i} className="citation">
              <strong>
                {c.document_id}
                {c.section ? ` §${c.section}` : ""}
              </strong>
              <br />"{c.quote}"
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
