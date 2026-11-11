from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache, wraps
from pathlib import Path
import csv
import io
import json
import math
import os
import re
import secrets
import time
from urllib.parse import urlparse

from flask import Flask, jsonify, request, session, send_from_directory, g, Response
from sqlalchemy import event, func
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import HTTPException

from .models import (db, User, Season, Patch, Weapon, WeaponStat, Magazine,
                     Match, MatchWeapon, Favorite, Audit, SchemaVersion)
from .ttk import simulate
from .reference import ReferenceTTK, LABEL_SLUG

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def recoil_references():
    try:
        rows = json.loads((ROOT / 'backend' / 's30_parameters.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return {row.get('slug'): {
        'pitch': row.get('values', {}).get('recoil-pitch'),
        'yaw': row.get('values', {}).get('recoil-yaw'),
        'source_date': row.get('source_date'),
    } for row in rows if row.get('values', {}).get('recoil-pitch') or row.get('values', {}).get('recoil-yaw')}


@lru_cache(maxsize=1)
def recoil_patterns():
    try:
        return json.loads((ROOT / 'backend' / 'recoil_patterns.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}


@event.listens_for(Engine, 'connect')
def enforce_sqlite_constraints(connection, _):
    if connection.__class__.__module__.startswith('sqlite3'):
        cur = connection.cursor()
        cur.execute('PRAGMA foreign_keys=ON')
        cur.execute('PRAGMA busy_timeout=5000')
        cur.close()


def create_app(config=None):
    instance = Path((config or {}).get('INSTANCE_PATH', ROOT / 'instance'))
    instance.mkdir(parents=True, exist_ok=True)
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env')
    except ImportError:
        pass
    secret_file = instance / 'session-secret'
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32), encoding='ascii')
    app = Flask(__name__, static_folder=None, instance_path=str(instance))
    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL') or 'sqlite:///' + (instance / 'apex.db').as_posix(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=os.getenv('SECRET_KEY') or secret_file.read_text(encoding='ascii'),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_NAME='apex_lab',
        MAX_CONTENT_LENGTH=1024 * 1024,
        DEMO_MODE=os.getenv('DEMO_MODE', 'true').lower() == 'true',
    )
    if config:
        app.config.update(config)
    db.init_app(app)
    login_attempts = defaultdict(list)

    def fail(message, status=400):
        return jsonify(error=message), status

    def payload():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError('请提交 JSON 对象')
        return data

    def integer(data, key, low, high, default=None):
        value = data.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value or not low <= value <= high:
            raise ValueError(f'{key} 须为 {low}–{high} 的整数')
        return int(value)

    def number(data, key, low, high, default=None):
        value = data.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{key} 须为 {low}–{high} 的数字')
        return float(value)

    def text(data, key, limit=100, required=True):
        value = data.get(key, '')
        if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
            raise ValueError(f'{key} 不能为空且不能超过 {limit} 字')
        return value.strip()

    def require_login(admin=False):
        def deco(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                if not g.user:
                    return fail('请先登录', 401)
                if admin and g.user.role != 'admin':
                    return fail('此操作需要管理员权限', 403)
                return fn(*args, **kwargs)
            return wrapper
        return deco

    @app.before_request
    def security():
        g.user = db.session.get(User, session['user_id']) if session.get('user_id') else None
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)
        if request.path.startswith('/api/') and request.method in ('POST','PATCH','PUT','DELETE'):
            token = request.headers.get('X-CSRF-Token', '')
            if not secrets.compare_digest(token, session['csrf']):
                return fail('页面会话已变化，请刷新后重试', 403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(ValueError)
    def invalid(error):
        db.session.rollback()
        return fail(str(error))

    @app.errorhandler(IntegrityError)
    def conflict(error):
        db.session.rollback()
        return fail('记录重复或关联数据不存在，请检查后重试', 409)

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith('/api/'):
            return fail('请求不存在或格式不正确', error.code)
        return error

    @app.errorhandler(Exception)
    def unexpected(error):
        db.session.rollback()
        app.logger.exception('Request failed')
        return fail('服务暂时不可用，请稍后重试；详细信息已记录到本地日志', 500)

    def user_json(user):
        return {'id':user.id,'username':user.username,'role':user.role} if user else None

    @app.get('/api/session')
    def get_session():
        return jsonify(user=user_json(g.user), csrf=session['csrf'], demo_mode=app.config['DEMO_MODE'])

    def login(user):
        session.clear()
        session['user_id'] = user.id
        session['csrf'] = secrets.token_urlsafe(32)
        return jsonify(user=user_json(user), csrf=session['csrf'])

    @app.post('/api/auth/<action>')
    def auth(action):
        if action == 'logout':
            session.clear()
            session['csrf'] = secrets.token_urlsafe(32)
            return jsonify(user=None, csrf=session['csrf'])
        if action == 'demo':
            if not app.config['DEMO_MODE']:
                return fail('演示登录未启用', 403)
            user = User.query.filter_by(username='demo', role='user').first()
            if not user:
                return fail('演示账号不存在', 404)
            return login(user)
        if action not in ('login','register'):
            return fail('操作不存在', 404)
        addr = request.remote_addr
        current = time.monotonic()
        login_attempts[addr] = [t for t in login_attempts[addr] if current-t < 600]
        if len(login_attempts[addr]) >= 30:
            return fail('尝试次数过多，请十分钟后重试', 429)
        login_attempts[addr].append(current)
        data = payload()
        username = text(data, 'username', 40)
        password = text(data, 'password', 128)
        if not re.fullmatch(r'[a-zA-Z0-9_\-\u4e00-\u9fff]{3,40}', username):
            raise ValueError('用户名为 3–40 位中文、字母、数字、下划线或短横线')
        user = User.query.filter_by(username=username).first()
        if action == 'register':
            if user:
                return fail('用户名已被使用', 409)
            if len(password) < 8:
                raise ValueError('密码至少 8 位')
            user = User(username=username,password_hash=generate_password_hash(password),role='user')
            db.session.add(user); db.session.commit()
        elif not user or not check_password_hash(user.password_hash, password):
            return fail('用户名或密码错误', 401)
        return login(user)

    @app.post('/api/password')
    @require_login()
    def password():
        data=payload()
        old=text(data,'old_password',128); new=text(data,'new_password',128)
        if not check_password_hash(g.user.password_hash, old):
            return fail('原密码错误',403)
        if len(new)<8:
            raise ValueError('新密码至少 8 位')
        g.user.password_hash=generate_password_hash(new); db.session.commit()
        return jsonify(ok=True)

    @app.get('/api/meta')
    def meta():
        patches=Patch.query.join(Season).filter(Season.number.in_([28,29,30])).order_by(Season.number.desc(),Patch.released_at.desc()).all()
        return jsonify(patches=[{'id':p.id,'name':p.name,'season':p.season.number,
                                 'date':None if p.released_at.year==1970 else p.released_at.isoformat()} for p in patches],
                       weapons=[{'id':w.id,'weapon_id':w.id,'name':w.name,'slug':w.slug,'category':w.category,'ammo':w.ammo,'image':w.image,'image_source':w.image_source,'favorite':bool(g.user and Favorite.query.filter_by(user_id=g.user.id,weapon_id=w.id).first())} for w in Weapon.query.order_by(Weapon.id)],
                       categories=[x[0] for x in db.session.query(Weapon.category).distinct()],
                       database=db.engine.dialect.name,
                       model='shot-events-1.0', sample_notice='S30 枪械参数基准为 2026-09-16；S28、S29 参数仍待补充。技能武器及无传统弹匣武器不参与当前 TTK 计算。')

    @app.get('/api/reference-ttk')
    def reference_ttk():
        patch=db.session.get(Patch,request.args.get('patch_id',type=int) or 0)
        season=patch.season.number if patch else 30
        rows=ReferenceTTK.query.filter_by(season=season).order_by(ReferenceTTK.seconds,ReferenceTTK.id).all()
        return jsonify(season=season,items=[{'label':r.label,'seconds':r.seconds,'slug':LABEL_SLUG.get(r.label)} for r in rows],
            source='老葛你又在打电动',source_date='2026-08-05' if rows else None,
            image='/assets/s30-ttk-reference.png' if rows else None)

    def stat_json(s):
        return {'id':s.id,'weapon_id':s.weapon_id,'patch_id':s.patch_id,'name':s.weapon.name,
                'slug':s.weapon.slug,'category':s.weapon.category,'ammo':s.weapon.ammo,
                'image':s.weapon.image,'image_source':s.weapon.image_source,'patch_name':s.patch.name,
                'body':s.body,'head':s.head,'leg':s.leg,'rpm':s.rpm,'pellets':s.pellets,
                'reload_time':s.reload_time,'startup':s.startup,'burst_size':s.burst_size,
                'burst_delay':s.burst_delay,'magazines':{str(m.tier):m.capacity for m in s.magazines},
                'status':s.status,'source_url':s.source_url,'note':s.note,'revision':s.revision,
                'recoil_reference':recoil_references().get(s.weapon.slug),
                'recoil_pattern':recoil_patterns().get(s.weapon.slug)}

    @app.get('/api/weapons')
    def weapons():
        patch_id=request.args.get('patch_id',type=int)
        if patch_id is None:
            latest=Patch.query.join(Season).filter(Season.number.in_([28,29,30])).order_by(Season.number.desc(),Patch.released_at.desc()).first()
            patch_id=latest.id if latest else 0
        query=WeaponStat.query.join(Weapon).filter(WeaponStat.patch_id==patch_id)
        if request.args.get('category'):
            query=query.filter(Weapon.category==request.args['category'])
        q=request.args.get('q','').strip()[:80]
        if q:
            query=query.filter(Weapon.name.contains(q, autoescape=True) | Weapon.slug.contains(q, autoescape=True))
        rows=query.order_by(Weapon.id).all()
        favorites={x.weapon_id for x in Favorite.query.filter_by(user_id=g.user.id)} if g.user else set()
        return jsonify(items=[dict(stat_json(s),favorite=s.weapon_id in favorites) for s in rows])

    @app.get('/api/weapons/<int:weapon_id>/history')
    def history(weapon_id):
        rows=WeaponStat.query.join(Patch).filter(WeaponStat.weapon_id==weapon_id).order_by(Patch.released_at).all()
        return jsonify(items=[stat_json(s) for s in rows])

    @app.post('/api/ttk')
    def ttk():
        data=payload(); ids=data.get('stat_ids')
        if not isinstance(ids,list) or not 1 <= len(ids) <= 50 or any(type(i) is not int for i in ids):
            raise ValueError('请选择 1–50 条枪械版本记录')
        health=number(data,'health',1,1000,200)
        tier=integer(data,'tier',0,3,3)
        zone=data.get('zone','body'); reload=data.get('include_reload',True)
        if type(reload) is not bool:
            raise ValueError('include_reload 须为布尔值')
        rows=WeaponStat.query.filter(WeaponStat.id.in_(ids)).all()
        if len(rows)!=len(set(ids)):
            return fail('部分枪械版本已不存在，请刷新',404)
        results=[dict(simulate(s,health,zone,tier,reload),stat_id=s.id,weapon_id=s.weapon_id,
                      name=s.weapon.name,status=s.status) for s in rows]
        results.sort(key=lambda r: r['ttk'] if r['ttk'] is not None else float('inf'))
        return jsonify(items=results,conditions={'health':health,'zone':zone,'tier':tier,'include_reload':reload})

    @app.post('/api/favorites/<int:weapon_id>')
    @require_login()
    def favorite(weapon_id):
        if not db.session.get(Weapon,weapon_id):
            return fail('枪械不存在',404)
        old=Favorite.query.filter_by(user_id=g.user.id,weapon_id=weapon_id).first()
        if old: db.session.delete(old)
        else: db.session.add(Favorite(user_id=g.user.id,weapon_id=weapon_id))
        db.session.commit()
        return jsonify(favorite=not bool(old))

    def match_json(m):
        slots=sorted(m.weapons,key=lambda w:w.slot)
        return {'id':m.id,'played_at':m.played_at.isoformat(),'map_name':m.map_name,'legend':m.legend,
                'placement':m.placement,'kills':m.kills,'damage':m.damage,'rp':m.rp,'note':m.note,
                'weapon_ids':[w.weapon_id for w in slots],'weapon_names':[w.weapon.name for w in slots],
                'is_sample':m.is_sample}

    def match_query():
        query=Match.query.filter_by(user_id=g.user.id)
        for key, op in [('from', 'ge'),('to', 'le')]:
            if request.args.get(key):
                try: value=date.fromisoformat(request.args[key])
                except ValueError: raise ValueError('日期格式应为 YYYY-MM-DD')
                query=query.filter(Match.played_at>=value if op=='ge' else Match.played_at<=value)
        if request.args.get('map'):
            query=query.filter_by(map_name=request.args['map'])
        return query

    @app.get('/api/matches')
    @require_login()
    def matches():
        query=match_query()
        page=max(1,request.args.get('page',1,type=int))
        items=query.order_by(Match.played_at.desc(),Match.id.desc()).offset((page-1)*50).limit(50).all()
        return jsonify(items=[match_json(m) for m in items],total=query.count(),page=page)

    @app.route('/api/matches',methods=['POST'])
    @app.route('/api/matches/<int:match_id>',methods=['PUT','DELETE'])
    @require_login()
    def mutate_match(match_id=None):
        m=Match.query.filter_by(id=match_id,user_id=g.user.id).first() if match_id else Match(user_id=g.user.id)
        if not m:
            return fail('比赛记录不存在',404)
        if request.method=='DELETE':
            db.session.delete(m); db.session.commit(); return jsonify(ok=True)
        data=payload()
        try: m.played_at=date.fromisoformat(text(data,'played_at',10))
        except ValueError: raise ValueError('比赛日期格式不正确')
        if m.played_at>date.today():
            raise ValueError('比赛日期不能晚于今天')
        m.map_name=text(data,'map_name',50); m.legend=text(data,'legend',50)
        m.placement=integer(data,'placement',1,20); m.kills=integer(data,'kills',0,100)
        m.damage=integer(data,'damage',0,50000); m.rp=integer(data,'rp',-1000,5000)
        m.note=text(data,'note',1000,False)
        ids=data.get('weapon_ids',[])
        if not isinstance(ids,list) or not 1<=len(ids)<=2 or any(type(i) is not int or not db.session.get(Weapon,i) for i in ids):
            raise ValueError('请选择 1–2 把有效枪械')
        m.weapons.clear(); db.session.add(m); db.session.flush()
        m.weapons=[MatchWeapon(weapon_id=i,slot=n+1) for n,i in enumerate(ids)]
        db.session.commit(); return jsonify(item=match_json(m))

    @app.get('/api/matches/stats')
    @require_login()
    def match_stats():
        try:
            min_map_matches = int(request.args.get('min_map_matches', '1'))
            if not 1 <= min_map_matches <= 1_000_000:
                raise ValueError
        except ValueError:
            return fail('最低场次须为 1–1000000 的整数', 400)
        ids=match_query().with_entities(Match.id).subquery()
        base=db.session.query(Match).filter(Match.id.in_(db.select(ids.c.id)))
        count,rp,kills,damage=base.with_entities(func.count(Match.id),func.coalesce(func.sum(Match.rp),0),
                  func.coalesce(func.sum(Match.kills),0),func.coalesce(func.avg(Match.damage),0)).one()
        daily=base.with_entities(Match.played_at,func.sum(Match.rp)).group_by(Match.played_at).order_by(Match.played_at).all()
        map_count = func.count(Match.id)
        map_avg_rp = func.avg(Match.rp)
        maps = (base.with_entities(Match.map_name, map_count, map_avg_rp, func.avg(Match.damage))
                .group_by(Match.map_name)
                .having(map_count >= min_map_matches)
                .order_by(map_avg_rp.desc(), Match.map_name)
                .all())
        # Distinct match/weapon pairs prevent two same-weapon slots from doubling a match.
        pairs=db.session.query(MatchWeapon.match_id,MatchWeapon.weapon_id).distinct().subquery()
        weapons=db.session.query(Weapon.name,func.count(Match.id),func.avg(Match.rp)).select_from(Weapon).join(pairs,pairs.c.weapon_id==Weapon.id).join(Match,Match.id==pairs.c.match_id).filter(Match.id.in_(db.select(ids.c.id))).group_by(Weapon.id,Weapon.name).all()
        return jsonify(count=count,total_rp=int(rp),total_kills=int(kills),avg_damage=round(float(damage)),
                       daily=[{'date':d.isoformat(),'rp':int(r)} for d,r in daily],
                       maps=[{'name':n,'count':c,'rp':round(float(r),1),'damage':round(float(d))} for n,c,r,d in maps],
                       weapons=[{'name':n,'count':c,'rp':round(float(r),1)} for n,c,r in weapons])

    @app.get('/api/matches/export')
    @require_login()
    def export_matches():
        out=io.StringIO(); writer=csv.writer(out)
        writer.writerow(['日期','地图','传奇','名次','击杀','伤害','RP','备注','样例'])
        def safe(value):
            value=str(value)
            return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
        for m in match_query().order_by(Match.played_at):
            writer.writerow([m.played_at,safe(m.map_name),safe(m.legend),m.placement,m.kills,m.damage,m.rp,safe(m.note),m.is_sample])
        return Response('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=apex-matches.csv'})

    def validate_stat(data):
        values={k:number(data,k,1,10000) for k in ('body','head','leg','rpm')}
        values.update(reload_time=number(data,'reload_time',0.01,30), startup=number(data,'startup',0,10,0),
                      pellets=integer(data,'pellets',1,30,1),burst_size=integer(data,'burst_size',1,10,1),
                      burst_delay=number(data,'burst_delay',0,5,0))
        if values['burst_size']>1 and values['burst_delay']<=0:
            raise ValueError('连发武器必须提供正数连发间隔')
        values['source_url']=text(data,'source_url',500,False)
        if values['source_url'] and urlparse(values['source_url']).scheme not in ('https','http'):
            raise ValueError('来源地址须为 HTTP(S) 链接')
        values['status']=data.get('status','sample')
        if values['status'] not in ('sample','partial','verified'):
            raise ValueError('核验状态无效')
        if values['status']=='verified' and not values['source_url']:
            raise ValueError('已核实数据必须填写来源')
        values['note']=text(data,'note',2000,False)
        mags=data.get('magazines')
        if not isinstance(mags,dict) or set(mags)!={'0','1','2','3'}:
            raise ValueError('弹匣必须提供 0、1、2、3 四个等级')
        capacities=[integer(mags,str(i),1,200) for i in range(4)]
        return values,capacities

    @app.put('/api/admin/stats/<int:stat_id>')
    @require_login(admin=True)
    def edit_stat(stat_id):
        s=db.session.get(WeaponStat,stat_id)
        if not s:return fail('数据不存在',404)
        data=payload(); revision=integer(data,'revision',1,1000000)
        values,capacities=validate_stat(data)
        before=stat_json(s)
        changed=WeaponStat.query.filter_by(id=stat_id,revision=revision).update(dict(values,revision=revision+1),synchronize_session=False)
        if changed!=1:
            db.session.rollback();return fail('该数据已被修改，请刷新后重新编辑',409)
        for m in s.magazines:m.capacity=capacities[m.tier]
        db.session.add(Audit(user_id=g.user.id,action='更新枪械参数',detail=json.dumps({'id':stat_id,'before':before,'after':values},ensure_ascii=False)))
        db.session.commit();db.session.expire_all()
        return jsonify(item=stat_json(db.session.get(WeaponStat,stat_id)))

    @app.post('/api/admin/import')
    @require_login(admin=True)
    def import_stats():
        data=payload();items=data.get('items')
        if not isinstance(items,list) or not 1<=len(items)<=100:
            raise ValueError('每次导入 1–100 条记录')
        # Validate the whole batch before writing anything; commit once.
        prepared=[];seen=set()
        for item in items:
            if not isinstance(item,dict):raise ValueError('每条数据须为对象')
            patch_id=integer(item,'patch_id',1,1000000)
            weapon_id=integer(item,'weapon_id',1,1000000)
            if not db.session.get(Patch,patch_id) or not db.session.get(Weapon,weapon_id):
                raise ValueError('版本或枪械不存在，请先创建')
            if (weapon_id,patch_id) in seen or WeaponStat.query.filter_by(weapon_id=weapon_id,patch_id=patch_id).first():
                raise ValueError('导入包含重复枪械版本；已有数据请使用编辑功能')
            seen.add((weapon_id,patch_id));values,capacities=validate_stat(item)
            prepared.append((weapon_id,patch_id,values,capacities))
        for wid,pid,values,capacities in prepared:
            s=WeaponStat(weapon_id=wid,patch_id=pid,**values)
            s.magazines=[Magazine(tier=i,capacity=n) for i,n in enumerate(capacities)]
            db.session.add(s)
        db.session.add(Audit(user_id=g.user.id,action='批量导入',detail=f'导入 {len(prepared)} 条枪械版本参数'))
        db.session.commit();return jsonify(inserted=len(prepared))

    @app.post('/api/admin/patches')
    @require_login(admin=True)
    def create_patch():
        data=payload();num=integer(data,'season',1,1000)
        name=text(data,'name',80);season_name=text(data,'season_name',80)
        released=date.fromisoformat(text(data,'released_at',10))
        season=Season.query.filter_by(number=num).first()
        if not season:season=Season(number=num,name=season_name);db.session.add(season);db.session.flush()
        patch=Patch(season_id=season.id,name=name,released_at=released)
        db.session.add(patch);db.session.add(Audit(user_id=g.user.id,action='创建版本',detail=name))
        db.session.commit();return jsonify(id=patch.id)

    @app.post('/api/admin/weapons')
    @require_login(admin=True)
    def create_weapon():
        data=payload();slug=text(data,'slug',50)
        if not re.fullmatch(r'[a-z0-9-]+',slug):raise ValueError('代号只能包含小写字母、数字、短横线')
        w=Weapon(slug=slug,name=text(data,'name',80),category=text(data,'category',30),ammo=text(data,'ammo',30))
        db.session.add(w);db.session.add(Audit(user_id=g.user.id,action='创建枪械',detail=w.name))
        db.session.commit();return jsonify(id=w.id)

    @app.get('/api/admin/audit')
    @require_login(admin=True)
    def audit():
        rows=Audit.query.order_by(Audit.id.desc()).limit(30).all()
        return jsonify(items=[{'id':r.id,'action':r.action,'detail':r.detail,'at':r.created_at.isoformat()+'Z'} for r in rows])

    @app.get('/api/health')
    def health():
        db.session.execute(db.text('SELECT 1'))
        return jsonify(ok=True,app='apex-lab',database=db.engine.dialect.name)

    @app.get('/')
    def index():
        return send_from_directory(ROOT / 'frontend','index.html')

    @app.get('/<path:path>')
    def static_file(path):
        return send_from_directory(ROOT / 'frontend',path)

    @app.cli.command('init-db')
    def init_db():
        from .seed import seed
        db.create_all();seed(app.instance_path,app.config['DEMO_MODE'])
        print('Database initialized.')

    return app
