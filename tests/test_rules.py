import os
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from ieet.rules.config import load_config, Config, LLMConfig
from ieet.rules.glossary import load_glossary, Glossary, GlossaryEntry
from ieet.rules.validation_rules import load_rules_from_file, RuleSet, ValidationRule

# --- Config Tests ---

def test_load_defaults_config():
    """Test that default configuration is loaded correctly."""
    config = load_config()
    assert isinstance(config, Config)
    assert config.llm.provider == "openai"
    assert config.compilation.engine == "xelatex"
    # defaults/config.yaml values
    assert config.llm.model == "gpt-4o-mini"

def test_config_merge():
    """Test that user configuration overrides defaults."""
    user_config_yaml = """
    llm:
      provider: "claude"
      temperature: 0.7
    """
    
    with patch("ieet.rules.config.load_user_config") as mock_user_load:
        mock_user_load.return_value = yaml.safe_load(user_config_yaml)
        
        config = load_config()
        
        # Overridden values
        assert config.llm.provider == "claude"
        assert config.llm.temperature == 0.7
        # Preserved default values
        assert config.llm.model == "gpt-4o-mini"
        assert config.compilation.engine == "xelatex"

# --- Glossary Tests ---

def test_glossary_parsing():
    """Test parsing of both simple and structured glossary entries."""
    data = {
        "Simple": "Target",
        "Complex": {
            "target": "ComplexTarget",
            "context": "Context",
            "priority": 5
        }
    }
    glossary = Glossary.from_dict(data)
    
    assert glossary.get("Simple").target == "Target"
    assert glossary.get("Complex").target == "ComplexTarget"
    assert glossary.get("Complex").context == "Context"
    assert glossary.get("Complex").priority == 5

def test_glossary_merge():
    """Test merging glossaries."""
    g1 = Glossary.from_dict({"A": "A1", "B": "B1"})
    g2 = Glossary.from_dict({"B": "B2", "C": "C1"})
    
    g1.merge(g2)
    
    assert g1.get("A").target == "A1"
    assert g1.get("B").target == "B2"  # Overwritten
    assert g1.get("C").target == "C1"  # Added

def test_load_glossary_integration():
    """Test loading the default glossary."""
    glossary = load_glossary()
    assert glossary.get("LLM") is not None
    assert glossary.get("Transformer") is not None

# --- Rule Tests ---

def test_load_rules_from_yaml(tmp_path):
    """Test loading validation rules from a YAML file."""
    rule_content = r"""
    rules:
      - id: "no-passive"
        description: "Avoid passive voice"
        pattern: '\\bwas\\s+\\w+ed\\b'
        severity: "warning"
        trigger: "post-translate"
      - id: "check-acronym"
        description: "Check undefined acronyms"
        pattern: "[A-Z]{3,}"
    """
    
    rule_file = tmp_path / "rules.yaml"
    rule_file.write_text(rule_content, encoding="utf-8")
    
    rule_set = load_rules_from_file(rule_file)
    
    assert len(rule_set.rules) == 2
    
    r1 = rule_set.rules[0]
    assert r1.id == "no-passive"
    assert r1.severity == "warning"
    assert r1.trigger == "post-translate"
    
    r2 = rule_set.rules[1]
    assert r2.id == "check-acronym"
    assert r2.severity == "warning"  # Default
    assert r2.trigger is None

def test_rule_filtering():
    """Test filtering rules by trigger."""
    rules = [
        ValidationRule(id="1", description="d", pattern="p", trigger="pre"),
        ValidationRule(id="2", description="d", pattern="p", trigger="post"),
        ValidationRule(id="3", description="d", pattern="p", trigger=None) # Applies to all? Or just default? Logic says explicit None match
    ]
    rs = RuleSet(rules=rules)
    
    pre_rules = rs.get_rules_by_trigger("pre")
    # Our logic in validation_rules.py: 
    # return [r for r in self.rules if r.trigger == trigger or r.trigger is None]
    
    assert len(pre_rules) == 2 # id="1" and id="3"
    ids = [r.id for r in pre_rules]
    assert "1" in ids
    assert "3" in ids
