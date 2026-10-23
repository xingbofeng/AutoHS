"""Compare two known setup cards without predicting draws or another turn."""

import copy

from autohs.behaviors.basic import MinionNoPoint
from autohs.behaviors.demon_hunter import active_count
from autohs.strategy.combat import attack_body, retaliation_loss
from autohs.strategy.entities import StrategyMinion

CAPTAINS = {"NEW1_027", "CORE_NEW1_027", "VAN_NEW1_027"}
SETUP = CAPTAINS | {"VAC_933", "TOY_518", "VAC_927", "VAC_938", "VAC_532",
                    "TOY_330t5", "VAC_929", "MIS_710", "CFM_325"}


def score_card(state, index):
    card = state.my_hand_cards[index]
    behavior = card.detail_card or MinionNoPoint
    return behavior.best_h_and_arg(state, index)


def summon(state, body, gap):
    body.zone = "PLAY"
    body.exhausted = int(not body.charge)
    if body.is_pirate:
        body.attack += active_count(state, "TOY_518")
        captains = active_count(state, *CAPTAINS)
        body.attack += captains
        body.max_health += captains
    body.attack += active_count(state, "TOY_330t5")
    if body.card_id in CAPTAINS or body.card_id == "TOY_330t5":
        for other in state.my_minions:
            if other.cardtype == "MINION" and (body.card_id == "TOY_330t5" or other.is_pirate):
                other.attack += 1
                if body.card_id in CAPTAINS:
                    other.max_health += 1
    state.my_minions.insert(gap, body)


def trigger_cliffside(state, index):
    sim = copy.deepcopy(state)
    location = sim.my_minions[index]
    location.exhausted = 1
    location.damage += 1
    gap = index + 1
    if location.health <= 0:
        sim.my_minions.remove(location)
        gap = index
    for _ in range(min(2, 7 - len(sim.my_minions))):
        token = StrategyMinion("VAC_926t", "PLAY", 0, 1, 0, True, False,
                               1, 1, charge=1, exhausted=0)
        summon(sim, token, gap)
    return sim


def play_setup(state, index, args):
    sim = copy.deepcopy(state)
    before = sum(m.cardtype == "MINION" for m in sim.my_minions)
    card = sim.my_hand_cards.pop(index)
    sim.my_used_mana += card.current_cost
    gap = args[0] if args else len(sim.my_minions)
    if card.cardtype == "LOCATION":
        card.zone = "PLAY"
        sim.my_minions.insert(gap, card)
        slots = 7 - len(sim.my_minions)
        if slots >= 2 or slots and sim.oppo_hero.health <= 12:
            sim = trigger_cliffside(sim, gap)
        elif slots:
            candidate = trigger_cliffside(sim, gap)
            if candidate.guaranteed_face_damage >= candidate.oppo_hero.health:
                sim = candidate
    else:
        summon(sim, card, gap)
    added = sum(m.cardtype == "MINION" for m in sim.my_minions) - before
    for remaining in sim.my_hand_cards:
        if remaining.card_id == "TOY_330t5":
            remaining.current_cost = max(0, remaining.current_cost - added)
    return sim


def setup_before_card(state, default_index, default_args):
    default = state.my_hand_cards[default_index]
    if default.card_id not in SETUP or default.card_id == "VAC_933":
        return None
    default_value = score_card(state, default_index)[0]
    if default_value >= 1000:
        return None

    def followup_value(sim):
        values = [0]
        for index, card in enumerate(sim.my_hand_cards):
            if card.card_id in SETUP and card.current_cost <= sim.my_remaining_mana \
                    and len(sim.my_minions) < 7:
                values.append(score_card(sim, index)[0])
        if sim.my_remaining_mana >= sim.my_hero_power.current_cost:
            values.append(sim.my_detail_hero_power.best_h_and_arg(sim, -1)[0])
        return max(values)

    baseline = default_value + followup_value(play_setup(state, default_index, default_args))
    best = None
    for index, card in enumerate(state.my_hand_cards):
        if index == default_index or card.card_id not in SETUP \
                or card.current_cost > state.my_remaining_mana or len(state.my_minions) >= 7:
            continue
        value, *args = score_card(state, index)
        if value <= 0:
            continue
        sim = play_setup(state, index, args)
        next_index = default_index - int(index < default_index)
        later = sim.my_hand_cards[next_index]
        if later.current_cost > sim.my_remaining_mana or len(sim.my_minions) >= 7:
            continue
        total = value + score_card(sim, next_index)[0]
        if total > baseline:
            baseline = total
            best = ("card", index, args)
    return best


def open_token_space(state):
    if len(state.my_minions) < 6:
        return None
    cliff = any(m.card_id == "VAC_929" and not m.exhausted
                and 7 - len(state.my_minions) + int(m.health == 1) < 2
                for m in state.my_minions)
    refill = len(state.my_hand_cards) <= 3 and any(
        card.card_id == "VAC_928" and card.current_cost <= state.my_remaining_mana
        for card in state.my_hand_cards
    )
    if not cliff and not refill:
        return None
    best = None
    best_gain = 0
    for index, original in enumerate(state.my_minions):
        if not original.can_attack_minion:
            continue
        body = attack_body(state, original)
        for target in state.touchable_oppo_minions:
            dies = not body.immune and not body.divine_shield and (
                target.attack >= body.health or target.poisonous and target.attack > 0
            )
            if not dies:
                continue
            gain = target.delta_h_after_damage(body.attack) - retaliation_loss(body, target)
            if original.can_beat_face and not state.oppo_has_taunt:
                gain -= state.oppo_hero.delta_h_after_damage(body.attack) * state.face_pressure_multiplier
            if gain > best_gain:
                best_gain = gain
                best = ("attack", index, target.zone_pos - 1)
    return best
