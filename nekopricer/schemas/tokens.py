tokens_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "tokens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"key": {"type": "string"}, "locked": {"type": "boolean"}, "user": {"type": "string"}},
                "required": ["key", "locked", "user"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["tokens"],
    "additionalProperties": False,
}
