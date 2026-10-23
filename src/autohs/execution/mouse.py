# -*- coding: UTF-8 -*-

"""
__Author__ = "MakiNaruto"
__Mail__: "become006@gmail.com"
__Version__ = "1.0.1"
__Created__ = "2024/10/11"
__Description__ = ""
"""
import sys
import time

import pyautogui

from autohs.app.pause import pause_controller


class MouseController:
    @staticmethod
    def _move_out_of_failsafe_corner():
        if not pyautogui.FAILSAFE or pyautogui.position() not in pyautogui.FAILSAFE_POINTS:
            return
        width, height = pyautogui.size()
        pyautogui.FAILSAFE = False
        try:
            pause_controller.checkpoint()
            pyautogui.moveTo(width // 2, height // 2)
        finally:
            pyautogui.FAILSAFE = True

    def mouseMoveToPosition(self, position, duration=0.2):
        """ 鼠标移动到指定位置 """
        pause_controller.checkpoint()
        self._move_out_of_failsafe_corner()
        pause_controller.checkpoint()
        pyautogui.moveTo(position, duration=duration, tween=pyautogui.easeInOutElastic)
        pause_controller.checkpoint()

    def mouseDragToPosition(self, position, duration=0.2):
        """ 鼠标在当前位置点击不放并移动到指定位置松开 """
        pause_controller.checkpoint()
        if sys.platform == "darwin":
            # Unity needs several frames while the pointer is held still.
            pyautogui.mouseDown()
            try:
                self.mouseMoveToPosition(position, duration=duration)
                time.sleep(0.3)
            finally:
                # Releasing a held button must bypass pause checks.
                pyautogui.mouseUp()
        else:
            pyautogui.dragTo(position, duration=duration, tween=pyautogui.easeInOutElastic, button='left')
        pause_controller.checkpoint()

    def mouseClickPosition(self, position):
        """ 鼠标移动到指定位置并点击一次 """
        self.mouseMoveToPosition(position)
        pause_controller.checkpoint()
        if sys.platform == "darwin":
            # Unity samples button state once per frame.
            pyautogui.mouseDown(position)
            try:
                time.sleep(0.12)
            finally:
                pyautogui.mouseUp(position)
        else:
            pyautogui.click(position)
        pause_controller.checkpoint()

    def mouseRightClickPosition(self, position):
        """ 鼠标移动到指定位置并点击一次 """
        self.mouseMoveToPosition(position)
        pause_controller.checkpoint()
        pyautogui.rightClick(position)
        pause_controller.checkpoint()

    def positionClickPosition(self, servant_pos, enemy_pos):
        self.mouseClickPosition(servant_pos)
        self.mouseClickPosition(enemy_pos)


if __name__ == '__main__':
    m = MouseController()
    m.mouseMoveToPosition([100, 100], duration=1.5)
