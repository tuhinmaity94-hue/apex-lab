from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint

db = SQLAlchemy()


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default='user')
    created_at = db.Column(db.DateTime, nullable=False, default=now)


class Season(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)


class Patch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'), nullable=False)
    name = db.Column(db.String(80), unique=True, nullable=False)
    released_at = db.Column(db.Date, nullable=False)
    season = db.relationship(Season)


class Weapon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(30), nullable=False, index=True)
    ammo = db.Column(db.String(30), nullable=False)
    image = db.Column(db.String(240), nullable=False, default='')
    image_source = db.Column(db.String(500), nullable=False, default='')


class WeaponStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    weapon_id = db.Column(db.Integer, db.ForeignKey('weapon.id'), nullable=False)
    patch_id = db.Column(db.Integer, db.ForeignKey('patch.id'), nullable=False, index=True)
    body = db.Column(db.Float, nullable=False)
    head = db.Column(db.Float, nullable=False)
    leg = db.Column(db.Float, nullable=False)
    rpm = db.Column(db.Float, nullable=False)
    pellets = db.Column(db.Integer, nullable=False, default=1)
    reload_time = db.Column(db.Float, nullable=False)
    startup = db.Column(db.Float, nullable=False, default=0)
    burst_size = db.Column(db.Integer, nullable=False, default=1)
    burst_delay = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='sample')
    source_url = db.Column(db.String(500), nullable=False, default='')
    note = db.Column(db.Text, nullable=False, default='')
    revision = db.Column(db.Integer, nullable=False, default=1)
    weapon = db.relationship(Weapon)
    patch = db.relationship(Patch)
    magazines = db.relationship('Magazine', cascade='all, delete-orphan', lazy='selectin')
    __table_args__ = (
        UniqueConstraint('weapon_id', 'patch_id', name='uq_weapon_patch'),
        CheckConstraint('body > 0 AND head > 0 AND leg > 0 AND rpm > 0', name='ck_positive_damage_rate'),
        CheckConstraint('reload_time > 0 AND pellets > 0 AND startup >= 0', name='ck_timing'),
    )


class Magazine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stat_id = db.Column(db.Integer, db.ForeignKey('weapon_stat.id', ondelete='CASCADE'), nullable=False)
    tier = db.Column(db.Integer, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    __table_args__ = (
        UniqueConstraint('stat_id', 'tier', name='uq_magazine_tier'),
        CheckConstraint('capacity > 0 AND tier >= 0 AND tier <= 3', name='ck_magazine'),
    )


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    played_at = db.Column(db.Date, nullable=False)
    map_name = db.Column(db.String(50), nullable=False)
    legend = db.Column(db.String(50), nullable=False)
    placement = db.Column(db.Integer, nullable=False)
    kills = db.Column(db.Integer, nullable=False)
    damage = db.Column(db.Integer, nullable=False)
    rp = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(1000), nullable=False, default='')
    is_sample = db.Column(db.Boolean, nullable=False, default=False)
    weapons = db.relationship('MatchWeapon', cascade='all, delete-orphan', lazy='selectin')
    __table_args__ = (
        db.Index('ix_match_user_date', 'user_id', 'played_at'),
        CheckConstraint('placement BETWEEN 1 AND 20 AND kills >= 0 AND damage >= 0', name='ck_match_values'),
    )


class MatchWeapon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id', ondelete='CASCADE'), nullable=False)
    weapon_id = db.Column(db.Integer, db.ForeignKey('weapon.id'), nullable=False)
    slot = db.Column(db.Integer, nullable=False)
    weapon = db.relationship(Weapon)
    __table_args__ = (UniqueConstraint('match_id', 'slot', name='uq_match_slot'),)


class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    weapon_id = db.Column(db.Integer, db.ForeignKey('weapon.id'), nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'weapon_id', name='uq_favorite'),)


class Audit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    detail = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)


class SchemaVersion(db.Model):
    version = db.Column(db.Integer, primary_key=True)
    applied_at = db.Column(db.DateTime, nullable=False, default=now)
