from labsniper import core
import os
import sys
import yaml


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
    credential = {
        "username": user_info["username"],
        "password": user_info["password"],
    }
    if "login_method" in user_info:
        credential["login_method"] = user_info["login_method"]

    equipment_id = config["equipment_id"]
    reserve_info = {}
    if os.path.exists(f"config/forms/{equipment_id}.yaml"):
        with open(f"config/forms/{equipment_id}.yaml", "r", encoding="utf-8") as f:
            reserve_info = yaml.load(f, Loader=yaml.FullLoader)
            if reserve_info is None:
                reserve_info = {}

    dtstart = core.get_timestamp(config["start"])
    dtend = core.get_timestamp(config["end"])

    hackstart = core.get_timestamp(config.get("hackstart", None))
    hackend = core.get_timestamp(config.get("hackend", None))
    if (hackstart is None) ^ (hackend is None):
        raise ValueError("Please specify both hackstart and hackend or neither.")

    component_id = config.get("component_id", None)
    hackuser_id = config.get("hackuser_id", None)

    schedule = bool(config.get("schedule", False))
    if schedule:
        days_in_advance = int(reserve_info.get("days_in_advance", 0))
        delay_seconds = float(config.get("delay_seconds", 0))
        intervene = core.schedule(
            dtend=dtend,
            days_in_advance=days_in_advance,
            delay_seconds=delay_seconds,
            ticket_alive_seconds=core.TICKET_ALIVE_SECONDS,
        )
    else:
        intervene = None

    print("Start.\n")

    res = core.single_reserve(
        credential=credential,
        dtstart=dtstart,
        dtend=dtend,
        reserve_info=reserve_info,
        equipment_id=equipment_id,
        component_id=component_id,
        intervene=intervene,
        hackstart=hackstart,
        hackend=hackend,
        hackuser_id=hackuser_id,
    )

    print(f"Success. Target component_id: \n{res['component_id']}")


if __name__ == "__main__":
    main()
