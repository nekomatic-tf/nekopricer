pricelist_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "sku": {"type": "string"},
                    "source": {"type": "string"},
                    "time": {"type": "number"},
                    "buy": {
                        "type": "object",
                        "properties": {"keys": {"type": "number"}, "metal": {"type": "number"}},
                        "required": ["keys", "metal"],
                        "additionalProperties": False,
                    },
                    "sell": {
                        "type": "object",
                        "properties": {"keys": {"type": "number"}, "metal": {"type": "number"}},
                        "required": ["keys", "metal"],
                        "additionalProperties": False,
                    },
                    "strategy": {
                        "type": "object",
                        "properties": {"type": {"type": "string"}, "valid": {"type": "boolean"}},
                        "required": ["type", "valid"],
                        "additionalProperties": False,
                    },
                    "fallback": {"type": "string"},
                },
                "required": ["name", "sku", "source", "time", "buy", "sell"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}
