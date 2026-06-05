import { Link, Route, Routes, useLocation } from "react-router-dom";
import HistoryPage from "./pages/HistoryPage";
import NewSubmissionPage from "./pages/NewSubmissionPage";
import PolicyChatPage from "./pages/PolicyChatPage";
import SubmissionDetailPage from "./pages/SubmissionDetailPage";

export default function App() {
  const loc = useLocation();
  const nav = [
    { to: "/", label: "History" },
    { to: "/new", label: "New submission" },
    { to: "/policy", label: "Policy Q&A" },
  ];

  return (
    <div className="layout">
      <header>
        <h1>Northwind Expense Pre-Review</h1>
        <nav>
          {nav.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              className={loc.pathname === to ? "active" : ""}
            >
              {label}
            </Link>
          ))}
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<HistoryPage />} />
        <Route path="/new" element={<NewSubmissionPage />} />
        <Route path="/submissions/:id" element={<SubmissionDetailPage />} />
        <Route path="/policy" element={<PolicyChatPage />} />
      </Routes>
    </div>
  );
}
