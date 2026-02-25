import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Any, Optional

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

from ieeA.compiler import LaTeXCompiler
from ieeA.downloader.arxiv import ArxivDownloader
from ieeA.parser.latex_parser import LaTeXParser
from ieeA.rules.config import load_config
from ieeA.rules.glossary import load_glossary
from ieeA.rules.examples import load_examples
from ieeA.translator import get_sdk_client
from ieeA.translator.pipeline import TranslationPipeline
from ieeA.parser.structure import validate_translated_placeholders
from ieeA.validator.engine import ValidationEngine

app = typer.Typer(
    name="ieeA",
    help="ieeA - arXiv Paper Translator",
    add_completion=False,
    no_args_is_help=True,
)
config_app = typer.Typer(help="Manage configuration")
glossary_app = typer.Typer(help="Manage glossary terms")
app.add_typer(config_app, name="config")
app.add_typer(glossary_app, name="glossary")

console = Console()

CONFIG_DIR = Path.home() / ".ieeA"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
GLOSSARY_FILE = CONFIG_DIR / "glossary.yaml"


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _print_provider_cache_summary(provider: Any) -> None:
    get_summary = getattr(provider, "get_cache_stats_summary", None)
    if not callable(get_summary):
        return

    try:
        summary = get_summary()
    except Exception as e:
        console.print(f"[yellow]Cache summary unavailable: {e}[/yellow]")
        return

    if not isinstance(summary, dict):
        return
    if int(summary.get("request_count", 0) or 0) <= 0:
        return

    formatter = getattr(provider, "format_cache_stats_summary", None)
    lines: list[str] = []
    if callable(formatter):
        try:
            formatted = formatter()
            if isinstance(formatted, str):
                lines = [formatted]
            elif isinstance(formatted, list):
                lines = [str(line) for line in formatted if str(line).strip()]
        except Exception as e:
            console.print(f"[yellow]Cache summary format failed: {e}[/yellow]")

    if not lines:
        lines = [
            "[CACHE SUMMARY] "
            f"requests={summary.get('request_count', 0)} "
            f"hit={summary.get('cache_hit_count', 0)} "
            f"miss={summary.get('cache_miss_count', 0)} "
            f"cached_tokens={summary.get('cached_tokens_total', 0)} "
            f"total_tokens={summary.get('total_tokens_total', 0)}"
        ]

    for line in lines:
        console.print(line, style="cyan", markup=False)


