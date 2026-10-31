# Personal Finance Coach Backend

## Architecture
Input (CSV / PDF / SMS / typed or dictated text) -> local PII sanitizer -> (a) LLM agent for parsing/intent/coaching and (b) deterministic Python math engine -> SQLite state store -> JSON API.

## Hard Rules
1. **LLM-Optional**: Must fully work with NO LLM key (rule-based fallbacks everywhere).
2. **Deterministic Math**: All arithmetic is Python, never the LLM.
3. **No Security Advice**: Never recommend specific securities (stocks, funds, tickers, crypto).
4. **Secure Keys**: Keys only from environment variables (.env locally, host secrets when deployed). Never hardcode.
5. **PII Privacy**: Sanitize PII before storing anything or sending text to any LLM.
6. **In-Memory Processing**: Uploaded files are processed in memory, never saved to disk.
7. **CORS**: Enable CORS (configurable allowed origins via env, default "*" for the hackathon).
