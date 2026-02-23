# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "typer>=0.12.0",
#     "rich>=13.0.0",
# ]
# ///
import subprocess
import sys
from typing import Annotated

import typer  # type: ignore
from rich import print

app = typer.Typer(help="Safe release manager for uv projects.")


def run(cmd: list[str], capture: bool = True) -> str:
    """Run a command and return output, or exit on failure."""
    try:
        result = subprocess.run(cmd, capture_output=capture, text=True, check=True)
        return result.stdout.strip() if capture else ""
    except subprocess.CalledProcessError as e:
        print(f"[bold red]Error running {' '.join(cmd)}[/bold red]")
        if e.stderr:
            print(f"[red]{e.stderr.strip()}[/red]")
        sys.exit(1)


def verify_git_state() -> None:
    """Ensure the repo is clean and synced with remote."""
    print("🔍 [blue]Checking git status...[/blue]")

    # 1. Check for uncommitted changes (staged or unstaged)
    status = run(["git", "status", "--porcelain"])
    if status:
        print("[bold red]❌ Working directory is not clean![/bold red]")
        print("Please commit or stash your changes before releasing:")
        print(f"[yellow]{status}[/yellow]")
        sys.exit(1)

    # 2. Check if local is synced with remote
    run(["git", "fetch"])
    local_hash = run(["git", "rev-parse", "HEAD"])
    try:
        remote_hash = run(["git", "rev-parse", "@{u}"])
    except SystemExit:
        print(
            "[yellow]⚠️ No upstream branch found. Skipping remote sync check.[/yellow]"
        )
        return

    if local_hash != remote_hash:
        ahead = run(["git", "rev-list", "HEAD", "--not", "@{u}", "--count"])
        behind = run(["git", "rev-list", "@{u}", "--not", "HEAD", "--count"])

        if int(behind) > 0:
            print(
                f"[bold red]❌ You are behind the remote by {behind} commits.[/bold red] Pull first."
            )
            sys.exit(1)
        if int(ahead) > 0:
            print(
                f"[bold red]❌ You have {ahead} unpushed commits.[/bold red] Push them first."
            )
            sys.exit(1)

    print("[green]✅ Git state is clean and synced.[/green]")


@app.command()
def main(
    increment: Annotated[str, typer.Argument(help="major, minor, or patch")] = "patch",
):
    # Phase 1: Guards
    verify_git_state()

    # Phase 2: Bump
    print(f"🚀 [blue]Bumping version ({increment})...[/blue]")
    run(["uv", "version", "--bump", increment], capture=False)
    new_version: str = run(["uv", "version", "--short"])
    tag_name: str = f"v{new_version}"

    # Phase 3: Commit and Tag
    print(f"📦 [blue]Creating tag {tag_name}...[/blue]")
    run(["git", "add", "pyproject.toml"], capture=False)
    # Check if uv.lock exists before adding it
    try:
        run(["git", "add", "uv.lock"])
    except SystemExit:
        pass

    run(["git", "commit", "-m", f"chore: release {tag_name}"], capture=False)
    run(["git", "tag", "-a", tag_name, "-m", tag_name], capture=False)

    # Phase 4: Push
    print("⬆️  [blue]Pushing to origin...[/blue]")
    run(["git", "push", "origin", "main"], capture=False)
    run(["git", "push", "origin", tag_name], capture=False)

    print(f"\n[bold green]✨ Successfully released {tag_name}![/bold green]")


if __name__ == "__main__":
    app()
