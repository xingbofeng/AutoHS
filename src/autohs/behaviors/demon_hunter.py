"""Behaviors for the Demon Hunter cards in the current deck."""

import copy

from autohs.behaviors.basic import (
    HeroPowerCard,
    MinionNoPoint,
    SpellNoPoint,
    SpellPointOppo,
    WeaponCard,
    clicks,
)


def active_minion(minion):
    return not any(getattr(minion, tag, False) for tag in ("silenced", "dormant", "untouchable"))


def active_count(state, *card_ids):
    return sum(getattr(minion, "card_id", "") in card_ids and active_minion(minion)
               for minion in state.my_minions)


def hero_can_gain_attack(state):
    hero = state.my_hero
    return not any(getattr(hero, tag, False) for tag in ("exhausted", "frozen", "cant_attack"))


def hero_attack_value(state, bonus):
    face_safe = (state.my_hero.health > getattr(state.oppo_hero, "attack", 0)
                 or getattr(state.my_hero, "immune", False) or active_count(state, "VAC_501"))
    value = bonus if hero_can_gain_attack(state) and face_safe else 0
    value += bonus * sum(getattr(minion, "card_id", "") == "MIS_710" and active_minion(minion)
                         and minion.can_beat_face for minion in state.my_minions)
    return value


def setup_lethal(state, hand_card_index, gap):
    if not getattr(state, "is_demon_hunter", False) or state.my_minion_num >= 7:
        return False
    from autohs.strategy.turn import play_setup

    sim = play_setup(state, hand_card_index, [gap])
    return sim.guaranteed_face_damage >= sim.oppo_hero.health


class DemonHunterHeroPower(HeroPowerCard):
    attack_bonus = 1

    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        if state.my_hero_power.exhausted:
            return 0,

        if state.oppo_has_taunt:
            from autohs.strategy.combat import redirected_value

            if not hero_can_gain_attack(state):
                return 0,
            best = 0
            for target in state.oppo_minions:
                if not getattr(target, "taunt", False) or not target.can_be_attacked:
                    continue
                protected = getattr(state.my_hero, "immune", False) or active_count(state, "VAC_501")
                if not protected and state.my_hero.health <= target.attack:
                    continue
                damage = state.my_hero.attack + cls.attack_bonus
                gain = target.delta_h_after_damage(damage)
                gain -= target.delta_h_after_damage(state.my_hero.attack)
                if not protected:
                    gain -= state.my_hero.delta_h_after_damage(target.attack)
                best = max(best, gain + redirected_value(state, target.attack))
            return best,

        # Attack bonuses are wasted when the hero cannot attack this turn.
        if hero_attack_value(state, cls.attack_bonus) <= 0:
            return 0,

        if (getattr(state, "guaranteed_face_damage", 0)
                + hero_attack_value(state, cls.attack_bonus) >= state.oppo_hero.health):
            return 1000,
        return 5 + cls.attack_bonus,

    @classmethod
    def use_with_arg(cls, state, card_index, *args):
        clicks().hero.useSkill()
        cls.finish_action()


class DemonClaws(DemonHunterHeroPower):
    pass


class DemonBite(DemonHunterHeroPower):
    attack_bonus = 2


class DemonHunterAcupuncture(SpellNoPoint):
    """VAC_419 damages both heroes, so it needs a clear lethal or Alana."""
    keep_in_hand_bool = False

    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        damage = 4 + state.my_total_spell_power + state.num_voidtouched_attendant_on_board
        alana_on_board = active_count(state, "VAC_501") > 0
        if not alana_on_board and not getattr(state.my_hero, "immune", False) \
                and state.my_hero.health <= damage:
            return 0,
        # This is an untargeted spell. Targeting restrictions do not stop it.
        if getattr(state.oppo_hero, "immune", False):
            return 0,
        redirects_to_face = (alana_on_board and not state.oppo_minions
                             and not getattr(state.my_hero, "immune", False))
        guaranteed = damage * (2 if redirects_to_face else 1)
        needles = [card for card in getattr(state, "my_hand_cards", ()) if card.card_id == "VAC_419"]
        mana = state.my_remaining_mana
        copies = 0
        for card in sorted(needles, key=lambda card: card.current_cost):
            if card.current_cost > mana:
                break
            if not alana_on_board and not getattr(state.my_hero, "immune", False) \
                    and state.my_hero.health <= damage * (copies + 1):
                break
            mana -= card.current_cost
            copies += 1
        guaranteed *= max(1, copies)
        lethal = (
            state.oppo_hero.health <= guaranteed + getattr(state, "guaranteed_face_damage", 0)
        )

        if lethal:
            return 1000,
        if alana_on_board:
            from autohs.strategy.combat import redirected_value

            return 5 + redirected_value(state, damage),
        return 0,