@app.command()
def translate(
    arxiv_url: str = typer.Argument(..., help="arXiv ID or URL to translate"),
    output_dir: Path = typer.Option(
        Path("output"), "-o", "--output-dir", help="Directory to save results"
    ),
    sdk: Optional[str] = typer.Option(
        None,
        help="SDK to use (openai, openai-coding, anthropic, anthropic-coding, or None for direct HTTP)",
    ),
    model: Optional[str] = typer.Option(None, help="Model name to use"),
    key: Optional[str] = typer.Option(None, help="API Key"),
    endpoint: Optional[str] = typer.Option(None, help="API endpoint URL"),
    no_compile: bool = typer.Option(False, help="Skip PDF compilation"),
    keep_source: bool = typer.Option(False, help="Keep downloaded source files"),
    concurrency: int = typer.Option(
        50,
        "-c",
        "--concurrency",
        help="Max concurrent API requests (lower = safer for rate limits)",
    ),
    high_quality: bool = typer.Option(
        False,
        "--high-quality",
        "-hq",
        help="启用高质量翻译模式，为每个 chunk 提供摘要上下文",
    ),
    abstract: Optional[str] = typer.Option(
        None, "--abstract", help="手动提供摘要文本（覆盖自动提取）"
    ),
):
    """
    Translate an arXiv paper to Chinese.
    """
    # Load configuration
    config = load_config()

    # Overrides
    sdk_name = sdk or config.llm.sdk
    model_name = model or config.llm.get_model()
    key_val = key or config.llm.key
    endpoint_val = endpoint or config.llm.endpoint

    if sdk_name is not None and not key_val:
        console.print(
            f"[bold red]Error:[/bold red] API key not found. "
            f"Please set llm.key in config or use --key."
        )
        raise typer.Exit(code=1)

    console.print(
        Panel.fit(
            f"[bold blue]ieeA Translation Pipeline[/bold blue]\n"
            f"Target: [cyan]{arxiv_url}[/cyan]\n"
            f"SDK: [green]{sdk_name or 'HTTP'}[/green] ({model_name})\n"
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
                parser = LaTeXParser(
                    extra_protected_envs=config.parser.extra_protected_environments,
                    font_config=config.fonts,
                )
                try:
                    doc = parser.parse_file(str(download_result.main_tex))
                    progress.update(
                        task, description=f"Parsed {len(doc.chunks)} chunks"
                    )
                except Exception as e:
                    progress.update(task, description=f"[red]Parsing failed: {e}[/red]")
                    raise

            # Save parser state for placeholder validation
            parser_state_path = (
                output_dir / download_result.arxiv_id / "parser_state.json"
            )
            doc.save_parser_state(parser_state_path)

            # 3. Translate
            console.print("\n[bold]Translating...[/bold]")
            glossary = load_glossary()
            provider_kwargs: dict[str, Any] = {"temperature": config.llm.temperature}
            if sdk_name in ("openai-coding", "anthropic-coding"):
                provider_kwargs["full_glossary"] = glossary

            provider = get_sdk_client(
                sdk_name,
                model=model_name,
                key=key_val,
                endpoint=endpoint_val,
                **provider_kwargs,
            )
            reset_cache_stats = getattr(provider, "reset_cache_stats", None)
            if callable(reset_cache_stats):
                try:
                    reset_cache_stats()
                except Exception as e:
                    console.print(
                        f"[yellow]Cache stats reset skipped: {e}[/yellow]"
                    )

            # Prepare high-quality mode parameters
            abstract_text = None
            examples = []
            if high_quality:
                # Get abstract: CLI argument > extracted abstract > fallback
                abstract_text = abstract or getattr(doc, "abstract", "") or ""
                # Load few-shot examples
                examples_path = getattr(config.translation, "examples_path", None)
                examples = (
                    load_examples(examples_path) if examples_path else load_examples()
                )
                console.print(
                    f"[cyan]High-quality mode enabled: {len(examples)} examples loaded[/cyan]"
                )

            pipeline = TranslationPipeline(
                provider=provider,
                glossary=glossary,
                state_file=output_dir
                / download_result.arxiv_id
                / "translation_state.json",
                few_shot_examples=examples,
                abstract_context=abstract_text,
                custom_system_prompt=config.translation.custom_system_prompt,
                model_name=model_name,
                hq_mode=high_quality,
                batch_short_threshold=config.translation.batch_short_threshold,
                batch_max_chars=config.translation.batch_max_chars,
                sequential_mode=(sdk_name in ("openai-coding", "anthropic-coding")),
            )

            chunk_data = [{"chunk_id": c.id, "content": c.content} for c in doc.chunks]

            console.print(
                f"[bold]Translating {len(chunk_data)} chunks (max {concurrency} concurrent)...[/bold]"
            )

            batch_stats = {"batches": 0, "long_chunks": 0, "total_calls": 0}

            def on_batch_stats(num_batches: int, num_long: int, total_calls: int):
                batch_stats["batches"] = num_batches
                batch_stats["long_chunks"] = num_long
                batch_stats["total_calls"] = total_calls

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
                    max_concurrent=concurrency,
                    progress_callback=update_progress,
                    batch_stats_callback=on_batch_stats,
                )

            if batch_stats["total_calls"] > 0:
                console.print(
                    f"[cyan]Batch optimization: {len(chunk_data)} chunks → "
                    f"{batch_stats['total_calls']} API calls "
                    f"({batch_stats['batches']} batches + {batch_stats['long_chunks']} long chunks)[/cyan]"
                )

            results = [tc.model_dump() for tc in translated_chunks]
            console.print(f"[green]Translation complete: {len(results)} chunks[/green]")
            _print_provider_cache_summary(provider)

            # Reconstruct
            translated_map = {r["chunk_id"]: r["translation"] for r in results}

            translated_map, ph_issues = validate_translated_placeholders(
                translated_map, doc
            )

            if ph_issues:
                console.print(
                    f"\n[yellow]Placeholder Issues ({len(ph_issues)}):[/yellow]"
                )
                for issue in ph_issues:
                    if issue["type"] == "typo_fixed":
                        console.print(
                            f"[yellow]  TYPO FIXED: chunk {issue['chunk_id'][:8]}..., "
                            f"{issue['bad']} → {issue['fixed_to']}[/yellow]"
                        )
                    elif issue["type"] == "hallucination":
                        console.print(
                            f"[yellow]  HALLUCINATION REMOVED: chunk {issue['chunk_id'][:8]}..., "
                            f"{issue['bad']} deleted[/yellow]"
                        )
                    elif issue["type"] == "missing":
                        console.print(
                            f"[red]  MISSING: chunk {issue['chunk_id'][:8]}..., "
                            f"{issue['bad']} lost in translation[/red]"
                        )

            translated_tex, translated_chunk_start_lines = (
                doc.reconstruct_with_chunk_start_lines(translated_map)
            )

            # Save
            out_file = download_result.main_tex.parent / "main_translated.tex"
            out_file.write_text(translated_tex, encoding="utf-8")
            console.print(f"[green]Translation saved to {out_file}[/green]")

            # 4. Validate
            console.print("\n[bold]Validating...[/bold]")
            validator = ValidationEngine()

            # Extract original text for validation
            original_full, source_chunk_start_lines = (
                doc.reconstruct_with_chunk_start_lines()
            )

            val_result = validator.validate(
                translated_tex,
                original_full,
                translated_chunks=translated_chunks,
                source_chunk_start_lines=source_chunk_start_lines,
                translation_chunk_start_lines=translated_chunk_start_lines,
            )

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
    Example: ieeA config set llm.model gpt-4
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
def ping(
    sdk: Optional[str] = typer.Option(
        None,
        help="SDK to use (openai, openai-coding, anthropic, anthropic-coding, or None for direct HTTP)",
    ),
    model: Optional[str] = typer.Option(None, help="Model name to use"),
    key: Optional[str] = typer.Option(None, help="API Key"),
    endpoint: Optional[str] = typer.Option(None, help="API endpoint URL"),
):
    """
    Test LLM connectivity. Sends a minimal request to verify the configured LLM is reachable.
    """
    config = load_config()

    sdk_name = sdk or config.llm.sdk
    model_name = model or config.llm.get_model()
    key_val = key or config.llm.key
    endpoint_val = endpoint or config.llm.endpoint

    console.print(
        Panel.fit(
            f"[bold blue]ieeA Ping[/bold blue]\n"
            f"SDK: [green]{sdk_name or 'HTTP'}[/green]\n"
            f"Model: [cyan]{model_name}[/cyan]\n"
            f"Endpoint: [yellow]{endpoint_val or 'default'}[/yellow]",
            title="Testing LLM Connectivity",
        )
    )

    async def do_ping():
        try:
            provider = get_sdk_client(
                sdk_name,
                model=model_name,
                key=key_val,
                endpoint=endpoint_val,
                temperature=config.llm.temperature,
            )
            start = time.perf_counter()
            result = await provider.ping()
            elapsed = time.perf_counter() - start

            console.print(
                f"\n[bold green]✅ 连通成功[/bold green]  "
                f"耗时 [cyan]{elapsed:.2f}s[/cyan]\n"
                f"  模型回复: [dim]{result[:120]}{'...' if len(result) > 120 else ''}[/dim]"
            )
        except Exception as e:
            console.print(f"\n[bold red]❌ 连通失败[/bold red]\n  {e}")
            raise typer.Exit(code=1)

    asyncio.run(do_ping())


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
