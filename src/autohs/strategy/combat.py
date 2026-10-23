"""Current-combat effects shared by card scores and attack decisions."""

import copy

from autohs.behaviors.demon_hunter import active_count, active_minion


def attack_body(state, minion):
    body = copy.copy(minion)
    if minion.is_pirate:
        bonus = active_count(state, "VAC_938") - int(
            minion.card_id == "VAC_938" and active_minion(minion)
        )
        body.attack += bonus
        body.max_health += bonus
    return body


def retaliation_loss(attacker, defender):
    if attacker.immune:
        return 0
    if defender.poisonous and defender.attack > 0 and not attacker.divine_shield:
        return attacker.heuristic_val
    return attacker.delta_h_after_damage(defender.attack)


def enemy_characters(state):
    return [state.oppo_hero] + [
        minion for minion in state.oppo_minions
        if getattr(minion, "cardtype", "MINION") == "MINION"
        and not getattr(minion, "dormant", False)
        and not getattr(minion, "untouchable", False)
        and minion.health > 0
    ]


def random_damage_value(state, damage):
    if damage <= 0:
        return 0
    values = []
    for target in enemy_characters(state):
        if getattr(target, "immune", False):
            values.append(0)
        elif target is state.oppo_hero:
            # A possible random lethal must not inherit the certain-lethal cliff.
            values.append(min(target.delta_h_after_damage(damage), damage * 2)
                          * getattr(state, "face_pressure_multiplier", 1))
        else:
            values.append(target.delta_h_after_damage(damage))
    return sum(values) / len(values)


def redirected_value(state, damage):
    if getattr(state.my_hero, "immune", False) or not active_count(state, "VAC_501"):
        return 0
    return random_damage_value(state, damage)


def cannon_triggers(state, attacker_index):
    return sum(
        state.my_minions[index].card_id == "VAC_532"
        and active_minion(state.my_minions[index])
        for index in (attacker_index - 1, attacker_index + 1)
        if 0 <= index < len(state.my_minions)
    )


def best_summon_gap(state, card):
    if not active_count(state, "VAC_532") and card.card_id != "VAC_532":
        return len(state.my_minions)
    best_gap = len(state.my_minions)
    best = -1
    for gap in range(len(state.my_minions) + 1):
        layout = state.my_minions[:gap] + [card] + state.my_minions[gap:]
        triggers = 0
        for pos, cannon in enumerate(layout):
            if cannon.card_id != "VAC_532" or not active_minion(cannon):
                continue
            for neighbor in (pos - 1, pos + 1):
                if 0 <= neighbor < len(layout):
                    body = layout[neighbor]
                    triggers += bool(body.charge or body.rush) if body is card else body.can_attack_minion
        if triggers > best or triggers == best and gap == len(state.my_minions):
            best = triggers
            best_gap = gap
    return best_gap


def remove_dead_minions(state):
    while any(body.health <= 0 for body in state.my_minions):
        body = next(body for body in state.my_minions if body.health <= 0)
        state.my_minions.remove(body)
        if not active_minion(body):
            continue
        captain = body.card_id in {"NEW1_027", "CORE_NEW1_027", "VAN_NEW1_027"}
        for other in state.my_minions:
            if other.cardtype != "MINION":
                continue
            if body.card_id == "TOY_330t5" or captain and other.is_pirate:
                other.attack = max(0, other.attack - 1)
                if captain:
                    other.max_health -= 1


def attack_order(state):
    engines = {"VAC_927", "VAC_938", "VAC_532", "NEW1_027", "CORE_NEW1_027", "VAN_NEW1_027", "TOY_330t5"}

    def priority(item):
        body = attack_body(state, item[1])
        engine = body.card_id in engines and active_minion(body)
        fragile = engine and body.health <= state.oppo_hero.attack and not body.immune and not body.divine_shield
        return fragile, body.card_id == "MIS_710", engine

    return sorted(enumerate(state.my_minions), key=priority)


