import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from ieet.compiler import LaTeXCompiler
from ieet.downloader.arxiv import ArxivDownloader
from ieet.parser.latex_parser import LaTeXParser
from ieet.rules.config import load_config
from ieet.rules.glossary import load_glossary
from ieet.translator import get_provider
from ieet.translator.pipeline import TranslationPipeline
from ieet.validator.engine import ValidationEngine

app = typer.Typer(
    name="ieet",
    help="ieeT - IEEE/arXiv Translator CLI",
    add_completion=False,
    no_args_is_help=True,
)
config_app = typer.Typer(help="Manage configuration")
glossary_app = typer.Typer(help="Manage glossary terms")
app.add_typer(config_app, name="config")
app.add_typer(glossary_app, name="glossary")

console = Console()

CONFIG_DIR = Path.home() / ".ieet"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
GLOSSARY_FILE = CONFIG_DIR / "glossary.yaml"


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


@app.command()
def translate(
    arxiv_url: str = typer.Argument(..., help="arXiv ID or URL to translate"),
    output_dir: Path = typer.Option(Path("output"), help="Directory to save results"),
    llm: Optional[str] = typer.Option(
        None, help="LLM provider (openai, claude, qwen, doubao)"
    ),
    model: Optional[str] = typer.Option(None, help="Model name to use"),
    api_key: Optional[str] = typer.Option(
        None, envvar="IEEET_API_KEY", help="API Key for the provider"
    ),
    no_compile: bool = typer.Option(False, help="Skip PDF compilation"),
    keep_source: bool = typer.Option(False, help="Keep downloaded source files"),
):
    """
    Translate an arXiv paper to Chinese.
    """
    # Load configuration
    config = load_config()

    # Overrides
    provider_name = llm or config.llm.provider
    model_name = model or config.llm.model
    api_key_val = api_key or config.llm.api_key or os.getenv(config.llm.api_key_env)

    if not api_key_val:
        console.print(
            f"[bold red]Error:[/bold red] API key not found for {provider_name}. "
            f"Please set {config.llm.api_key_env} or use --api-key."
        )
        raise typer.Exit(code=1)

    console.print(
        Panel.fit(
            f"[bold blue]ieeT Translation Pipeline[/bold blue]\n"
            f"Target: [cyan]{arxiv_url}[/cyan]\n"
            f"Provider: [green]{provider_name}[/green] ({model_name})\n"
            f"Output: [yellow]{output_dir}[/yellow]",
            title="Starting Job",
        )
    )

    async def run_pipeline():
        try:
            # 1. Download
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Downloading source...", total=None)
                downloader = ArxivDownloader()
                try:
                    download_result = downloader.download(arxiv_url, output_dir)
                    progress.update(
                        task, description=f"Downloaded: {download_result.arxiv_id}"
                    )
                except Exception as e:
                    progress.update(
                        task, description=f"[red]Download failed: {e}[/red]"
                    )
                    raise

            # 2. Parse
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Parsing LaTeX...", total=None)
                parser = LaTeXParser()
                try:
                    doc = parser.parse_file(str(download_result.main_tex))
                    progress.update(
                        task, description=f"Parsed {len(doc.chunks)} chunks"
                    )
                except Exception as e:
                    progress.update(task, description=f"[red]Parsing failed: {e}[/red]")
                    raise

            # 3. Translate
            console.print("\n[bold]Translating...[/bold]")
            glossary = load_glossary()
            provider = get_provider(
                provider_name,
                model=model_name,
                api_key=api_key_val,
                base_url=config.llm.base_url,
                temperature=config.llm.temperature,
            )
            pipeline = TranslationPipeline(
                provider=provider,
                glossary=glossary,
                state_file=output_dir
                / download_result.arxiv_id
                / "translation_state.json",
            )

            chunk_data = [{"chunk_id": c.id, "content": c.content} for c in doc.chunks]

            console.print(
                f"[bold]Translating {len(chunk_data)} chunks (max 20 concurrent)...[/bold]"
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task_id = progress.add_task(
                    "Translating chunks...", total=len(chunk_data)
                )

                def update_progress(completed: int, total: int):
                    progress.update(task_id, completed=completed, total=total)

                translated_chunks = await pipeline.translate_document(
                    chunks=chunk_data,
                    context="Academic Paper",
                    max_concurrent=20,
                    progress_callback=update_progress,
                )

            results = [tc.model_dump() for tc in translated_chunks]
            console.print(f"[green]Translation complete: {len(results)} chunks[/green]")

            # Reconstruct
            translated_map = {r["chunk_id"]: r["translation"] for r in results}
            translated_tex = doc.reconstruct(translated_map)

            # Save
            out_file = download_result.main_tex.parent / "main_translated.tex"
            out_file.write_text(translated_tex, encoding="utf-8")
            console.print(f"[green]Translation saved to {out_file}[/green]")

            # 4. Validate
            console.print("\n[bold]Validating...[/bold]")
            validator = ValidationEngine()

            # Extract original text for validation
            original_full = doc.reconstruct()

            val_result = validator.validate(translated_tex, original_full)

            if val_result.valid:
                console.print("[green]Validation Passed[/green]")
            else:
                console.print(
                    f"[yellow]Validation Issues ({len(val_result.errors)}):[/yellow]"
                )
                for err in val_result.errors:
                    color = "red" if err.severity == "error" else "yellow"
                    console.print(f"[{color}]- {err.message}[/{color}]")
                    if err.suggestion:
                        console.print(f"  Suggestion: {err.suggestion}", style="dim")

            # 5. Compile
            if not no_compile:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Compiling PDF...", total=None)
                    compiler = LaTeXCompiler(timeout=config.compilation.timeout)
                    try:
                        latex_source = out_file.read_text(encoding="utf-8")
                        # Inject Chinese font support before compilation
                        latex_source = compiler.inject_chinese_support(latex_source)
                        # Save the final version that will be compiled (for debugging)
                        out_file.write_text(latex_source, encoding="utf-8")
                        pdf_path = (
                            output_dir
                            / download_result.arxiv_id
                            / f"{download_result.arxiv_id}.pdf"
                        )
                        result = compiler.compile(
                            latex_source,
                            pdf_path,
                            working_dir=download_result.main_tex.parent,
                        )
                        if result.success:
                            progress.update(
                                task, description=f"Compiled: {result.pdf_path}"
                            )
                            console.print(
                                Panel(
                                    f"[bold green]Success![/bold green]\nPDF: {result.pdf_path}"
                                )
                            )
                        else:
                            progress.update(
                                task, description=f"[red]Compilation failed[/red]"
                            )
                            console.print(
                                f"[yellow]Error: {result.error_message}[/yellow]"
                            )
                            console.print(
                                "[yellow]Generated .tex file is saved. You may try compiling it manually.[/yellow]"
                            )
                    except Exception as e:
                        progress.update(
                            task, description=f"[red]Compilation failed: {e}[/red]"
                        )
                        console.print(
                            "[yellow]Generated .tex file is saved. You may try compiling it manually.[/yellow]"
                        )

        except Exception as e:
            console.print(f"[bold red]Pipeline failed:[/bold red] {e}")
            raise typer.Exit(code=1)

    asyncio.run(run_pipeline())


@config_app.command("show")
def config_show():
    """Show current configuration."""
    config = load_config()
    console.print(config.model_dump())


@config_app.command("set")
def config_set(key: str, value: str):
    """
    Set a configuration value (dot-separated).
    Example: ieet config set llm.model gpt-4
    """
    ensure_config_dir()

    # Load raw yaml to preserve structure if possible, or just dict
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # Update nested key
    keys = key.split(".")
    current = data
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]
        if not isinstance(current, dict):
            console.print(f"[red]Error: {k} is not a dictionary[/red]")
            raise typer.Exit(1)

    # Attempt type conversion
    val = value
    if value.lower() == "true":
        val = True
    elif value.lower() == "false":
        val = False
    elif value.isdigit():
        val = int(value)
    else:
        try:
            val = float(value)
        except ValueError:
            pass

    current[keys[-1]] = val

    with open(CONFIG_FILE, "w") as f:
        yaml.dump(data, f)

    console.print(f"[green]Updated {key} = {val}[/green]")


