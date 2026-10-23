"""Safe fallback behaviors for the current Tavern Brawl deck."""

import time

from autohs.behaviors.basic import (
    Location,
    SpellNoPoint,
    SpellPointOppo,
    clicks,
)
from autohs.behaviors.demon_hunter import (
    active_count,
    active_minion,
    hero_can_gain_attack,
    setup_lethal,
)


class Headhunt(SpellPointOppo):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        damage = 2 + state.my_total_spell_power
        if not state.oppo_hero.immune and state.oppo_hero.health + state.oppo_hero.armor <= damage:
            return 1000, -1

        best, target = 1.0 if not state.oppo_hero.immune else 0.0, -1
        for index, minion in enumerate(state.oppo_minions):
            if minion.can_be_pointed_by_spell:
                value = minion.delta_h_after_damage(damage)
                if value > best:
                    best, target = value, index
        return best, target


class Advantage(SpellPointOppo):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        damage = 1 + state.my_total_spell_power
        draw_value = 1.2 if state.my_hand_card_num < 10 else 0
        attack_value = 0.6 if state.my_hero.can_attack else 0
        best, target = draw_value + attack_value, -1
        for index, minion in enumerate(state.oppo_minions):
            if minion.can_be_pointed_by_spell:
                value = minion.delta_h_after_damage(damage)
                if value > best:
                    best, target = value, index
        return best, target


class EmergencyMeeting(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        free_slots = max(0, 7 - state.my_minion_num)
        return 5 if free_slots >= 3 else (2 if free_slots else 0),


class Infestation(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        return 2 if state.my_hand_card_num < 10 else 0,


class EmberRune(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        return 4 if state.oppo_minions else 2,


class FirstArgusPortal(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        return 1 if state.my_hand_card_num < 10 else 0,


class Cliffside(Location):
    value = 2.0
    keep_in_hand_bool = False

    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        if not getattr(state, "is_demon_hunter", False):
            return super().best_h_and_arg(state, hand_card_index)
        # Playing the location uses a slot before its two pirates appear.
        pirates = min(2, max(0, 6 - state.my_minion_num))
        if not pirates:
            return 0, 0
        attack = 1 + active_count(state, "TOY_518", "NEW1_027", "CORE_NEW1_027",
                                  "VAN_NEW1_027", "TOY_330t5")
        gap = max(range(state.my_minion_num + 1), key=lambda pos: sum(
            state.my_minions[index].card_id == "VAC_532" and active_minion(state.my_minions[index])
            for index in (pos - 1, pos) if 0 <= index < state.my_minion_num
        ))
        if setup_lethal(state, hand_card_index, gap):
            return 1000, gap
        if not state.oppo_has_taunt and state.oppo_hero.can_be_pointed_by_minion \
                and state.guaranteed_face_damage + pirates * attack >= state.oppo_hero.health:
            return 1000, gap
        # Value immediate Charge bodies, pirate engines, and later activations.
        value = (6 if pirates == 2 else 2) + 2 * pirates * attack
        value += 2 * active_count(state, "VAC_532")
        if hero_can_gain_attack(state):
            value += pirates * active_count(state, "VAC_927")
        return value, gap

    @classmethod
    def location_trigger_h_and_arg(cls, state, my_minion_index):
        free_slots = max(0, 7 - state.my_minion_num)
        locations = getattr(state, "my_minions", [])
        if my_minion_index < len(locations) and locations[my_minion_index].health == 1:
            free_slots += 1
        if getattr(state, "is_demon_hunter", False) and free_slots:
            from autohs.strategy.turn import trigger_cliffside

            sim = trigger_cliffside(state, my_minion_index)
            if sim.guaranteed_face_damage >= sim.oppo_hero.health:
                return 1000,
        if getattr(state, "is_demon_hunter", False) and free_slots \
                and not state.oppo_has_taunt and state.oppo_hero.can_be_pointed_by_minion:
            attack = 1 + active_count(state, "TOY_518", "NEW1_027", "CORE_NEW1_027",
                                      "VAN_NEW1_027", "TOY_330t5")
            if state.guaranteed_face_damage + min(2, free_slots) * attack >= state.oppo_hero.health:
                return 1000,
            if free_slots == 1 and state.oppo_hero.health <= 12:
                return cls.value,
        if free_slots < 2:
            return 0,
        # The two 1/1 Charge pirates are immediately useful for board control.
        return cls.value + (1.5 if state.oppo_minions else 0),

    @classmethod
    def location_trigger(cls, state, my_minion_index, args):
        clicks().minion.chooseMyMinion(my_minion_index, state.my_minion_num)
        clicks().game.cancelClick()
        time.sleep(1)


class PerpetualLegacy(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        return 3 if state.my_hero.can_attack else 0.5,
