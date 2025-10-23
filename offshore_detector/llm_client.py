"""
OpenAI LLM client for transaction classification with structured output.
Uses Responses API with web_search tool and pydantic validation.
"""
import os
import logging
import json
from typing import Dict, Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import ValidationError

from schema import TransactionClassification, TransactionSignals, Classification, MatchSignal, LABEL_MAP_RU
from prompts import get_system_prompts, build_user_prompt


# Initialize OpenAI client
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o')  # Default to gpt-4o
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# Removed _extract_output_text - not needed with Responses API streaming


def _parse_json_response(text: str) -> dict:
    """
    Parse JSON from LLM response, handling markdown code blocks.
    
    Args:
        text: Raw text from LLM
    
    Returns:
        Parsed JSON dict
    
    Raises:
        json.JSONDecodeError: If parsing fails
    """
    if not text:
        raise json.JSONDecodeError("Empty response text", "", 0)
    
    # Clean up text
    text = text.strip()
    
    # Remove markdown code blocks
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0].strip()
    elif '```' in text:
        text = text.split('```')[1].split('```')[0].strip()
    
    # Parse JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logging.error(f"JSON parse error: {e}")
        logging.error(f"Text preview: {text[:500]}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def _call_openai_api(system_prompt_a: str, system_prompt_b: str, user_prompt: str) -> str:
    """
    Call OpenAI Responses API with retry logic and web_search tool.
    
    Args:
        system_prompt_a: System prompt with offshore list
        system_prompt_b: System prompt with web_search instructions
        user_prompt: User prompt with transaction data
    
    Returns:
        Raw text response from API
    
    Raises:
        Exception: If API call fails after retries
    """
    if not client:
        raise ValueError("OpenAI client not initialized. Check OPENAI_API_KEY.")
    
    try:
        # Combine system prompts
        combined_instructions = f"{system_prompt_a}\n\n{system_prompt_b}"
        
        # Build request - using Responses API
        request_args = {
            'model': OPENAI_MODEL,
            'instructions': combined_instructions.strip(),
            'input': [{"role": "user", "content": user_prompt}],
            'tools': [{"type": "web_search"}],
            'tool_choice': "auto",
            'metadata': {"user_location": "Country: KZ, Timezone: Asia/Almaty"}
        }
        
        # Stream response and collect output
        output_parts = []
        with client.responses.stream(**request_args) as stream:
            for event in stream:
                if event.type == 'response.output_text.delta' and hasattr(event, 'delta'):
                    output_parts.append(event.delta)
            
            # Get final response
            final_response = stream.get_final_response()
        
        # Combine output parts
        text = ''.join(output_parts)
        
        if not text:
            raise ValueError("Empty response from OpenAI API")
        
        return text
        
    except Exception as e:
        logging.error(f"OpenAI API call failed: {e}", exc_info=True)
        raise


def classify_transaction(
    transaction_data: dict,
    local_signals: dict
) -> TransactionClassification:
    """
    Classify a single transaction using OpenAI with structured output.
    
    Args:
        transaction_data: Dict with all transaction fields
        local_signals: Dict with SWIFT and fuzzy matching signals
    
    Returns:
        TransactionClassification pydantic model instance
    """
    # Get system prompts
    system_prompt_a, system_prompt_b = get_system_prompts()
    
    # Build user prompt
    user_prompt = build_user_prompt(transaction_data, local_signals)
    
    try:
        # Call API
        logging.debug(f"Calling OpenAI API for transaction: {transaction_data.get('№п/п', 'unknown')}")
        raw_response = _call_openai_api(system_prompt_a, system_prompt_b, user_prompt)
        
        # Parse JSON
        parsed = _parse_json_response(raw_response)
        
        # Validate and construct pydantic model
        classification = TransactionClassification(**parsed)
        
        logging.info(f"Transaction classified: {classification.classification.label} "
                    f"(confidence: {classification.classification.confidence:.2f})")
        
        return classification
        
    except json.JSONDecodeError as e:
        # JSON parsing failed
        logging.error(f"Failed to parse LLM response as JSON: {e}")
        return _create_fallback_classification(
            transaction_data, 
            local_signals, 
            f"JSON parse error: {str(e)}"
        )
        
    except ValidationError as e:
        # Pydantic validation failed
        logging.error(f"LLM response failed schema validation: {e}")
        return _create_fallback_classification(
            transaction_data,
            local_signals,
            f"Schema validation error: {str(e)}"
        )
        
    except Exception as e:
        # Other errors (API failure, etc.)
        logging.error(f"Unexpected error in transaction classification: {e}", exc_info=True)
        return _create_fallback_classification(
            transaction_data,
            local_signals,
            f"Classification error: {str(e)}"
        )


def _create_fallback_classification(
    transaction_data: dict,
    local_signals: dict,
    error_msg: str
) -> TransactionClassification:
    """
    Create a fallback classification when LLM fails.
    Uses simple heuristics based on local signals.
    
    Args:
        transaction_data: Transaction data dict
        local_signals: Local matching signals
        error_msg: Error message to include
    
    Returns:
        TransactionClassification with fallback values
    """
    # Simple heuristic: if SWIFT is offshore, mark as OFFSHORE_SUSPECT
    swift_info = local_signals.get('swift', {})
    is_offshore_swift = swift_info.get('is_offshore', False)
    
    # Check if any fuzzy matches exist
    has_matches = any([
        local_signals.get('country_code_match'),
        local_signals.get('country_name_match'),
        local_signals.get('city_match')
    ])
    
    # Determine label
    if is_offshore_swift:
        label = "OFFSHORE_SUSPECT"
        confidence = 0.6
        reasoning = "SWIFT код указывает на возможную офшорную юрисдикцию (автоматическая классификация)"
    elif has_matches:
        label = "OFFSHORE_SUSPECT"
        confidence = 0.5
        reasoning = "Обнаружены совпадения с офшорными юрисдикциями (автоматическая классификация)"
    else:
        label = "OFFSHORE_NO"
        confidence = 0.7
        reasoning = "Офшорные признаки не обнаружены (автоматическая классификация)"
    
    # Build signals
    signals = TransactionSignals(
        swift_country_code=swift_info.get('code'),
        swift_country_name=swift_info.get('name'),
        is_offshore_by_swift=is_offshore_swift,
        country_name_match=MatchSignal(**(local_signals.get('country_name_match') or {})),
        country_code_match=MatchSignal(**(local_signals.get('country_code_match') or {})),
        city_match=MatchSignal(**(local_signals.get('city_match') or {}))
    )
    
    return TransactionClassification(
        transaction_id=transaction_data.get('№п/п'),
        direction=transaction_data.get('direction', 'incoming'),
        amount_kzt=transaction_data.get('amount_kzt_normalized', 0.0),
        signals=signals,
        classification=Classification(label=label, confidence=confidence),
        reasoning_short_ru=reasoning,
        sources=[],
        llm_error=error_msg
    )


def format_result_column(classification: TransactionClassification) -> str:
    """
    Format the classification result as a string for the "Результат" Excel column.
    
    Format: Итог: {label_ru} | Уверенность: {conf%} | Объяснение: {reasoning} | 
            Совпадения: {signals} | Источники: {sources}
    
    Args:
        classification: TransactionClassification instance
    
    Returns:
        Formatted result string
    """
    # Get Russian label
    label_ru = LABEL_MAP_RU.get(classification.classification.label, classification.classification.label)
    
    # Format confidence as percentage
    conf_pct = int(classification.classification.confidence * 100)
    
    # Build signals summary
    signals_parts = []
    if classification.signals.swift_country_name:
        signals_parts.append(f"SWIFT:{classification.signals.swift_country_name}")
    if classification.signals.country_name_match and classification.signals.country_name_match.value:
        signals_parts.append(f"Страна:{classification.signals.country_name_match.value}")
    if classification.signals.city_match and classification.signals.city_match.value:
        signals_parts.append(f"Город:{classification.signals.city_match.value}")
    
    signals_str = ", ".join(signals_parts) if signals_parts else "нет"
    
    # Build sources summary
    sources_str = "; ".join(classification.sources) if classification.sources else "нет"
    
    # Assemble final string
    result = (
        f"Итог: {label_ru} | "
        f"Уверенность: {conf_pct}% | "
        f"Объяснение: {classification.reasoning_short_ru} | "
        f"Совпадения: {signals_str} | "
        f"Источники: {sources_str}"
    )
    
    # Add error note if present
    if classification.llm_error:
        result += f" | ОШИБКА: {classification.llm_error}"
    
    return result
