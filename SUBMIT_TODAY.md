# Submit today — 4-hour checklist

Replace `YOUR_GITHUB_USER` and `YOUR_LIVE_URL` as you go.

---

## Hour 1 — Local proof (must work before deploy)

```bash
cd "/Users/yashaswipatki/Downloads/case study"
cp .env.example .env
# Edit .env → paste OPENAI_API_KEY=sk-...
```

**Terminal 1 — backend**

```bash
cd backend
source .venv/bin/activate
# If no venv: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Wait until logs show startup (employees seeded). First run indexes policies (~1–2 min).

**Terminal 2 — frontend**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and run this **5-minute demo** for each row:

| Sample folder | What graders expect |
|---------------|---------------------|
| `01_clean_denver` | Mostly compliant |
| `02_clean_boston_conf` | Mostly compliant |
| `03_dinner_over_cap` | Dinner over $75 cap → flagged/rejected |
| `04_alcohol_solo_travel` | Alcohol on solo trip → flagged/rejected |
| `05_receipt_mismatch` | Uses **trip context**, not receipt alone |

**Per sample:** New submission → pick employee → match trip from `data/submissions/XX_*/employee_info.json` → Load sample folder → Run AI pre-review → spot-check 1–2 line items.

Also test:

- **Override** one line with a comment
- **Policy Q&A:** “What is the solo dinner cap?” (should cite policy)
- **Policy Q&A:** “What’s the weather in Seattle?” (should refuse)
- Restart backend → submission still in **History**

---

## Hour 2 — GitHub (public repo)

```bash
cd "/Users/yashaswipatki/Downloads/case study"
git init
git add .
git status   # confirm .env is NOT listed
git commit -m "Northwind expense pre-review — case study submission"
```

Create empty repo on GitHub: `northwind-expense-review` (public).

```bash
git remote add origin https://github.com/YOUR_GITHUB_USER/northwind-expense-review.git
git branch -M main
git push -u origin main
```

---

## Hour 3 — Live deploy (Render — fastest)

1. https://render.com → Sign up → **New +** → **Web Service**
2. Connect GitHub repo
3. Settings:
   - **Environment:** Docker
   - **Dockerfile path:** `./Dockerfile`
   - **Instance:** Free (or Starter if free sleeps too much)
4. **Environment variables:**
   - `OPENAI_API_KEY` = your key
5. **Disk** (important for persistence): add 1GB mount at `/app/backend` or entire `/app`
6. Deploy → copy URL → e.g. `https://northwind-expense.onrender.com`

**After deploy:** open URL → repeat one sample (`03_dinner_over_cap`) → confirm review works.

Update README top line:

```markdown
**Live demo:** https://YOUR_APP.onrender.com
```

Commit and push:

```bash
git add README.md && git commit -m "Add live demo URL" && git push
```

---

## Hour 4 — Eval + email/package

```bash
cd backend && source .venv/bin/activate
export OPENAI_API_KEY=sk-...
python ../eval/run_eval.py --fixture ../eval/fixtures/example_expected.json
```

Screenshot or save eval JSON output for your records.

### What to send graders

1. **GitHub:** `https://github.com/YOUR_GITHUB_USER/northwind-expense-review`
2. **Live URL:** `https://YOUR_APP.onrender.com`
3. **One paragraph:**

   > Demo: open Live URL → New submission → select seeded employee → Load sample folder `03_dinner_over_cap` → Run AI pre-review. Policy Q&A tab for grounded questions. Overrides persist in History after refresh. Eval: `python eval/run_eval.py --fixture eval/fixtures/example_expected.json` (see README).

---

## If you only have 2 hours

Skip perfect tuning on all 5 samples. Minimum bar:

1. ✅ Local demo works on **03** and **04** (violation cases)
2. ✅ GitHub public
3. ✅ Render deployed with `OPENAI_API_KEY`
4. ✅ README has live URL + how to run

---

## Common blockers

| Problem | Fix |
|---------|-----|
| Review returns needs_review for everything | Check `OPENAI_API_KEY`; wait for policy index on first start |
| Render app sleeps | First load takes 30–60s; mention in submission note |
| Data lost on redeploy | Add Render persistent disk or note SQLite resets on free tier |
| Only 8 policy PDFs | OK — TEP-001 bundle includes meal/alcohol rules; note in README |

---

## Deliverables checklist

- [ ] Public GitHub repo
- [ ] Live URL in README
- [ ] README: local run, API keys, architecture, tradeoffs, cost, eval
- [ ] Browser: upload, review, override, history, policy Q&A
- [ ] Eval harness runs
