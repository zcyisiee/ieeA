# Custom Rules & Glossary Guide

This guide covers how to create custom glossaries and validation rules for ieeT.

## Glossary

A glossary ensures consistent translation of technical terms across your document.

### Glossary File Format

Create a YAML file with term mappings:

```yaml
# glossary.yaml

# Simple mappings (term -> translation)
"LLM": "大语言模型"
"SOTA": "最先进的"
"CNN": "卷积神经网络"
"RNN": "循环神经网络"

# Structured mappings (with metadata)
"Transformer":
  target: "Transformer架构"
  context: "Deep Learning"
  domain: "NLP"
  notes: "Architecture based on self-attention"

"attention mechanism":
  target: "注意力机制"
  priority: 10  # Higher priority terms are matched first

"self-attention":
  target: "自注意力"
  context: "Neural Networks"
```

### Glossary Fields

| Field | Required | Description |
|-------|----------|-------------|
| `target` | Yes | The Chinese translation |
| `context` | No | When this translation applies |
| `domain` | No | Subject area (NLP, CV, etc.) |
| `notes` | No | Additional context for translators |
| `priority` | No | Matching priority (higher = first) |

### Using Your Glossary

```bash
# Via command line
ieeA translate paper.tex --glossary my-glossary.yaml

# Via configuration
# In ~/.ieeA/config.yaml:
glossary:
  path: ~/my-glossary.yaml
  use_builtin: true
  merge: true
```

### Built-in Glossary

ieeT includes a built-in glossary with common ML/AI terms. To use only the built-in glossary:

```yaml
glossary:
  use_builtin: true
  merge: false
```

To merge your glossary with the built-in:

```yaml
glossary:
  path: my-glossary.yaml
  use_builtin: true
  merge: true  # Your terms override built-in on conflict
```

### Glossary Best Practices

1. **Longer terms first**: "attention mechanism" should come before "attention"
2. **Case sensitivity**: Terms are case-sensitive by default
3. **Context matters**: Use the `context` field for ambiguous terms
4. **Consistent style**: Choose one style and stick with it

## Validation Rules

Validation rules help catch translation errors automatically.

### Rule File Format

Create a YAML file with validation rules:

```yaml
# rules.yaml
rules:
  - id: no-english-quotes
    description: "Replace English quotes with Chinese quotes"
    severity: warning
    pattern: '"([^"]+)"'
    replacement: '"\1"'
    
  - id: preserve-urls
    description: "URLs should not be translated"
    severity: error
    pattern: 'https?://[^\s]+'
    
  - id: no-double-periods
    description: "Avoid double periods"
    severity: warning
    pattern: '。。'
    replacement: '。'
    
  - id: check-parentheses
    description: "Use Chinese parentheses"
    severity: info
    pattern: '\(([^)]+)\)'
    replacement: '（\1）'
```

### Rule Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier for the rule |
| `description` | Yes | Human-readable description |
| `severity` | No | `error`, `warning`, or `info` (default: `warning`) |
| `pattern` | Yes | Regex pattern to match |
| `replacement` | No | Replacement text (enables auto-fix) |
| `trigger` | No | When to apply: `pre-compile`, `post-translate` |

### Severity Levels

- **error**: Translation will fail validation
- **warning**: Flagged but translation continues
- **info**: Informational only

### Using Custom Rules

```bash
# Via command line
ieeA translate paper.tex --rules my-rules.yaml

# Via configuration
validation:
  rules_path: ~/my-rules.yaml
```

### Auto-Fix Rules

Rules with a `replacement` field can automatically fix issues:

```bash
# Apply auto-fixes
ieeA translate paper.tex --auto-fix
```

### Built-in Validation

ieeT performs these validations automatically:

1. **Brace Balance**: Check `{}`, `()`, `[]` are balanced
2. **Citation Preservation**: All `\cite{}` references preserved
3. **Reference Preservation**: All `\ref{}` references preserved
4. **Math Environment Preservation**: Math environments intact
5. **Length Ratio Check**: Translation length is reasonable

### Example Rules for Academic Papers

```yaml
# academic-rules.yaml
rules:
  # Preserve figure references
  - id: figure-ref
    description: "Figure references should use Chinese format"
    severity: warning
    pattern: 'Figure\s+(\d+)'
    replacement: '图\1'
    
  # Preserve table references
  - id: table-ref
    description: "Table references should use Chinese format"
    severity: warning
    pattern: 'Table\s+(\d+)'
    replacement: '表\1'
    
  # Preserve equation references
  - id: equation-ref
    description: "Equation references should use Chinese format"
    severity: warning
    pattern: 'Equation\s+\((\d+)\)'
    replacement: '公式（\1）'
    
  # Check for untranslated common words
  - id: untranslated-the
    description: "The word 'the' should be translated"
    severity: info
    pattern: '\bthe\b'
    
  # Ensure proper Chinese punctuation
  - id: chinese-comma
    description: "Use Chinese comma"
    severity: warning
    pattern: ',(?=[\u4e00-\u9fff])'
    replacement: '，'
```

## Combining Glossary and Rules

For best results, use both:

```yaml
# config.yaml
glossary:
  path: technical-terms.yaml
  use_builtin: true
  merge: true

validation:
  rules_path: academic-rules.yaml
  auto_fix: true
```

## Next Steps

- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [Known Limitations](known-limitations.md) - Current limitations
