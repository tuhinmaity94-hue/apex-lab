"""Small historical comparison dataset; deliberately NOT advertised as live data.
S24 body/head damage values below were checked against EA's Takeover notes.
Other timing, magazine, leg and S23 head values are educational assumptions.
Every stat record is labeled partial/sample and exposes this limitation.
"""
from datetime import date, timedelta
from pathlib import Path
import secrets
from werkzeug.security import generate_password_hash
from .models import db, User, Season, Patch, Weapon, WeaponStat, Magazine, Match, MatchWeapon, SchemaVersion

SOURCE = 'https://www.ea.com/games/apex-legends/apex-legends/news/takeover-patch-notes'
# slug, name, category, ammo, old damage, S24 body/head, rpm, mags, reload, pellets, wiki
WEAPONS = [
    ('r301', 'R-301 卡宾枪', '突击步枪', '轻型', 13, 14, 18, 810, [18,20,25,28], 3.2, 1, 'R-301_Carbine'),
    ('flatline', 'VK-47 平行步枪', '突击步枪', '重型', 18, 19, 25, 600, [20,25,28,30], 3.1, 1, 'VK-47_Flatline'),
    ('r99', 'R-99 冲锋枪', '冲锋枪', '轻型', 14, 13, 16, 1080, [20,23,26,28], 2.45, 1, 'R-99_SMG'),
    ('volt', '电能冲锋枪', '冲锋枪', '能量', 15, 16, 19, 720, [19,21,23,26], 2.25, 1, 'Volt_SMG'),
    ('alternator', '转换者冲锋枪', '冲锋枪', '轻型', 16, 18, 22, 600, [19,22,25,27], 2.23, 1, 'Alternator_SMG'),
    ('car', 'C.A.R. 冲锋枪', '冲锋枪', '重型 / 轻型', 13, 14, 17, 930, [19,21,23,26], 2.13, 1, 'C.A.R._SMG'),
    ('wingman', '辅助手枪', '手枪', '狙击', 45, 48, 72, 156, [5,6,7,8], 2.1, 1, 'Wingman'),
    ('mastiff', '敖犬霰弹枪', '霰弹枪', '霰弹', 14, 16, 16, 66, [5,5,5,5], 3.4, 6, 'Mastiff_Shotgun'),
    ('spitfire', 'M600 喷火轻机枪', '轻机枪', '轻型', 19, 21, 26, 540, [35,40,45,50], 3.8, 1, 'M600_Spitfire'),
    ('prowler', '猎兽冲锋枪', '冲锋枪', '重型', 15, 16, 19, 1250, [20,25,30,35], 2.6, 1, 'Prowler_Burst_PDW'),
]


def seed(instance_dir, demo=True):
    if not db.session.get(SchemaVersion, 1):
        db.session.add(SchemaVersion(version=1))
    if not User.query.filter_by(role='admin').first():
        password = secrets.token_urlsafe(12)
        db.session.add(User(username='admin', role='admin', password_hash=generate_password_hash(password)))
        Path(instance_dir, 'initial-admin.txt').write_text(
            '本地管理员账号：admin\n初始密码：' + password + '\n请登录后修改密码。不要提交此文件。\n', encoding='utf-8')
    if not Weapon.query.first():
        for slug, name, category, ammo, *rest in WEAPONS:
            db.session.add(Weapon(slug=slug, name=name, category=category, ammo=ammo,
                image='/assets/'+slug+'.png', image_source='https://apexlegends.wiki.gg/wiki/'+rest[-1]))
        db.session.flush()
    from .reference import seed_reference, seed_catalog, seed_s30_weapon_archive
    seed_reference()
    seed_catalog()
    seed_s30_weapon_archive()
    if demo and not User.query.filter_by(username='demo').first():
        user = User(username='demo', role='user', password_hash=generate_password_hash(secrets.token_urlsafe(24)))
        db.session.add(user); db.session.flush()
        weapons = Weapon.query.order_by(Weapon.id).all()
        rows = [(1,5,1398,185), (8,2,760,32), (12,0,280,-45), (3,4,1220,120),
                (6,3,980,65), (16,1,420,-55), (2,6,1850,165), (5,2,880,48)]
        for i,(placement,kills,damage,rp) in enumerate(rows):
            m = Match(user_id=user.id, played_at=date.today()-timedelta(days=7-i),
                      map_name=['世界边缘','奥林匹斯','风暴点'][i%3], legend=['恶灵','探路者','命脉'][i%3],
                      placement=placement,kills=kills,damage=damage,rp=rp,note='教学样例，可编辑或删除',is_sample=True)
            m.weapons = [MatchWeapon(weapon_id=weapons[i%len(weapons)].id,slot=1),
                         MatchWeapon(weapon_id=weapons[(i+3)%len(weapons)].id,slot=2)]
            db.session.add(m)
    db.session.commit()
