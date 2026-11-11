/* Vue 3 browser build. Served locally: no runtime CDN, no build step required. */
const { createApp, ref, reactive, computed, watch, nextTick, onMounted } = Vue;

const ICONS = {
  grid: ['M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z'],
  chart: ['M3 3v18h18', 'M7 14l4-5 4 3 5-7'],
  journal: ['M4 3h16v18H4z', 'M8 7h8 M8 11h8 M8 15h5'],
  settings: ['M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8', 'M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z'],
  chevron: ['m8 10 4 4 4-4'],
  arrow: ['M4 12h16 m-6-6 6 6-6 6'],
  plus: ['M12 5v14 M5 12h14'],
  search: ['M10.5 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15', 'm16 16 5 5'],
  star: ['m12 3 2.8 5.8 6.4.9-4.6 4.5 1.1 6.4-5.7-3-5.7 3 1.1-6.4L2.8 9.7l6.4-.9z'],
  info: ['M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20', 'M12 11v6 M12 7h.01'],
  alert: ['m12 3 10 18H2z', 'M12 9v5 M12 17h.01'],
  close: ['m6 6 12 12 M6 18 18 6'],
  check: ['m5 12 4 4L19 6'],
  compare: ['M5 4v16 M19 4v16 M2 8h6 M16 16h6', 'm10 8 3-3 3 3 M13 5v7 M8 16l3 3 3-3 M11 19v-7'],
  sliders: ['M4 5h16 M4 12h16 M4 19h16', 'M8 3v4 M16 10v4 M10 17v4'],
  edit: ['M14 5 19 10 M4 15 15 4a3 3 0 0 1 5 5L9 20H4z'],
  trash: ['M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7'],
  refresh: ['M20 7v5h-5 M4 17v-5h5', 'M5 8a8 8 0 0 1 13-3l2 3 M4 16l2 3a8 8 0 0 0 13-3'],
  download: ['M12 3v12 m-5-5 5 5 5-5 M4 15v6h16v-6'],
  lock: ['M5 10h14v11H5z M8 10V6a4 4 0 0 1 8 0v4 M12 14v3'],
};

