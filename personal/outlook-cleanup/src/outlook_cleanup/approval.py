from __future__ import annotations

from rich.console import Console
from rich.table import Table

from outlook_cleanup.models import Decision


def render_candidates(decisions: list[Decision], console: Console) -> None:
    purge = [d for d in decisions if d.verdict == "purge"]
    kept = [d for d in decisions if d.verdict == "keep"]
    console.print(
        f"[bold]Scanned {len(decisions)} messages[/]: "
        f"[red]{len(purge)} purge[/] / [green]{len(kept)} keep[/]"
    )
    if not purge:
        return

    table = Table(title="Purge candidates", show_lines=False)
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Tab", style="magenta")
    table.add_column("Classifier", style="yellow")
    table.add_column("From", overflow="fold")
    table.add_column("Subject", overflow="fold")
    table.add_column("Reason", overflow="fold")
    table.add_column("Suggested rule", overflow="fold", style="dim")

    for idx, d in enumerate(purge, start=1):
        sender = f"{d.message.sender.name or ''} <{d.message.sender.address}>".strip()
        table.add_row(
            str(idx),
            d.message.inference_classification,
            d.classifier,
            sender,
            d.message.subject or "(no subject)",
            d.reason,
            d.suggested_rule or "",
        )
    console.print(table)


def prompt_approval(decisions: list[Decision], console: Console) -> set[int]:
    """Return the set of 1-based indices the user approves to move."""
    purge = [d for d in decisions if d.verdict == "purge"]
    if not purge:
        return set()

    console.print(
        "\n[bold]Action?[/] "
        "[cyan]a[/]=approve all  "
        "[cyan]s[/]=select (e.g. 1,3,5-8)  "
        "[cyan]n[/]=approve none  "
        "[cyan]q[/]=quit"
    )
    while True:
        choice = console.input("> ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            raise SystemExit(0)
        if choice in {"n", "none", ""}:
            return set()
        if choice in {"a", "all"}:
            return set(range(1, len(purge) + 1))
        if choice in {"s", "select"}:
            spec = console.input("indices> ").strip()
            try:
                return _parse_indices(spec, len(purge))
            except ValueError as e:
                console.print(f"[red]{e}[/]")
                continue
        try:
            return _parse_indices(choice, len(purge))
        except ValueError as e:
            console.print(f"[red]{e}[/]")


def prompt_promote_rules() -> bool:
    answer = input("Promote suggested rules from approved LLM verdicts to rules.yaml? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def _parse_indices(spec: str, max_idx: int) -> set[int]:
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo_s, hi_s = part.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
            if lo < 1 or hi > max_idx or lo > hi:
                raise ValueError(f"range out of bounds: {part}")
            out.update(range(lo, hi + 1))
        else:
            n = int(part)
            if n < 1 or n > max_idx:
                raise ValueError(f"index out of bounds: {n}")
            out.add(n)
    return out
