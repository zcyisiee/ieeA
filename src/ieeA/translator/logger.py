"""Translation logging infrastructure."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List
from rich.console import Console

console = Console()


class TranslationLogger:
    """Structured logger for translation pipeline."""

    def __init__(self, output_dir: Path, verbose: bool = False, hq_mode: bool = False):
        """Initialize logger.

        Args:
            output_dir: Directory where log file will be saved
            verbose: Whether to enable verbose console output
            hq_mode: Whether high-quality mode is enabled
        """
        self.output_dir = output_dir
        self.verbose = verbose
        self.hq_mode = hq_mode

        # Log data structure
        self.log_data: Dict[str, Any] = {
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "hq_mode": hq_mode,
            "source_file": "",
            "chunks": [],
            "batches": [],
            "skipped": [],
            "timing": {"total_seconds": 0, "llm_seconds": 0},
        }

        # Timing tracking
        self.start_time: Optional[datetime] = None
        self.llm_time_total: float = 0.0

    def set_source_file(self, filepath: str):
        """Set the source file path."""
        self.log_data["source_file"] = filepath

    def start_timing(self):
        """Start timing the translation process."""
        self.start_time = datetime.now()

    def log_chunk(
        self,
        chunk_id: str,
        chunk_type: str,
        length: int,
        batched: bool = False,
        batch_id: Optional[str] = None,
    ):
        """Log a chunk being processed.

        Args:
            chunk_id: Unique chunk identifier
            chunk_type: Type of chunk (e.g., 'paragraph', 'title', 'abstract')
            length: Character length of chunk
            batched: Whether this chunk is part of a batch
            batch_id: ID of the batch (if batched=True)
        """
        chunk_entry = {
            "chunk_id": chunk_id,
            "type": chunk_type,
            "length": length,
            "batched": batched,
            "batch_id": batch_id,
            "timestamp": datetime.now().isoformat(),
        }
        self.log_data["chunks"].append(chunk_entry)

        if self.verbose:
            console.print(
                f"[dim]Chunk {chunk_id}: {chunk_type} ({length} chars)"
                f"{f' [batch: {batch_id}]' if batched else ''}[/dim]"
            )

    def log_skip(self, chunk_id: str, reason: str, content: str):
        """Log a skipped chunk.

        Args:
            chunk_id: Unique chunk identifier
            reason: Reason for skipping
            content: The skipped content (truncated if too long)
        """
        # Truncate content for logging
        display_content = content[:100] + "..." if len(content) > 100 else content

        skip_entry = {
            "chunk_id": chunk_id,
            "reason": reason,
            "content": display_content,
            "timestamp": datetime.now().isoformat(),
        }
        self.log_data["skipped"].append(skip_entry)

        if self.verbose:
            console.print(f"[yellow]Skipped {chunk_id}: {reason}[/yellow]")

    def log_batch(
        self, batch_id: str, batch_type: str, chunk_count: int, total_chars: int
    ):
        """Log a batch translation.

        Args:
            batch_id: Unique batch identifier
            batch_type: Type of batch
            chunk_count: Number of chunks in batch
            total_chars: Total character count in batch
        """
        batch_entry = {
            "batch_id": batch_id,
            "type": batch_type,
            "chunk_count": chunk_count,
            "total_chars": total_chars,
            "timestamp": datetime.now().isoformat(),
        }
        self.log_data["batches"].append(batch_entry)

        if self.verbose:
            console.print(
                f"[dim]Batch {batch_id}: {chunk_count} chunks, {total_chars} chars[/dim]"
            )

    def add_llm_time(self, seconds: float):
        """Add LLM API call time.

        Args:
            seconds: Time spent on LLM API call
        """
        self.llm_time_total += seconds

    def save(self) -> Optional[Path]:
        """Save log file to disk.

        Returns:
            Path to saved log file, or None if save failed
        """
        # Finalize timing
        if self.start_time:
            total_seconds = (datetime.now() - self.start_time).total_seconds()
            self.log_data["timing"]["total_seconds"] = total_seconds
            self.log_data["timing"]["llm_seconds"] = self.llm_time_total

        # Generate log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"translation_log_{timestamp}.json"
        log_path = self.output_dir / log_filename

        try:
            # Ensure output directory exists
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Write log file
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(self.log_data, f, indent=2, ensure_ascii=False)

            if self.verbose:
                console.print(f"[green]Log saved to {log_path}[/green]")

            return log_path

        except Exception as e:
            console.print(f"[yellow]Warning: Failed to save log file: {e}[/yellow]")
            return None
