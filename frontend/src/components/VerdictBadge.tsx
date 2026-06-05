import type { Verdict } from "../api";

const labels: Record<Verdict, string> = {
  compliant: "Compliant",
  flagged: "Flagged",
  rejected: "Rejected",
  needs_review: "Needs review",
};

export default function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <span className={`badge ${verdict}`}>{labels[verdict]}</span>;
}
