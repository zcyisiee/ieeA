# CLI Implementation

## Design Decisions
- **Typer & Rich**: Used `typer` for command parsing and `rich` for output formatting to provide a modern, colorful CLI experience.
- **Asyncio**: The `translate` command runs the async pipeline using `asyncio.run()`.
- **Progress Bars**: Used `rich.progress` to show status for download, parsing, translation, and compilation steps.
- **Configuration**: Implemented nested configuration handling (e.g., `llm.provider`) to allow easy updates via CLI.
- **Error Handling**: Used `try/except` blocks to catch pipeline errors and display them with `[red]` formatting, avoiding raw stack traces for expected errors.

## Commands
- `ieet translate <url>`: Main entry point. Handles the full pipeline.
- `ieet config show/set`: Config management.
- `ieet glossary add`: Term management.
- `ieet validate`: Standalone validation tool.

## Issues / Limitations
- **Help Message**: There is a known issue with `typer`'s help generation (`--help`) causing a `TypeError` in the current test environment, possibly due to `click`/`typer` version mismatch. The command execution itself functions correctly.
- **Progress Tracking**: The `TranslationPipeline` processes chunks internally. To visualize progress, we manually iterate through chunks in the CLI instead of using `translate_document` directly. This gives better feedback but duplicates some loop logic.

## Future Improvements
- Add interactive mode for resolving validation errors.
- Support batch processing of multiple URLs.
- Add `glossary list` and `glossary import` commands.
