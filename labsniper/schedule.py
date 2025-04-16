from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .equipment import Equipment
from .reservation import Hack, Intervene, Reservation, ReservationService
from .user import User


class MultiReservationService:
    def __init__(self, reservation_services=Iterable[ReservationService]):
        if not isinstance(reservation_services, Iterable):
            msg = "Invalid parameter. Detail:\n"
            msg += "给定的预约服务数据列表类型不正确，请检查输入参数。"
            raise TypeError(msg)

        self.num_jobs = len(reservation_services)
        if self.num_jobs == 0:
            msg = "Invalid parameter. Detail:\n"
            msg += "没有可执行的任务，请检查输入参数。"
            raise ValueError(msg)

        if not all(
            isinstance(reservation_service, ReservationService)
            for reservation_service in reservation_services
        ):
            msg = "Invalid parameter. Detail:\n"
            msg += "部分给定的预约服务的数据类型不正确，请检查输入参数。"
            raise TypeError(msg)

        self.reservation_services = reservation_services

    def worker(self, reservation_service: ReservationService) -> str:
        try:
            return reservation_service.go()
        except Exception as e:
            return str(e)

    def execute(self) -> list[str]:
        with ThreadPoolExecutor(max_workers=self.num_jobs) as executor:
            future_map = {
                executor.submit(self.worker, reservation_service): i
                for i, reservation_service in enumerate(self.reservation_services)
            }
            results = [None] * self.num_jobs
            for future in as_completed(future_map):
                idx = future_map[future]
                results[idx] = future.result()
        return results


class MultiReservationScheduler:
    def __init__(
        self,
        target_timestamp: float | int,
        creation_advances: Iterable[float, int],
        submission_advances: Iterable[float, int],
        user: User,
        equipment: Equipment,
        reservation: Reservation,
        time_offset: float | int = 0,
        hack: Hack | None = None,
    ) -> None:
        if len(creation_advances) != len(submission_advances):
            msg = "Invalid parameter. Detail:\n"
            msg += "由创建和提交请求的提前量决定的任务数量不一致，请检查输入参数。"
            raise ValueError(msg)

        self.num_jobs = len(creation_advances)
        if self.num_jobs == 0:
            msg = "Invalid parameter. Detail:\n"
            msg += "没有可执行的任务，请检查输入参数。"
            raise ValueError(msg)

        self.service_args = {
            "user": user,
            "equipment": equipment,
            "reservation": reservation,
            "hack": hack,
        }
        self.intervene_args_all = [
            {
                "target_timestamp": target_timestamp,
                "creation_advance": creation_advances[i],
                "submission_advance": submission_advances[i],
                "time_offset": time_offset,
            }
            for i in range(self.num_jobs)
        ]
        self.creation_advances = creation_advances
        self.submission_advances = submission_advances

    def create_services(self) -> list[ReservationService]:
        reservation_services = []
        for intervene_args in self.intervene_args_all:
            intervene = Intervene(**intervene_args)
            reservation_service = ReservationService(**self.service_args)
            reservation_service.set_intervene(intervene)
            reservation_services.append(reservation_service)
        return reservation_services

    def execute(self) -> list[str]:
        reservation_services = self.create_services()
        multi_reservation_service = MultiReservationService(
            reservation_services=reservation_services
        )
        return multi_reservation_service.execute()
