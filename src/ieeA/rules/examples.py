"""Few-shot example loading for translation."""

import yaml
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def load_builtin_examples() -> List[Dict[str, str]]:
    """Load built-in examples from package defaults.

    Returns:
        List of example dicts with 'source' and 'target' keys
    """
    base_path = Path(__file__).parent.parent
    examples_path = base_path / "defaults" / "examples.yaml"
    if examples_path.exists():
        try:
            with open(examples_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("examples", [])
            return []
        except Exception as e:
            logger.warning(f"Failed to load built-in examples: {e}")
            return []
    return []


def load_examples(custom_path: Optional[str] = None) -> List[Dict[str, str]]:
    """Load examples from built-in defaults and optional custom path.

    Args:
        custom_path: Optional path to user's custom examples.yaml

    Returns:
        List of example dicts with 'source' and 'target' keys.
        Custom examples are appended after built-in examples.
    """
    examples = load_builtin_examples()

    if custom_path:
        try:
            custom_file = Path(custom_path)
            if custom_file.exists():
                with open(custom_file, "r", encoding="utf-8") as f:
                    custom_data = yaml.safe_load(f)
                if isinstance(custom_data, list):
                    custom_examples = custom_data
                elif isinstance(custom_data, dict):
                    custom_examples = custom_data.get("examples", [])
                else:
                    custom_examples = []
                examples.extend(custom_examples)
                logger.info(
                    f"Loaded {len(custom_examples)} custom examples from {custom_path}"
                )
        except Exception as e:
            logger.warning(f"Failed to load custom examples from {custom_path}: {e}")

    logger.info(f"Total examples loaded: {len(examples)}")
    return examples
