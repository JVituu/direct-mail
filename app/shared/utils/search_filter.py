import json


OR_FILTER_PREFIX = "__MALA_DIRETA_OR_FILTER__:"


def encode_or_filter(values: list[str] | tuple[str, ...] | set[str]) -> str:
    clean_values = [str(value).strip() for value in values if str(value).strip()]
    return OR_FILTER_PREFIX + json.dumps(clean_values, ensure_ascii=False)


def decode_or_filter(search: str) -> list[str] | None:
    clean_search = str(search or "").strip()
    if not clean_search.startswith(OR_FILTER_PREFIX):
        return None

    payload = clean_search[len(OR_FILTER_PREFIX) :]
    try:
        values = json.loads(payload)
    except json.JSONDecodeError:
        return []

    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]
