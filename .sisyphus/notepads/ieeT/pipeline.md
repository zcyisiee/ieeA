# Translation Pipeline Implementation Notes

## Prompt Engineering Decisions

1. **Placeholder Format**: Used `{{GLOSS_NNN}}` format for glossary term placeholders
   - Double braces prevent conflicts with LaTeX commands
   - Numbered format allows tracking multiple terms

2. **Prompt Structure**: Chinese prompt following hjfy.top recommendations
   - Clear translation style instructions (意译/改写风格)
   - Explicit LaTeX preservation requirement
   - Glossary hints embedded in prompt
   - Few-shot examples support for better quality

3. **System vs User Message**: Kept flexibility for both approaches
   - `build_translation_prompt()` for single-message providers
   - `build_system_message()` for providers with separate system messages

## Retry Strategy

1. **Exponential Backoff**: `delay = base_delay * 2^attempt`
   - Base delay: 1.0 second (configurable)
   - Max retries: 3 (configurable)
   - Prevents API rate limit exhaustion

2. **Error Propagation**: After max retries, original error is raised
   - Allows caller to handle specific error types
   - No silent failures

## State Management

1. **Resume Capability**: JSON state file with completed chunk IDs
   - Saves after each chunk translation
   - Loads on pipeline start to skip completed chunks
   - Preserves order in final output

2. **State Structure**:
   ```json
   {
     "completed": ["chunk_001", "chunk_002"],
     "results": [{"chunk_id": "...", "source": "...", "translation": "..."}]
   }
   ```

## Glossary Preprocessing

1. **Longest Match First**: Terms sorted by length descending
   - Prevents partial matches (e.g., "attention" matching before "attention mechanism")
   
2. **Case Sensitivity**: Exact match required
   - Consistent with Glossary.get() behavior