const app = createApp({
  setup() {
    const nav = [
      {id:'weapons',name:'枪械数据库',icon:'grid',no:'01'},
      {id:'ttk',name:'TTK数据库',icon:'chart',no:'02'},
      {id:'journal',name:'排位数据库',icon:'journal',no:'03'},
    ];
    const validPages = ['weapons','ttk','journal','admin'];
    const route = () => validPages.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'weapons';
    const page=ref(route()), meta=reactive({patches:[],weapons:[],categories:[],database:'sqlite'});
    const pageTitle=computed(()=>nav.find(item=>item.id===page.value)?.name??'数据管理');
    const pageEyebrow=computed(()=>({weapons:'THE ARSENAL / 武器档案',ttk:'TIME TO KILL / 理论伤害分析',journal:'YOUR PROGRESS / 每一场都有记录',admin:'DATA WORKSPACE / 版本与参数维护'}[page.value]));
    const pageDescription=computed(()=>({weapons:'从单发伤害到版本变化，找到适合你的那把枪。',ttk:'设定条件，比较击倒时间，读懂每一发子弹的价值。',journal:'记下比赛，观察变化，为下一次落地积累经验。',admin:'维护可信的数据，为每一次比较保留依据。'}[page.value]));
    const fatal=ref(''), loading=ref(false), busy=ref(false), user=ref(null), csrf=ref(''), demoMode=ref(false);
    const patchId=ref(null), allWeapons=ref([]), category=ref(''), search=ref(''), favoritesOnly=ref(false), sort=ref('default');
    const selected=ref([]), conditions=reactive({health:200,zone:'body',tier:3,include_reload:true}), labRows=ref([]);
    const comparisonWeapons=computed(()=>allWeapons.value.filter(w=>w.magazines?.[String(conditions.tier)]));
    const unsupportedWeapons=computed(()=>allWeapons.value.filter(w=>!w.magazines?.[String(conditions.tier)]));
    const patchName=computed(()=>meta.patches.find(p=>p.id===Number(patchId.value))?.name||'');
    const zoneText=computed(()=>({body:'身体',head:'头部',leg:'腿部'}[conditions.zone]));
    const catalogWeapons=computed(()=>meta.weapons.map(w=>allWeapons.value.find(s=>s.weapon_id===w.id)||{...w,id:'pending-'+w.id,status:'pending',magazines:{},note:'该赛季单发伤害、射速和弹匣参数待补充。'}));
    const filteredWeapons=computed(()=>{
      const q=search.value.trim().toLowerCase().replace(/[-\s.]/g,'');
      const rows=catalogWeapons.value.filter(w=>(!category.value||w.category===category.value)&&(!favoritesOnly.value||w.favorite)&&(!q||(w.name+w.slug).toLowerCase().replace(/[-\s.]/g,'').includes(q)));
      if(sort.value==='damage')rows.sort((a,b)=>b.body*b.pellets-a.body*a.pellets);
      if(sort.value==='rpm')rows.sort((a,b)=>b.rpm-a.rpm);
      return rows;
    });
    const toast=ref(''),toastError=ref(false);let toastTimer;
    function notify(message,error=false){toast.value=message;toastError.value=error;clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.value='',5000);}
    async function api(path,method='GET',body){
      let res;
      try {res=await fetch('/api'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json',...(method!=='GET'?{'X-CSRF-Token':csrf.value}:{})},...(body!==undefined?{body:JSON.stringify(body)}:{})});}
      catch(e){throw Error('无法连接本地服务，请确认启动窗口仍在运行。');}
      let data;try{data=await res.json();}catch(e){throw Error('服务器响应格式不正确，请重试。');}
      if(!res.ok)throw Error(data.error||'请求失败');
      if(data.csrf)csrf.value=data.csrf;
      return data;
    }
    async function refreshMeta(){const m=await api('/meta');Object.assign(meta,m);if(!meta.patches.some(p=>p.id===Number(patchId.value)))patchId.value=meta.patches[0]?.id||null;}
    async function initialize(){
      fatal.value='';
      try{const s=await api('/session');user.value=s.user;demoMode.value=s.demo_mode;await refreshMeta();await loadWeapons();await loadPage();}
      catch(e){fatal.value=e.message;}
    }
    let weaponRequest=0;
    async function loadWeapons(){
      const req=++weaponRequest;loading.value=true;
      const oldIds=selected.value.map(id=>allWeapons.value.find(w=>w.id===id)?.weapon_id);
      try{await refreshMeta();const data=await api('/weapons?patch_id='+Number(patchId.value||0));if(req!==weaponRequest)return;
        allWeapons.value=data.items;selected.value=data.items.filter(w=>oldIds.includes(w.weapon_id)&&w.magazines?.[String(conditions.tier)]).map(w=>w.id);
        if(page.value==='ttk'){if(!selected.value.length)selected.value=data.items.filter(w=>w.magazines?.[String(conditions.tier)]).slice(0,2).map(w=>w.id);await calculate();}
        else await calculate();
      }catch(e){notify(e.message,true);}finally{if(req===weaponRequest)loading.value=false;}
    }
    function toggleCompare(id){
      if(selected.value.includes(id))selected.value=selected.value.filter(x=>x!==id);
      else if(!allWeapons.value.find(w=>w.id===id)?.magazines?.[String(conditions.tier)])notify('该枪械缺少所选弹匣等级数据，暂不支持 TTK 对比。');
      else if(selected.value.length<4)selected.value.push(id);
      else notify('最多同时对比 4 把枪械，请先移除一把。');
    }
    async function favorite(w){
      if(!user.value){openAuth();return;}
      try{const d=await api('/favorites/'+w.weapon_id,'POST',{});w.favorite=d.favorite;const base=meta.weapons.find(x=>x.id===w.weapon_id);if(base)base.favorite=d.favorite;}
      catch(e){notify(e.message,true);}
    }
    function toggleFavorites(){if(!user.value){openAuth();return;}favoritesOnly.value=!favoritesOnly.value;}
    const statusText=s=>({pending:'参数待补充',partial:'部分核实',sample:'教学样例',verified:'已核实'}[s]||s);
    const nice=n=>Number.isInteger(Number(n))?Number(n).toString():Number(n).toFixed(2).replace(/0+$/,'').replace(/\.$/,'');
    const signed=n=>Number(n)>0?'+'+n:String(n);
    const ammoClass=a=>a.includes('重型')?'heavy':a.includes('能量')?'energy':a.includes('霰弹')?'shotgun':a.includes('狙击')?'sniper':'light';
    const formatTime=t=>new Date(t).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
    const today=new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,10);

    const rankingChart=ref(null),damageChart=ref(null),rpChart=ref(null);
    const charts=new Map();
    const palette=['#f56b4b','#69bfb0','#a9a1ef','#edc471'];
    function disposeCharts(){charts.forEach(c=>c.dispose());charts.clear();}
    function chart(el,option){
      if(!el)return;
      let c=charts.get(el);if(!c){c=echarts.init(el,null,{renderer:'svg'});charts.set(el,c);}
      c.setOption({backgroundColor:'transparent',textStyle:{fontFamily:'Inter, Segoe UI, Microsoft YaHei, sans-serif',color:'#abb1bc'},animationDuration:300,...option},true);
    }
    const axis={axisLine:{lineStyle:{color:'#363b44'}},axisTick:{show:false},axisLabel:{color:'#9ca4b1',fontSize:12},nameTextStyle:{color:'#9ca4b1',fontSize:12},splitLine:{lineStyle:{color:'#282d35'}}};
    function rankingColor(index,total){
      const fast=[205,28,181],slow=[82,31,169],t=total>1?index/(total-1):0;
      return 'rgb('+fast.map((value,i)=>Math.round(value+(slow[i]-value)*t)).join(',')+')';
    }
    function renderRanking(){
      const ranked=labRows.value,total=ranked.length;
      const rankedWeaponIds=new Set(ranked.map(r=>r.weapon_id));
      const excluded=catalogWeapons.value.filter(w=>!rankedWeaponIds.has(w.weapon_id)).map(w=>({
        weapon_id:w.weapon_id,
        name:w.name.replace('卡宾枪','').replace('轻机枪','').replace('冲锋枪','')+(w.status==='pending'?'（参数待补）':'（无弹匣）'),
        unavailable:true,
      }));
      const rows=[...ranked,...excluded];
      const r99=ranked.find(r=>allWeapons.value.find(w=>w.id===r.stat_id)?.slug==='r99'&&r.ttk!==null);
      const width=rankingChart.value?.clientWidth||720;
      chart(rankingChart.value,{
        grid:{left:Math.min(210,Math.max(112,Math.round(width*.23))),right:75,top:34,bottom:52},tooltip:{trigger:'axis',axisPointer:{type:'shadow'},renderMode:'richText'},
        xAxis:{...axis,type:'value',name:'击倒时间（秒）',nameLocation:'middle',nameGap:30,min:0},
        yAxis:{...axis,type:'category',inverse:true,data:rows.map(r=>r.name.replace('卡宾枪','').replace('轻机枪','').replace('冲锋枪','')),axisLabel:{...axis.axisLabel,interval:0,hideOverlap:false},splitLine:{show:false}},
        series:[{type:'bar',barMaxWidth:20,data:rows.map((r,i)=>({value:r.unavailable||r.ttk===null?0:+r.ttk.toFixed(3),unavailable:!!r.unavailable,noKnockdown:r.ttk===null&&!r.unavailable,itemStyle:{color:r.unavailable||r.ttk===null?'#575263':rankingColor(i,total),borderRadius:[0,4,4,0]}})),label:{show:true,position:'right',color:'#e5e5ed',fontSize:12,formatter:p=>p.data.unavailable?'未纳入':p.data.noKnockdown?'无法击倒':p.value.toFixed(3)+' s'},...(r99?{markLine:{symbol:'none',label:{formatter:'R-99 基准',color:'#f05a50',position:'insideEndTop'},lineStyle:{color:'#f05a50',width:2},data:[{xAxis:r99.ttk}]}}:{})}],
      });
    }
    async function renderDamage(){
      await nextTick();const rows=labRows.value.filter(r=>selected.value.includes(r.stat_id));
      if(!rows.length)return;
      const maxTime=Math.max(...rows.map(r=>r.events.at(-1)?.[0]||0),0.1);
      chart(damageChart.value,{
        color:palette,grid:{left:62,right:28,top:35,bottom:72},
        tooltip:{trigger:'axis',renderMode:'richText'},legend:{bottom:0,textStyle:{color:'#aeb5c1',fontSize:12},itemWidth:14,itemHeight:3},
        xAxis:{...axis,type:'value',name:'发射时间（秒）',nameLocation:'middle',nameGap:28,min:0,max:+(maxTime*1.1).toFixed(2)},
        yAxis:{...axis,type:'value',name:'累计伤害（HP）',min:0},
        series:rows.map((r,i)=>({name:r.name,type:'line',step:'end',symbol:'circle',symbolSize:3,lineStyle:{width:2},data:[[0,0],...r.events],
          ...(i===0?{markLine:{symbol:'none',label:{formatter:`击倒线 ${conditions.health} HP`,color:'#d9b779',position:'insideEndTop'},lineStyle:{color:'#806b48',type:'dashed'},data:[{yAxis:conditions.health}]}}:{})})),
      });
    }
    let calcRequest=0;
    async function calculate(){
      const comparable=comparisonWeapons.value;
      selected.value=selected.value.filter(id=>comparable.some(w=>w.id===id));
      if(!comparable.length){labRows.value=[];return;}
      const req=++calcRequest;
      try{const d=await api('/ttk','POST',{...conditions,stat_ids:comparable.map(w=>w.id)});if(req!==calcRequest)return;labRows.value=d.items;await nextTick();renderRanking();if(page.value==='ttk')await renderDamage();}
      catch(e){notify(e.message,true);}
    }
    watch(selected,()=>{if(page.value==='ttk')renderDamage();},{deep:true});

    const modal=ref(''),dialog=ref(null),deleteDialog=ref(null),formError=ref('');
    const authMode=ref('login'),authForm=reactive({username:'',password:''}),passwordForm=reactive({old_password:'',new_password:''});
    let pressedOnBackdrop=false;
    function closeModal(){pressedOnBackdrop=false;modal.value='';formError.value='';}
    function isDialogBackdrop(event){
      if(event.target!==dialog.value)return false;
      const rect=dialog.value.getBoundingClientRect();
      return event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom;
    }
    function rememberDialogPress(event){
      pressedOnBackdrop=event.isPrimary&&event.button===0&&isDialogBackdrop(event);
    }
    function dialogBackdrop(event){
      // A drag starting in an input can report its click on the dialog itself.
      const shouldClose=pressedOnBackdrop&&event.detail>0&&isDialogBackdrop(event);
      pressedOnBackdrop=false;
      if(shouldClose)closeModal();
    }
    watch(modal,async value=>{formError.value='';await nextTick();if(value){if(!dialog.value.open)dialog.value.showModal();}else if(dialog.value.open)dialog.value.close();});
    function openAuth(){authMode.value='login';authForm.username='';authForm.password='';modal.value='auth';}
    function accountDialog(){passwordForm.old_password='';passwordForm.new_password='';modal.value='account';}
    async function formAction(fn){
      if(busy.value)return;busy.value=true;formError.value='';
      try{await fn();}catch(e){formError.value=e.message;notify(e.message,true);}finally{busy.value=false;}
    }
    async function afterLogin(d){user.value=d.user;closeModal();await loadWeapons();await loadPage();notify('已登录：'+d.user.username);}
    async function submitAuth(){await formAction(async()=>afterLogin(await api('/auth/'+authMode.value,'POST',{...authForm})));}
    async function demoLogin(){await formAction(async()=>afterLogin(await api('/auth/demo','POST',{})));}
    async function logout(){await formAction(async()=>{await api('/auth/logout','POST',{});user.value=null;favoritesOnly.value=false;closeModal();await loadWeapons();notify('已退出登录');});}
    async function changePassword(){await formAction(async()=>{await api('/password','POST',{...passwordForm});closeModal();notify('密码已修改');});}
    const detail=ref(null),weaponHistory=ref([]),detailZone=ref('body');
    const detailZoneDamage=computed(()=>detail.value?.[detailZone.value]);
    const recoilPolyline=computed(()=>detail.value?.recoil_pattern?.points?.map(point=>point.join(',')).join(' ')||'');
    async function openWeapon(w){detail.value=w;detailZone.value='body';weaponHistory.value=[];modal.value='weapon';try{weaponHistory.value=(await api('/weapons/'+w.weapon_id+'/history')).items;}catch(e){notify(e.message,true);}}

    const maps=['世界边缘','奥林匹斯','风暴点','诸王峡谷','残月','电流区'];
    const legends=['恶灵','探路者','命脉','寻血猎犬','班加罗尔','动力小子','地平线','机器人亡灵','罗芭','瓦尔基里','纽卡斯尔','催化姬'];
    const journal=ref([]),journalStats=ref({}),journalTotal=ref(0),logPage=ref(1),logFilters=reactive({from:'',to:'',map:''});
    const minMapMatches=ref(1);
    const logQuery=computed(()=>{const p=new URLSearchParams();Object.entries(logFilters).forEach(([k,v])=>{if(v)p.set(k,v);});return p.size?'?'+p.toString():'';});
    const matchForm=ref({weapon_ids:[]}),confirmDelete=ref(null);
    let journalRequest=0;
    async function loadJournal(reset=true){
      if(!user.value)return;if(reset)logPage.value=1;const seq=++journalRequest;
      const separator=logQuery.value?'&':'?';
      const statsQuery=logQuery.value+separator+'min_map_matches='+minMapMatches.value;
      try{const [list,stats]=await Promise.all([api('/matches'+logQuery.value+separator+'page='+logPage.value),api('/matches/stats'+statsQuery)]);
        if(seq!==journalRequest)return;journal.value=list.items;journalTotal.value=list.total;journalStats.value=stats;await nextTick();renderRP();
      }catch(e){notify(e.message,true);}
    }
    function resetLogFilters(){Object.assign(logFilters,{from:'',to:'',map:''});minMapMatches.value=1;loadJournal();}
    function openMatch(m){
      matchForm.value=m?JSON.parse(JSON.stringify(m)):{played_at:today,map_name:maps[0],legend:'恶灵',placement:5,kills:0,damage:0,rp:0,note:'',weapon_ids:[meta.weapons[0]?.id,meta.weapons[1]?.id]};
      modal.value='match';
    }
    async function saveMatch(){await formAction(async()=>{const m={...matchForm.value,weapon_ids:matchForm.value.weapon_ids.filter(i=>i!=null&&i!=='').map(Number)};await api('/matches'+(m.id?'/'+m.id:''),m.id?'PUT':'POST',m);closeModal();await loadJournal();notify('比赛已保存，统计已更新');});}
    watch(confirmDelete,async value=>{await nextTick();if(value&&!deleteDialog.value.open)deleteDialog.value.showModal();else if(!value&&deleteDialog.value.open)deleteDialog.value.close();});
    async function deleteMatch(){await formAction(async()=>{await api('/matches/'+confirmDelete.value.id,'DELETE',{});confirmDelete.value=null;await loadJournal();notify('比赛记录已删除');});}
    function renderRP(){
      if(!journalStats.value.count)return;let sum=0;
      chart(rpChart.value,{color:[palette[0]],grid:{left:62,right:24,top:32,bottom:45},tooltip:{trigger:'axis',renderMode:'richText'},
        xAxis:{...axis,type:'category',name:'比赛日期',nameLocation:'middle',nameGap:30,data:journalStats.value.daily.map(x=>x.date.slice(5))},
        yAxis:{...axis,type:'value',name:'累计变化（RP）'},
        series:[{name:'累计 RP',type:'line',symbolSize:6,lineStyle:{width:2},data:journalStats.value.daily.map(x=>sum+=x.rp),areaStyle:{color:'rgba(245,107,75,.07)'}}]});
    }
    const audit=ref([]),statForm=ref(null),importText=ref(''),newPatch=ref({}),newWeapon=ref({});
    const statFields=[{key:'body',label:'身体伤害',min:1,max:10000},{key:'head',label:'头部伤害',min:1,max:10000},{key:'leg',label:'腿部伤害',min:1,max:10000},
      {key:'rpm',label:'射速（RPM）',min:1,max:10000},{key:'pellets',label:'每次弹丸数',min:1,max:30,step:1},{key:'reload_time',label:'空仓换弹（秒）',min:.01,max:30},
      {key:'startup',label:'初始预热（秒）',min:0,max:10},{key:'burst_size',label:'连发发数（自动填 1）',min:1,max:10,step:1},{key:'burst_delay',label:'连发间隔（末发到首发，秒）',min:0,max:5}];
    function blankStat(){return {weapon_id:meta.weapons[0]?.id,patch_id:Number(patchId.value),body:14,head:18,leg:11.2,rpm:810,pellets:1,reload_time:3.2,startup:0,burst_size:1,burst_delay:0,magazines:{'0':18,'1':20,'2':25,'3':28},status:'sample',source_url:'',note:'教学样例参数，请核实后再标记为真实数据。'};}
    function openNewStat(){statForm.value=blankStat();modal.value='stat';}
    function editStat(w){statForm.value=JSON.parse(JSON.stringify(w));modal.value='stat';}
    async function loadAudit(){if(user.value?.role!=='admin')return;try{audit.value=(await api('/admin/audit')).items;}catch(e){notify(e.message,true);}}
    async function saveStat(){await formAction(async()=>{const s=statForm.value;await api(s.id?'/admin/stats/'+s.id:'/admin/import',s.id?'PUT':'POST',s.id?s:{items:[s]});closeModal();await loadWeapons();await loadAudit();notify('版本参数已保存');});}
    function fillImportExample(){importText.value=JSON.stringify({items:[blankStat()]},null,2);}
    async function importStats(){await formAction(async()=>{let data;try{data=JSON.parse(importText.value);}catch(e){throw Error('JSON 格式不正确，请检查逗号、括号和引号。');}const r=await api('/admin/import','POST',data);closeModal();await loadWeapons();await loadAudit();notify('成功导入 '+r.inserted+' 条记录');});}
    async function savePatch(){await formAction(async()=>{const r=await api('/admin/patches','POST',newPatch.value);await refreshMeta();patchId.value=r.id;closeModal();await loadWeapons();await loadAudit();notify('版本已创建，现在可以录入参数');});}
    async function saveWeapon(){await formAction(async()=>{await api('/admin/weapons','POST',newWeapon.value);await refreshMeta();closeModal();await loadAudit();notify('枪械档案已创建，请为它添加版本参数');});}

    async function loadPage(){
      if(['weapons','ttk'].includes(page.value)){if(page.value==='ttk'&&!selected.value.length)selected.value=comparisonWeapons.value.slice(0,2).map(w=>w.id);await nextTick();renderRanking();if(page.value==='ttk')await renderDamage();}
      if(page.value==='journal')await loadJournal();
      if(page.value==='admin')await loadAudit();
    }
    watch(page,async()=>{disposeCharts();closeModal();await nextTick();await loadPage();window.scrollTo({top:0});});
    onMounted(()=>{
      window.addEventListener('hashchange',()=>page.value=route());
      window.addEventListener('resize',()=>charts.forEach(c=>c.resize()));
      initialize();
    });
    return {catalogWeapons,nav,page,meta,pageTitle,pageEyebrow,pageDescription,fatal,loading,busy,user,demoMode,patchId,allWeapons,category,search,favoritesOnly,sort,selected,
      conditions,labRows,comparisonWeapons,unsupportedWeapons,patchName,zoneText,filteredWeapons,toast,toastError,initialize,loadWeapons,toggleCompare,favorite,toggleFavorites,statusText,nice,signed,ammoClass,formatTime,today,
      rankingChart,damageChart,rpChart,calculate,modal,dialog,deleteDialog,formError,authMode,authForm,passwordForm,closeModal,rememberDialogPress,dialogBackdrop,openAuth,accountDialog,submitAuth,demoLogin,logout,changePassword,
      detail,detailZone,detailZoneDamage,recoilPolyline,weaponHistory,openWeapon,maps,legends,journal,journalStats,journalTotal,logPage,logFilters,logQuery,minMapMatches,matchForm,confirmDelete,loadJournal,resetLogFilters,openMatch,saveMatch,deleteMatch,
      audit,statForm,statFields,importText,newPatch,newWeapon,openNewStat,editStat,loadAudit,saveStat,fillImportExample,importStats,savePatch,saveWeapon,location:window.location};
  }
});
app.component('app-icon',{props:['name'],computed:{paths(){return ICONS[this.name]||ICONS.info;}},template:'<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path v-for="(d,i) in paths" :key="i" :d="d" /></svg>'});
app.mount('#app');
