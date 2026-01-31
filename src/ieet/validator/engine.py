import re
from typing import List, Optional, Any
from pydantic import BaseModel
from ieet.validator.rules import BuiltInRules
from ieet.rules.validation_rules import RuleSet, ValidationRule

class ValidationError(BaseModel):
    message: str
    severity: str = "error" # error, warning, info
    location: Optional[int] = None
    suggestion: Optional[str] = None

class ValidationResult(BaseModel):
    valid: bool
    errors: List[ValidationError]
    score: float = 1.0

class ValidationEngine:
    def __init__(self):
        pass

    def validate(self, translated: str, original: str, rules: Optional[RuleSet] = None) -> ValidationResult:
        errors = []
        
        # 1. Structural Validation (Built-in)
        # Braces
        brace_errors = BuiltInRules.check_braces(translated)
        for msg in brace_errors:
            errors.append(ValidationError(message=f"Unbalanced braces: {msg}", severity="error"))
            
        # Citations
        cite_errors = BuiltInRules.check_citations(original, translated)
        for msg in cite_errors:
            errors.append(ValidationError(message=msg, severity="error"))
            
        # References
        ref_errors = BuiltInRules.check_references(original, translated)
        for msg in ref_errors:
            errors.append(ValidationError(message=msg, severity="error"))
            
        # Math Environments
        math_errors = BuiltInRules.check_math_environments(original, translated)
        for msg in math_errors:
            errors.append(ValidationError(message=msg, severity="error"))
            
        # Length Ratio (Warning only)
        ratio_errors = BuiltInRules.check_length_ratio(original, translated)
        for msg in ratio_errors:
            errors.append(ValidationError(message=f"Length ratio warning: {msg}", severity="warning"))

        # 2. User-Defined Rules (Regex)
        if rules:
            for rule in rules.rules:
                if rule.pattern:
                    matches = re.finditer(rule.pattern, translated)
                    for match in matches:
                        msg = rule.description or f"Matched pattern: {rule.pattern}"
                        errors.append(ValidationError(
                            message=msg, 
                            severity=rule.severity,
                            location=match.start(),
                            suggestion=rule.replacement
                        ))

        # Determine validity
        # Valid if no errors (warnings are okay for 'valid' but flagged)
        valid = not any(e.severity == "error" for e in errors)
        
        return ValidationResult(
            valid=valid,
            errors=errors,
            score=1.0 # Placeholder for scoring logic
        )

    def apply_fixes(self, translated: str, rules: RuleSet) -> str:
        """Apply auto-fix rules."""
        fixed_text = translated
        
        for rule in rules.rules:
            if rule.replacement is not None and rule.pattern:
                # Naive application: apply regex substitution
                # Be careful with overlapping rules or order dependency
                try:
                    fixed_text = re.sub(rule.pattern, rule.replacement, fixed_text)
                except re.error as e:
                    print(f"Error applying rule {rule.id}: {e}")
                    
        return fixed_text
