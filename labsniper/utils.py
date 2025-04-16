import sys
from datetime import datetime


def normalize_string(
    value,
    param_name: str = "参数",
    allow_empty: bool = False,
) -> str:
    """
    Normalizes and validates an input value into a string representation.

    This function handles None, empty strings, numeric values, and string inputs,
    while rejecting all other types. Whitespace strings are preserved as-is.

    Args:
        value: The input value to normalize. Accepts None, strings, or numbers.
        param_name: The name of the parameter for error messages.
        allow_empty: If True, accepts None or empty string and returns empty string.

    Returns:
        str: The normalized string value:
             - Empty string for None/empty input when allow_empty=True
             - String representation for numbers
             - Original string (with whitespace preserved) for string inputs

    Raises:
        ValueError: When empty input is received with allow_empty=False
        TypeError: When input is neither None, string, nor number

    Examples:
        >>> normalize_string(123)
        '123'
        >>> normalize_string(" hello ")
        ' hello '
        >>> normalize_string(None, allow_empty=True)
        ''
    """
    msg = "Invalid parameter. Detail:\n"
    if value is None or value == "":
        if not allow_empty:
            msg += f"参数无效，{param_name}不能为空。"
            raise ValueError(msg)
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    else:
        msg += f"参数无效，{param_name}必须为字符串或数字类型，而不是{type(value)}."
        raise TypeError(msg)


def get_timestamp(input_time: str) -> int:
    """
    Converts a string representation of time into a Unix timestamp.
    Args:
        input_time (str): The input time string in the format "YYYY-mm-dd HH:MM:SS".
    Returns:
        int: The Unix timestamp corresponding to the input time.
    Raises:
        ValueError: If the input time string is not in the correct format.
        RuntimeError: If there is an error during the conversion process.
    Examples:
        >>> get_timestamp("2024-04-01 09:30:00")
        1711935000
    """
    if input_time is None or input_time == "":
        msg = "Invalid parameter. Detail:\n参数无效，时间不能为空。"
        raise ValueError(msg)

    time_format = "%Y-%m-%d %H:%M:%S"

    try:
        time_obj = datetime.strptime(input_time, time_format)  # Parse time
    except TypeError as e:
        msg = f"Invalid parameter. Detail:\n参数无效，时间必须为字符串类型，而不是{type(input_time)}."
        raise TypeError(msg) from e
    except ValueError as e:
        msg = f'Invalid time format. Detail:\n时间格式不正确，请使用"YYYY-mm-dd HH:MM:SS"，例如"2024-04-01 09:30:00".'
        raise ValueError(msg) from e

    try:
        timestamp = int(time_obj.timestamp())  # Convert datetime object to timestamp
    except OSError as e:
        msg = f'Time conversion error. Detail:\n尝试转换"{datetime.strftime(time_obj, time_format)}"时发生错误，请检查时间是否在合理范围内。'
        raise RuntimeError(msg) from e
    return timestamp


def simple_exception_output(exc_type, exc_value, exc_traceback):
    print(f"{exc_type.__name__}: {exc_value}")


sys.excepthook = simple_exception_output
