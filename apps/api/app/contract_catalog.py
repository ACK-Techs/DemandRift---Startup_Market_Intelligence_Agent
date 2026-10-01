"""Public, deterministic contract catalog (no runtime credentials or private data)."""
import json

from fastapi import APIRouter

from app.contracts import SCHEMA_VERSION, WIRE_MODELS


def wire_catalog() -> dict:
    definitions = {}
    for model in WIRE_MODELS:
        schema = model.model_json_schema(mode="serialization")
        nested = schema.pop("$defs", {})
        for name, definition in {**nested, model.__name__: schema}.items():
            if name in definitions and definitions[name] != definition:
                raise ValueError(f"contract definition collision: {name}")
            definitions[name] = definition
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": SCHEMA_VERSION,
        "models": {m.__name__: {"$ref": f"#/$defs/{m.__name__}"} for m in WIRE_MODELS},
        "$defs": dict(sorted(definitions.items())),
    }


def openapi_wire_schemas() -> dict:
    # OpenAPI uses a different local reference prefix than standalone JSON Schema.
    encoded = json.dumps(wire_catalog()["$defs"], ensure_ascii=False)
    definitions = json.loads(encoded.replace('"#/$defs/', '"#/components/schemas/Wire_'))
    # Legacy preview names remain isolated until persistent routes replace them.
    return {"Wire_" + name: definition for name, definition in definitions.items()}


router = APIRouter(prefix="/api/v1", tags=["contracts"])


@router.get("/contracts")
def get_contract_catalog() -> dict:
    return wire_catalog()
