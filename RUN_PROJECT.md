# BuildWise Agentic AI — Local Run Guide (Windows PowerShell)

Beginner-friendly steps to clone, set up, and run the **BuildWise Agentic AI** capstone project on Windows using PowerShell.

**Repository:** https://github.com/samarth0506/buildwise-agentic-ai-platform.git  
**Recommended branch (Member 2 backend):** `member2-backend`

---

## 1. Project overview

BuildWise Agentic AI is a Bangalore real-estate + construction chatbot platform. It routes user questions to specialist agents (property, construction, documentation, maintenance, escalation), applies risk rules and human-in-the-loop (HITL) review, creates support tickets, and writes audit logs.

**Main demo query:** `Why is Tower B delayed?`

**Tech stack (Member 2 backend):**

- Python 3.10+ (3.12 recommended)
- LangChain + FAISS + local HuggingFace embeddings (no paid APIs)
- JSON file storage for review queue, tickets, and audit logs
- Optional Streamlit UI (Member 3 — see [Section 12](#12-streamlit-ui-if-available))

---

## 2. Folder structure summary

```
buildwise-agentic-ai-platform/
├── agents/                 # Member 1 specialist agents + intent classifier
├── middleware/             # Router, risk rules, HITL, tickets, audit logging
├── rag/                    # Data loader + FAISS retriever
├── scripts/                # Synthetic data generator
├── data/                   # CSV datasets, FAQ, JSON runtime stores
├── tests/                  # Backend smoke / integration tests
├── vectorstore/
│   └── faiss_index/        # Local FAISS index (built on your machine)
├── requirements.txt
└── RUN_PROJECT.md          # This guide
```

**Key data files:**

| File | Purpose |
|------|---------|
| `data/property_data.csv` | Property listings |
| `data/construction_status.csv` | Tower construction updates (includes Tower B delay demo row) |
| `data/maintenance_issues.csv` | Maintenance records |
| `data/documentation_cases.csv` | Documentation cases |
| `data/documentation_faq.txt` | FAQ text for RAG |
| `data/review_queue.json` | Human review queue (runtime) |
| `data/tickets.json` | Support tickets (runtime) |
| `data/audit_logs.json` | Audit trail (runtime) |

---

## 3. Prerequisites

Install before starting:

1. **Git** — https://git-scm.com/download/win  
2. **Python 3.10+** — https://www.python.org/downloads/  
   - During install, check **“Add Python to PATH”**.
3. **PowerShell** (Windows Terminal recommended)
4. **Internet** (first run only — downloads the embedding model ~90 MB)

Verify:

```powershell
git --version
python --version
pip --version
```

---

## 4. Git clone

Open PowerShell and run:

```powershell
cd $HOME\Desktop
git clone https://github.com/samarth0506/buildwise-agentic-ai-platform.git
cd buildwise-agentic-ai-platform
```

If you already cloned the repo, `cd` into the existing folder instead.

---

## 5. Branch checkout

Member 2 backend work lives on `member2-backend`:

```powershell
git fetch origin
git checkout member2-backend
git pull origin member2-backend
```

Confirm branch:

```powershell
git branch
git status
```

You should see `* member2-backend`.

---

## 6. Virtual environment setup

Always run project commands from the **repository root** (the folder that contains `agents/`, `middleware/`, and `requirements.txt`).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Your prompt should show `(.venv)`.

To deactivate later:

```powershell
deactivate
```

---

## 7. Dependency installation

With the virtual environment activated:

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

Quick import check:

```powershell
python -c "import agents; import middleware; import rag; print('Imports OK')"
```

---

## 8. Synthetic data generation

Generates ~200 rows per CSV and resets runtime JSON files to `[]`:

```powershell
python scripts/generate_synthetic_data.py
```

Expected output includes:

- `property_data.csv: 200 rows`
- `construction_status.csv: 200 rows`
- `Tower B demo row: Present: YES`
- JSON stores: `valid []`

---

## 9. RAG vectorstore rebuild

Builds or rebuilds the local FAISS index from `data/`:

```powershell
python -c "from rag.retriever import build_vectorstore; build_vectorstore(force_rebuild=True); print('Vectorstore rebuilt')"
```

After success, these files appear locally (they are **gitignored**):

- `vectorstore/faiss_index/index.faiss`
- `vectorstore/faiss_index/index.pkl`

Optional retrieval smoke test:

```powershell
python -c "from rag.retriever import retrieve_context; print(retrieve_context('Why is Tower B delayed?', top_k=2))"
```

---

## 10. Middleware router test

Run the built-in router demo (5 capstone queries):

```powershell
python middleware/router.py
```

Single-query test from Python:

```powershell
python -c "from middleware.router import handle_user_query; print(handle_user_query('Why is Tower B delayed?'))"
```

Expected for Tower B:

- `intent`: `construction_status`
- `status`: `pending_review`
- `review_id` and `audit_log_id` populated
- `final_response` mentions Tower B delay

---

## 11. Review queue / ticket / audit log verification

After running router tests, verify JSON stores:

```powershell
python -c "
import json
from pathlib import Path
for name in ['review_queue.json','tickets.json','audit_logs.json']:
    p = Path('data') / name
    data = json.loads(p.read_text(encoding='utf-8'))
    print(f'{name}: {len(data)} entries')
"
```

Or run the integration audit:

```powershell
python tests/integration_audit_member2.py
```

**Reset runtime JSON to empty** (optional, before a clean demo):

```powershell
python -c "
from middleware.hitl_service import save_review_queue
from middleware.ticket_service import save_tickets
from middleware.audit_logger import save_audit_logs
save_review_queue([]); save_tickets([]); save_audit_logs([])
print('JSON stores reset to []')
"
```

---

## 12. Streamlit UI (if available)

On **`member2-backend`**, `app.py` is **not included** — backend only.

If you switch to Member 3’s UI branch (e.g. `member3-ui`) and `app.py` exists:

```powershell
pip install streamlit
streamlit run app.py
```

Then open the URL shown in the terminal (usually http://localhost:8501).

---

## 13. Common errors and fixes

### `fatal: not a git repository`

**Cause:** You are not inside the cloned repo folder.

**Fix:**

```powershell
cd $HOME\Desktop\buildwise-agentic-ai-platform
git status
```

Run all git commands from the folder that contains `.git`.

---

### Execution policy error when activating venv

**Example:** `running scripts is disabled on this system`

**Fix (current user, recommended):**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
```

**Alternative (one session only):**

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\.venv\Scripts\Activate.ps1
```

---

### `ModuleNotFoundError: No module named 'agents'` (or `middleware`, `rag`)

**Cause:** Commands run from the wrong folder or venv not activated.

**Fix:**

```powershell
cd $HOME\Desktop\buildwise-agentic-ai-platform
.\.venv\Scripts\Activate.ps1
python -c "import agents; import middleware; import rag; print('OK')"
```

Always run Python from the **project root**, not from inside `agents/` or `middleware/`.

---

### Missing data files

**Cause:** Synthetic data not generated yet.

**Fix:**

```powershell
python scripts/generate_synthetic_data.py
```

---

### Corrupted JSON files (`review_queue.json`, `tickets.json`, `audit_logs.json`)

**Symptoms:** JSON decode errors or router/HITL failures.

**Fix — reset to empty lists:**

```powershell
python -c "
from pathlib import Path
for f in ['review_queue.json','tickets.json','audit_logs.json']:
    Path('data', f).write_text('[]\n', encoding='utf-8')
print('Reset complete')
"
```

Or re-run synthetic data generation (also resets JSON):

```powershell
python scripts/generate_synthetic_data.py
```

---

### FAISS rebuild hanging or very slow

**Cause:** First run downloads `sentence-transformers/all-MiniLM-L6-v2` (~90 MB). This can take several minutes on slow networks.

**If it appears stuck:**

1. Press **Ctrl+C** to cancel.
2. Pre-download the model:

```powershell
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2'); print('Model loaded')"
```

3. Retry vectorstore rebuild:

```powershell
python -c "from rag.retriever import build_vectorstore; build_vectorstore(force_rebuild=True); print('Vectorstore rebuilt')"
```

**Corporate proxy / SSL errors:** If Hugging Face download fails, try offline mode after the model is cached once:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
python -c "from rag.retriever import build_vectorstore; build_vectorstore(force_rebuild=True); print('Vectorstore rebuilt')"
```

---

### `LangChainDeprecationWarning` for HuggingFaceEmbeddings

**Fix:** Ensure dependencies are up to date:

```powershell
pip install -r requirements.txt
```

The project uses `langchain-huggingface` (already listed in `requirements.txt`).

---

### Orange **M** on files in VS Code

**Meaning:** Git shows uncommitted changes (normal after running data generation or router tests).

**Fix:** Commit intentional changes, or discard:

```powershell
git status
git restore data/property_data.csv   # example: discard one file
```

---

## 14. Git commit and push

Check what changed:

```powershell
git status
git diff --stat
```

Stage and commit (example):

```powershell
git add RUN_PROJECT.md
git add middleware/ scripts/ tests/
git add data/*.csv data/*.json data/*.txt
git commit -m "Add local run guide and Member 2 backend updates"
```

**Do not commit** (already in `.gitignore`):

- `vectorstore/faiss_index/index.faiss`
- `vectorstore/faiss_index/index.pkl`
- `.venv/`
- `__pycache__/`
- `.env`

Push to GitHub:

```powershell
git push -u origin member2-backend
```

If push is rejected due to permissions, ask the repo owner to add your GitHub account as a collaborator.

---

## Quick reference — full setup from scratch

```powershell
cd $HOME\Desktop
git clone https://github.com/samarth0506/buildwise-agentic-ai-platform.git
cd buildwise-agentic-ai-platform
git checkout member2-backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt

python scripts/generate_synthetic_data.py

python -c "from rag.retriever import build_vectorstore; build_vectorstore(force_rebuild=True); print('Vectorstore rebuilt')"

python middleware/router.py

python -c "from middleware.router import handle_user_query; print(handle_user_query('Why is Tower B delayed?'))"
```

---

## Team contacts / branches

| Branch | Owner | Contents |
|--------|-------|----------|
| `member1-agents` | Member 1 | Specialist agents + confidence middleware |
| `member2-backend` | Member 2 | RAG, synthetic data, router, HITL, tickets, audit |
| `member3-ui` | Member 3 | Streamlit UI (`app.py`, `ui/`) |

For UI demos, merge or checkout Member 3’s branch after backend verification.

---

*Last updated for `member2-backend` — BuildWise Agentic AI capstone.*
