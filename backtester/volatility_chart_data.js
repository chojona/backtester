/* Pure chart adapters. Times stay UTC; formatting is applied only on the axes. */
(function(root,factory){
    if(typeof module==='object'&&module.exports)module.exports=factory();
    else root.VolatilityChartData=factory();
})(typeof globalThis!=='undefined'?globalThis:this,function(){
    'use strict';
    function timeframe(session,minutes){
        if(![1,5,15,60,240,1440].includes(minutes))throw new Error('Unsupported chart interval');
        const raw=session.bars[String(minutes)];
        if(!raw)throw new Error('Missing source interval');
        const ohlc=raw.map(b=>({time:b[0]/1000,open:b[1],high:b[2],low:b[3],close:b[4]}));
        const volume=raw.map(b=>({time:b[0]/1000,value:b[5],color:b[4]>=b[1]?'#46c7ac99':'#ec7e9299'}));
        for(let i=0;i<ohlc.length;i++){
            if(!Number.isFinite(volume[i].value)||volume[i].value<0)throw new Error('Invalid volume');
            if(i&&ohlc[i].time<=ohlc[i-1].time)throw new Error('Chart times must increase');
        }
        return {minutes,ohlc,volume,count:ohlc.length};
    }
    function applyTimeframe(session,minutes,series,sessions=[session]){
        const included=session===null?sessions:minutes>=60?sessions.filter(s=>s.contract===session.contract):[session];
        const source={bars:{[String(minutes)]:included
            .flatMap(s=>s.bars[String(minutes)]||[])
            .sort((a,b)=>a[0]-b[0])}};
        const result=timeframe(source,minutes);
        result.rolls=[];
        let previous=null;
        for(const item of [...included].sort((a,b)=>a.date.localeCompare(b.date))){
            const bars=item.bars[String(minutes)]||[];
            if(!bars.length)continue;
            if(previous!==null&&previous!==item.contract)
                result.rolls.push({time:bars[0][0]/1000,from:previous,to:item.contract});
            previous=item.contract;
        }
        series.candles.setData(result.ohlc);
        series.ohlc.setData(result.ohlc);
        series.volume.setData(result.volume);
        return result;
    }
    function runs(rows,field){
        const result=[];let run=[];
        for(const row of rows){
            const time=row[0]/1000,value=row[field];
            if(value===null||!Number.isFinite(value)||run.length&&time<=run[run.length-1].time){
                if(run.length)result.push(run);run=[];
                if(value===null||!Number.isFinite(value))continue;
            }
            run.push({time,value});
        }
        if(run.length)result.push(run);
        return result;
    }
    function timeKey(time){
        if(typeof time==='object'&&time!==null)return time.year+'-'+String(time.month).padStart(2,'0')+'-'+String(time.day).padStart(2,'0');
        return String(time);
    }
    function exactAt(points,time){
        const key=timeKey(time);
        return points.find(p=>timeKey(p.time)===key);
    }
    function defaultWindow(count,visible=160){
        return {from:Math.max(0,count-visible),to:Math.max(0,count-1)+5};
    }
    function fitAllData(chart,entries){
        const times=new Set();
        for(const entry of entries)for(const point of entry.points)times.add(timeKey(point.time));
        if(!times.size)return null;
        const padding=Math.max(1,times.size*.04);
        const range={from:-.5-padding,to:times.size-.5+padding};
        const scale=chart.timeScale();
        scale.applyOptions({minBarSpacing:.001,rightOffset:0,fixLeftEdge:false,fixRightEdge:false});
        scale.setVisibleLogicalRange(range);
        for(let pane=0;pane<chart.panes().length;pane++)
            chart.priceScale('left',pane).applyOptions({autoScale:true,scaleMargins:{top:.12,bottom:.12}});
        return range;
    }
    return {timeframe,applyTimeframe,runs,timeKey,exactAt,defaultWindow,fitAllData};
});
