# ⚡ Power Desk

A small ERCOT-style power trading web app, built as a realistic **system under test** for
learning automated testing: unit, API and Playwright E2E tests in Python, wired into
GitHub Actions CI the way a real team would run them.

## The app

| Page | What it does |
|---|---|
| `/login` | Session login. Demo users: `trader1`/`trader1pass`, `trader2`/`trader2pass`, `viewer1`/`viewer1pass` |
| `/` | Dashboard: hub marks, trade count, mark-to-market P&L |
| `/trades/new` | Trade ticket with live mark + notional, server-side validation, fat-finger confirmation |
| `/blotter` | Booked trades, filter by hub |
| `/positions` | Net position and P&L per hub |

The JSON API (`/api/...`) exposes the same functions. Business rules live in `app/trading.py`:

- Quantity 1–100 MW per trade, whole MW
- Price between −$250 and $5,000/MWh
- Delivery after today and within 30 days
- Net position limit ±200 MW per trader per hub (risk-reducing trades always allowed)
- Price more than 50% from the hub mark needs explicit confirmation
- Viewers (risk / management) see the whole desk but cannot trade

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m playwright install chromium

uvicorn app.main:app --reload        # http://127.0.0.1:8000
```

## The test suite

```
tests/
├── conftest.py            # starts the app on a free port per worker; API login fixtures
├── support/data.py        # test-data builders: trade_payload(), book()
├── unit/                  # pure logic: rules, P&L math         (~40 tests, <0.1 s)
├── api/                   # HTTP API: status codes, auth, wiring  (~25 tests, ~2 s)
└── e2e/                   # Playwright in a real browser          (~14 tests, ~8 s)
    ├── pages/             # page objects: the ONLY code that knows the UI's structure
    └── conftest.py        # login via API, shared cookies with the browser
```

```bash
pytest                                 # everything
pytest -m unit                         # one layer (markers come from the folder)
pytest -m smoke                        # critical path only (what PRs run in the browser)
pytest -n auto                         # parallel; every worker gets its own server + DB
pytest -m e2e --headed --slowmo 500    # watch the browser
pytest -m e2e --browser firefox        # another engine
pytest --tracing retain-on-failure     # keep a trace for failed tests, then:
playwright show-trace test-results/<test>/trace.zip
```

**Running against a deployed environment.** `pytest --base-url https://staging.example.com`
skips the local server. Tests that need to wipe data skip themselves unless the target
reports `env: test`, so you cannot accidentally reset production.

### Patterns worth noticing

1. **Test pyramid.** Each rule is proven exhaustively in fast unit tests, proven *wired up*
   in a few API tests, and only the user-visible flows get browser tests.
2. **Arrange through the API, assert through the UI.** E2E tests seed trades with
   `book(ui_api, ...)` instead of clicking through the ticket each time.
3. **Log in once through the UI** (`test_login.py`); everywhere else log in via API.
4. **Stable locators.** Tests use labels, roles and `data-testid`, never CSS layout.
5. **Determinism.** In the test environment the business date is pinned (`APP_TODAY`)
   and prices are fixed, so P&L assertions are exact, and every test starts from an empty book.
6. **Web-first assertions.** `expect(locator).to_have_text(...)` retries until it passes
   or times out; there is no `sleep()` anywhere in the suite.

## CI/CD pipelines

| Workflow | Trigger | What runs | Why |
|---|---|---|---|
| `pr.yml` | every pull request | lint → unit + API → E2E **smoke** (Chromium) | Fast gate; make it a required check |
| `main.yml` | merge to `main` | unit + API, full E2E in 2 parallel shards | Full regression on what was just merged |
| `nightly.yml` | 3:17 am CT daily | full E2E on Chromium, Firefox, WebKit | Breadth without slowing PRs |

Failed E2E jobs upload **traces, screenshots and videos** as artifacts. Download the trace
and open it with `playwright show-trace` or at trace.playwright.dev.

After the first push, protect `main`: *Settings → Branches → Add rule → Require status
checks* and select `lint`, `unit-and-api` and `e2e-smoke`.

## Learning roadmap

Work through these as if you were the SDET on the team. Each one is a branch and a PR.

1. **Read and run.** Run each layer. Open `reports/` HTML output. Run one E2E test headed.
2. **First green PR.** Change the dashboard greeting, open a PR, watch the three PR jobs.
3. **Feature + tests in one PR.** Add a rule: *max 50 MW per trade for WEST hub*. Write the
   unit test first, then the code, then one API test. Ask yourself: does this need an E2E test?
4. **Break it and triage.** In a branch, change the ticket's "Book trade" button text.
   Let CI fail, download the trace artifact, find the cause in the trace viewer, fix it
   *in the page object only*.
5. **Flaky test clinic.** Add `time.sleep(random.random())` to the `/positions` route and
   replace one `expect(...)` with a plain `assert locator.inner_text() == ...`. Run it
   20 times (`pytest --count` via pytest-repeat, or a loop). See why web-first assertions matter.
6. **Post-deploy smoke.** Write a read-only `-m prod_safe` suite that can run against any
   environment (health, login, dashboard renders), and a workflow that runs it after deploy.
7. **AI layer.** Install Playwright MCP in Claude Code, point it at the running app, and ask
   it to (a) explore the blotter and propose missing test cases, (b) write them using the
   existing page objects, (c) fix tests after you rename a `data-testid`. Review every line it
   writes against the business rules above, not just against what the app currently does.
