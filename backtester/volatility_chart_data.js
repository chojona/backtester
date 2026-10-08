/* Pure chart adapters. Times stay UTC; formatting is applied only on the axes. */
(function(root,factory){
    if(typeof module==='object'&&module.exports)module.exports=factory();
    else root.VolatilityChartData=factory();
})(typeof globalThis!=='undefined'?globalThis:this,function(){
    'use strict';
    function timeframe(session,minutes){
        if(![1,5,15].includes(minutes))throw new Error('Unsupported chart interval');
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
    function applyTimeframe(session,minutes,series){
        const result=timeframe(session,minutes);
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
    return {timeframe,applyTimeframe,runs,timeKey,exactAt,defaultWindow};
});
