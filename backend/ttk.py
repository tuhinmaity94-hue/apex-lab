"""Deterministic shot-event model, version 1.0.

First shot occurs at startup. Burst delay is last-to-next-first, NOT an
additional pause. An empty reload replaces the normal inter-shot gap.
Shotguns assume every pellet hits the selected zone. No travel time, latency,
damage reduction, ramp-up, or target movement is modeled.
"""
import math


def simulate(stat, health=200, zone='body', tier=3, include_reload=True):
    if zone not in ('body', 'head', 'leg'):
        raise ValueError('命中部位无效')
    if not isinstance(health, (int, float)) or not math.isfinite(health) or not 1 <= health <= 1000:
        raise ValueError('总生命值须为 1–1000')
    mags = {m.tier: m.capacity for m in stat.magazines}
    if tier not in mags:
        raise ValueError('该版本没有所选弹匣数据')
    damage = getattr(stat, zone) * stat.pellets
    bullets = math.ceil(health / damage)
    capacity = mags[tier]
    result = {'bullets': bullets, 'shot_damage': round(damage, 3),
              'mag_damage': round(damage * capacity, 2), 'capacity': capacity,
              'ttk': None, 'reloads': 0, 'events': [], 'model': 'shot-events-1.0'}
    limit = bullets if include_reload else min(capacity, bullets)
    time = stat.startup
    for i in range(limit):
        if i:
            in_mag = i % capacity
            if in_mag == 0:
                time += stat.reload_time
                result['reloads'] += 1
            elif stat.burst_size > 1 and in_mag % stat.burst_size == 0:
                time += stat.burst_delay
            else:
                time += 60.0 / stat.rpm
        result['events'].append([round(time, 6), round((i + 1) * damage, 3)])
    if limit == bullets:
        result['ttk'] = round(time, 6)
    else:
        result['reason'] = '一弹匣无法击倒；开启计入换弹后比较'
    return result
