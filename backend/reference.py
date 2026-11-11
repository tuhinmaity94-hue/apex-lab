"""Transcribed user-supplied S30 chart, not simulation parameters."""
from datetime import date
import json
import re
from pathlib import Path
from .models import db, Season, Patch, SchemaVersion, Weapon, WeaponStat, Magazine

ROWS = [
('塞拉转轮机枪',.73),('专注轻机枪（最高射速）',.80),('猎兽（全自动）',.83),
('哈沃克（忽略蓄力）',.83),('EVA-8（双发+紫栓）',.84),('双持莫桑比克（紫栓）',.86),
('复仇女神（预热4枪）',.87),('C.A.R 冲锋枪',.90),('双持P2020（锤击点）',.90),
('平行步枪',.90),('转换者（双发）',.90),('R-99',.91),('暴走轻机枪（充能）',.92),
('L-STAR（进空投）',.92),('猎兽（五连发）',.94),('R-301',.97),('喷火轻机枪',.99),
('RE-45（忽略蓄力）',.99),('电能冲锋枪',1.01),('双持P2020（普通）',1.02),
('专注轻机枪（有涡轮+冷启动）',1.07),('复仇女神（冷启动）',1.08),('转换者（普通）',1.08),
('小帮手',1.09),('赫姆洛克（精英）',1.18),('暴走轻机枪（普通）',1.20),
('专注轻机枪（无涡轮+冷启动）',1.33),('3030连发枪（进空投）',1.35),('G7侦查枪（单发）',1.44),
('敖犬（紫枪栓）',1.52),('波塞克（充能手雷+满弦）',1.52),('三重狙击枪（腰射/更快射速）',1.68),
('和平捍卫者（紫枪栓）',2.12),('克雷贝尔（空投）',2.15),('波塞克（满弦）',2.28),
('长弓（普通）',2.30),('充能步枪（连发模式）',2.31),('三重狙击枪（开镜）',2.33),
('万蒂奇大招',2.62),('哨兵狙击枪（充电）',2.72),('充能步枪（普通模式）',2.91),('哨兵狙击枪（普通）',3.21),
]

