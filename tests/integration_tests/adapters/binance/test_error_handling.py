# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2026 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------

import pytest

from nautilus_trader.adapters.binance.http.error import BinanceError
from nautilus_trader.adapters.binance.http.error import BinanceServerError
from nautilus_trader.adapters.binance.http.error import is_ambiguous_submit_error
from nautilus_trader.adapters.binance.http.error import should_retry
from nautilus_trader.adapters.binance.http.error import should_retry_submit_order


@pytest.fixture
def retry_error():
    """
    Create a BinanceError with a retryable error code.
    """
    return BinanceError(
        status=400,
        message={"code": -1021, "msg": "Timestamp for this request is outside of the recvWindow."},
        headers={},
    )


@pytest.fixture
def non_retry_error():
    """
    Create a BinanceError with a non-retryable error code.
    """
    return BinanceError(
        status=400,
        message={"code": -1000, "msg": "Unknown error"},
        headers={},
    )


def test_should_retry_with_dict_message_containing_code(retry_error):
    result = should_retry(retry_error)
    # -1021 is in BINANCE_RETRY_ERRORS, so should return True
    assert result is True


def test_should_retry_with_dict_message_missing_code():
    error = BinanceError(
        status=400,
        message={"msg": "Some error message without code"},
        headers={},
    )

    result = should_retry(error)
    # Should not crash and return False
    assert result is False


def test_should_retry_with_string_message_json_parseable():
    error = BinanceError(
        status=400,
        message='{"code": -1021, "msg": "Timestamp error"}',
        headers={},
    )

    result = should_retry(error)
    # Should parse JSON and find code -1021
    assert result is True


def test_should_retry_with_string_message_not_json():
    error = BinanceError(
        status=400,
        message="This is just a plain string error message",
        headers={},
    )

    result = should_retry(error)
    # Should not crash and return False
    assert result is False


def test_should_retry_with_malformed_json_string():
    error = BinanceError(
        status=400,
        message='{"code": -1021, "msg": "Malformed JSON',  # Missing closing brace
        headers={},
    )

    result = should_retry(error)
    # Should not crash and return False
    assert result is False


def test_should_retry_with_none_message():
    error = BinanceError(
        status=400,
        message=None,
        headers={},
    )

    result = should_retry(error)
    # Should not crash and return False
    assert result is False


def test_should_retry_with_non_retry_error_code(non_retry_error):
    result = should_retry(non_retry_error)
    assert result is False


def test_should_retry_with_non_binance_error():
    error = ValueError("Some other error")

    result = should_retry(error)
    assert result is False


def test_should_retry_with_empty_dict_message():
    error = BinanceError(
        status=400,
        message={},
        headers={},
    )

    result = should_retry(error)
    assert result is False


def test_should_retry_with_string_code_value():
    error = BinanceError(
        status=400,
        message={"code": "-1021", "msg": "String code value"},
        headers={},
    )

    result = should_retry(error)
    # Should handle string to int conversion
    assert result is True


def test_should_retry_with_invalid_code_type():
    error = BinanceError(
        status=400,
        message={"code": "invalid", "msg": "Invalid code type"},
        headers={},
    )

    result = should_retry(error)
    # Should not crash on invalid int conversion
    assert result is False


@pytest.mark.parametrize("error_code", [-1006, -1007])
def test_unknown_execution_status_is_not_retryable_for_submit(error_code):
    error = BinanceError(
        status=504,
        message={"code": error_code, "msg": "Execution status unknown."},
        headers={},
    )

    assert is_ambiguous_submit_error(error)
    assert should_retry_submit_order(error) is False


def test_definitive_retry_error_remains_retryable_for_submit():
    error = BinanceError(
        status=400,
        message={"code": -1021, "msg": "Timestamp outside recvWindow."},
        headers={},
    )

    assert not is_ambiguous_submit_error(error)
    assert should_retry_submit_order(error) is True


def test_timeout_remains_retryable_for_non_submit_operations():
    error = BinanceError(
        status=504,
        message={"code": -1007, "msg": "Execution status unknown."},
        headers={},
    )

    assert should_retry(error) is True


@pytest.mark.parametrize(
    "error",
    [
        BinanceServerError(status=200, message="Non-JSON response", headers={}),
        BinanceServerError(status=500, message="Internal server error", headers={}),
        BinanceError(
            status=503,
            message={"code": -1003, "msg": "Service unavailable"},
            headers={},
        ),
    ],
)
def test_http_5xx_is_ambiguous_and_not_retryable_for_submit(error):
    assert is_ambiguous_submit_error(error)
    assert should_retry_submit_order(error) is False
