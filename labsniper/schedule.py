import sys
import threading
from collections.abc import Iterable

from .equipment import Equipment
from .reservation import Hack, Intervene, Reservation, ReservationService
from .user import User
from .utils import simple_exception_output


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

    def worker(self, reservation_service: ReservationService) -> None:
        try:
            reservation_service.go()
        except Exception as e:
            simple_exception_output(*sys.exc_info())

    def execute(self) -> None:
        threads: list[threading.Thread] = []
        for reservation_service in self.reservation_services:
            thread = threading.Thread(target=self.worker, args=(reservation_service,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()


class MultiReservationScheduler:
    def __init__(
        self,
        reserve_open_timestamp: float | int,
        creation_advances: Iterable[float, int],
        submission_advances: Iterable[float, int],
        user: User,
        equipment: Equipment,
        reservation: Reservation,
        server_time_offset: float | int = 0,
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
                "reserve_open_timestamp": reserve_open_timestamp,
                "creation_advance": creation_advances[i],
                "submission_advance": submission_advances[i],
                "server_time_offset": server_time_offset,
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

    def execute(self) -> None:
        reservation_services = self.create_services()
        multi_reservation_service = MultiReservationService(
            reservation_services=reservation_services
        )
        multi_reservation_service.execute()
