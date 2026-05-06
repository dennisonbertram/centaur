"""Unit tests for pure functions in api.tool_manager."""

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.tool_manager import (  # noqa: E402
    _LIFECYCLE_METHODS,
    _friendly_type_name,
    _normalize_for_serialization,
    _tool_arg_validation_error,
    _to_toon,
    ToolMethod,
)


# ---------------------------------------------------------------------------
# _normalize_for_serialization
# ---------------------------------------------------------------------------


class TestNormalizeNoneAndPrimitives:
    def test_none(self):
        assert _normalize_for_serialization(None) is None

    def test_str(self):
        assert _normalize_for_serialization("hello") == "hello"

    def test_int(self):
        assert _normalize_for_serialization(42) == 42

    def test_float(self):
        assert _normalize_for_serialization(3.14) == 3.14

    def test_bool(self):
        assert _normalize_for_serialization(True) is True


class TestNormalizeBytes:
    def test_small_bytes_base64(self):
        data = b"hello"
        result = _normalize_for_serialization(data)
        assert result["encoding"] == "base64"
        assert result["byte_length"] == 5
        assert "content_base64" in result

    def test_large_bytes_preview(self):
        data = b"x" * (2 * 1024 * 1024)  # 2 MB — exceeds default 1 MB limit
        result = _normalize_for_serialization(data)
        assert result["encoding"] == "base64_preview"
        assert result["byte_length"] == len(data)


class TestNormalizeEnum:
    def test_enum_returns_value(self):
        class Color(Enum):
            RED = "red"
            BLUE = "blue"

        assert _normalize_for_serialization(Color.RED) == "red"


class TestNormalizeDataclass:
    def test_dataclass(self):
        @dataclass
        class Point:
            x: int
            y: int

        result = _normalize_for_serialization(Point(1, 2))
        assert result == {"x": 1, "y": 2}


class TestNormalizeCollections:
    def test_dict(self):
        result = _normalize_for_serialization({"a": 1, "b": "two"})
        assert result == {"a": 1, "b": "two"}

    def test_list(self):
        result = _normalize_for_serialization([1, "two", None])
        assert result == [1, "two", None]

    def test_nested(self):
        class Status(Enum):
            OK = "ok"

        @dataclass
        class Item:
            name: str

        data = {"items": [Item("a")], "status": Status.OK}
        result = _normalize_for_serialization(data)
        assert result == {"items": [{"name": "a"}], "status": "ok"}

    def test_tuple_becomes_list(self):
        assert _normalize_for_serialization((1, 2)) == [1, 2]

    def test_set_becomes_list(self):
        result = _normalize_for_serialization({1})
        assert result == [1]


class TestNormalizeModelDump:
    def test_model_dump_fallback(self):
        class FakeModel:
            def model_dump(self):
                return {"key": "val"}

        result = _normalize_for_serialization(FakeModel())
        assert result == {"key": "val"}

    def test_to_dict_fallback(self):
        class Legacy:
            def to_dict(self):
                return {"legacy": True}

        result = _normalize_for_serialization(Legacy())
        assert result == {"legacy": True}


# ---------------------------------------------------------------------------
# _friendly_type_name
# ---------------------------------------------------------------------------


class TestFriendlyTypeName:
    def test_str(self):
        assert _friendly_type_name(str) == "string"

    def test_int(self):
        assert _friendly_type_name(int) == "integer"

    def test_float(self):
        assert _friendly_type_name(float) == "number"

    def test_bool(self):
        assert _friendly_type_name(bool) == "boolean"

    def test_list(self):
        assert _friendly_type_name(list) == "array"

    def test_dict(self):
        assert _friendly_type_name(dict) == "object"

    def test_none_type(self):
        assert _friendly_type_name(type(None)) == "null"

    def test_optional_str(self):
        result = _friendly_type_name(Optional[str])
        assert "string" in result
        assert "null" in result

    def test_list_of_str(self):
        assert _friendly_type_name(list[str]) == "array[string]"

    def test_dict_str_int(self):
        assert _friendly_type_name(dict[str, int]) == "object[string, integer]"

    def test_union_types(self):
        result = _friendly_type_name(Union[str, int])
        assert "string" in result
        assert "integer" in result

    def test_pipe_union(self):
        result = _friendly_type_name(str | int)
        assert "string" in result
        assert "integer" in result


class TestToolArgValidation:
    def test_unexpected_argument_reports_suggestion(self):
        def fn(channel: str, limit: int = 10):
            return None

        error = _tool_arg_validation_error(
            ToolMethod("upload_file", fn),
            {"channel_id": "C123", "limit": 5},
        )

        assert error == {
            "error": "tool_argument_validation_failed",
            "message": "Unexpected argument(s): channel_id",
            "unexpected_args": ["channel_id"],
            "accepted_args": ["channel", "limit"],
            "did_you_mean": {"channel_id": "channel"},
        }

    def test_missing_required_argument_reports_shape(self):
        def fn(spreadsheet_id: str, range_notation: str, values: list):
            return None

        error = _tool_arg_validation_error(
            ToolMethod("sheets_update", fn),
            {"spreadsheet_id": "sheet"},
        )

        assert error == {
            "error": "tool_argument_validation_failed",
            "message": "Missing required argument(s): range_notation, values",
            "missing_args": ["range_notation", "values"],
            "accepted_args": ["range_notation", "spreadsheet_id", "values"],
        }

    def test_var_kwargs_method_accepts_extra_arguments(self):
        def fn(**kwargs):
            return kwargs

        assert (
            _tool_arg_validation_error(ToolMethod("dynamic", fn), {"anything": True})
            is None
        )


# ---------------------------------------------------------------------------
# _to_toon
# ---------------------------------------------------------------------------


class TestToToon:
    def test_returns_string(self):
        assert isinstance(_to_toon({"key": "value"}), str)

    def test_handles_none(self):
        assert isinstance(_to_toon(None), str)

    def test_handles_list(self):
        assert isinstance(_to_toon([1, 2, 3]), str)

    def test_handles_nested_data(self):
        data = {"users": [{"name": "Alice", "age": 30}], "count": 1}
        result = _to_toon(data)
        assert isinstance(result, str)
        assert "Alice" in result

    def test_handles_empty_dict(self):
        result = _to_toon({})
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _LIFECYCLE_METHODS
# ---------------------------------------------------------------------------


class TestLifecycleMethods:
    def test_close_excluded(self):
        assert "close" in _LIFECYCLE_METHODS

    def test_connect_excluded(self):
        assert "connect" in _LIFECYCLE_METHODS

    def test_disconnect_excluded(self):
        assert "disconnect" in _LIFECYCLE_METHODS

    def test_shutdown_excluded(self):
        assert "shutdown" in _LIFECYCLE_METHODS

    def test_regular_method_not_excluded(self):
        assert "search" not in _LIFECYCLE_METHODS
        assert "get" not in _LIFECYCLE_METHODS
