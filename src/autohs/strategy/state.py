import copy
import random
from itertools import combinations
from typing import List

from autohs.behaviors.basic import MinionNoPoint, clicks
from autohs.behaviors.demon_hunter import (
    active_count,
    active_minion,
)
from autohs.constants import *
from autohs.infrastructure.logging import logger
from autohs.strategy.combat import (
    attack_body,
    attack_order,
    cannon_triggers,
    combined_trade_gain,
    face_damage,
    random_damage_value,
    redirected_value,
    retaliation_loss,
)
from autohs.strategy.entities import *


class StrategyState:
    def __init__(self, log_state : LogState=None):
        # 注意地标也算 minion
        self.oppo_minions: List[StrategyMinion] = []
        self.oppo_graveyard: List[StrategyEntity] = []
        self.my_minions: List[StrategyMinion] = []
        self.my_hand_cards: List[StrategyEntity] = []
        self.my_graveyard: List[StrategyEntity] = []

        self.my_hero: StrategyHero = None
        self.my_hero_power: StrategyHeroPower = None
        self.can_use_power: bool = False
        self.my_weapon: StrategyWeapon = None
        self.oppo_hero: StrategyHero = None
        self.oppo_hero_power: StrategyHeroPower = None
        self.oppo_weapon: StrategyWeapon = None
        self.oppo_hand_card_num: int = 0

        self.my_total_mana: int = int(log_state.my_entity.query_tag("RESOURCES"))
        self.my_used_mana: int = int(log_state.my_entity.query_tag("RESOURCES_USED"))
        self.my_temp_mana: int = int(log_state.my_entity.query_tag("TEMP_RESOURCES"))
        self.my_corpses = int(log_state.my_entity.query_tag("CORPSES"))
        self.my_num_turns_in_play = int(
            log_state.my_entity.query_tag("TURN")
        )

        for entity in log_state.entity_dict.values():
            if entity.query_tag("ZONE") == "HAND":
                if log_state.is_my_entity(entity):
                    hand_card = generate_strategy_entity(entity, log_state)
                    self.my_hand_cards.append(hand_card)
                else:
                    self.oppo_hand_card_num += 1

            elif entity.zone == "PLAY":
                if entity.cardtype == "GAME" or entity.cardtype == "PLAYER":
                    continue

                elif entity.cardtype == "MINION" or entity.cardtype == "LOCATION":
                    minion = generate_strategy_entity(entity, log_state)
                    if log_state.is_my_entity(entity):
                        self.my_minions.append(minion)
                    else:
                        self.oppo_minions.append(minion)

                elif entity.cardtype == "HERO":
                    hero = generate_strategy_entity(entity, log_state)
                    if log_state.is_my_entity(entity):
                        self.my_hero = hero
                    else:
                        self.oppo_hero = hero

                # 好吧，有些时候英雄技能会在对局中被替换掉，比如暗黑主教本尼迪塔斯的开局效果。
                # 不过在 python 的 3.7 版本之后，字典的遍历顺序是按照插入顺序的，后出现的技能
                # 会覆盖掉先出现的技能，完美。
                elif entity.cardtype == "HERO_POWER":
                    hero_power = generate_strategy_entity(entity, log_state)
                    if log_state.is_my_entity(entity):
                        self.my_hero_power = hero_power
                    else:
                        self.oppo_hero_power = hero_power

                elif entity.cardtype == "WEAPON":
                    weapon = generate_strategy_entity(entity, log_state)
                    if log_state.is_my_entity(entity):
                        self.my_weapon = weapon
                    else:
                        self.oppo_weapon = weapon

            elif entity.zone == "GRAVEYARD":
                if log_state.is_my_entity(entity):
                    self.my_graveyard.append(entity)
                else:
                    self.oppo_graveyard.append(entity)

        self.my_minions.sort(key=lambda temp: temp.zone_pos)
        self.oppo_minions.sort(key=lambda temp: temp.zone_pos)
        self.my_hand_cards.sort(key=lambda temp: temp.zone_pos)

    def should_give_up(self):
        # 为时尚早
        THRESHOLD = 7

        if self.my_total_mana <= 6:
            return False

        score = 0
        if self.oppo_hero.health >= 30:
            score += 4
        if self.oppo_hero.health >= 25:
            score += 2
        elif self.oppo_hero.health >= 15:
            score += 1

        if self.my_hand_card_num <= 1:
            score += 2

        if self.my_minion_num <= 1:
            score += 2

        if self.oppo_hand_card_num >= 4:
            score += 1

        if self.oppo_minion_num >= 4:
            score += 2

        if self.oppo_has_taunt:
            score += 1

        logger.debug(f"智能投降分数: {score}/{THRESHOLD}")
        if score >= THRESHOLD:
            return True
        return False

    def will_die_next_turn(self):
        if self.mine_has_taunt:
            return False

        if self.my_hero.health <= self.oppo_total_attack + self.num_voidtouched_attendant_on_board * self.oppo_minion_num:
            return True

        return False

    def debug_print_battlefield(self):
        logger.debug("对手英雄:")
        logger.debug("    " + str(self.oppo_hero))
        logger.debug(f"技能:")
        logger.debug("    " + self.oppo_hero_power.name + " 费用：" + str(self.oppo_hero_power.current_cost))
        if self.oppo_weapon:
            logger.debug("头上有把武器:")
            logger.debug("    " + str(self.oppo_weapon))
        if self.oppo_minion_num > 0:
            logger.debug(f"对手有{self.oppo_minion_num}个随从:")
            for minion in self.oppo_minions:
                logger.debug("    " + str(minion))
        else:
            logger.debug(f"对手没有随从")
        logger.debug(f"总卡费启发值: {self.oppo_heuristic_value}")

        logger.debug("--------------------")

        logger.debug("我的英雄:")
        logger.debug("    " + str(self.my_hero))
        logger.debug(f"技能:")
        logger.debug("    " + self.my_hero_power.name + " 费用：" + str(self.my_hero_power.current_cost))
        if self.my_weapon:
            logger.debug("头上有把武器:")
            logger.debug("    " + str(self.my_weapon))
        if self.my_minion_num > 0:
            logger.debug(f"我有{self.my_minion_num}个随从:")
            for minion in self.my_minions:
                logger.debug("    " + str(minion))
        else:
            logger.debug("我没有随从")
        logger.debug(f"总卡费启发值: {self.my_heuristic_value}")

    def debug_print_out(self):
        if len(self.oppo_graveyard) > 0:
            logger.debug(f"对手墓地:")
            logger.debug("    " + ", ".join([entity.name for entity in self.oppo_graveyard]))
        else:
            logger.debug(f"对手墓地为空")

        logger.debug(f"对手有{self.oppo_hand_card_num}张手牌")

        self.debug_print_battlefield()
        logger.debug("--------------------")

        logger.debug(f"水晶: {self.my_remaining_mana}/{self.my_total_mana}")
        logger.debug(f"我有{self.my_hand_card_num}张手牌:")
        for hand_card in self.my_hand_cards:
            logger.debug(f"    [{hand_card.zone_pos}] {hand_card.name} "
                        f"cost:{hand_card.current_cost}")
        if len(self.my_graveyard) > 0:
            logger.debug(f"我的墓地:")
            logger.debug("    " + ", ".join([entity.name for entity in self.my_graveyard]))
        else:
            logger.debug(f"我的墓地为空")

    @property
    def my_remaining_mana(self):
        return self.my_total_mana - self.my_used_mana + self.my_temp_mana

    @property
    def oppo_minion_num(self):
        return len(self.oppo_minions)

    def num_card_in_hand(self, name_or_id):
        return sum(1 for hand_card in self.my_hand_cards if hand_card.name == name_or_id or hand_card.card_id == name_or_id)

    def if_card_in_hand(self, name_or_id):
        return any(hand_card.name == name_or_id or hand_card.card_id == name_or_id for hand_card in self.my_hand_cards)

    @property
    def my_minion_num(self):
        return len(self.my_minions)

    @property
    def my_hand_card_num(self):
        return len(self.my_hand_cards)

    # 用卡费体系算启发值
    @property
    def oppo_heuristic_value(self):
        total_h_val = 0
        if self.oppo_hero:
            total_h_val += self.oppo_hero.heuristic_val
        if self.oppo_weapon:
            total_h_val += self.oppo_weapon.heuristic_val
        for minion in self.oppo_minions:
            total_h_val += minion.heuristic_val
        return total_h_val

    @property
    def my_heuristic_value(self):
        total_h_val = 0
        if self.my_hero:
            total_h_val = self.my_hero.heuristic_val
        if self.my_weapon:
            total_h_val += self.my_weapon.heuristic_val
        for minion in self.my_minions:
            total_h_val += minion.heuristic_val
        return total_h_val

    @property
    def heuristic_value(self):
        return round(self.my_heuristic_value - self.oppo_heuristic_value, 3)

    @property
    def min_cost(self):
        minium = 100
        for hand_card in self.my_hand_cards:
            minium = min(minium, hand_card.current_cost)
        return minium

    @property
    def my_total_spell_power(self):
        return sum([minion.spell_power for minion in self.my_minions])

    @property
    def my_detail_hero_power(self):
        return self.my_hero_power.detail_hero_power

    @property
    def touchable_oppo_minions(self) -> List[StrategyMinion]:
        ret = []

        for oppo_minion in self.oppo_minions:
            if oppo_minion.taunt and oppo_minion.can_be_pointed_by_minion \
                    and not self._skip_optional_attack_target(oppo_minion):
                ret.append(oppo_minion)

        if len(ret) == 0:
            for oppo_minion in self.oppo_minions:
                if oppo_minion.can_be_pointed_by_minion \
                        and not self._skip_optional_attack_target(oppo_minion):
                    ret.append(oppo_minion)

        return ret

    @staticmethod
    def _skip_optional_attack_target(minion):
        return getattr(minion, "is_harmless_zero_attack_deathrattle", False)

    @property
    def oppo_has_taunt(self):
        if active_count(self, "BT_187", "CORE_BT_187"):
            return False
        for oppo_minion in self.oppo_minions:
            if oppo_minion.taunt and not oppo_minion.stealth and not oppo_minion.untouchable:
                return True

        return False

    @property
    def is_demon_hunter(self):
        return getattr(getattr(self, "my_hero", None), "card_id", "").startswith("HERO_10")

    @property
    def face_damage_ignoring_taunt(self):
        return face_damage(self)

    @property
    def guaranteed_face_damage(self):
        if self.oppo_has_taunt:
            return 0
        return self.face_damage_ignoring_taunt

    @property
    def face_pressure_multiplier(self):
        if not self.is_demon_hunter:
            return 1
        health = self.oppo_hero.health
        baseline = 1.25 if health <= 12 else 1
        if health >= 20 or self.oppo_has_taunt or not self.oppo_hero.can_be_pointed_by_minion:
            return baseline

        enemies = [minion for minion in self.oppo_minions
                   if minion.cardtype == CARD_MINION and minion.health > 0
                   and not minion.dormant and not minion.frozen and not minion.cant_attack]
        incoming = sum(minion.attack * (2 if minion.windfury else 1) for minion in enemies)
        if not self.oppo_hero.frozen and not self.oppo_hero.cant_attack:
            weapon = getattr(self, "oppo_weapon", None)
            weapon_attack = weapon.attack if weapon is not None and weapon.health > 0 else 0
            incoming += max(self.oppo_hero.attack, weapon_attack) * (
                2 if weapon is not None and weapon.windfury else 1
            )
        if incoming >= self.my_hero.health or any(
                minion.attack > 0 and (minion.life_steal or minion.poisonous) for minion in enemies):
            return baseline

        aura_ids = {"NEW1_027", "CORE_NEW1_027", "VAN_NEW1_027", "TOY_330t5"}
        auras = [minion for minion in self.my_minions
                 if minion.card_id in aura_ids and active_minion(minion)]
        next_turn_damage = 0
        for minion in self.my_minions:
            if minion.cardtype != CARD_MINION or minion.card_id == "MIS_710" \
                    or minion.dormant or minion.frozen or minion.cant_attack:
                continue
            # Do not rely on temporary hero attack, a surviving aura, or enemy restraint.
            aura_loss = sum(aura is not minion and (aura.card_id == "TOY_330t5" or minion.is_pirate)
                            for aura in auras)
            remaining_health = minion.health - aura_loss
            if minion.can_beat_face and not minion.immune and not minion.divine_shield:
                remaining_health -= self.oppo_hero.attack
            if remaining_health > incoming:
                next_turn_damage += max(0, minion.attack - aura_loss)

        current_damage = self.guaranteed_face_damage
        if current_damage + next_turn_damage >= health:
            logger.debug(f"两回合抢血加权: 当前伤害 {current_damage}, "
                         f"下回合保守估计 {next_turn_damage}, 打脸收益倍率 1.5")
            return 1.5
        return baseline

    @property
    def mine_has_taunt(self):
        for my_minion in self.my_minions:
            if my_minion.taunt and not my_minion.stealth:
                return True

        return False

    @property
    def my_total_attack(self):
        count = 0
        for my_minion in self.my_minions:
            if my_minion.can_beat_face:
                count += my_minion.attack

        if self.my_hero.can_attack:
            count += self.my_hero.attack

        return count

    @property
    def oppo_total_attack(self):
        count = 0
        for oppo_minion in self.oppo_minions:
            count += oppo_minion.attack

        if self.oppo_hero.can_attack:
            count += self.oppo_hero.attack

        return count

    # 场上有多少个虚触侍从，敌我双方都会生效，所以都算进去
    @property
    def num_voidtouched_attendant_on_board(self):
        count = 0
        for minion in self.my_minions + self.oppo_minions:
            if minion.card_id == "SW_446":
                count += 1

        return count

    @property
    def num_mindbreaker_on_board(self):
        count = 0
        for minion in self.my_minions + self.oppo_minions:
            if minion.card_id == "CORE_ICC_902" or minion.card_id == "ICC_902":
                count += 1

        return count

    # 我手牌里有几个空降歹徒，有的话就应该丢海盗
    @property
    def airborne_gangsters_in_hand(self):
        count = 0
        for hand_card in self.my_hand_cards:
            if hand_card.card_id == "DRG_056":
                count += 1

        return count

    @property
    # 给亡者复生用的
    def num_minions_in_my_graveyard(self):
        count = 0
        for entity in self.my_graveyard:
            if entity.cardtype == "MINION":
                count += 1

        return count

    def fight_between(self, oppo_index, my_index):
        oppo_minion = self.oppo_minions[oppo_index]
        my_minion = self.my_minions[my_index]

        if oppo_minion.get_damaged(my_minion.attack):
            self.oppo_minions.pop(oppo_index)

        if my_minion.get_damaged(oppo_minion.attack):
            self.my_minions.pop(my_index)

    def random_distribute_damage(self, damage, oppo_index_list, my_index_list):
        if len(oppo_index_list) == len(my_index_list) == 0:
            return

        random_x = random.randint(0, len(oppo_index_list) + len(my_index_list) - 1)

        if random_x < len(oppo_index_list):
            oppo_index = oppo_index_list[random_x]
            minion = self.oppo_minions[oppo_index]
            if minion.get_damaged(damage):
                self.oppo_minions.pop(oppo_index)
        else:
            my_index = my_index_list[random_x - len(oppo_index_list)]
            minion = self.my_minions[my_index]
            if minion.get_damaged(damage):
                self.my_minions.pop(my_index)

    def get_best_location_trigger(self):
        best_delta_h = 0
        best_location_index = -1
        best_args = []

        logger.debug("考虑触发地标")

        for my_index, my_minion in enumerate(self.my_minions):
            if my_minion.cardtype != CARD_LOCATION:
                continue

            if my_minion.exhausted or my_minion.detail_card is None:
                continue

            delta_h, *args = my_minion.detail_card.location_trigger_h_and_arg(self, my_index)
            logger.debug(f"地标-[{my_index}]({my_minion.name}) 价值: {delta_h}, "
                        f"args: {args}")
            if delta_h > best_delta_h:
                best_delta_h = delta_h
                best_location_index = my_index
                best_args = args

        return best_location_index, best_args

    def get_best_combined_trade(self):
        attackers = [index for index, body in attack_order(self)
                     if body.can_attack_minion]
        if self.my_hero.can_attack:
            attackers.append(-1)
        best_gain = 0
        best = None
        captains = {"NEW1_027", "CORE_NEW1_027", "VAN_NEW1_027"}
        for target in self.touchable_oppo_minions:
            aura_gain = 0
            if target.card_id in captains and active_minion(target):
                for other in self.oppo_minions:
                    if other is target or not other.is_pirate:
                        continue
                    weakened = copy.copy(other)
                    weakened.attack = max(0, weakened.attack - 1)
                    weakened.max_health -= 1
                    aura_gain += other.heuristic_val - weakened.heuristic_val
            for count in range(1 if aura_gain else 2, len(attackers) + 1):
                for group in combinations(attackers, count):
                    orders = [group]
                    if -1 in group:
                        minions = tuple(index for index in group if index != -1)
                        orders = [(-1,) + minions, minions + (-1,)]
                        if active_count(self, "VAC_927") and any(
                                self.my_minions[index].is_pirate for index in minions):
                            orders.sort(key=lambda order: order[0] == -1)
                    if target.divine_shield:
                        orders.append(tuple(sorted(group, key=lambda i: (
                            self.my_hero.attack if i == -1 else attack_body(self, self.my_minions[i]).attack
                        ))))
                    for order in orders:
                        gain = combined_trade_gain(self, target, order)
                        if gain is not None and gain + aura_gain > best_gain:
                            best_gain = gain + aura_gain
                            best = (order[0], target.zone_pos - 1)
        if best is not None:
            logger.debug(f"合力解场决策: {best}, 净收益: {best_gain}")
        return best

    def get_best_attack_target(self):
        touchable_oppo_minions = self.touchable_oppo_minions
        has_taunt = self.oppo_has_taunt
        face_weight = self.face_pressure_multiplier
        beat_face_win = self.my_total_attack >= self.oppo_hero.health
        if self.is_demon_hunter:
            beat_face_win = self.guaranteed_face_damage >= self.oppo_hero.health
            if not beat_face_win:
                combined_trade = self.get_best_combined_trade()
                if combined_trade is not None:
                    return combined_trade
            ready = [(index, minion) for index, minion in attack_order(self)
                     if minion.can_beat_face]
            if not has_taunt and self.oppo_hero.can_be_pointed_by_minion and beat_face_win:
                if ready:
                    logger.debug("海盗瞎确定斩杀，随从先攻击，英雄后攻击")
                    return ready[0][0], -1
                if self.my_hero.can_attack and (self.my_hero.health > self.oppo_hero.attack
                        or self.my_hero.immune or active_count(self, "VAC_501")):
                    return -1, -1

        max_delta_h_val = -999999   # 如果设成0，会出现一个嘲讽卡住所有随从的情况
        max_my_index = -2
        max_oppo_index = -2
        min_attack = 0
        pirates_can_buff_hero = self.is_demon_hunter and active_count(self, "VAC_927") and any(
            minion.is_pirate and minion.can_attack_minion for minion in self.my_minions
        )

        # 枚举每一个己方随从
        logger.debug("枚举随从")
        ordered = attack_order(self) if self.is_demon_hunter else list(enumerate(self.my_minions))
        for my_index, my_minion in ordered:
            if not my_minion.can_attack_minion:
                continue
            if pirates_can_buff_hero and my_minion.card_id == "MIS_710" and active_minion(my_minion):
                continue
            body = attack_body(self, my_minion) if self.is_demon_hunter else my_minion

            # 如果没有墙,随从又能打脸,应该试一试
            if not has_taunt \
                    and my_minion.can_beat_face \
                    and self.oppo_hero.can_be_pointed_by_minion:
                if beat_face_win:
                    logger.debug(f"攻击决策: [{my_index}]({my_minion.name})->"
                                f"[-1]({self.oppo_hero.name}) "
                                f"斩杀了")
                    return my_index, -1

                tmp_delta_h = self.oppo_hero.delta_h_after_damage(
                    body.attack + self.num_voidtouched_attendant_on_board
                ) * face_weight
                if self.is_demon_hunter and (body.immune or body.divine_shield or body.health > self.oppo_hero.attack):
                    tmp_delta_h += cannon_triggers(self, my_index) * random_damage_value(self, 1)

                logger.debug(f"攻击决策: [{my_index}]({my_minion.name})->"
                            f"[-1]({self.oppo_hero.name}) "
                            f"delta_h_val:{tmp_delta_h}")

                if tmp_delta_h > max_delta_h_val:
                    max_delta_h_val = tmp_delta_h
                    max_my_index = my_index
                    max_oppo_index = -1
                    min_attack = 999

            for oppo_minion in touchable_oppo_minions:
                oppo_index = oppo_minion.zone_pos - 1

                tmp_delta_h = 0
                tmp_delta_h -= (retaliation_loss(body, oppo_minion) if self.is_demon_hunter
                                else my_minion.delta_h_after_damage(oppo_minion.attack))
                tmp_delta_h += oppo_minion.delta_h_after_damage(body.attack)
                if self.is_demon_hunter and (body.immune or body.divine_shield
                        or body.health > oppo_minion.attack and not oppo_minion.poisonous):
                    tmp_delta_h += cannon_triggers(self, my_index) * random_damage_value(self, 1)

                logger.debug(f"攻击尝试：[{my_index}]({my_minion.name})->"
                            f"[{oppo_index}]({oppo_minion.name}) "
                            f"delta_h_val: {tmp_delta_h}")

                if tmp_delta_h > max_delta_h_val or \
                        tmp_delta_h == max_delta_h_val and my_minion.attack < min_attack:
                    max_delta_h_val = tmp_delta_h
                    max_my_index = my_index
                    max_oppo_index = oppo_index
                    min_attack = my_minion.attack

        # 试一试英雄攻击
        if self.my_hero.can_attack:
            if self.is_demon_hunter and active_count(self, "VAC_927") and max_my_index >= 0:
                logger.debug("海盗先攻击，为英雄和布袋手偶累积攻击力")
                return max_my_index, max_oppo_index
            logger.debug("考虑英雄攻击")
            protected = getattr(self.my_hero, "immune", False) or active_count(self, "VAC_501")
            weapon_loss = self.my_weapon.attack if self.my_weapon is not None else 0
            if not has_taunt and self.oppo_hero.can_be_pointed_by_minion:
                if beat_face_win:
                    logger.debug(f"攻击决策: [-1]({self.my_hero.name})->"
                                f"[-1]({self.oppo_hero.name}) "
                                f"斩杀了")
                    return -1, -1
                if self.my_hero.health > getattr(self.oppo_hero, "attack", 0) \
                        or protected:
                    if not self.is_demon_hunter:
                        return -1, -1
                    # Face is a candidate, not an early exit before cheap removal.
                    face_gain = self.oppo_hero.delta_h_after_damage(
                        self.my_hero.attack + self.num_voidtouched_attendant_on_board
                    ) * face_weight - weapon_loss
                    if not protected:
                        face_gain -= self.my_hero.delta_h_after_damage(self.oppo_hero.attack)
                    face_gain += redirected_value(self, self.oppo_hero.attack)
                    logger.debug(f"英雄打脸收益: {face_gain}")
                    if face_gain > max_delta_h_val:
                        max_delta_h_val = face_gain
                        max_my_index = -1
                        max_oppo_index = -1

            for oppo_minion in touchable_oppo_minions:
                oppo_index = oppo_minion.zone_pos - 1
                if self.my_hero.health <= oppo_minion.attack and not protected:
                    continue

                tmp_delta_h = oppo_minion.delta_h_after_damage(self.my_hero.attack) - weapon_loss
                if not protected:
                    tmp_delta_h -= self.my_hero.delta_h_after_damage(oppo_minion.attack)
                tmp_delta_h += redirected_value(self, oppo_minion.attack)

                logger.debug(f"攻击决策: [-1]({self.my_hero.name})->"
                            f"[{oppo_index}]({oppo_minion.name}) "
                            f"delta_h_val: {tmp_delta_h}")

                if tmp_delta_h >= max_delta_h_val:
                    max_delta_h_val = tmp_delta_h
                    max_my_index = -1
                    max_oppo_index = oppo_index

        logger.debug(f"最终决策: max_my_index: {max_my_index}, "
                    f"max_oppo_index: {max_oppo_index}")

        return max_my_index, max_oppo_index

    def next_battle_action(self):
        # Re-evaluate after every real action, including a hero attack reopening a location.
        if self.is_demon_hunter and self.guaranteed_face_damage >= self.oppo_hero.health:
            attacker, target = self.get_best_attack_target()
            if attacker != -2:
                return "attack", attacker, target

        location_index, location_args = self.get_best_location_trigger()
        if location_index != -1:
            location = self.my_minions[location_index].detail_card
            if location.location_trigger_h_and_arg(self, location_index)[0] >= 1000:
                return "location", location_index, location_args

        card_index, card_args = self.best_h_index_arg()
        setup_ids = {"VAC_933", "TOY_518", "VAC_927", "VAC_938", "VAC_532",
                     "NEW1_027", "CORE_NEW1_027", "VAN_NEW1_027", "TOY_330t5"}
        if card_index == -1 and self.my_detail_hero_power.best_h_and_arg(self, -1)[0] >= 1000:
            return "card", card_index, card_args
        if card_index >= 0:
            card = self.my_hand_cards[card_index]
            if card.card_id == "VAC_928" and card_index not in (0, self.my_hand_card_num - 1):
                for edge in (0, self.my_hand_card_num - 1):
                    other = self.my_hand_cards[edge]
                    if other.detail_card and other.current_cost + card.current_cost <= self.my_remaining_mana:
                        value, *args = other.detail_card.best_h_and_arg(self, edge)
                        if value > 0:
                            return "card", edge, args
            lethal = card.detail_card and card.detail_card.best_h_and_arg(self, card_index)[0] >= 1000
            if self.is_demon_hunter and not lethal:
                from autohs.strategy.turn import open_token_space, setup_before_card

                opening = open_token_space(self)
                if opening is not None:
                    return opening
                sequence = setup_before_card(self, card_index, card_args)
                if sequence is not None:
                    return sequence
            setup = (self.is_demon_hunter and card.card_id in setup_ids
                     and (self.my_minion_num <= 4 or card.card_id == "VAC_933"))
            if lethal or setup:
                return "card", card_index, card_args

        if location_index != -1:
            return "location", location_index, location_args
        if card_index != -2:
            return "card", card_index, card_args
        attacker, target = self.get_best_attack_target()
        if attacker != -2:
            return "attack", attacker, target
        return "end", -2, []

    def my_entity_attack_oppo(self, my_index, oppo_index):
        if my_index == -1:
            if oppo_index == -1:
                clicks().attack.myHeroAttackEnemyHero()
            else:
                clicks().attack.myHeroAttackEnemyMinion(oppo_index, self.oppo_minion_num)
        else:
            if oppo_index == -1:
                clicks().attack.minionAttackEnemyHero(my_index, self.my_minion_num)
            else:
                clicks().attack.minionAttackEnemyMinion(my_index, self.my_minion_num, oppo_index, self.oppo_minion_num)

    def copy_new_one(self):
        # TODO: 有必要deepcopy吗
        tmp = copy.deepcopy(self)
        for i in range(self.oppo_minion_num):
            tmp.oppo_minions[i] = copy.deepcopy(self.oppo_minions[i])
        for i in range(self.my_minion_num):
            tmp.my_minions[i] = copy.deepcopy(self.my_minions[i])
        for i in range(self.my_hand_card_num):
            tmp.my_hand_cards[i] = copy.deepcopy(self.my_hand_cards[i])
        return tmp

    def best_h_index_arg(self):
        logger.debug("------ 开始决策 ------")
        best_delta_h = 0
        best_index = -2
        best_args = []
        first_turn = getattr(self, "my_num_turns_in_play", 2) == 1
        best_minion = None
        best_weapon = None

        # 考虑使用手牌
        for hand_card_index, hand_card in enumerate(self.my_hand_cards):
            delta_h = 0
            args = []

            if hand_card.current_cost > self.my_remaining_mana or (
                    self.my_minion_num >= 7 and hand_card.cardtype in (CARD_MINION, CARD_LOCATION)):
                logger.debug(f"卡牌-[{hand_card_index}]({hand_card.name}) 跳过")
                continue

            detail_card = hand_card.detail_card
            if detail_card is None:
                if hand_card.cardtype == CARD_MINION and not hand_card.battlecry:
                    delta_h, *args = MinionNoPoint.best_h_and_arg(self, hand_card_index)
                    logger.debug(f"卡牌-[{hand_card_index}]({hand_card.name}) "
                                f"delta_h: {delta_h}, *args: {[]} (默认行为) ")
                else:
                    logger.debug(f"卡牌-[{hand_card_index}]({hand_card.name})无法评判")
            else:
                res = detail_card.best_h_and_arg(self, hand_card_index)
                if not isinstance(res, tuple): #解决如果战吼随从没有对方可点击的随从的问题
                    logger.warning(f"卡牌-[{hand_card_index}]({hand_card.name}) best_h_and_arg返回值格式错误: {res}")
                    res = (res,)
                delta_h, *args = res

                logger.debug(f"卡牌-[{hand_card_index}]({hand_card.name}) "
                            f"delta_h: {delta_h}, *args: {args} (手写行为)")

            if hand_card.cardtype == CARD_MINION and self.my_minion_num < 7 \
                    and delta_h >= 0 and (detail_card is not None or not hand_card.battlecry) \
                    and (best_minion is None or delta_h > best_minion[0]):
                best_minion = (delta_h, hand_card_index, args)
            if hand_card.cardtype == CARD_WEAPON and delta_h >= 0 \
                    and (best_weapon is None or delta_h > best_weapon[0]):
                best_weapon = (delta_h, hand_card_index, args)

            if delta_h > best_delta_h:
                best_delta_h = delta_h
                best_index = hand_card_index
                best_args = args

        # 考虑使用英雄技能
        if self.my_remaining_mana >= self.my_hero_power.current_cost and \
                self.my_detail_hero_power and \
                not self.my_hero_power.exhausted \
                and self.num_mindbreaker_on_board == 0:
            hero_power = self.my_detail_hero_power

            delta_h, *args = hero_power.best_h_and_arg(self, -1)

            logger.debug(f"技能-[ ]({self.my_hero_power.name}) "
                        f"delta_h: {delta_h} "
                        f"*args: {args}")

            if delta_h > best_delta_h:
                best_index = -1
                best_delta_h = delta_h
                best_args = args
        else:
            logger.debug(f"技能-[ ]({self.my_hero_power.name}) 跳过")

        preserve_minion_mana = (self.is_demon_hunter and best_index == -1
                                and best_minion is not None
                                and self.my_hand_cards[best_minion[1]].current_cost
                                + self.my_hero_power.current_cost > self.my_remaining_mana)
        preserve_minion_mana = preserve_minion_mana or (
            self.is_demon_hunter and best_index == -1 and best_minion is not None
            and any(card.card_id == "VAC_928" for card in self.my_hand_cards)
        )
        preserve_weapon_mana = (self.is_demon_hunter and best_index == -1
                                and best_weapon is not None
                                and best_weapon[0] > 0
                                and best_weapon[1] != best_index
                                and self.my_remaining_mana >= self.my_hand_cards[best_weapon[1]].current_cost
                                and self.my_hand_cards[best_weapon[1]].current_cost
                                + self.my_hero_power.current_cost > self.my_remaining_mana)
        if (first_turn or preserve_minion_mana or preserve_weapon_mana) \
                and best_delta_h < 1000:
            if preserve_weapon_mana:
                best_delta_h, best_index, best_args = best_weapon
                logger.debug("技能会占用可挂武器的费用，优先挂武器")
            elif best_minion is not None:
                best_delta_h, best_index, best_args = best_minion
                logger.debug("首回合或技能占用铺场费用，优先下随从")

        logger.debug(f"决策结果: best_delta_h:{best_delta_h}, "
                    f"best_index:{best_index}, best_args:{best_args}")
        logger.debug("------ 结束决策 ------")
        return best_index, best_args

    def use_best_entity(self, index, args):
        if index == -1:
            logger.debug("将使用技能")
            hero_power = self.my_detail_hero_power
            hero_power.use_with_arg(self, -1, *args)
        else:
            self.use_card(index, *args)

    # 会返回这张卡的cost
    def use_card(self, index, *args):
        hand_card = self.my_hand_cards[index]
        detail_card = hand_card.detail_card
        logger.debug(f"将使用卡牌[{index}] {hand_card.name}")

        if detail_card is None:
            MinionNoPoint.use_with_arg(self, index, *args)
        else:
            detail_card.use_with_arg(self, index, *args)

        self.my_hand_cards.pop(index)
        return hand_card.current_cost