@glossary_app.command("add")
def glossary_add(
    term: str = typer.Argument(..., help="Term to add"),
    translation: str = typer.Argument(..., help="Translation of the term"),
    domain: Optional[str] = typer.Option(None, help="Domain context"),
    notes: Optional[str] = typer.Option(None, help="Additional notes"),
):
    """Add a term to the glossary."""
    ensure_config_dir()

    if GLOSSARY_FILE.exists():
        with open(GLOSSARY_FILE, "r") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data[term] = {"target": translation, "domain": domain, "notes": notes}

    with open(GLOSSARY_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)

    console.print(f"[green]Added term:[/green] {term} -> {translation}")


@app.command()
def validate(
    tex_file: Path = typer.Argument(..., exists=True, help="Path to .tex file"),
    original_file: Optional[Path] = typer.Option(
        None, help="Original .tex file for comparison"
    ),
):
    """
    Validate a LaTeX file.
    """
    with open(tex_file, "r", encoding="utf-8") as f:
        content = f.read()

    original = ""
    if original_file and original_file.exists():
        with open(original_file, "r", encoding="utf-8") as f:
            original = f.read()

    validator = ValidationEngine()
    result = validator.validate(content, original)

    if result.valid:
        console.print("[green]File is valid![/green]")
    else:
        console.print(f"[red]Found {len(result.errors)} errors[/red]")
        for err in result.errors:
            console.print(f"- {err.message} ({err.severity})")


def main():
    app()


if __name__ == "__main__":
    main()
