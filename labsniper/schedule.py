from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .equipment import Equipment
from .reservation import Hack, Intervene, Reservation, ReservationService
from .user import User


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
