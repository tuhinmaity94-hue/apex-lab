import json,re,requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
MAP=dict(zip('r301 flatline r99 volt alternator car wingman mastiff spitfire prowler devotion havoc eva8 mozambique nemesis p2020 rampage lstar re45 hemlok repeater g7 bocek triple-take peacekeeper kraber longbow charge-rifle sentinel'.split(),'r-301 flatline r-99 volt alternator car wingman mastiff spitfire prowler-auto devotion havoc eva-8 mozambique-akimbo nemesis-zero p2020-akimbo rampage l-star re-45-burst hemlok-auto 30-30-repeater g7-scout bocek-max triple-take peacekeeper kraber longbow-dmr charge-rifle sentinel'.split()))
def collect(item):
 slug,remote=item;url='https://apex-legends.ttkdb.com/en/weapons/'+remote
 r=requests.get(url,timeout=35);r.raise_for_status();s=r.content.decode('utf-8')
 props=[]
 for c in re.findall(r'self.__next_f.push\((.*?)\)</script>',s):
  x=json.loads(c)[1]
  try:
   o=json.loads(x.split(':',1)[1]);v=o[3]
   if isinstance(v,dict):props.append(v)
  except (ValueError,IndexError,TypeError,KeyError):pass
 rows=next(v['rows']['base']['base'] for v in props if 'weaponName' in v and 'rows' in v)
 mags=next((v['magazines']['base']['base'] for v in props if 'magazines' in v),[])
 data={'slug':slug,'source_url':url,'source_date':'2026-09-16','values':{x['key']:x['value'] for x in rows},'magazines':mags}
 print(slug,'OK',flush=True);return data
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=5) as pool:data=list(pool.map(collect,MAP.items()))
 (ROOT/'backend'/'s30_parameters.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

