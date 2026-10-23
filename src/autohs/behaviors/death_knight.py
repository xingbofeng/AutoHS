"""Behaviors for the user's Wild Unholy Death Knight deck."""

import time

from autohs.behaviors.basic import (
    HeroPowerCard,
    MinionNoPoint,
    SpellNoPoint,
    SpellPointOppo,
    clicks,
)
from autohs.config import autohs_config


class GhoulCharge(HeroPowerCard):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        if state.my_hero_power.exhausted or state.my_minion_num >= 7:
            return 0,
        return 1.2,

    @classmethod
    def use_with_arg(cls, state, card_index, *args):
        clicks().hero.useSkill()
        time.sleep(1)


class SkeletalSidekick(MinionNoPoint):
    @classmethod
    def utilize_delta_h_and_arg(cls, state, hand_card_index):
        value, gap = super().utilize_delta_h_and_arg(state, hand_card_index)
        candidates = [
            (index, minion) for index, minion in enumerate(state.my_minions)
            if ("UNDEAD" in minion.races or "ALL" in minion.races)
            and minion.can_be_pointed_by_minion
        ]
        if not candidates:
            return value, gap, -1
        index, target = max(candidates, key=lambda item: (
            item[1].can_beat_face, item[1].health, item[1].divine_shield,
        ))
        return value + (3 if target.can_beat_face else 1), gap, index

    @classmethod
    def use_with_arg(cls, state, card_index, gap, target):
        clicks().cards.putMinionOnBattleGround(
            card_index, state.my_hand_card_num, gap, state.my_minion_num,
        )
        if target >= 0:
            time.sleep(0.3)
            shifted_target = target + int(gap <= target)
            clicks().minion.chooseMyMinion(shifted_target, state.my_minion_num + 1)
        clicks().game.cancelClick()
        time.sleep(autohs_config.basic_minion_put_interval)


class DrawMinion(MinionNoPoint):
    keep_in_hand_bool = False
    draw_count = 1

    @classmethod
    def utilize_delta_h_and_arg(cls, state, hand_card_index):
        value, gap = super().utilize_delta_h_and_arg(state, hand_card_index)
        available = max(0, 10 - (state.my_hand_card_num - 1))
        return value + min(cls.draw_count, available), gap


class RemnantOfRage(DrawMinion):
    draw_count = 2


class DrBoom(MinionNoPoint):
    keep_in_hand_bool = False

    @classmethod
    def utilize_delta_h_and_arg(cls, state, hand_card_index):
        value, gap = super().utilize_delta_h_and_arg(state, hand_card_index)
        return value + min(2, max(0, 6 - state.my_minion_num)), gap


class DiscoverMinion(MinionNoPoint):
    keep_in_hand_bool = False


class RiteOfAtrocity(SpellNoPoint):
    keep_in_hand_bool = False

    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        if state.my_hand_card_num >= 10:
            return 0,
        return 1.5 if state.my_corpses >= 2 else 0.5,


class MiningCasualties(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        return 2 * min(2, 7 - state.my_minion_num),


class Asphyxiate(SpellNoPoint):
    keep_in_hand_bool = False

    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        if not state.oppo_minions:
            return 0,
        highest = max(minion.attack for minion in state.oppo_minions)
        targets = [minion for minion in state.oppo_minions if minion.attack == highest]
        value = sum(
            0 if minion.immune or minion.dormant else minion.heuristic_val
            for minion in targets
        ) / len(targets)
        return max(0, value - 2),


class DownWithTheShip(SpellPointOppo):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        damage = 3 + sum(minion.spell_power for minion in state.my_minions)
        if not state.oppo_hero.immune and state.oppo_hero.health + state.oppo_hero.armor <= damage:
            return 1000, -1
        best, target = (0.0 if state.oppo_hero.immune else 1.0), -1
        for index, minion in enumerate(state.oppo_minions):
            if minion.can_be_pointed_by_spell:
                value = minion.delta_h_after_damage(damage)
                if value > best:
                    best, target = value, index
        return best, target


class GraveStrength(SpellNoPoint):
    keep_in_hand_bool = False

    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        ready = [minion for minion in state.my_minions if minion.can_beat_face]
        if not ready:
            return 0,
        buff = 3 if state.my_corpses >= 5 else 1
        if (not state.oppo_has_taunt and not state.oppo_hero.immune
                and sum(m.attack + buff for m in ready) >= state.oppo_hero.health + state.oppo_hero.armor):
            return 1000,
        if len(ready) < 2:
            return 0,
        return len(ready) * buff,
