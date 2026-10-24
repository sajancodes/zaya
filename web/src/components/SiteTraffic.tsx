import React, {useEffect, useState} from 'react';

type Counts = Record<string, number>;
type Row = {label:string; count:number};
type Daily = {day:string; visits:number; pageviews:number; unique_browsers:number; download_clicks:number};
type Report = {days:number; started_at:number|null; updated_at:number; totals:Counts; period:Counts; daily:Daily[]; breakdowns:Record<string,Row[]>; definition:string};
const number = (value:number) => value.toLocaleString();

function exportReport(data:Report) {
  const rows: (string|number)[][] = [['Report','Dimension','Visits','Page views','Unique browser IDs','Download clicks','Count']];
  Object.entries(data.totals).forEach(([key,value])=>rows.push(['All time',key,'','','','',value]));
  Object.entries(data.period).forEach(([key,value])=>rows.push([`Last ${data.days} days`,key,'','','','',value]));
  data.daily.forEach(row=>rows.push(['Daily UTC',row.day,row.visits,row.pageviews,row.unique_browsers,row.download_clicks,'']));
  Object.entries(data.breakdowns).forEach(([key,values])=>values.forEach(row=>rows.push([key,row.label,'','','','',row.count])));
  rows.push(['Definition',data.definition,'','','','','']);
  rows.push(['Collected since',data.started_at ? new Date(data.started_at*1000).toISOString() : 'No events yet','','','','','']);
  const csv = rows.map(row=>row.map(value=>`"${String(value).replace(/^[=+@-]/,"'$&").replace(/"/g,'""')}"`).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));
  const link = document.createElement('a'); link.href=url; link.download=`zaya-site-report-${data.days}days.csv`; link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function Breakdown({title,rows,label}:{title:string; rows:Row[]; label:string}) {
  return <article className="card"><h3>{title}</h3>{rows.length ? <table className="data-table"><thead><tr><th>{label}</th><th>Count</th></tr></thead><tbody>{rows.slice(0,10).map(row=><tr key={row.label}><td>{row.label}</td><td>{number(row.count)}</td></tr>)}</tbody></table> : <p>No consented activity recorded yet.</p>}{rows.length>10 && <p>Top 10 shown. Export CSV for all rows.</p>}</article>;
}

export const SiteTraffic:React.FC = () => {
  const [days,setDays] = useState(30);
  const [revision,setRevision] = useState(0);
  const [data,setData] = useState<Report|null>(null);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState('');
  useEffect(()=>{
    const controller = new AbortController();
    setLoading(true);setError('');setData(null);
    fetch(`/api/admin/site-analytics?days=${days}`,{signal:controller.signal})
      .then(response=>{if(!response.ok) throw new Error(response.status===401 ? 'Your session expired. Sign out and sign in again.' : 'Website reports are unavailable. Retry in a moment.'); return response.json();})
      .then(setData).catch(err=>{if(err.name!=='AbortError')setError(err.message);})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[days,revision]);
  const max = Math.max(1,...(data?.daily || []).flatMap(row=>[row.pageviews,row.visits]));
  return <section className="site-traffic" aria-label="Website analytics" aria-busy={loading}>
    <div className="traffic-heading"><div><div className="hero-tag">Website traffic</div><h2>How people find and explore Zaya</h2><p>Consented website activity, separate from app installations and server download counters.</p></div><div className="traffic-actions"><label>Report period <select value={days} onChange={event=>setDays(Number(event.target.value))}><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option></select></label><button className="btn" disabled={loading} onClick={()=>setRevision(value=>value+1)}>Refresh</button><button className="btn" disabled={!data || loading} onClick={()=>data && exportReport(data)}>Export CSV</button></div></div>
    {loading && <p role="status">Loading website reports…</p>}
    {error && <p className="admin-error" role="alert">{error}</p>}
    {data && <>
      <div className="metric-grid">{[
        ['Total site visits',data.totals.visits,'All time since collection began'],
        ['Total page views',data.totals.pageviews,'All time; repeat views included'],
        [`Visits · ${data.days} days`,data.period.visits,'30-minute browser sessions'],
        [`Unique browsers · ${data.days} days`,data.period.unique_browsers,'Estimated anonymous browser IDs, not people'],
        [`Download clicks · ${data.days} days`,data.period.download_clicks,'Includes Windows, Linux and Android links'],
        [`Returning visits · ${data.days} days`,data.period.returning_visits,'Visits using a previously seen browser ID'],
      ].map(([title,value,note])=><article className="metric-card" key={String(title)}><div className="metric-label">{title}</div><div className="metric-value">{number(Number(value))}</div><div className="metric-sub">{note}</div></article>)}</div>
      <article className="card traffic-trend"><div className="traffic-heading"><h3>Daily traffic · UTC</h3><span className="metric-sub">Visits <span className="traffic-key visits"/> Page views <span className="traffic-key views"/></span></div>{data.daily.length ? <><svg viewBox="0 0 700 150" className="traffic-chart" aria-hidden="true">{data.daily.map((row,index)=>{const width=700/data.daily.length;return <g key={row.day}><title>{row.day}: {row.visits} visits, {row.pageviews} page views</title><rect x={index*width+1} y={145-row.pageviews/max*130} width={Math.max(1,width-2)} height={row.pageviews/max*130} fill="#38648e" rx="1"/><rect x={index*width+1} y={145-row.visits/max*130} width={Math.max(1,(width-2)/2)} height={row.visits/max*130} fill="#85def0" rx="1"/></g>;})}</svg><details><summary>View daily figures</summary><table className="data-table"><thead><tr><th>Date</th><th>Visits</th><th>Page views</th><th>Unique browsers</th><th>Download clicks</th></tr></thead><tbody>{data.daily.map(row=><tr key={row.day}><td>{row.day}</td><td>{number(row.visits)}</td><td>{number(row.pageviews)}</td><td>{number(row.unique_browsers)}</td><td>{number(row.download_clicks)}</td></tr>)}</tbody></table></details></> : <p>Reports will appear after visitors allow analytics. Earlier visits were not recorded.</p>}</article>
      <div className="traffic-breakdowns"><Breakdown title="Most visited pages" rows={data.breakdowns.pages} label="Page · views"/><Breakdown title="Traffic sources" rows={data.breakdowns.source} label="Source category · visits"/><Breakdown title="Devices" rows={data.breakdowns.device} label="Device category · visits"/><Breakdown title="Browsers" rows={data.breakdowns.browser} label="Browser family · visits"/><Breakdown title="Operating systems" rows={data.breakdowns.os} label="OS family · visits"/><Breakdown title="Download interest" rows={data.breakdowns.platforms} label="Platform · clicks"/></div>
      <p className="traffic-definition">{data.definition}<br/>Collection began: {data.started_at ? new Date(data.started_at*1000).toLocaleString() : 'Waiting for the first consented visit'}. Updated: {new Date(data.updated_at*1000).toLocaleString()}.</p>
    </>}
  </section>;
};
