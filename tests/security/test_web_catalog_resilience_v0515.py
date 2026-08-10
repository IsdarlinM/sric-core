from __future__ import annotations

import json

from sric.web_catalog import _option_metadata


class CompatibleThirdPartyParameter:
    name = "custom"
    required = False
    multiple = False
    nargs = 1
    default = None
    type = None


def test_unknown_click_compatible_parameter_is_serialized_not_raised() -> None:
    payload = _option_metadata(CompatibleThirdPartyParameter())
    assert payload["name"] == "custom"
    assert payload["kind"] == "argument"
    assert payload["parameter_class"] == "CompatibleThirdPartyParameter"
    json.dumps(payload, allow_nan=False)
