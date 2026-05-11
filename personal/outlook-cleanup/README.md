# outlook-cleanup

A Python CLI that reads your Outlook inbox (both Focused and Other), uses
hand-curated rules + a Claude LLM fallback to decide what is unwanted, and
moves approved messages into a Permanently Delete folder you maintain. Every
LLM call can also propose a sender/domain/subject rule so repeat junk stops
needing the LLM next time. Always dry-runs first — nothing moves without your
approval.

This is personal automation, intentionally kept outside of Superpowers core
(see `../../CLAUDE.md`).

## Requirements

- Python 3.11+
- An Outlook mailbox with a folder named **Permanently Delete** (rename via
  `purge_folder_name` in config if you call it something else)
- An Azure AD app registration with `Mail.ReadWrite` delegated permission
- An Anthropic API key

## One-time setup

### 1. Register an Azure AD app

In the [Microsoft Entra admin center](https://entra.microsoft.com/) →
**Identity** → **Applications** → **App registrations** → **New
registration**.

- Name: `outlook-cleanup` (or anything)
- Supported account types: pick whatever matches your account (a personal
  Microsoft account works with **Accounts in any organizational directory and
  personal Microsoft accounts**)
- Redirect URI: leave blank (device-code flow does not need one)

After creation, copy:

- **Application (client) ID** → `client_id`
- **Directory (tenant) ID** → `tenant_id` (use `common` if you used the
  any-org/personal option)

Then **API permissions** → **Add a permission** → **Microsoft Graph** →
**Delegated permissions** → check **Mail.ReadWrite** → **Add** → **Grant
admin consent** (if your tenant requires it).

Finally, **Authentication** → **Advanced settings** → set **Allow public
client flows** to **Yes**. Device-code is a public-client flow and this
switch is required.

### 2. Install

```bash
cd personal/outlook-cleanup
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Configure

```bash
mkdir -p ~/.config/outlook-cleanup
cp config.example.yaml ~/.config/outlook-cleanup/config.yaml
# edit ~/.config/outlook-cleanup/config.yaml — fill in tenant_id, client_id
cp rules.example.yaml ~/.config/outlook-cleanup/rules.yaml   # optional starter rules
export ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Authenticate

```bash
outlook-cleanup auth login
```

Paste the printed code into the URL it shows, sign in once. The refresh
token is cached at `~/.config/outlook-cleanup/token_cache.bin`.

### 5. Verify the destination folder

```bash
outlook-cleanup folders list
```

Look for `Permanently Delete  <-- purge target` in the output. If it's not
there, create the folder in Outlook or change `purge_folder_name` in
`config.yaml`.

## Usage

Dry-run only (no moves, just print the table and write a run log):

```bash
outlook-cleanup run --limit 50 --no-act
```

Real run (you'll be prompted before any move):

```bash
outlook-cleanup run --limit 50
```

Limit by recency:

```bash
outlook-cleanup run --since 24h
outlook-cleanup run --since 7d
```

Auto-promote suggested rules without prompting:

```bash
outlook-cleanup run --auto-approve-rules
```

Show the current rules file:

```bash
outlook-cleanup rules show
```

### Approval prompt

After the dry-run table prints, you choose:

- `a` — approve all purge candidates
- `s` — enter indices, e.g. `1,3,5-8`
- `n` — approve none
- `q` — quit immediately
- or type the indices directly

Each run writes a JSON decision log to
`~/.config/outlook-cleanup/runs/<timestamp>.json`.

## How "learning" works

1. **Allow-list** in `rules.yaml` → keep, skip LLM.
2. **Block-list** in `rules.yaml` → purge, skip LLM.
3. **LLM fallback** (Claude) for the rest. If it says PURGE and the pattern
   generalizes, it suggests a rule like `domain:promo.example`.
4. After you approve moves, the tool offers to add those suggested rules to
   `rules.yaml` so the next run matches them without an LLM call.

You can edit `~/.config/outlook-cleanup/rules.yaml` directly at any time.

## Tests

```bash
pip install -e '.[dev]'
pytest -q
```

## Files

- Config: `~/.config/outlook-cleanup/config.yaml`
- Rules: `~/.config/outlook-cleanup/rules.yaml`
- Token cache: `~/.config/outlook-cleanup/token_cache.bin`
- Run logs: `~/.config/outlook-cleanup/runs/<timestamp>.json`