class OutcastDraw(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        return (2.5 if state.my_hand_card_num < 10 else 0),


class GlidingWings(OutcastDraw):
    keep_in_hand_bool = False

    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        if state.my_hand_card_num > 3 or state.my_remaining_mana < 3:
            return 0,
        if len(state.my_minions) < 7 and any(
               card.cardtype == "MINION" and card.current_cost <= state.my_remaining_mana
               for card in getattr(state, "my_hand_cards", ())):
            return 0,
        return (8 if hand_card_index in (0, state.my_hand_card_num - 1) else 7),


class MiningAxe(WeaponCard):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        if state.my_weapon is not None:
            return 0,
        ready_buccaneers = sum(minion.card_id in ("CFM_325", "WON_351", "CORE_WON_351")
                               and minion.can_beat_face for minion in state.my_minions)
        # The weapon deals one damage and draws a card on each of its two
        # swings. Value the immediate tempo and the remaining durability.
        immediate_damage = 1 if hero_can_gain_attack(state) and not state.oppo_has_taunt else 0
        return 4 + immediate_damage + 6 * ready_buccaneers,


class IgneousHeart(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        damage = 2 + state.my_total_spell_power
        best_value = 0
        best_target = None

        for side, minions in (("enemy", state.oppo_minions), ("mine", state.my_minions)):
            for index, minion in enumerate(minions):
                if not minion.can_be_pointed_by_spell or getattr(minion, "immune", False):
                    continue
                if side == "enemy" and getattr(
                    minion, "is_harmless_zero_attack_deathrattle", False,
                ):
                    continue
                survives = getattr(minion, "divine_shield", False) or minion.health > damage
                attack_value = hero_attack_value(state, 3) if survives else 0
                if side == "mine" and attack_value <= 0:
                    continue
                damage_value = minion.delta_h_after_damage(damage)
                value = attack_value + (damage_value if side == "enemy" else -abs(damage_value))
                if attack_value and not state.oppo_has_taunt \
                        and getattr(state, "guaranteed_face_damage", 0) + attack_value >= state.oppo_hero.health:
                    value = 1000
                if hasattr(minion, "get_damaged") and hasattr(state, "guaranteed_face_damage"):
                    from autohs.catalog.lookup import query_json_get_dict
                    from autohs.strategy.combat import remove_dead_minions

                    sim = copy.deepcopy(state)
                    targets = sim.my_minions if side == "mine" else sim.oppo_minions
                    target = targets[index]
                    target.get_damaged(damage)
                    if target.health > 0:
                        sim.my_hero.attack += 3
                        for puppet in sim.my_minions:
                            if puppet.card_id == "MIS_710" and active_minion(puppet):
                                puppet.attack += 3
                    else:
                        cleanup = copy.copy(sim)
                        cleanup.my_minions = targets
                        remove_dead_minions(cleanup)
                        if side == "mine":
                            sim.my_minions = cleanup.my_minions
                        else:
                            sim.oppo_minions = cleanup.my_minions
                    deathrattle = (target.health <= 0 and not target.silenced
                                  and "DEATHRATTLE" in query_json_get_dict(target.card_id).get("mechanics", []))
                    if not deathrattle and sim.guaranteed_face_damage >= sim.oppo_hero.health:
                        value = 1000
                if value > best_value:
                    best_value = value
                    best_target = (side, index)

        return best_value, best_target

    @classmethod
    def use_with_arg(cls, state, card_index, *args):
        if not args or args[0] is None:
            return
        side, target_index = args[0]
        clicks().cards.chooseHandCard(card_index, state.my_hand_card_num)
        if side == "mine":
            clicks().minion.chooseMyMinion(target_index, state.my_minion_num)
        else:
            clicks().minion.chooseEnemyMinion(target_index, state.oppo_minion_num)
        clicks().game.cancelClick()
        cls.finish_action()


class RushSpell(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        best_value = 0
        best_target = None

        for index, minion in enumerate(state.my_minions):
            if not minion.can_be_pointed_by_spell:
                continue
            finale = state.my_remaining_mana == 0
            needs_rush = (minion.exhausted and not minion.can_attack_minion and state.oppo_minions
                          and not any(getattr(minion, tag, False)
                                      for tag in ("frozen", "dormant", "cant_attack")))
            if not finale and not needs_rush:
                continue
            value = (2 if finale else 0) + (minion.attack * 0.5 if needs_rush else 0)
            if needs_rush and hasattr(minion, "get_damaged"):
                from autohs.strategy.combat import attack_body, retaliation_loss

                body = attack_body(state, minion)
                if finale:
                    body.attack += 1
                    body.max_health += 1
                gain = max((target.delta_h_after_damage(body.attack) - retaliation_loss(body, target)
                            for target in state.touchable_oppo_minions), default=0)
                if not finale and gain <= 0:
                    continue
                value = max(value, gain)
            if finale and getattr(minion, "can_beat_face", False) and not state.oppo_has_taunt \
                    and getattr(state, "guaranteed_face_damage", 0) + 1 >= state.oppo_hero.health:
                value = 1000
            if value > best_value:
                best_value = value
                best_target = index

        return best_value, best_target

    @classmethod
    def use_with_arg(cls, state, card_index, *args):
        if not args or args[0] is None:
            return
        clicks().cards.chooseHandCard(card_index, state.my_hand_card_num)
        clicks().minion.chooseMyMinion(args[0], state.my_minion_num)
        clicks().game.cancelClick()
        cls.finish_action()


class IllidariStudies(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        return 1.5,


class SpectralSight(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        return 1.5,


class ChaosStrike(SpellNoPoint):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        # The attack bonus matters only if the hero can use it this turn.
        return 1.2 if state.my_hero.can_attack or state.my_hero.exhausted == 0 else 0.4,


class EyeBeam(SpellPointOppo):
    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        damage = 3 + state.my_total_spell_power
        best_delta_h = 0
        best_oppo_index = -1

        for oppo_index, oppo_minion in enumerate(state.oppo_minions):
            if not oppo_minion.can_be_pointed_by_spell:
                continue
            delta_h = oppo_minion.delta_h_after_damage(damage)
            if delta_h > best_delta_h:
                best_delta_h = delta_h
                best_oppo_index = oppo_index

        return best_delta_h, best_oppo_index


class AldrachiWarblades(WeaponCard):
    value = 2.0

    @classmethod
    def best_h_and_arg(cls, state, hand_card_index):
        # Do not replace a weapon that is already equipped.
        if state.my_weapon is not None:
            return 0,
        return cls.value,


class MurlocTidehunter(MinionNoPoint):
    value = 2.0


class Felscreamer(MinionNoPoint):
    value = 2.5


class PrimevalLord(MinionNoPoint):
    value = 2.5


class CrimsonSigilRunner(MinionNoPoint):
    value = 1.0


class Battlefiend(MinionNoPoint):
    value = 2.0


class GanargBrute(MinionNoPoint):
    value = 2.0


class KaynSunfury(MinionNoPoint):
    value = 4.5
    keep_in_hand_bool = False

    @classmethod
    def utilize_delta_h_and_arg(cls, state, hand_card_index):
        damage = state.face_damage_ignoring_taunt + state.my_hand_cards[hand_card_index].attack
        lethal = (state.oppo_has_taunt and state.oppo_hero.can_be_pointed_by_minion
                  and damage >= state.oppo_hero.health)
        return (1000 if lethal else cls.value), state.my_minion_num


class PatchesThePilot(MinionNoPoint):
    value = 80


class PirateDealer(MinionNoPoint):
    value = 8
    live_value = 1

    @classmethod
    def utilize_delta_h_and_arg(cls, state, hand_card_index):
        cost = state.my_hand_cards[hand_card_index].current_cost
        ready_cliff = state.my_minion_num <= 4 and any(
            minion.card_id == "VAC_929" and not minion.exhausted for minion in state.my_minions
        )
        affordable_cliff = state.my_minion_num <= 3 and any(
            card.card_id == "VAC_929" and cost + card.current_cost <= state.my_remaining_mana
            for card in state.my_hand_cards
        )
        return (40 if ready_cliff or affordable_cliff else cls.value), state.my_minion_num


class PirateSupport(MinionNoPoint):
    value = 7

    @classmethod
    def keep_in_hand(cls, state, hand_card_index):
        card = state.my_hand_cards[hand_card_index]
        return card.current_cost <= 2 and any(
            index != hand_card_index and other.cardtype == "MINION" and other.current_cost <= 1
            for index, other in enumerate(state.my_hand_cards)
        )

    @classmethod
    def utilize_delta_h_and_arg(cls, state, hand_card_index):
        if setup_lethal(state, hand_card_index, state.my_minion_num):
            return 1000, state.my_minion_num
        ready = sum(minion.is_pirate and minion.can_beat_face for minion in state.my_minions)
        return cls.value + ready * 2, state.my_minion_num


class PowerCountZilliax(MinionNoPoint):
    keep_in_hand_bool = False

    @classmethod
    def utilize_delta_h_and_arg(cls, state, hand_card_index):
        ready = sum(minion.can_beat_face for minion in state.my_minions)
        value = 7 + 2 * ready
        if ready and not state.oppo_has_taunt and state.oppo_hero.can_be_pointed_by_minion \
                and state.guaranteed_face_damage + ready >= state.oppo_hero.health:
            value = 1000
        return value, state.my_minion_num


class CoconutCannoneer(PirateSupport):
    @classmethod
    def utilize_delta_h_and_arg(cls, state, hand_card_index):
        # A gap's two neighbours remain adjacent to the newly placed cannon.
        gap = max(range(state.my_minion_num + 1), key=lambda pos: sum(
            state.my_minions[index].can_attack_minion
            for index in (pos - 1, pos) if 0 <= index < state.my_minion_num
        ))
        return (1000 if setup_lethal(state, hand_card_index, gap) else cls.value), gap


class Alanna(MinionNoPoint):
    value = 6
    keep_in_hand_bool = False

    @classmethod
    def utilize_delta_h_and_arg(cls, state, hand_card_index):
        combo = any(card.card_id == "VAC_419" and card.current_cost
                    + state.my_hand_cards[hand_card_index].current_cost <= state.my_remaining_mana
                    for card in state.my_hand_cards)
        value = 18 if combo else cls.value
        if state.my_hero.can_attack and hasattr(state, "touchable_oppo_minions"):
            from autohs.strategy.combat import redirected_value

            sim = copy.copy(state)
            sim.my_minions = state.my_minions + [state.my_hand_cards[hand_card_index]]
            gains = []
            for target in state.touchable_oppo_minions:
                protection = 0 if getattr(state.my_hero, "immune", False) else min(
                    target.attack, state.my_hero.delta_h_after_damage(target.attack)
                )
                gains.append(protection + redirected_value(sim, target.attack))
            value += max(gains, default=0)
        return value, state.my_minion_num


class IllidariInquisitor(MinionNoPoint):
    value = 6.0


class OgreNinja(MinionNoPoint):
    value = 5.0