class ReferenceTTK(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season = db.Column(db.Integer, nullable=False, index=True)
    label = db.Column(db.String(120), nullable=False)
    seconds = db.Column(db.Float, nullable=False)
    __table_args__ = (db.UniqueConstraint('season', 'label'), db.CheckConstraint('seconds > 0'))

def seed_reference():
    if db.session.get(SchemaVersion, 2):
        return
    # Remove obsolete sample parameters, preserving weapons, accounts and journals.
    for patch in Patch.query.join(Season).filter(~Season.number.in_([28,29,30])).all():
        for stat in WeaponStat.query.filter_by(patch_id=patch.id).all():
            db.session.delete(stat)
        db.session.flush()
        db.session.delete(patch)
    db.session.flush()
    for season in Season.query.filter(~Season.number.in_([28,29,30])).all():
        db.session.delete(season)
    db.session.flush()
    for number in [28,29,30]:
        season=Season.query.filter_by(number=number).first()
        if not season:
            season=Season(number=number,name=f'S{number}')
            db.session.add(season); db.session.flush()
        name=f'S{number} · 赛季汇总'
        if not Patch.query.filter_by(name=name).first():
            # Internal sentinel only: summary is not an actual patch release.
            db.session.add(Patch(season_id=season.id,name=name,released_at=date(1970,1,1)))
    for label,seconds in ROWS:
        db.session.add(ReferenceTTK(season=30,label=label,seconds=seconds))
    db.session.add(SchemaVersion(version=2))

# One stable weapon identity per base weapon; configurations retain their own labels.
ROW_SLUGS = 'sheila devotion prowler havoc eva8 mozambique nemesis car p2020 flatline alternator r99 rampage lstar prowler r301 spitfire re45 volt p2020 devotion nemesis alternator wingman hemlok rampage devotion repeater g7 mastiff bocek triple-take peacekeeper kraber bocek longbow charge-rifle triple-take vantage sentinel charge-rifle sentinel'.split()
LABEL_SLUG = dict(zip((r[0] for r in ROWS), ROW_SLUGS))
EXTRA_WEAPONS = [
('sheila','塞拉转轮机枪','技能武器','Sheila'),('devotion','专注轻机枪','轻机枪','Devotion_LMG'),
('havoc','哈沃克步枪','突击步枪','HAVOC_Rifle'),('eva8','EVA-8','霰弹枪','EVA-8_Auto'),
('mozambique','莫桑比克','霰弹枪','Mozambique_Shotgun'),('nemesis','复仇女神','突击步枪','Nemesis_Burst_AR'),
('p2020','P2020','手枪','P2020'),('rampage','暴走轻机枪','轻机枪','Rampage_LMG'),
('lstar','L-STAR','轻机枪','L-STAR_EMG'),('re45','RE-45','手枪','RE-45_Auto'),
('hemlok','赫姆洛克','突击步枪','Hemlok_Burst_AR'),('repeater','30-30 连发枪','精确射手武器','30-30_Repeater'),
('g7','G7 侦查枪','精确射手武器','G7_Scout'),('bocek','波塞克','精确射手武器','Bocek_Compound_Bow'),
('triple-take','三重狙击枪','精确射手武器','Triple_Take'),('peacekeeper','和平捍卫者','霰弹枪','Peacekeeper'),
('kraber','克雷贝尔','狙击枪','Kraber_.50-Cal_Sniper'),('longbow','长弓','狙击枪','Longbow_DMR'),
('charge-rifle','充能步枪','狙击枪','Charge_Rifle'),('vantage','万蒂奇大招','技能武器',"Vantage/Sniper's_Mark"),
('sentinel','哨兵狙击枪','狙击枪','Sentinel'),
]

def seed_catalog():
    from pathlib import Path
    from .models import Weapon
    assets = Path(__file__).resolve().parents[1] / 'frontend' / 'assets'
    pages = {slug: page for slug, name, category, page in EXTRA_WEAPONS}
    for slug, name, category, page in EXTRA_WEAPONS:
        image = '/assets/' + slug + '.png' if (assets / (slug + '.png')).exists() else ''
        source = 'https://apexlegends.wiki.gg/wiki/' + page
        existing = Weapon.query.filter_by(slug=slug).first()
        if not existing:
            db.session.add(Weapon(slug=slug, name=name, category=category, ammo='待核实',
                                  image=image, image_source=source if image else ''))
        elif image and existing.image != image:
            existing.image = image
            existing.image_source = source
    for weapon in Weapon.query.all():
        local = assets / (weapon.slug + '.png')
        if local.exists() and not weapon.image:
            weapon.image = '/assets/' + weapon.slug + '.png'
            if not weapon.image_source and weapon.slug in pages:
                weapon.image_source = 'https://apexlegends.wiki.gg/wiki/' + pages[weapon.slug]
    db.session.flush()


def seed_s30_weapon_archive():
    """Import the dated S30 weapon baseline without overwriting admin edits."""
    source_file = Path(__file__).with_name('s30_parameters.json')
    data = json.loads(source_file.read_text(encoding='utf-8'))
    season = Season.query.filter_by(number=30).first()
    if not season:
        season = Season(number=30, name='S30')
        db.session.add(season)
        db.session.flush()
    patch_name = 'S30 · Marked（2026-09-16 数据基线）'
    patch = Patch.query.filter_by(name=patch_name).first()
    if not patch:
        patch = Patch(season_id=season.id, name=patch_name, released_at=date(2026, 9, 16))
        db.session.add(patch)
        db.session.flush()

    categories = {
        'Assault rifle': '突击步枪', 'Light machine gun': '轻机枪',
        'Marksman weapon': '精确射手武器', 'Pistol': '手枪',
        'Shotgun': '霰弹枪', 'Sniper rifle': '狙击枪',
        'Submachine gun': '冲锋枪',
    }
    ammo_names = {
        'Light ammo': '轻型', 'Heavy ammo': '重型', 'Energy ammo': '能量',
        'Shotgun shells': '霰弹', 'Sniper ammo': '狙击', 'Arrows': '箭矢',
        'Heavy ammo + Light ammo': '重型 / 轻型',
    }

    def numeric(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r'-?[\d,]+(?:\.\d+)?', str(value))
        return float(match.group(0).replace(',', '')) if match else None

    for row in data:
        values = row['values']
        weapon = Weapon.query.filter_by(slug=row['slug']).first()
        if not weapon:
            continue
        if WeaponStat.query.filter_by(weapon_id=weapon.id, patch_id=patch.id).first():
            continue
        weapon.category = categories.get(values.get('category'), weapon.category)
        ammo = values.get('ammo', '')
        weapon.ammo = '重型 / 轻型' if 'Heavy ammo' in ammo and 'Light ammo' in ammo else ammo_names.get(ammo, weapon.ammo)

        body = numeric(values.get('body-damage')) or numeric(values.get('selected-damage'))
        rpm = numeric(values.get('rpm'))
        if not body or not rpm:
            continue
        head_multiplier = numeric(values.get('head-multiplier')) or 1
        leg_multiplier = numeric(values.get('leg-multiplier')) or 1
        pellets = int(numeric(values.get('projectiles')) or 1)
        burst_size = int(numeric(values.get('burst')) or 1)
        burst_delay = numeric(values.get('burst-delay')) or 0
        startup = numeric(values.get('state-activation'))
        if startup is None:
            startup = numeric(values.get('charge')) or 0
        reload_time = numeric(values.get('empty-reload')) or numeric(values.get('reload'))
        if not reload_time:
            continue

        note = (
            '参数基准：2026-09-16 S30 Marked；来源页面列出的身体伤害、倍率、射速、弹匣及空仓换弹。'
            '头部与腿部伤害按来源倍率计算。TTK 是本项目逐发模型；蓄力、逐发装填、热量、弹丸命中和特殊射击模式未必能完整模拟。'
        )
        if int(numeric(values.get('magazine')) or 0) <= 0:
            note += ' 来源记录无传统弹匣；暂不提供弹匣等级或 TTK 计算。'
        elif not row.get('magazines'):
            note += ' 来源未列出扩容弹匣；各等级沿用基础弹匣容量。'
        stat = WeaponStat(
            weapon_id=weapon.id, patch_id=patch.id,
            body=body, head=round(body * head_multiplier, 3),
            leg=round(body * leg_multiplier, 3), rpm=rpm, pellets=pellets,
            reload_time=reload_time, startup=startup, burst_size=burst_size,
            burst_delay=burst_delay, status='partial',
            source_url=row.get('source_url', ''), note=note,
        )
        db.session.add(stat)
        db.session.flush()
        capacities = [int(numeric(mag.get('capacity')) or 0) for mag in row.get('magazines', [])[:4]]
        base_capacity = int(numeric(values.get('magazine')) or 0)
        if len(capacities) == 4 and all(capacities):
            pass
        elif base_capacity > 0:
            capacities = [base_capacity] * 4
        else:
            capacities = []
        stat.magazines = [Magazine(tier=tier, capacity=capacity) for tier, capacity in enumerate(capacities)]
