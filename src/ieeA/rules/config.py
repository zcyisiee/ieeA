import json
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class LLMConfig(BaseModel):
    sdk: Optional[str] = "openai"
    models: Union[str, List[str]] = "gpt-4o-mini"
    key: Optional[str] = None
    endpoint: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4000

    @field_validator("sdk")
    @classmethod
    def validate_sdk(cls, v):
        if v is not None and v not in ("openai", "anthropic"):
            raise ValueError(f"sdk must be 'openai', 'anthropic', or None, got '{v}'")
        return v

    @field_validator("models")
    @classmethod
    def validate_models(cls, v):
        if isinstance(v, str) and not v.strip():
            raise ValueError("models cannot be empty")
        if isinstance(v, list) and len(v) == 0:
            raise ValueError("models list cannot be empty")
        return v

    def get_model(self) -> str:
        if isinstance(self.models, list):
            return self.models[0]
        return self.models


class CompilationConfig(BaseModel):
    engine: str = "xelatex"
    timeout: int = 120
    clean_aux: bool = True


class PathsConfig(BaseModel):
    output_dir: str = "output"
    cache_dir: str = ".cache"


class FontConfig(BaseModel):
    """CJK font configuration."""

    main: Optional[str] = None
    sans: Optional[str] = None
    mono: Optional[str] = None
    auto_detect: bool = True


class TranslationConfig(BaseModel):
    """Translation configuration."""

    custom_system_prompt: Optional[str] = None
    custom_user_prompt: Optional[str] = None
    preserve_terms: List[str] = Field(default_factory=list)
    quality_mode: str = "standard"  # "standard" or "high"
    examples_path: Optional[str] = None  # User-defined few-shot examples path


class Config(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    compilation: CompilationConfig = Field(default_factory=CompilationConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    fonts: FontConfig = Field(default_factory=FontConfig)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)


def load_defaults() -> Dict[str, Any]:
    """Load default configuration from the package."""
    base_path = Path(__file__).parent.parent
    default_path = base_path / "defaults" / "config.yaml"

    if default_path.exists():
        with open(default_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def load_user_config() -> Dict[str, Any]:
    """Load user configuration from ~/.ieeA/config.yaml."""
    home = Path.home()
    config_path = home / ".ieeA" / "config.yaml"

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries."""
    result = base.copy()
    for k, v in update.items():
        if isinstance(v, dict) and k in result and isinstance(result[k], dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config() -> Config:
    """Load and merge configuration from defaults and user overrides."""
    config_data = load_defaults()
    user_data = load_user_config()
    merged_data = deep_merge(config_data, user_data)
    return Config(**merged_data)
