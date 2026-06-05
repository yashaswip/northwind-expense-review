export type Verdict =
  | "compliant"
  | "flagged"
  | "rejected"
  | "needs_review";

export interface Employee {
  id: number;
  employee_id: string;
  name: string;
  grade: number;
  title: string;
  department: string;
  manager_id: string;
  home_base: string;
  seeded: boolean;
}

export interface PolicyCitation {
  document_id: string;
  section?: string | null;
  quote: string;
}

export interface Override {
  id: number;
  previous_verdict: Verdict;
  new_verdict: Verdict;
  comment: string;
  reviewer: string;
  created_at: string;
}

export interface LineItem {
  id: number;
  receipt_id: number;
  filename: string;
  category: string;
  vendor: string | null;
  expense_date: string | null;
  amount: number | null;
  currency: string;
  description: string | null;
  verdict: Verdict;
  effective_verdict: Verdict;
  confidence: number;
  reasoning: string;
  policy_citations: PolicyCitation[];
  has_override: boolean;
  overrides: Override[];
}

export interface SubmissionSummary {
  id: number;
  employee_name: string;
  employee_code: string;
  trip_purpose: string;
  trip_dates: string;
  status: string;
  line_count: number;
  flagged_count: number;
  created_at: string;
}

export interface SubmissionDetail {
  id: number;
  employee: Employee;
  trip_purpose: string;
  trip_dates: string;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  line_items: LineItem[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

export const api = {
  health: () => request<{ policies_indexed: number; openai_configured: boolean }>("/api/health"),
  employees: () => request<Employee[]>("/api/employees"),
  createEmployee: (body: Omit<Employee, "id" | "seeded">) =>
    request<Employee>("/api/employees", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  submissions: (params?: Record<string, string>) => {
    const q = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<SubmissionSummary[]>(`/api/submissions${q}`);
  },
  submission: (id: number) => request<SubmissionDetail>(`/api/submissions/${id}`),
  createSubmission: (body: {
    employee_id: number;
    trip_purpose: string;
    trip_dates: string;
    notes?: string;
  }) =>
    request<SubmissionDetail>("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  uploadReceipts: (id: number, files: FileList) => {
    const fd = new FormData();
    Array.from(files).forEach((f) => fd.append("files", f));
    return request<{ uploaded: string[]; count: number }>(
      `/api/submissions/${id}/receipts`,
      { method: "POST", body: fd }
    );
  },
  review: (id: number) =>
    request<SubmissionDetail>(`/api/submissions/${id}/review`, { method: "POST" }),
  override: (lineItemId: number, body: { new_verdict: Verdict; comment: string }) =>
    request<LineItem>(`/api/submissions/line-items/${lineItemId}/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, reviewer: "finance_reviewer" }),
    }),
  policyAsk: (question: string) =>
    request<{
      answer: string;
      citations: PolicyCitation[];
      refused: boolean;
      refusal_reason?: string;
    }>("/api/policy/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
};