def face_damage(state):
    if not state.oppo_hero.can_be_pointed_by_minion:
        return 0
    sim = copy.copy(state)
    sim.my_minions = [copy.copy(body) for body in state.my_minions]
    sim.my_hero = copy.copy(state.my_hero)
    ordered = [body for _, body in attack_order(sim) if body.can_beat_face]
    damage = 0
    for original in ordered:
        if original not in sim.my_minions or original.health <= 0:
            continue
        pos = sim.my_minions.index(original)
        body = attack_body(sim, original)
        sim.my_minions[pos] = body
        damage += body.attack
        cannons = cannon_triggers(sim, pos)
        if not body.immune:
            body.get_damaged(sim.oppo_hero.attack)
        remove_dead_minions(sim)
        if body.health > 0 and len(enemy_characters(sim)) == 1:
            damage += cannons
        if body.is_pirate:
            bonus = active_count(sim, "VAC_927")
            sim.my_hero.attack += bonus
            for puppet in sim.my_minions:
                if puppet.card_id == "MIS_710" and active_minion(puppet):
                    puppet.attack += bonus
    hero = sim.my_hero
    protected = hero.immune or active_count(sim, "VAC_501")
    if hero.can_attack and (protected or hero.health > sim.oppo_hero.attack):
        damage += hero.attack
        if not hero.immune and active_count(sim, "VAC_501") and len(enemy_characters(sim)) == 1:
            damage += sim.oppo_hero.attack
    return damage


def combined_trade_gain(state, target, order):
    sim = copy.copy(state)
    sim.my_hero = copy.copy(state.my_hero)
    sim.my_minions = [copy.copy(body) for body in state.my_minions]
    actors = dict(enumerate(sim.my_minions))
    defender = copy.copy(target)
    sim.oppo_minions = [defender if body is target else body for body in state.oppo_minions]
    losses = opportunity_damage = redirects = 0
    for index in order:
        if index == -1:
            protected = sim.my_hero.immune or active_count(sim, "VAC_501")
            if not protected and sim.my_hero.health <= defender.attack:
                return None
            damage = sim.my_hero.attack
            if not protected:
                losses += sim.my_hero.delta_h_after_damage(defender.attack)
                sim.my_hero.get_damaged(defender.attack)
            redirects += redirected_value(sim, defender.attack)
            losses += state.my_weapon.attack if state.my_weapon is not None else 0
            opportunity_damage += damage
            if state.my_weapon is not None and state.my_weapon.health <= 1:
                sim.my_hero.attack = max(0, sim.my_hero.attack - state.my_weapon.attack)
                for puppet in sim.my_minions:
                    if puppet.card_id == "MIS_710" and active_minion(puppet):
                        puppet.attack = max(0, puppet.attack - state.my_weapon.attack)
        else:
            original = actors[index]
            if original not in sim.my_minions:
                return None
            body = attack_body(sim, original)
            pos = sim.my_minions.index(original)
            sim.my_minions[pos] = body
            actors[index] = body
            damage = body.attack
            losses += retaliation_loss(body, defender)
            if original.can_beat_face:
                opportunity_damage += damage
            if not body.immune:
                if defender.poisonous and defender.attack and not body.divine_shield:
                    body.damage = body.max_health
                else:
                    body.get_damaged(defender.attack)
            if body.health <= 0:
                before = [(other, other.heuristic_val) for other in sim.my_minions if other is not body]
                remove_dead_minions(sim)
                losses += sum(max(0, value - other.heuristic_val) for other, value in before)
            if body.is_pirate:
                bonus = active_count(sim, "VAC_927")
                sim.my_hero.attack += bonus
                for puppet in sim.my_minions:
                    if puppet.card_id == "MIS_710" and active_minion(puppet):
                        puppet.attack += bonus
        poison = index != -1 and actors[index].poisonous and not defender.divine_shield
        defender.get_damaged(damage)
        if poison and damage > 0:
            defender.damage = defender.max_health
        if defender.health <= 0:
            opportunity = 0
            if not state.oppo_has_taunt and state.oppo_hero.can_be_pointed_by_minion:
                opportunity = state.oppo_hero.delta_h_after_damage(opportunity_damage)
                opportunity *= state.face_pressure_multiplier
            return target.heuristic_val - losses - opportunity + redirects
    return None
