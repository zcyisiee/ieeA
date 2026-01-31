import yaml
from pathlib import Path
from typing import Dict, Union, Optional, Any
from pydantic import BaseModel, Field

class GlossaryEntry(BaseModel):
    target: str
    context: Optional[str] = None
    domain: Optional[str] = None
    priority: int = 0
    notes: Optional[str] = None

class Glossary(BaseModel):
    terms: Dict[str, GlossaryEntry] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Union[str, Dict]]) -> "Glossary":
        terms = {}
        for key, value in data.items():
            if isinstance(value, str):
                terms[key] = GlossaryEntry(target=value)
            elif isinstance(value, dict):
                terms[key] = GlossaryEntry(**value)
        return cls(terms=terms)

    def merge(self, other: "Glossary") -> None:
        """Merge another glossary into this one. 
        Entries from 'other' overwrite existing entries with the same key.
        """
        for key, entry in other.terms.items():
            self.terms[key] = entry
            
    def get(self, term: str) -> Optional[GlossaryEntry]:
        """Case-sensitive lookup."""
        return self.terms.get(term)

def load_default_glossary() -> Dict[str, Any]:
    base_path = Path(__file__).parent.parent
    path = base_path / "defaults" / "glossary.yaml"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def load_user_glossary() -> Dict[str, Any]:
    home = Path.home()
    path = home / ".ieet" / "glossary.yaml"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def load_glossary() -> Glossary:
    """Load and merge glossary from defaults and user overrides."""
    default_data = load_default_glossary()
    glossary = Glossary.from_dict(default_data)
    
    user_data = load_user_glossary()
    user_glossary = Glossary.from_dict(user_data)
    
    glossary.merge(user_glossary)
    return glossary
