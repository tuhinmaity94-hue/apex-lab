"""Run: python -m unittest discover -s tests -v.
All databases and credentials created by these tests stay in temporary folders.
"""
import copy
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError
from backend.app import create_app
from backend.models import db, User, Match, Weapon, WeaponStat, Audit, Patch, Season, Magazine
from backend.seed import seed
from backend.ttk import simulate


def sample_stat(**overrides):
    data=dict(body=20,head=30,leg=15,rpm=600,pellets=1,reload_time=2,startup=0,
              burst_size=1,burst_delay=0,magazines=[SimpleNamespace(tier=i,capacity=5) for i in range(4)])
    data.update(overrides)
    return SimpleNamespace(**data)


class TTKTests(unittest.TestCase):
    def test_first_shot_has_no_extra_interval(self):
        self.assertEqual(simulate(sample_stat(),20)['ttk'],0)
        self.assertAlmostEqual(simulate(sample_stat(),100)['ttk'],.4)

    def test_reload_replaces_shot_interval(self):
        result=simulate(sample_stat(),120)
        self.assertEqual(result['reloads'],1)
        self.assertAlmostEqual(result['ttk'],2.4)

    def test_insufficient_magazine_without_reload(self):
        result=simulate(sample_stat(),120,include_reload=False)
        self.assertIsNone(result['ttk'])
        self.assertEqual(len(result['events']),5)

    def test_burst_gap_and_startup(self):
        s=sample_stat(burst_size=3,burst_delay=.3,startup=.2)
        self.assertAlmostEqual(simulate(s,80)['ttk'],.7)

    def test_shotgun_pellets_and_head_zone(self):
        s=sample_stat(body=10,head=12,pellets=6)
        self.assertEqual(simulate(s,120)['bullets'],2)
        self.assertEqual(simulate(s,72,zone='head')['ttk'],0)

    def test_invalid_inputs(self):
        for hp in [0,-1,float('nan'),1001]:
            with self.assertRaises(ValueError):simulate(sample_stat(),hp)
        with self.assertRaises(ValueError):simulate(sample_stat(),zone='unknown')


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:',
                             'INSTANCE_PATH':self.temp.name,'SECRET_KEY':'test-only'})
        self.ctx=self.app.app_context();self.ctx.push();db.create_all();seed(self.temp.name)
        # Explicit synthetic fixtures for CRUD/calculator tests, never shipped as season data.
        fixture_patch = Patch(season=Season.query.filter_by(number=30).one(),
                              name='Synthetic test patch', released_at=date(2026, 1, 1))
        db.session.add(fixture_patch)
        db.session.flush()
        self.fixture_catalog = f'/api/weapons?patch_id={fixture_patch.id}'
        for weapon in Weapon.query.order_by(Weapon.id).limit(10):
            stat=WeaponStat(weapon_id=weapon.id,patch_id=fixture_patch.id,
                body=20,head=30,leg=15,rpm=600,pellets=1,reload_time=2,status='partial')
            stat.magazines=[Magazine(tier=i,capacity=30) for i in range(4)]
            db.session.add(stat)
        admin=User.query.filter_by(username='admin').one()
        admin.password_hash=generate_password_hash('test-admin-password')
        db.session.commit();self.client=self.app.test_client()
        self.token=self.client.get('/api/session').json['csrf']

    def tearDown(self):
        db.session.remove();db.drop_all();db.engine.dispose();self.ctx.pop();self.temp.cleanup()

    def call(self,path,method='POST',data=None):
        r=self.client.open('/api'+path,method=method,json={} if data is None else data,headers={'X-CSRF-Token':self.token})
        if r.is_json and r.json.get('csrf'):self.token=r.json['csrf']
        return r

    def login_demo(self):
        self.assertEqual(self.call('/auth/demo').status_code,200)

    def login_admin(self):
        self.assertEqual(self.call('/auth/login',data={'username':'admin','password':'test-admin-password'}).status_code,200)

    def match_data(self):
        return {'played_at':date.today().isoformat(),'map_name':'测试地图','legend':'恶灵','placement':3,
                'kills':4,'damage':1234,'rp':125,'note':'test only','weapon_ids':[1,2]}

    def test_catalog_and_ttk(self):
        rows=self.client.get(self.fixture_catalog).json['items']
        self.assertEqual(len(rows),10)
        self.assertTrue(all(r['status']=='partial' for r in rows))
        result=self.call('/ttk',data={'stat_ids':[r['id'] for r in rows],'health':200}).json
        self.assertEqual(len(result['items']),10)
        self.assertEqual(sorted(x['ttk'] for x in result['items']),[x['ttk'] for x in result['items']])

    def test_csrf_and_access_control(self):
        self.assertEqual(self.client.post('/api/auth/demo',json={}).status_code,403)
        self.assertEqual(self.client.get('/api/matches').status_code,401)
        self.login_demo()
        self.assertEqual(self.client.get('/api/admin/audit').status_code,403)
        self.assertEqual(self.call('/admin/import',data={'items':[]}).status_code,403)

    def test_match_crud_and_aggregate(self):
        self.login_demo()
        before=self.client.get('/api/matches/stats').json
        response=self.call('/matches',data=self.match_data())
        self.assertEqual(response.status_code,200,response.json)
        mid=response.json['item']['id']
        after=self.client.get('/api/matches/stats').json
        self.assertEqual(after['count'],before['count']+1)
        self.assertEqual(after['total_rp'],before['total_rp']+125)
        data=self.match_data();data.update(rp=-20,weapon_ids=[2])
        self.assertEqual(self.call('/matches/'+str(mid),'PUT',data).status_code,200)
        self.assertEqual(self.client.get('/api/matches/stats').json['total_rp'],before['total_rp']-20)
        self.assertEqual(self.call('/matches/'+str(mid),'DELETE').status_code,200)
        self.assertEqual(self.client.get('/api/matches/stats').json['count'],before['count'])

    def test_account_isolation(self):
        self.login_demo();mid=self.client.get('/api/matches').json['items'][0]['id']
        self.call('/auth/logout')
        r=self.call('/auth/register',data={'username':'new-user','password':'local-test-123'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get('/api/matches').json['total'],0)
        self.assertEqual(self.call('/matches/'+str(mid),'DELETE').status_code,404)
        self.assertEqual(self.call('/matches/'+str(mid),'PUT',self.match_data()).status_code,404)

    def test_map_minimum_applies_to_filtered_map_groups_only(self):
        self.call('/auth/register',data={'username':'map-analyst','password':'local-test-123'})
        for name, rp in [('Alpha', 30), ('Alpha', 50), ('Bravo', 100)]:
            data = dict(self.match_data(), map_name=name, rp=rp)
            self.assertEqual(self.call('/matches', data=data).status_code, 200)

        today = date.today().isoformat()
        default = self.client.get('/api/matches/stats').json
        self.assertEqual([row['name'] for row in default['maps']], ['Bravo', 'Alpha'])
        filtered = self.client.get(f'/api/matches/stats?from={today}&to={today}&min_map_matches=2').json
        self.assertEqual(filtered['maps'], [{'name': 'Alpha', 'count': 2, 'rp': 40.0, 'damage': 1234.0}])
        self.assertEqual({key: value for key, value in filtered.items() if key != 'maps'},
                         {key: value for key, value in default.items() if key != 'maps'})
        self.assertEqual(self.client.get('/api/matches/stats?min_map_matches=3').json['maps'], [])
        for invalid in ('0', '1.5', 'abc', '1000001'):
            self.assertEqual(self.client.get(f'/api/matches/stats?min_map_matches={invalid}').status_code, 400)

    def test_bad_match_does_not_modify_data(self):
        self.login_demo();before=Match.query.count();data=self.match_data();data['placement']=21
        self.assertEqual(self.call('/matches',data=data).status_code,400)
        data=self.match_data();data['weapon_ids']=[99999]
        self.assertEqual(self.call('/matches',data=data).status_code,400)
        self.assertEqual(Match.query.count(),before)

    def test_favorites_and_password_change(self):
        self.login_admin()
        self.assertTrue(self.call('/favorites/1').json['favorite'])
        self.assertFalse(self.call('/favorites/1').json['favorite'])
        self.assertEqual(self.call('/password',data={'old_password':'wrong','new_password':'new-test-password'}).status_code,403)
        self.assertEqual(self.call('/password',data={'old_password':'test-admin-password','new_password':'new-test-password'}).status_code,200)
        self.call('/auth/logout')
        self.assertEqual(self.call('/auth/login',data={'username':'admin','password':'new-test-password'}).status_code,200)

    def test_admin_revision_and_audit(self):
        self.login_admin();row=self.client.get(self.fixture_catalog).json['items'][0]
        old=copy.deepcopy(row);row['body']=17
        r=self.call('/admin/stats/'+str(row['id']),'PUT',row)
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(r.json['item']['body'],17)
        self.assertEqual(r.json['item']['revision'],old['revision']+1)
        self.assertEqual(self.call('/admin/stats/'+str(row['id']),'PUT',old).status_code,409)
        self.assertEqual(Audit.query.count(),1)

    def test_atomic_import_and_unique_constraint(self):
        self.login_admin();row=self.client.get(self.fixture_catalog).json['items'][0]
        before=WeaponStat.query.count()
        pid=self.call('/admin/patches',data={'season':25,'season_name':'测试','name':'test patch','released_at':'2025-05-06'}).json['id']
        row['patch_id']=pid;bad=copy.deepcopy(row);bad['weapon_id']=2;bad['rpm']=0
        self.assertEqual(self.call('/admin/import',data={'items':[row,bad]}).status_code,400)
        self.assertEqual(WeaponStat.query.count(),before)
        self.assertEqual(self.call('/admin/import',data={'items':[row]}).status_code,200)
        self.assertEqual(self.call('/admin/import',data={'items':[row]}).status_code,400)
        self.assertEqual(WeaponStat.query.count(),before+1)

    def test_csv_formula_escaping_and_filter(self):
        self.login_demo();data=self.match_data();data['note']='=HYPERLINK("example")'
        self.call('/matches',data=data)
        response=self.client.get('/api/matches/export?map=测试地图')
        self.assertEqual(response.status_code,200)
        self.assertIn("'=HYPERLINK",response.get_data(as_text=True))
        self.assertEqual(self.client.get('/api/matches?map=测试地图').json['total'],1)

    def test_foreign_keys_are_enabled(self):
        with self.assertRaises(IntegrityError):
            db.session.add(WeaponStat(weapon_id=9999,patch_id=1,body=1,head=1,leg=1,rpm=1,reload_time=1))
            db.session.commit()
        db.session.rollback()

    def test_path_traversal_and_private_files_not_served(self):
        self.assertEqual(self.client.get('/.env').status_code,404)
        self.assertEqual(self.client.get('/instance/initial-admin.txt').status_code,404)
        self.assertEqual(self.client.get('/../backend/app.py').status_code,404)


if __name__=='__main__':unittest.main()
