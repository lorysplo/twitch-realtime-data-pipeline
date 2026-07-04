#!/usr/bin/env python3
"""
offline_dashboard_lambda.py — offline warehouse dashboard (AWS Lambda + Function URL).
Same approach as the live dashboard (a Lambda web page + Chart.js), but the data source is
a "snapshot" of the Athena Gold star-schema tables.
The snapshot dashboard_snapshot.json is bundled into the deployment package, so the page
loads instantly with zero Athena query cost.
To refresh: rerun dbt -> build_dashboard_snapshot.py -> redeploy this function.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "dashboard_snapshot.json"), encoding="utf-8") as f:
    SNAP = f.read()


def handler(event, context):
    qs = event.get("queryStringParameters") or {}
    if qs.get("api"):
        return {"statusCode": 200,
                "headers": {"content-type": "application/json", "cache-control": "no-store"},
                "body": SNAP}
    return {"statusCode": 200,
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": HTML.replace("__SNAPSHOT__", SNAP)}


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Twitch Offline Warehouse Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root { --purple:#9146ff; --bg:#0e0e10; --panel:#17171c; --line:#26262e;
          --text:#efeff1; --muted:#848494; --faint:#5c5c6b; }
  body { min-height:100vh; color:var(--text); padding:clamp(16px,3vw,36px);
    font-family:"Inter",system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
    background:radial-gradient(1100px 520px at 80% -12%, rgba(145,70,255,.22), transparent 60%),
               radial-gradient(900px 480px at -10% 110%, rgba(56,130,246,.10), transparent 55%), var(--bg); }
  .wrap { max-width:1180px; margin:0 auto; }
  header { display:flex; flex-wrap:wrap; align-items:baseline; gap:14px; margin-bottom:6px; }
  h1 { font-size:clamp(20px,3.2vw,30px); font-weight:800; letter-spacing:.5px; }
  h1 .tw { color:var(--purple); }
  .badge { padding:5px 12px; border-radius:999px; background:rgba(145,70,255,.15);
    border:1px solid rgba(145,70,255,.4); color:#b794ff; font-size:12px; font-weight:700; }
  .sub { color:var(--muted); font-size:13px; margin-bottom:20px; }
  .sub b { color:#b794ff; font-weight:600; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:14px; margin-bottom:18px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px 18px;
    position:relative; overflow:hidden; }
  .card::before { content:""; position:absolute; left:0; top:12px; bottom:12px; width:3px;
    border-radius:3px; background:var(--accent,var(--purple)); }
  .card .label { color:var(--muted); font-size:12px; }
  .card .value { margin-top:6px; font-size:30px; font-weight:800; font-variant-numeric:tabular-nums;
    letter-spacing:-.5px; line-height:1.05; }
  .row { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }
  @media (max-width:820px){ .row { grid-template-columns:1fr; } }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:18px 20px; margin-bottom:16px; }
  .panel h2 { font-size:14px; color:var(--muted); font-weight:600; margin-bottom:14px; }
  .chart-wrap { position:relative; height:300px; }
  .full { grid-column:1/-1; }
  footer { margin-top:8px; color:var(--faint); font-size:12px; text-align:center; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <span class="badge">OFFLINE WAREHOUSE · BATCH</span>
    <h1><span class="tw">TWITCH</span> Offline Analytics</h1>
  </header>
  <div class="sub">Source: S3 data lake → Spark scoring → <b>Redshift</b> warehouse (dbt star schema · Gold) → snapshot · Dimensions: <b>dim_channel/user/date/game</b> · Facts: <b>fact_message/event/viewer</b></div>

  <div class="cards" id="kpis"></div>

  <div class="row">
    <div class="panel"><h2>By channel · Messages &amp; unique users (DAU)</h2><div class="chart-wrap"><canvas id="cChannel"></canvas></div></div>
    <div class="panel"><h2>By channel · Avg sentiment (-1 angry ~ +1 hyped)</h2><div class="chart-wrap"><canvas id="cSent"></canvas></div></div>
  </div>

  <div class="panel full"><h2>Daily message volume (stacked by channel)</h2><div class="chart-wrap"><canvas id="cDaily"></canvas></div></div>

  <div class="row">
    <div class="panel"><h2>Peak concurrent viewers (by channel)</h2><div class="chart-wrap"><canvas id="cViewers"></canvas></div></div>
    <div class="panel"><h2>Revenue events · subs / resubs / gifted (stacked)</h2><div class="chart-wrap"><canvas id="cRev"></canvas></div></div>
  </div>

  <div class="panel full"><h2>Raid attribution · 7 total (live dashboard alerts on the spot → offline attributes precisely)</h2><div class="chart-wrap" style="height:240px"><canvas id="cRaid"></canvas></div></div>

  <footer>Real historical Twitch chat (anonymized) · AWS offline batch layer: S3 + Spark + Glue + Redshift + dbt · complements the live dashboard</footer>
</div>

<script>
const S = __SNAPSHOT__;
const PAL = ['#9146ff','#38bdf8','#34d399','#fbbf24','#f472b6','#fb923c','#a78bfa','#22d3ee'];
const channels = S.by_channel.map(r=>r.channel);
const cidx = {}; channels.forEach((c,i)=>cidx[c]=i);
const colOf = c => PAL[cidx[c] % PAL.length];
const COMMON = { responsive:true, maintainAspectRatio:false,
  plugins:{ legend:{ labels:{ color:'#848494', boxWidth:12, boxHeight:12, font:{size:11} } } },
  scales:{ x:{ ticks:{color:'#5c5c6b',font:{size:11}}, grid:{color:'rgba(255,255,255,.05)'} },
           y:{ ticks:{color:'#5c5c6b'}, grid:{color:'rgba(255,255,255,.05)'} } } };
const fmt = n => n>=1000 ? (n/1000).toFixed(n>=10000?0:1)+'k' : n;

// KPI cards
const K = S.kpis;
const cards = [
  ['Total messages', K.msgs.toLocaleString(), '#9146ff'],
  ['Unique users', K.users.toLocaleString(), '#38bdf8'],
  ['Channels', K.channels, '#34d399'],
  ['Days covered', K.days+' d', '#fbbf24'],
  ['Raids', K.raids, '#f472b6'],
  ['Cheer bits', K.bits.toLocaleString(), '#fb923c'],
];
document.getElementById('kpis').innerHTML = cards.map(([l,v,c])=>
  `<div class="card" style="--accent:${c}"><div class="label">${l}</div><div class="value">${v}</div></div>`).join('');

// Messages + DAU per channel (dual axis)
new Chart(cChannel, { data:{ labels:channels, datasets:[
  { type:'bar', label:'Messages', data:S.by_channel.map(r=>r.msgs),
    backgroundColor:channels.map(colOf), borderRadius:5, yAxisID:'y' },
  { type:'line', label:'Unique users (DAU)', data:S.by_channel.map(r=>r.dau),
    borderColor:'#fff', borderWidth:2, pointRadius:3, pointBackgroundColor:'#fff', yAxisID:'y2' },
]}, options:{ ...COMMON, scales:{ x:COMMON.scales.x,
  y:{ ...COMMON.scales.y, ticks:{ color:'#5c5c6b', callback:fmt } },
  y2:{ position:'right', ticks:{ color:'#5c5c6b', callback:fmt }, grid:{drawOnChartArea:false} } } } });

// Avg sentiment per channel (diverging)
new Chart(cSent, { type:'bar', data:{ labels:channels, datasets:[
  { label:'Avg sentiment', data:S.by_channel.map(r=>r.avg_sent),
    backgroundColor:S.by_channel.map(r=> r.avg_sent>=0 ? '#34d399' : '#f87171'), borderRadius:5 } ]},
  options:{ ...COMMON, plugins:{legend:{display:false}},
    scales:{ x:COMMON.scales.x, y:{ ...COMMON.scales.y, suggestedMin:-0.1, suggestedMax:0.1 } } } });

// Daily trend (stacked by channel)
const dates = [...new Set(S.daily.map(r=>r.dt))].sort();
const dailyDs = channels.map(ch=>({ label:ch, stack:'m',
  data:dates.map(d=>{ const x=S.daily.find(r=>r.dt===d&&r.channel===ch); return x?x.msgs:0; }),
  backgroundColor:colOf(ch), borderRadius:3 }));
new Chart(cDaily, { type:'bar', data:{ labels:dates, datasets:dailyDs },
  options:{ ...COMMON, scales:{ x:{...COMMON.scales.x, stacked:true},
    y:{...COMMON.scales.y, stacked:true, ticks:{color:'#5c5c6b',callback:fmt}} } } });

// Peak viewers (horizontal)
new Chart(cViewers, { type:'bar', data:{ labels:S.viewers.map(r=>r.channel), datasets:[
  { label:'Peak viewers', data:S.viewers.map(r=>r.peak),
    backgroundColor:S.viewers.map(r=>colOf(r.channel)), borderRadius:5 } ]},
  options:{ ...COMMON, indexAxis:'y', plugins:{legend:{display:false},
    tooltip:{callbacks:{afterLabel:(c)=>S.viewers[c.dataIndex].game}}},
    scales:{ x:{...COMMON.scales.x, ticks:{color:'#5c5c6b',callback:fmt}}, y:COMMON.scales.y } } });

// Revenue events (stacked)
new Chart(cRev, { type:'bar', data:{ labels:S.revenue.map(r=>r.channel), datasets:[
  { label:'New subs', data:S.revenue.map(r=>r.subs), backgroundColor:'#9146ff', stack:'r', borderRadius:3 },
  { label:'Resubs', data:S.revenue.map(r=>r.resubs), backgroundColor:'#38bdf8', stack:'r', borderRadius:3 },
  { label:'Gifted subs', data:S.revenue.map(r=>r.gifts), backgroundColor:'#fbbf24', stack:'r', borderRadius:3 },
]}, options:{ ...COMMON, scales:{ x:{...COMMON.scales.x,stacked:true}, y:{...COMMON.scales.y,stacked:true} } } });

// Raid attribution (horizontal, by channel)
new Chart(cRaid, { type:'bar', data:{ labels:S.raids.map((r,i)=>`${r.channel} #${i+1}`), datasets:[
  { label:'Incoming viewers', data:S.raids.map(r=>r.viewers),
    backgroundColor:S.raids.map(r=>colOf(r.channel)), borderRadius:5 } ]},
  options:{ ...COMMON, indexAxis:'y', plugins:{legend:{display:false}}, scales:COMMON.scales } });
</script>
</body>
</html>"""
