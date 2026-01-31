from typing import List, Optional, Any
from pydantic import BaseModel, Field
import yaml
from pathlib import Path

class ValidationRule(BaseModel):
    id: str
    description: str
    severity: str = "warning"  # error, warning, info
    pattern: str  # Regex pattern to match
    replacement: Optional[str] = None  # Suggested replacement
    trigger: Optional[str] = None # Event trigger (e.g., "pre-compile", "post-translate")
    
class RuleSet(BaseModel):
    rules: List[ValidationRule] = Field(default_factory=list)
    
    def get_rules_by_trigger(self, trigger: str) -> List[ValidationRule]:
        return [r for r in self.rules if r.trigger == trigger or r.trigger is None]

def load_rules_from_file(path: Path) -> RuleSet:
    if not path.exists():
        return RuleSet()
        
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        
    # Expecting a list of rules under a "rules" key or just a list
    rules_data = data.get("rules", []) if isinstance(data, dict) else data
    
    # Handle case where rules_data might be None
    if rules_data is None:
        rules_data = []
        
    rules = []
    for r in rules_data:
        if isinstance(r, dict):
            try:
                rules.append(ValidationRule(**r))
            except Exception as e:
                # Log error or skip invalid rule
                print(f"Warning: Failed to load rule {r.get('id', 'unknown')}: {e}")
                
    return RuleSet(rules=rules)
