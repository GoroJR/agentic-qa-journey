# AI Test Case Generator

A command-line tool that generates structured QA test cases from acceptance criteria using Claude.

Part of my **Agentic QA Engineer** journey — building practical AI tooling for quality engineering workflows.

## What it does

Feed it Acceptance Criteria, get back structured JSON containing:
- **Happy Path** — expected successful flows
- **Edge Cases** — boundary conditions, unusual but valid inputs
- **Negative Cases** — invalid inputs, error handling, security concerns (SQL injection, XSS, etc.)

## Tech stack

- **Python 3.13**
- **Anthropic Claude Haiku 4.5** — ~$0.001 per generation
- **python-dotenv** for secrets management

## Quick start

```bash
git clone https://github.com/GoroJR/agentic-qa-journey.git
cd agentic-qa-journey
pip install -r requirements.txt

# Add your API key (get one at https://console.anthropic.com)
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" > .env

# Run with a sample
python test_generator.py sample_ac.txt > my_output.json
```

## Example

**Input** (`sample_ac.txt`):

```
User Story: Login with email and password

Acceptance Criteria:
- User can log in with a valid email and password
- Email field must be a valid email format
- Password must be at least 8 characters
- After 5 failed attempts, account is locked for 15 minutes
- Successful login redirects to /dashboard
- Failed login shows error message without revealing which field was wrong
```

**Output:** see [`example_output.json`](./example_output.json) — 25 test cases covering happy paths, boundary conditions, lockout edge cases, SQL injection, XSS, and case sensitivity.

## Design notes

A few real-world LLM engineering lessons baked into this code:

- **Structured outputs over defensive parsing** — v1 stripped markdown fences before `json.loads()` because Claude occasionally wrapped JSON in them. v2 uses `client.messages.parse()` with a Pydantic schema (`schemas.py`), so the response is constrained to the schema and validated on arrival. Schema violations, refusals and truncated responses become clear errors instead of crashes.
- **stdout/stderr separation** — status messages go to stderr, structured output goes to stdout. Lets you pipe JSON to a file with `>` without polluting it.
- **No emojis in CLI output** — Windows `cp1252` codec can't encode many Unicode characters. Plain ASCII is bulletproof across environments and CI/CD.

## Evaluating the generator

Generating test cases is easy. Knowing whether they're *good* is the hard part. The `evals/` folder measures that.

**Golden set** (`evals/golden/`): 5 features (login, password reset, promo code, search with filters, file upload), each with acceptance criteria and 10-11 expected scenarios a senior QA would insist on: boundaries, lockouts, enumeration, injection.

**Three layers of scoring:**

| Layer | What it checks | How |
|---|---|---|
| Schema | Output matches the TestSuite structure | Pydantic + structured outputs |
| Structure | ID format, duplicates, empty steps or expected results | Deterministic code (`evals/checks.py`) |
| Quality | Which expected scenarios are genuinely covered; specificity, correctness, non-duplication (1-5) | LLM-as-judge (`evals/judge.py`) |

The judge has to cite test case IDs that really exist in the suite. Otherwise the scenario counts as missed, so it can't hand out credit for coverage that isn't there.

**Run it** (needs an API key in `.env`):

```bash
python -m evals.run_evals                                  # all cases
python -m evals.run_evals --cases login promo_code         # a subset
python -m evals.run_evals --repeats 3                      # measure run-to-run variance
python -m evals.run_evals --generator-model claude-haiku-5-5   # compare models
```

Each run prints a summary table and writes a full JSON report to `evals/results/`, including per-scenario judge notes and the cost of the run.

**Offline tests** (no API key, run in CI): `python -m pytest`

## Why this matters

Test case design is one of the highest-leverage tasks in QA — and one of the most automatable with LLMs. This is a working prototype of an **AI-assisted acceptance criteria to test case workflow** for enterprise QA teams.

## Roadmap

- [ ] Web UI (Streamlit)
- [ ] Direct Jira / Azure DevOps ticket integration
- [ ] Output formats: Gherkin, TestRail CSV, xUnit
- [x] Coverage scoring against original requirements (`evals/`)
- [ ] Playwright test stub generation from test cases

## Author

**Erick Rodrigo Jimenez** — QA Automation Engineer pivoting into Agentic QA  
[LinkedIn](https://linkedin.com/in/erickrodrigoja)
