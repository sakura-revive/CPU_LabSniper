import time

TICKET_ALIVE_SECONDS = 30
CONNECTION_ALIVE_SECONDS = 10


class Intervene:
    def __init__(
        self,
        target_timestamp: int | float,
        creation_advance_seconds: int | float,
        submission_advance_seconds: int | float,
        time_offset: int | float = 0,  # server_time - local_time
    ) -> None:
        self.param_check(target_timestamp, "目标时间戳")
        self.param_check(creation_advance_seconds, "创建请求的提前秒数")
        self.param_check(submission_advance_seconds, "提交请求的提前秒数")
        self.param_check(time_offset, "服务器时间校正偏移量", allow_negative=True)

        if creation_advance_seconds - submission_advance_seconds > TICKET_ALIVE_SECONDS:
            msg = "Invalid parameter. Detail:\n"
            msg += f"给定的创建请求和提交请求的时间间隔过长，建议设置为{TICKET_ALIVE_SECONDS}秒以内。"
            raise ValueError(msg)

        if submission_advance_seconds > CONNECTION_ALIVE_SECONDS:
            msg = "Invalid parameter. Detail:\n"
            msg += f"给定的提交请求的提前时间过长，建议设置为{CONNECTION_ALIVE_SECONDS}秒以内。"
            raise ValueError(msg)

        self.target_timestamp = target_timestamp
        self.creation_advance_seconds = creation_advance_seconds
        self.submission_advance_seconds = submission_advance_seconds
        self.time_offset = time_offset

    @staticmethod
    def param_check(
        param,
        param_name: str,
        allow_negative: bool = False,
    ) -> None:
        msg = "Invalid parameter. Detail:\n参数无效，"
        if not isinstance(param, (int, float)):
            msg += f"给定的{param_name}必须为整数或浮点数，不能为{type(param)}."
            raise TypeError(msg)
        if param < 0 and not allow_negative:
            msg += f"给定的{param_name}不能为负数。"
            raise ValueError(msg)

    def get_server_time(self) -> float:
        return time.time() + self.time_offset

    def wait_until(self, target_timestamp: float, poll_interval: float) -> None:
        while True:
            remaining = target_timestamp - self.get_server_time()
            if remaining <= 0:
                break
            time.sleep(poll_interval)

    def pause_before_request_creation(self) -> None:
        self.wait_until(
            self.target_timestamp - self.creation_advance_seconds,
            poll_interval=min(1, self.creation_advance_seconds / 10),
        )

    def pause_before_request_submission(self) -> None:
        self.wait_until(
            self.target_timestamp - self.submission_advance_seconds,
            poll_interval=min(0.001, self.submission_advance_seconds / 100),
        )
