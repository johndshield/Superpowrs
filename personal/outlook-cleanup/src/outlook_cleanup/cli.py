from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
import typer
from rich.console import Console

from outlook_cleanup import approval, auth, rules
from outlook_cleanup.classifier import Pipeline
from outlook_cleanup.config import (
    Config,
    config_path,
    load_config,
    rules_path,
    runs_dir,
)
from outlook_cleanup.graph import GraphClient
from outlook_cleanup.llm import AnthropicClassifier
from outlook_cleanup.models import Decision

app = typer.Typer(no_args_is_help=True, add_completion=False)
auth_app = typer.Typer(no_args_is_help=True, help="Authentication commands.")
folders_app = typer.Typer(no_args_is_help=True, help="Mail-folder helpers.")
rules_app = typer.Typer(no_args_is_help=True, help="Rule management.")
app.add_typer(auth_app, name="auth")
app.add_typer(folders_app, name="folders")
app.add_typer(rules_app, name="rules")

console = Console()


@auth_app.command("login")
def auth_login() -> None:
    """Run the device-code flow and cache the token."""
    cfg = load_config()
    auth.login(cfg)
    console.print("[green]Auth cache written.[/]")


@folders_app.command("list")
def folders_list() -> None:
    """List mail folders; useful to confirm the Permanently Delete folder exists."""
    cfg = load_config()
    token = auth.get_token(cfg)
    with GraphClient(token) as gc:
        folders = gc.list_folders()
        try:
            purge_id = gc.find_folder_id(cfg.purge_folder_name)
        except KeyError:
            purge_id = None
    for name, fid in sorted(folders.items()):
        marker = "  <-- purge target" if fid == purge_id else ""
        console.print(f"{name}  [dim]{fid}[/]{marker}")
    if purge_id is None:
        console.print(
            f"[red]Folder {cfg.purge_folder_name!r} not found. "
            f"Create it in Outlook or update purge_folder_name in {config_path()}.[/]"
        )


@rules_app.command("show")
def rules_show() -> None:
    """Print the current rules file."""
    path = rules_path()
    if not path.exists():
        console.print(f"[yellow]No rules file at {path}[/]")
        return
    console.print(path.read_text())


@app.command()
def run(
    limit: int = typer.Option(200, help="Max messages to fetch from inbox."),
    since: str | None = typer.Option(
        None, help='Only consider mail received after this. Examples: "24h", "7d", ISO timestamp.'
    ),
    no_act: bool = typer.Option(False, "--no-act", help="Dry-run only; never move anything."),
    auto_approve_rules: bool = typer.Option(
        False, help="Promote LLM suggested-rules to rules.yaml without asking."
    ),
) -> None:
    """Scan inbox, classify, ask for approval, move approved messages."""
    cfg = load_config()
    if not cfg.anthropic_api_key:
        raise typer.BadParameter(
            "ANTHROPIC_API_KEY not set (env var or config). Required for LLM classification."
        )

    since_dt = _parse_since(since)
    token = auth.get_token(cfg)

    classifier = AnthropicClassifier(
        api_key=cfg.anthropic_api_key, model=cfg.model, preferences=cfg.preferences
    )
    rule_set = rules.load(rules_path())
    pipeline = Pipeline(rule_set, classifier)

    with GraphClient(token) as gc:
        try:
            destination_id = gc.find_folder_id(cfg.purge_folder_name)
        except KeyError as e:
            raise typer.BadParameter(str(e)) from e

        console.print(f"[dim]Fetching up to {limit} inbox messages...[/]")
        messages = list(gc.list_inbox_messages(limit=limit, since=since_dt))
        console.print(f"Fetched {len(messages)} messages. Classifying...")

        decisions = pipeline.classify_many(messages)
        approval.render_candidates(decisions, console)

        purge = [d for d in decisions if d.verdict == "purge"]
        if not purge:
            _write_run_log(decisions)
            return

        if no_act:
            console.print("[yellow]--no-act set; not moving anything.[/]")
            _write_run_log(decisions)
            return

        approved_idx = approval.prompt_approval(decisions, console)
        if not approved_idx:
            console.print("No items approved.")
            _write_run_log(decisions)
            return

        approved = {id(purge[i - 1]): purge[i - 1] for i in approved_idx}

        for d in decisions:
            if id(d) not in approved:
                continue
            try:
                gc.move_message(d.message.id, destination_id)
                d.action = "moved"
                console.print(f"[red]moved[/] {d.message.subject[:60]}")
            except Exception as e:  # noqa: BLE001
                d.action = "failed"
                console.print(f"[red]failed[/] {d.message.id}: {e}")

    promoted = _promote_rules_if_wanted(decisions, rule_set, cfg, auto_approve_rules)
    _write_run_log(decisions, promoted=promoted)
    console.print(
        f"[green]Done.[/] Moved {sum(1 for d in decisions if d.action == 'moved')}, "
        f"promoted {len(promoted)} new rules."
    )


def _promote_rules_if_wanted(
    decisions: list[Decision],
    rule_set,
    cfg: Config,
    auto: bool,
) -> list[str]:
    candidates = [
        d
        for d in decisions
        if d.action == "moved" and d.classifier == "llm" and d.suggested_rule
    ]
    if not candidates:
        return []
    if not auto and not approval.prompt_promote_rules():
        return []
    promoted: list[str] = []
    for d in candidates:
        if rules.promote(rule_set, d.suggested_rule):  # type: ignore[arg-type]
            promoted.append(d.suggested_rule)  # type: ignore[arg-type]
    if promoted:
        rules.save(rules_path(), rule_set)
    return promoted


def _write_run_log(decisions: list[Decision], promoted: list[str] | None = None) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = runs_dir() / f"{timestamp}.json"
    payload = {
        "timestamp": timestamp,
        "decisions": [
            {
                "id": d.message.id,
                "sender": d.message.sender.address,
                "subject": d.message.subject,
                "received_at": d.message.received_at.isoformat(),
                "verdict": d.verdict,
                "classifier": d.classifier,
                "reason": d.reason,
                "suggested_rule": d.suggested_rule,
                "action": d.action,
            }
            for d in decisions
        ],
        "promoted_rules": promoted or [],
    }
    path.write_text(json.dumps(payload, indent=2))
    console.print(f"[dim]Run log: {path}[/]")


def _parse_since(spec: str | None) -> datetime | None:
    if not spec:
        return None
    s = spec.strip()
    if s.endswith("h") and s[:-1].isdigit():
        return datetime.now(timezone.utc) - timedelta(hours=int(s[:-1]))
    if s.endswith("d") and s[:-1].isdigit():
        return datetime.now(timezone.utc) - timedelta(days=int(s[:-1]))
    try:
        return datetime.fromisoformat(s)
    except ValueError as e:
        raise typer.BadParameter(f"Cannot parse --since {s!r}") from e
