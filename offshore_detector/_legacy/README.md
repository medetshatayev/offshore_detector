# Legacy Files

This directory contains old implementation files that have been replaced in the refactored codebase.

## Replaced Files

- **ai_classifier.py** → Replaced by `llm_client.py` (improved API usage, structured output)
- **analyzer.py** → Replaced by `processor.py` (cleaner architecture, better separation of concerns)
- **app.py** → Replaced by `web_app.py` (migrated from Flask to FastAPI)
- **fuzzy_matcher.py** → Replaced by `simple_matcher.py` (simplified matching logic per requirements)
- **web_research.py** → Removed (simplified to use LLM's web_search tool instead)

## Why Refactored?

The codebase was refactored to:
1. Meet exact production requirements (System Prompt A & B, structured output schema)
2. Simplify matching logic (only simple fuzzy matching, no complex web research)
3. Improve maintainability (better module separation, pydantic validation)
4. Use FastAPI instead of Flask (better async support, automatic OpenAPI docs)
5. Add comprehensive logging, error handling, and security features

## Backward Compatibility

The main `offshore_detector.py` module still exports `process_transactions` for backward compatibility.
