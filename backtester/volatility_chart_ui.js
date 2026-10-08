/* Local TradingView Lightweight Charts integration. No network/data API calls. */
(()=>{
'use strict';
const data=JSON.parse(document.getElementById('chart-data').textContent);
const L=window.LightweightCharts,D=window.VolatilityChartData;
const $=id=>document.getElementById(id);
const color={blue:'#61a7ff',teal:'#46c7ac',rose:'#ec7e92',gold:'#f2bd70',purple:'#ad9af7'};
const shortTime=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',hour12:false});
const fullTime=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
const dayTime=new Intl.DateTimeFormat('en-US',{timeZone:'UTC',month:'short',day:'numeric'});
const formatPrice=new Intl.NumberFormat('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const formatVolume=new Intl.NumberFormat('en-US');
const compact=v=>Math.abs(v)>=1000?(v/1000).toFixed(1)+'k':v.toFixed(Math.abs(v)<.01?4:Math.abs(v)<1?3:1);
const dateValue=t=>typeof t==='number'?t*1000:typeof t==='string'?Date.parse(t+'T00:00:00Z'):Date.UTC(t.year,t.month-1,t.day);
let chosen=0,interval=5,style='candles',current=null,loading=false,syncingRange=false,syncingCrosshair=false;
const intraday=[],overview=[];
let activeIntradaySource='trading',activeOverviewSource=null,activeCrosshairSource=null;
function makeChart(id,daily=false){
 const chart=L.createChart($(id),{
  autoSize:true,
  layout:{background:{type:L.ColorType.Solid,color:'#101722'},textColor:'#93a5bc',fontFamily:'system-ui, sans-serif',fontSize:12,
    attributionLogo:true,panes:{separatorColor:'#253144',separatorHoverColor:'#385775',enableResize:true}},
  grid:{vertLines:{color:'#1a2535'},horzLines:{color:'#202c3d'}},
  leftPriceScale:{visible:true,borderColor:'#283549',minimumWidth:82,autoScale:true,scaleMargins:{top:.12,bottom:.08}},
  rightPriceScale:{visible:false},
  timeScale:{borderColor:'#283549',timeVisible:!daily,secondsVisible:false,barSpacing:7,minBarSpacing:.5,rightOffset:5,
    tickMarkFormatter:t=>daily?dayTime.format(dateValue(t)):shortTime.format(dateValue(t)),
    shiftVisibleRangeOnNewBar:false},
  crosshair:{mode:L.CrosshairMode.Magnet,vertLine:{color:'#7188a6',style:L.LineStyle.Dashed,labelBackgroundColor:'#2e4664'},
    horzLine:{color:'#7188a6',style:L.LineStyle.Dashed,labelBackgroundColor:'#2e4664'}},
  localization:{timeFormatter:t=>daily?dayTime.format(dateValue(t)):fullTime.format(dateValue(t))},
  handleScroll:{mouseWheel:true,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false},
  handleScale:{axisPressedMouseMove:{time:true,price:true},axisDoubleClickReset:{time:true,price:true},mouseWheel:true,pinch:true},
 });
 const item={chart,id,series:[],daily};
 const host=$(id);
 host.title='Drag to pan · Scroll to zoom · Drag the left axis to scale · Double-click an axis to reset';
 for(const event of ['pointerdown','wheel','keydown'])host.addEventListener(event,()=>{
   if(daily)activeOverviewSource=id;else activeIntradaySource=id;
 },{capture:true,passive:true});
 host.addEventListener('pointermove',()=>{activeCrosshairSource=id;},{capture:true,passive:true});
 host.addEventListener('pointerdown',()=>{activeCrosshairSource=id;},{capture:true,passive:true});
 (daily?overview:intraday).push(item);
 chart.timeScale().subscribeVisibleTimeRangeChange(range=>{
  if(loading||syncingRange||!range||(daily?activeOverviewSource:activeIntradaySource)!==id)return;
  syncingRange=true;
  try{for(const other of daily?overview:intraday)if(other!==item&&other.series.some(s=>s.points.length))other.chart.timeScale().setVisibleRange(range);}
  finally{syncingRange=false;}
 });
 chart.subscribeCrosshairMove(param=>{
  if(loading||syncingCrosshair||activeCrosshairSource!==id)return;
  syncingCrosshair=true;
  try{
   if(item===trading)updateHud(param);
   for(const target of daily?overview:intraday){
    if(target===item)continue;
    let match=null;
    if(param.time!==undefined)for(const entry of target.series){
      if(entry.hidden)continue;
      const point=D.exactAt(entry.points,param.time);
      if(point&&('value' in point||'close' in point)){match={entry,point};break;}
    }
    if(match)target.chart.setCrosshairPosition(match.point.value??match.point.close,param.time,match.entry.api);
    else target.chart.clearCrosshairPosition();
   }
  }finally{syncingCrosshair=false;}
 });
 return item;
}
function addLine(item,points,lineColor,extra={}){
 const api=item.chart.addSeries(L.LineSeries,{priceScaleId:'left',color:lineColor,lineWidth:2,priceLineVisible:false,lastValueVisible:false,
    crosshairMarkerVisible:true,pointMarkersVisible:points.length===1,
    priceFormat:{type:'custom',formatter:compact,minMove:.000001},...extra});
 api.setData(points);item.series.push({api,points});return api;
}
function clearLines(item){for(const entry of item.series)item.chart.removeSeries(entry.api);item.series=[];}
const trading=makeChart('trading');
const candles=trading.chart.addSeries(L.CandlestickSeries,{priceScaleId:'left',upColor:color.teal,downColor:color.rose,wickUpColor:color.teal,
 wickDownColor:color.rose,borderVisible:false,priceFormat:{type:'price',precision:2,minMove:.01}});
const ohlc=trading.chart.addSeries(L.BarSeries,{priceScaleId:'left',upColor:color.teal,downColor:color.rose,thinBars:false,openVisible:true,
 visible:false,priceFormat:{type:'price',precision:2,minMove:.01}});
const volume=trading.chart.addSeries(L.HistogramSeries,{priceScaleId:'left',priceFormat:{type:'volume'},priceLineVisible:false,lastValueVisible:false},1);
trading.chart.panes()[0].setStretchFactor(4);
trading.chart.panes()[1].setStretchFactor(1);
const returns=makeChart('returns'),cumulative=makeChart('cumulative'),profile=makeChart('profile');
function updateHud(param){
 if(!current)return;
 const target=param&&param.time!==undefined?D.exactAt(current.ohlc,param.time):current.ohlc[current.count-1];
 const el=$('ohlc');el.replaceChildren();
 if(!target)return;
 const vol=D.exactAt(current.volume,target.time);
 for(const [label,value] of [['O',target.open],['H',target.high],['L',target.low],['C',target.close],['V',vol?.value]]){
  if(value===undefined)continue;const span=document.createElement('span');span.append(label+' ');const b=document.createElement('b');
  b.textContent=label==='V'?formatVolume.format(value):formatPrice.format(value);span.append(b);el.append(span);
 }
}
function stylePrice(){
 candles.applyOptions({visible:style==='candles'});ohlc.applyOptions({visible:style==='bars'});
 for(const entry of trading.series)if(entry.api===candles||entry.api===ohlc)entry.hidden=(entry.api===candles?style!=='candles':style!=='bars');
}
function setPriceData(){
 current=D.applyTimeframe(data.sessions[chosen],interval,{candles,ohlc,volume});
 trading.series=[{api:candles,points:current.ohlc},{api:ohlc,points:current.ohlc},{api:volume,points:current.volume}];
 stylePrice();
 $('bar-count').textContent=interval+'m · '+current.count.toLocaleString()+' bars';
 $('price-empty').hidden=current.count>0;
 updateHud();
}
function fit(){
 if(!current.count)return;
 activeIntradaySource='trading';
 trading.chart.priceScale('left',0).applyOptions({autoScale:true});
 trading.chart.timeScale().fitContent();
 syncFromPrice();
}
function syncFromPrice(){
 const range=trading.chart.timeScale().getVisibleRange();if(!range)return;
 syncingRange=true;try{for(const item of intraday)if(item!==trading&&item.series.some(s=>s.points.length))item.chart.timeScale().setVisibleRange(range);}finally{syncingRange=false;}
}
function setDefaultView(){
 if(current.count)trading.chart.timeScale().setVisibleLogicalRange(D.defaultWindow(current.count));
 syncFromPrice();
}
function setTimeframe(minutes){
 if(![1,5,15].includes(minutes))throw new Error('Unsupported interval');
 activeIntradaySource='trading';
 loading=true;
 try{interval=minutes;setPriceData();document.querySelectorAll('[data-interval]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.interval)===interval)));setDefaultView();}
 finally{loading=false;}
}
function loadSession(index){
 activeIntradaySource='trading';
 loading=true;
 try{
  chosen=index;const s=data.sessions[chosen];
  $('price-title').textContent=data.instrument+' / '+s.contract+(s.complete?'':' · partial');
  $('references').textContent=s.references+' prior complete sessions';
  $('observed-legend').hidden=s.prefix_complete;
  clearLines(returns);clearLines(cumulative);clearLines(profile);
  for(const run of D.runs(s.series,1))addLine(returns,run,color.blue,{lineWidth:1});
  for(const [field,c] of [[2,color.blue],[3,color.gold],[4,color.teal],[5,color.purple],...(!s.prefix_complete?[[7,color.rose]]:[])])
    for(const run of D.runs(s.series,field))addLine(cumulative,run,c,field===7?{lineStyle:L.LineStyle.Dotted}:{});
  const profiles=D.runs(s.series,6);
  for(const run of profiles)addLine(profile,run,color.purple,{lineWidth:1});
  $('profile-empty').hidden=profiles.length>0;
  setPriceData();setDefaultView();
 }finally{loading=false;}
}
for(let i=0;i<data.sessions.length;i++){const option=document.createElement('option');option.value=i;option.textContent=data.sessions[i].date+' · '+data.sessions[i].contract;$('session').append(option);}
$('session').addEventListener('change',()=>loadSession(Number($('session').value)));
document.querySelectorAll('[data-interval]').forEach(button=>button.addEventListener('click',()=>setTimeframe(Number(button.dataset.interval))));
$('chart-style').addEventListener('change',()=>{style=$('chart-style').value;stylePrice();});
$('price-scale').addEventListener('change',()=>trading.chart.priceScale('left',0).applyOptions({mode:L.PriceScaleMode[$('price-scale').value],autoScale:true}));
$('reset').addEventListener('click',fit);
$('fullscreen').addEventListener('click',()=>{const panel=$('trading-panel');if(document.fullscreenElement)document.exitFullscreen();else panel.requestFullscreen?.();});
$('trading').addEventListener('keydown',event=>{
 const ts=trading.chart.timeScale(),r=ts.getVisibleLogicalRange();if(!r)return;
 const span=r.to-r.from,center=(r.from+r.to)/2;
 if(event.key==='+'||event.key==='='||event.key==='-'){const factor=event.key==='-'?1.25:.8;ts.setVisibleLogicalRange({from:center-span*factor/2,to:center+span*factor/2});event.preventDefault();}
 else if(event.key==='ArrowLeft'||event.key==='ArrowRight'){const shift=span*.1*(event.key==='ArrowLeft'?-1:1);ts.setVisibleLogicalRange({from:r.from+shift,to:r.to+shift});event.preventDefault();}
});
for(const spec of data.overview){
 const item=makeChart('overview-'+spec.id,true);
 for(const field of spec.series){
  const points=field.points.map(p=>p.value===null?{time:p.time}:{time:p.time,value:p.value});
  if(spec.histogram){const api=item.chart.addSeries(L.HistogramSeries,{priceScaleId:'left',color:field.color,priceFormat:{type:'custom',formatter:compact,minMove:.000001},priceLineVisible:false,lastValueVisible:false});api.setData(points);item.series.push({api,points});}
  else addLine(item,points,field.color,spec.id==='quarticity'?{priceFormat:{type:'custom',formatter:v=>v.toExponential(2),minMove:1e-12}}:{});
 }
 item.chart.timeScale().fitContent();
}
loadSession(0);
})();
