import os
import sys

import yaml

from labsniper.credential import LocalCredential, SSOCredential, ManualCredential
from labsniper.equipment import Equipment
from labsniper.form import Form
from labsniper.monitor import ThreadMonitor
from labsniper.reservation import Hack, Reservation, ReservationService, Intervene
from labsniper.schedule import MultiReservationScheduler
from labsniper.user import User
from labsniper.utils import get_timestamp, simple_exception_output


def main():
    REQUIRED_PARAMS = ["user", "equipment_id", "start", "end"]
    config_file = "config/config.yaml"
    if len(sys.argv) >= 2:
        config_file = sys.argv[1]
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"{config_file} not found.")
    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    if config is None:
        config = {}

    for param in REQUIRED_PARAMS:
        if param not in config:
            raise ValueError(f'Please specify "{param}" in the config file.')

    user = config["user"]
    if not os.path.exists(f"config/users/{user}.yaml"):
        raise FileNotFoundError(f"config/users/{user}.yaml not found.")
    with open(f"config/users/{user}.yaml", "r", encoding="utf-8") as f:
        user_info: dict = yaml.load(f, Loader=yaml.FullLoader)
        if not isinstance(user_info, dict):
            raise ValueError(f"config/users/{user}.yaml should be a dict.")

    if "login_method" not in user_info:
        raise ValueError('Please specify "login_method" in the user config file.')
    login_method = user_info["login_method"]

    if not isinstance(login_method, str):
        raise ValueError("login_method should be a string.")
    login_method = login_method.upper()
    if login_method == "SSO":
        credential = SSOCredential(user_info["username"], user_info["password"])
    elif login_method == "LOCAL":
        credential = LocalCredential(user_info["username"], user_info["password"])
    elif login_method == "MANUAL":
        credential = ManualCredential(user_info["cookies"])
    else:
        raise ValueError(f"Invalid login method: {login_method}.")

    user = User(credential)
    user.login()

    equipment_id = config["equipment_id"]
    equipment = Equipment(equipment_id, user)

    reserve_info = {}
    if os.path.exists(f"config/forms/{equipment_id}.yaml"):
        with open(f"config/forms/{equipment_id}.yaml", "r", encoding="utf-8") as f:
            reserve_info = yaml.load(f, Loader=yaml.FullLoader)
            if reserve_info is None:
                reserve_info = {}
    form = Form(reserve_info)

    start = config["start"]
    end = config["end"]

    hackstart = config.get("hackstart", None)
    hackend = config.get("hackend", None)

    component_id = config.get("component_id", None)
    hackuser_id = config.get("hackuser_id", None)

    reservation = Reservation(
        start=start,
        end=end,
        form=form,
        component_id=component_id,
    )
    hack = Hack(
        start=hackstart,
        end=hackend,
        current_user_id=hackuser_id,
    )

    reserve_open_time = config.get("reserve_open_time", None)
    if reserve_open_time is None or reserve_open_time == "":
        reservation_service = ReservationService(
            user=user,
            equipment=equipment,
            reservation=reservation,
            hack=hack,
        )
        reservation_service.go()
    else:
        server_time_offset = config.get("server_time_offset", 0)
        brute_force = bool(config.get("brute_force", False))
        if brute_force:
            scheduler = MultiReservationScheduler(
                reserve_open_timestamp=get_timestamp(reserve_open_time),
                creation_advances=[i + 8 for i in range(10)],
                submission_advances=[i * 0.3 for i in range(10)],
                user=user,
                equipment=equipment,
                reservation=reservation,
                server_time_offset=server_time_offset,
                hack=hack,
            )
            scheduler.execute()
        else:
            reservation_service = ReservationService(
                user=user,
                equipment=equipment,
                reservation=reservation,
                hack=hack,
            )
            intervene = Intervene(
                reserve_open_timestamp=get_timestamp(reserve_open_time),
                creation_advance=8,
                submission_advance=0.3,
                server_time_offset=server_time_offset,
            )
            reservation_service.set_intervene(intervene)
            reservation_service.go()


if __name__ == "__main__":
    with ThreadMonitor(main_title="主程序", thread_title="任务汇总", max_cols=4):
        try:
            main()
        except Exception as e:
            simple_exception_output(*sys.exc_info())
