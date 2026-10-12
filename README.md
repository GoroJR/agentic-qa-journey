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

- **Defensive JSON parsing** — even with explicit instructions, Claude occasionally wraps responses in markdown fences. The parser strips them before `json.loads()`.
- **stdout/stderr separation** — status messages go to stderr, structured output goes to stdout. Lets you pipe JSON to a file with `>` without polluting it.
- **No emojis in CLI output** — Windows `cp1252` codec can't encode many Unicode characters. Plain ASCII is bulletproof across environments and CI/CD.

## Why this matters

Test case design is one of the highest-leverage tasks in QA — and one of the most automatable with LLMs. This is a working prototype of an **AI-assisted acceptance criteria to test case workflow** for enterprise QA teams.

## Roadmap

- [ ] Web UI (Streamlit)
- [ ] Direct Jira / Azure DevOps ticket integration
- [ ] Output formats: Gherkin, TestRail CSV, xUnit
- [ ] Coverage scoring against original requirements
- [ ] Playwright test stub generation from test cases

## Author

**Erick Rodrigo Jimenez** — QA Automation Engineer pivoting into Agentic QA  
[LinkedIn](https://linkedin.com/in/erickrodrigoja)
