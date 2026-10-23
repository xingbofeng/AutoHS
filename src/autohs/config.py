import json
import platform
from autohs.infrastructure.logging import logger
from autohs.desktop.coordinates import (
    COORDINATES_1920_1080,
    COORDINATES_2560_1440,
    scale_from_1920,
)
from autohs.paths.install import HEARTHSTONE_ROOT
# 每个回合开始发个表情的概率
EMOJ_RATIO = 0.05

# 随从相互攻击的启发值包括两个部分：敌方随从受伤的带来的收益；
# 以及我方随从受伤带来的损失。下面两个比例表示这两个启发值变化
# 数值应该以怎样权值比例相加。如果是控制卡组，可以略微调高
# OPPO_MINION_DELTA_H_FACTOR 来鼓励解场；如果是快攻卡组则反之
OPPO_MINION_DELTA_H_FACTOR = 1
MY_MINION_DELTA_H_FACTOR = 1
# OPPO_HERO_DELTA_H_FACTOR 越高就越喜欢打脸
OPPO_HERO_DELTA_H_FACTOR = 2

# 对于没有单独建一个类去描述的卡牌, 如果它的法力值花费大于这个值,
# 就在留牌阶段被换掉
REPLACE_COST_BAR = 3

# 鼠标点击相关
OPERATE_INTERVAL = 0.2
STATE_CHECK_INTERVAL = 1
TINY_OPERATE_INTERVAL = 0.1
BASIC_MINION_PUT_INTERVAL = 0.6
BASIC_SPELL_WAIT_TIME = 1.2
BASIC_WEAPON_WAIT_TIME = 0.8
HERO_POWER_WAIT_TIME = 0.8
LOCATION_TRIGGER_WAIT_TIME = 0.8
POST_ACTION_SETTLE_TIME = 0.6
DISCOVER_SETTLE_TIME = 0.6
MOUSE_MOVE_DURATION = 0.08
MOUSE_CLICK_HOLD = 0.08
MOUSE_DRAG_HOLD = 0.12
PYAUTOGUI_PAUSE = 0.02
ACTION_CONFIRMATION_POLL_INTERVAL = 0.05
LOG_TAIL_IDLE_INTERVAL = 0.05
BATTLEFIELD_STABLE_INTERVAL = 0.15
BATTLEFIELD_STABLE_COUNT = 3
PLATFORM = platform.system()


class AutoHSConfig:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.max_play_time = 0
        self.max_win_count = 0
        self.hearthstone_install_path = HEARTHSTONE_ROOT if PLATFORM == "Darwin" else ""
        self.user_name = ""
        self.give_up_with_dignity = False
        self.click_coordinates = None
        self.exit_func = None
        self.debug_log_start = False
        self.has_loading_screen = False

        self.emoj_ratio = EMOJ_RATIO
        self.oppo_minion_delta_h_factor = OPPO_MINION_DELTA_H_FACTOR
        self.my_minion_delta_h_factor = MY_MINION_DELTA_H_FACTOR
        self.oppo_hero_delta_h_factor = OPPO_HERO_DELTA_H_FACTOR
        self.replace_cost_bar = REPLACE_COST_BAR
        self.operate_interval = OPERATE_INTERVAL
        self.state_check_interval = STATE_CHECK_INTERVAL
        self.tiny_operate_interval = TINY_OPERATE_INTERVAL
        self.basic_minion_put_interval = BASIC_MINION_PUT_INTERVAL
        self.basic_spell_wait_time = BASIC_SPELL_WAIT_TIME
        self.basic_weapon_wait_time = BASIC_WEAPON_WAIT_TIME
        self.hero_power_wait_time = HERO_POWER_WAIT_TIME
        self.location_trigger_wait_time = LOCATION_TRIGGER_WAIT_TIME
        self.post_action_settle_time = POST_ACTION_SETTLE_TIME
        self.discover_settle_time = DISCOVER_SETTLE_TIME
        self.mouse_move_duration = MOUSE_MOVE_DURATION
        self.mouse_click_hold = MOUSE_CLICK_HOLD
        self.mouse_drag_hold = MOUSE_DRAG_HOLD
        self.pyautogui_pause = PYAUTOGUI_PAUSE
        self.action_confirmation_poll_interval = ACTION_CONFIRMATION_POLL_INTERVAL

    def save_config(self, path="configs.json"):
        try:
            with open(path, "w") as f:
                export_dict = {k: v for k, v in self.__dict__.items() if k not in ["click_coordinates", "exit_func", "has_loading_screen"]}
                json.dump(export_dict, f)
                logger.info(f"配置文件成功保存至{path}")
        except (IOError, OSError) as e:
            logger.error(f"保存配置文件时出错: {e}")

    def load_config(self, path="configs.json"):
        logger.info(f"加载配置文件: {path}")
        try:
            with open(path, "r") as f:
                self.__dict__.update(json.load(f))
                logger.info(f"配置文件加载成功，配置：{self.__dict__}")
        except FileNotFoundError:
            logger.error("配置文件 configs.json 未找到")


autohs_config = AutoHSConfig()


def bind_screen(width, height):
    autohs_config.width = width
    autohs_config.height = height
    if width == 1920 and height == 1080:
        autohs_config.click_coordinates = COORDINATES_1920_1080
    elif width == 2560 and height == 1440:
        autohs_config.click_coordinates = COORDINATES_2560_1440
    else:
        autohs_config.click_coordinates = None
    return width, height


def bind_window(left, top, right, bottom):
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        autohs_config.click_coordinates = None
        return None
    autohs_config.click_coordinates = scale_from_1920(left, top, width, height)
    return autohs_config.click_coordinates


class LiveClickCoordinates:
    def __getitem__(self, key):
        table = autohs_config.click_coordinates
        if table is None:
            raise RuntimeError("尚未绑定点击坐标")
        return table[key]


live_click_coordinates = LiveClickCoordinates()
