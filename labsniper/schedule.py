import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .equipment import Equipment
from .reservation import Hack, Reservation, ReservationService
from .user import User

TICKET_ALIVE_SECONDS = 30
CONNECTION_ALIVE_SECONDS = 10


class Intervene:
    def __init__(
        self,
        target_timestamp: int | float,
        creation_advance: int | float,
        submission_advance: int | float,
        time_offset: int | float = 0,  # server_time - local_time
    ) -> None:
        self.param_check(target_timestamp, "目标时间戳")
        self.param_check(creation_advance, "创建请求的提前秒数")
        self.param_check(submission_advance, "提交请求的提前秒数")
        self.param_check(time_offset, "服务器时间校正偏移量", allow_negative=True)

        if creation_advance - submission_advance > TICKET_ALIVE_SECONDS:
            msg = "Invalid parameter. Detail:\n"
            msg += f"给定的创建请求和提交请求的时间间隔过长，建议设置为{TICKET_ALIVE_SECONDS}秒以内。"
            raise ValueError(msg)

        if submission_advance > CONNECTION_ALIVE_SECONDS:
            msg = "Invalid parameter. Detail:\n"
            msg += f"给定的提交请求的提前时间过长，建议设置为{CONNECTION_ALIVE_SECONDS}秒以内。"
            raise ValueError(msg)

        self.target_timestamp = target_timestamp
        self.creation_advance = creation_advance
        self.submission_advance = submission_advance
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
            self.target_timestamp - self.creation_advance,
            poll_interval=min(1, self.creation_advance / 10),
        )

    def pause_before_request_submission(self) -> None:
        self.wait_until(
            self.target_timestamp - self.submission_advance,
            poll_interval=min(0.001, self.submission_advance / 100),
        )


class MultiReservationScheduler:
    def __init__(
        self,
        target_timestamp: float | int,
        creation_advance: float | int,
        submission_advances: Iterable[float, int],
        user: User,
        equipment: Equipment,
        reservation: Reservation,
        time_offset: float | int = 0,
        hack: Hack | None = None,
    ) -> None:
        self.service_args = {
            "user": user,
            "equipment": equipment,
            "reservation": reservation,
            "hack": hack,
        }
        self.intervene_args_all = [
            {
                "target_timestamp": target_timestamp,
                "creation_advance": creation_advance,
                "submission_advance": submission_advance,
                "time_offset": time_offset,
            }
            for submission_advance in submission_advances
        ]
        self.num_jobs = len(self.intervene_args_all)
        if self.num_jobs == 0:
            msg = "Invalid parameter. Detail:\n"
            msg += "没有可执行的任务，请检查输入参数。"
            raise ValueError(msg)

    def worker(self, service_args: dict, intervene_args: dict) -> str:
        try:
            intervene = Intervene(**intervene_args)
            reservation_service = ReservationService(**service_args)
            reservation_service.set_intervene(intervene)
            return reservation_service.go()
        except Exception as e:
            return str(e)

    def execute(self) -> None:
        with ThreadPoolExecutor(max_workers=self.num_jobs) as executor:
            future_map = {
                executor.submit(
                    self.worker,
                    self.service_args,
                    intervene_args,
                ): {
                    "idx": i,
                    "submission_advance": intervene_args["submission_advance"],
                }
                for i, intervene_args in enumerate(self.intervene_args_all)
            }
            results = [None] * self.num_jobs
            for future in as_completed(future_map):
                idx = future_map[future]["idx"]
                submission_advance = future_map[future]["submission_advance"]
                results[idx] = future.result()
                print(f"提交时间提前{submission_advance:.1f}秒的结果：\n{results[idx]}")
                print("===" * 20)
                print()
