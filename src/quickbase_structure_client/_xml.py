"""Validation and serialization for documented structural XML operations."""

from __future__ import annotations

import math
import re
from typing import Any, Dict
from xml.etree import ElementTree

from quickbase_structure_client._validation import validate_field_id
from quickbase_structure_client.exceptions import (
    QuickbasePayloadError,
    QuickbaseValidationError,
)

XML_ACTIONS = frozenset({"API_SetKeyField", "API_SetFieldProperties"})
XML_BOOLEAN_OPTIONS = frozenset(
    {
        "appears_by_default", "bold", "find_enabled", "no_wrap", "required", "unique",
        "doesdatacopy", "append_only", "allowHTML", "sort_as_given", "allow_new_choices",
        "blank_is_zero", "does_average", "does_total", "default_today", "display_dow",
        "display_relative", "display_time", "display_zone", "has_extension",
        "display_as_button",
    }
)
XML_FIELD_OPTIONS = XML_BOOLEAN_OPTIONS | frozenset(
    {
        "comments", "default_value", "fieldhelp", "label", "num_lines", "width", "maxlength",
        "choices", "numberfmt", "comma_start", "currency_format", "currency_symbol",
        "decimal_places", "display_month", "formula",
    }
)


def validate_xml_id(value: int | str) -> str:
    """Return a positive field ID without accepting booleans or URL fragments."""
    return _xml_text(validate_field_id(value))


def _xml_text(value: str | int | float | bool) -> str:
    """Convert a scalar to XML text and reject invalid XML characters."""
    try:
        text = str(int(value)) if isinstance(value, bool) else str(value)
    except ValueError as exc:
        raise QuickbaseValidationError("XML value is too large to serialize.") from exc
    if any(
        ord(char) not in (9, 10, 13)
        and not (0x20 <= ord(char) <= 0xD7FF or 0xE000 <= ord(char) <= 0xFFFD
                 or 0x10000 <= ord(char) <= 0x10FFFF)
        for char in text
    ):
        raise QuickbaseValidationError("XML values must contain valid XML characters.")
    return text


def validate_xml_field_options(options: Dict[str, Any]) -> Dict[str, Any]:
    """Validate XML field tags and return a copy with independent choice lists.

    These names come from ``API_SetFieldProperties``, not the REST schema.
    Quickbase validates field-type applicability and property-specific limits.

    Args:
        options: Non-empty dictionary of documented XML field properties.

    Returns:
        A copy suitable for XML serialization.

    Raises:
        QuickbaseValidationError: If a name, value, or collection is invalid.
    """
    if not isinstance(options, dict) or not options:
        raise QuickbaseValidationError("XML field options must be a non-empty dictionary.")
    result: Dict[str, Any] = {}
    for key, value in options.items():
        if not isinstance(key, str) or key not in XML_FIELD_OPTIONS:
            raise QuickbaseValidationError(
                "Unsupported XML field option. Use documented API_SetFieldProperties tags."
            )
        if key == "choices":
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise QuickbaseValidationError("XML choices must be a list of strings.")
            result[key] = [_xml_text(item) for item in value]
            continue
        if not isinstance(value, (str, int, float, bool)) or (
            isinstance(value, float) and not math.isfinite(value)
        ):
            raise QuickbaseValidationError("XML field option values must be finite scalars.")
        if key in XML_BOOLEAN_OPTIONS and (
            not isinstance(value, (bool, int, str)) or value not in (True, False, 0, 1, "0", "1")
        ):
            raise QuickbaseValidationError("XML boolean options require a boolean, 0, or 1.")
        _xml_text(value)
        result[key] = value
    return result


def build_xml_request(
    action: str,
    payload: Dict[str, Any],
    user_token: str,
    app_token: str | None,
) -> str:
    """Build an escaped XML request for a supported structural operation.

    Authentication is added here so resource wrappers never handle user tokens.
    Caller-supplied authentication tags are rejected.
    """
    if (
        not isinstance(action, str)
        or action not in XML_ACTIONS
        or not isinstance(payload, dict)
        or "fid" not in payload
    ):
        raise QuickbaseValidationError("A supported XML action and a field ID are required.")
    field_id = validate_xml_id(payload["fid"])
    options = {key: value for key, value in payload.items() if key != "fid"}
    if action == "API_SetFieldProperties":
        options = validate_xml_field_options(options)
    elif options:
        raise QuickbaseValidationError("API_SetKeyField accepts only the fid payload property.")
    if app_token is not None and (not isinstance(app_token, str) or not app_token.strip()):
        raise QuickbaseValidationError("app_token must be a non-empty string when supplied.")

    root = ElementTree.Element("qdbapi")
    ElementTree.SubElement(root, "usertoken").text = _xml_text(user_token)
    if app_token is not None:
        ElementTree.SubElement(root, "apptoken").text = _xml_text(app_token)
    ElementTree.SubElement(root, "fid").text = field_id
    for key, value in options.items():
        node = ElementTree.SubElement(root, key)
        if key == "choices":
            for choice in value:
                ElementTree.SubElement(node, "choice").text = choice
        else:
            node.text = _xml_text(value)
    return ElementTree.tostring(root, encoding="unicode")


def parse_xml_response(text: str) -> Dict[str, str]:
    """Parse a structural XML response without exposing raw response content.

    Returns:
        First-level response values, including ``errcode`` as a string.

    Raises:
        QuickbasePayloadError: If the response is malformed or lacks an error code.
    """
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise QuickbasePayloadError("XML responses must not contain document type declarations.")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise QuickbasePayloadError("Quickbase returned a malformed XML response.") from exc
    codes = root.findall("errcode")
    if root.tag != "qdbapi" or len(codes) != 1 or not re.fullmatch(
        r"[0-9]{1,10}", (codes[0].text or "").strip()
    ):
        raise QuickbasePayloadError("Quickbase XML response has no valid, unique error code.")
    result = {child.tag: child.text or "" for child in root}
    result["errcode"] = (codes[0].text or "").strip()
    return result
