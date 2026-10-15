"""Facade over the five click controllers. Constructing it is deferred."""


class Controller:
    def __init__(self) -> None:
        from autohs.execution.attack import AttackController
        from autohs.execution.cards import CardsController
        from autohs.execution.game import GameController
        from autohs.execution.hero import HeroController
        from autohs.execution.minion import MinionController

        self.cards = CardsController()
        self.game = GameController()
        self.hero = HeroController()
        self.minion = MinionController()
        self.attack = AttackController()


_controller = None


def get_controller():
    global _controller
    if _controller is None:
        _controller = Controller()
    return _controller


class _LazyController:
    def __getattr__(self, name):
        return getattr(get_controller(), name)


controller = _LazyController()
