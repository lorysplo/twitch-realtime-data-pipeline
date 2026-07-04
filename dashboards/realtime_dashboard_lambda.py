#!/usr/bin/env python3
"""
dashboard_lambda.py — cloud web dashboard (AWS Lambda + Function URL).
Hitting the function URL returns an auto-refreshing HTML dashboard page directly;
the page's JS requests `?api=1` every 2 seconds to fetch the last 5 minutes of metrics
(reading from DynamoDB, including the channel dimension).
Supports multiple channels: the tabs at the top switch between "all / a single channel,"
and the "all" mode stacks multiple channels for comparison.
"""
import json
import os
import time

import boto3
from boto3.dynamodb.conditions import Attr

AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
TABLE_NAME = os.environ.get("METRICS_TABLE", "twitch-realtime-metrics")

ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = ddb.Table(TABLE_NAME)


def handler(event, context):
    qs = event.get("queryStringParameters") or {}
    if qs.get("api"):
        return api_response()
    return {
        "statusCode": 200,
        "headers": {"content-type": "text/html; charset=utf-8"},
        "body": HTML,
    }


def api_response():
    now = int(time.time())
    # Paginate to read everything: a single scan returns only ~1MB (one page) before filtering, and
    # once the table grows the most recent data may not be on the first page. We must follow
    # LastEvaluatedKey through all pages, or we miss recent metrics (learned the hard way in testing).
    raw = []
    kwargs = {"FilterExpression": Attr("window").gte(now - 300)}
    while True:
        resp = table.scan(**kwargs)
        raw.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    out = []
    viewer_rows = {}   # channel -> (window, viewers, game), keeping the latest entry
    for i in raw:
        ch = i.get("channel", "unknown")
        if ch.startswith("#viewers#"):           # second topic: live viewer count
            nm = i.get("name") or ch[len("#viewers#"):]
            w = int(i["window"])
            if nm not in viewer_rows or w >= viewer_rows[nm][0]:
                viewer_rows[nm] = (w, int(i.get("viewers", 0)), i.get("game", "") or "")
            continue
        out.append({                              # first topic: chat metrics
            "channel": ch,
            "window": int(i["window"]),
            "count": int(i.get("count", 0)),
            "avg_sentiment": float(i.get("avg_sentiment", 0)),
            "top_emote": i.get("top_emote", "") or "",
        })
    out.sort(key=lambda x: x["window"])
    viewers = {nm: {"viewers": v[1], "game": v[2], "window": v[0]}
               for nm, v in viewer_rows.items()}
    return {
        "statusCode": 200,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
        },
        "body": json.dumps({"now": now, "items": out, "viewers": viewers}),
    }


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Twitch Live Chat Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --purple: #9146ff; --bg: #0e0e10; --panel: #17171c; --panel-line: #26262e;
    --text: #efeff1; --muted: #848494; --faint: #5c5c6b;
    --green: #34d399; --red: #f87171; --amber: #fbbf24;
  }
  body {
    min-height: 100vh; color: var(--text);
    font-family: "Inter", system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    background:
      radial-gradient(1100px 520px at 80% -12%, rgba(145,70,255,.22), transparent 60%),
      radial-gradient(900px 480px at -10% 110%, rgba(56,130,246,.10), transparent 55%),
      var(--bg);
    padding: clamp(16px, 3vw, 36px);
  }
  .wrap { max-width: 1180px; margin: 0 auto; }

  header { display: flex; flex-wrap: wrap; align-items: center; gap: 14px; margin-bottom: 8px; }
  .live {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 7px 14px; border-radius: 999px;
    background: rgba(239,68,68,.12); border: 1px solid rgba(239,68,68,.35);
    color: #fca5a5; font-size: 13px; font-weight: 700; letter-spacing: 1.5px;
  }
  .live i {
    width: 9px; height: 9px; border-radius: 50%; background: #ef4444;
    box-shadow: 0 0 0 0 rgba(239,68,68,.7); animation: pulse 1.6s infinite;
  }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(239,68,68,.7); }
    70% { box-shadow: 0 0 0 9px rgba(239,68,68,0); }
    100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
  }
  h1 { font-size: clamp(20px, 3.2vw, 30px); font-weight: 800; letter-spacing: .5px; }
  h1 .tw { color: var(--purple); }
  .updated { margin-left: auto; color: var(--faint); font-size: 13px; }
  .pipeline { color: var(--muted); font-size: 13px; margin-bottom: 16px; }
  .pipeline b { color: #b794ff; font-weight: 600; }
  .stale {
    display: none; margin: 0 0 16px; padding: 10px 16px; border-radius: 12px;
    background: rgba(251,191,36,.10); border: 1px solid rgba(251,191,36,.35);
    color: var(--amber); font-size: 14px;
  }

  .tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
  .tab {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 18px; border-radius: 999px; cursor: pointer; user-select: none;
    background: var(--panel); border: 1px solid var(--panel-line);
    color: var(--muted); font-size: 14px; font-weight: 600; transition: all .15s;
  }
  .tab:hover { border-color: #3a3a46; color: var(--text); }
  .tab.on { background: var(--purple); border-color: var(--purple); color: #fff; }
  .tab .dot { width: 8px; height: 8px; border-radius: 50%; }
  .tab .n { font-weight: 500; opacity: .75; font-size: 12px; font-variant-numeric: tabular-nums; }

  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr)); gap: 16px; margin-bottom: 18px; }
  .card {
    position: relative; overflow: hidden;
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,0)), var(--panel);
    border: 1px solid var(--panel-line); border-radius: 18px; padding: 20px 22px;
  }
  .card::before {
    content: ""; position: absolute; left: 0; top: 14px; bottom: 14px; width: 3px;
    border-radius: 3px; background: var(--accent, var(--purple));
  }
  .card .label { color: var(--muted); font-size: 13px; }
  .card .value {
    margin-top: 8px; font-size: clamp(34px, 4.5vw, 46px); font-weight: 800;
    font-variant-numeric: tabular-nums; line-height: 1.05; letter-spacing: -1px;
  }
  .card .value.small { font-size: clamp(22px, 3vw, 30px); letter-spacing: 0; word-break: break-all; }
  .card .hint { margin-top: 6px; color: var(--faint); font-size: 12px; }

  .gauge { margin-top: 14px; }
  .gauge .bar {
    position: relative; height: 10px; border-radius: 999px;
    background: linear-gradient(90deg, #ef4444, #6b7280 48%, #6b7280 52%, #22c55e);
    opacity: .9;
  }
  .gauge .pin {
    position: absolute; top: 50%; left: 50%;
    width: 18px; height: 18px; border-radius: 50%;
    background: #fff; border: 4px solid var(--purple);
    transform: translate(-50%, -50%); transition: left .6s cubic-bezier(.2,.8,.2,1);
    box-shadow: 0 2px 10px rgba(0,0,0,.5);
  }
  .gauge .ticks { display: flex; justify-content: space-between; color: var(--faint); font-size: 11px; margin-top: 7px; }

  .row { display: grid; grid-template-columns: 1.7fr 1fr; gap: 16px; }
  @media (max-width: 860px) { .row { grid-template-columns: 1fr; } }
  .panel {
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,0)), var(--panel);
    border: 1px solid var(--panel-line); border-radius: 18px; padding: 20px 22px;
  }
  .panel h2 { font-size: 14px; color: var(--muted); font-weight: 600; margin-bottom: 14px; letter-spacing: .3px; }
  .chart-wrap { position: relative; height: 300px; }

  .emote { display: grid; grid-template-columns: 30px 1fr; gap: 10px; align-items: center; margin: 11px 0; }
  .emote .rank {
    width: 26px; height: 26px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 800; background: #232330; color: var(--muted);
  }
  .emote.r1 .rank { background: linear-gradient(135deg,#fcd34d,#b45309); color: #1a1200; }
  .emote.r2 .rank { background: linear-gradient(135deg,#e5e7eb,#6b7280); color: #111; }
  .emote.r3 .rank { background: linear-gradient(135deg,#fdba74,#9a3412); color: #1f0d00; }
  .emote .name { font-size: 14px; font-weight: 600; display: flex; justify-content: space-between; gap: 8px; }
  .emote .name span:last-child { color: var(--muted); font-weight: 500; font-variant-numeric: tabular-nums; }
  .emote .track { grid-column: 2; height: 7px; border-radius: 999px; background: #232330; overflow: hidden; }
  .emote .fill {
    height: 100%; border-radius: 999px; width: 0;
    background: linear-gradient(90deg, var(--purple), #d8b4fe);
    transition: width .8s cubic-bezier(.2,.8,.2,1);
  }
  .vbar { margin: 16px 0; }
  .vbar-top { display: flex; justify-content: space-between; align-items: baseline; font-size: 14px; font-weight: 600; margin-bottom: 7px; }
  .vbar-top .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 8px; vertical-align: middle; }
  .vbar-top .num { font-size: 18px; font-variant-numeric: tabular-nums; }
  .vtrack { height: 12px; border-radius: 999px; background: #232330; overflow: hidden; }
  .vfill { height: 100%; border-radius: 999px; width: 0; transition: width .8s cubic-bezier(.2,.8,.2,1); }
  .vgame { color: var(--faint); font-size: 12px; margin-top: 6px; }
  .empty { color: var(--faint); font-size: 13px; }
  footer { margin-top: 20px; color: var(--faint); font-size: 12px; text-align: center; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <span class="live"><i></i>LIVE</span>
    <h1><span class="tw">TWITCH</span> Live Chat Dashboard</h1>
    <span class="updated">Last updated <span id="updated">--:--:--</span></span>
  </header>
  <div class="pipeline">Replay (local) ▸ <b>Kinesis</b> (chat + viewers · 2 streams) ▸ <b>Lambda</b> ▸ <b>DynamoDB</b> ▸ this page · auto-refresh every 2s</div>
  <div class="stale" id="stale">⚠ No new data for 30s — the source (replay) may have stopped</div>

  <div class="tabs" id="tabs"></div>

  <div class="cards">
    <div class="card" style="--accent:#9146ff">
      <div class="label">Chat · last 15s</div>
      <div class="value" id="m-count">0</div>
      <div class="hint">messages</div>
    </div>
    <div class="card" style="--accent:#38bdf8">
      <div class="label">Message rate</div>
      <div class="value" id="m-rate">0.0</div>
      <div class="hint">msg / sec</div>
    </div>
    <div class="card" style="--accent:#34d399">
      <div class="label">Audience sentiment</div>
      <div class="value" id="m-sent">+0.00</div>
      <div class="gauge">
        <div class="bar"><div class="pin" id="pin"></div></div>
        <div class="ticks"><span>😡 -1</span><span>😐 0</span><span>🎉 +1</span></div>
      </div>
    </div>
    <div class="card" style="--accent:#fbbf24">
      <div class="label">Top emote now</div>
      <div class="value small" id="m-emote">—</div>
      <div class="hint">Most spammed recently</div>
    </div>
    <div class="card" style="--accent:#a970ff">
      <div class="label">Current viewers</div>
      <div class="value" id="m-viewers">0</div>
      <div class="hint" id="m-viewers-hint">Live viewers</div>
    </div>
  </div>

  <div class="row">
    <div class="panel">
      <h2 id="rate-title">Last 5 min · Message rate (per 15s, by channel)</h2>
      <div class="chart-wrap"><canvas id="rateChart"></canvas></div>
    </div>
    <div class="panel">
      <h2 id="sent-title">Last 5 min · Sentiment trend (-1 angry ~ +1 hyped)</h2>
      <div class="chart-wrap"><canvas id="sentChart"></canvas></div>
    </div>
  </div>

  <div class="row">
    <div class="panel">
      <h2>Last 5 min · Top emotes</h2>
      <div id="emotes"><div class="empty">Waiting for data…</div></div>
    </div>
    <div class="panel">
      <h2>Current viewers by channel</h2>
      <div id="viewerbars"><div class="empty">Waiting for data…</div></div>
    </div>
  </div>

  <footer>Real Twitch chat replayed by original timestamps · AWS (Kinesis ×2 / Lambda / DynamoDB)</footer>
</div>

<script>
const PALETTE = ['#9146ff', '#38bdf8', '#34d399', '#fbbf24', '#f472b6', '#fb923c'];
let selected = 'all';
let last = null;
const chColor = {};
function colorOf(ch) {
  if (!chColor[ch]) chColor[ch] = PALETTE[Object.keys(chColor).length % PALETTE.length];
  return chColor[ch];
}

function lineOpts(extra) {
  return {
    responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { mode: 'index', intersect: false },
    plugins: { legend: { display: extra.legend !== false,
      labels: { color: '#848494', boxWidth: 10, boxHeight: 10, usePointStyle: true, font: { size: 12 } } } },
    scales: {
      x: { ticks: { color: '#5c5c6b', maxTicksLimit: 7, font: { size: 11 } }, grid: { display: false } },
      y: Object.assign({ ticks: { color: '#5c5c6b' }, grid: { color: 'rgba(255,255,255,.06)' } }, extra.y || {})
    }
  };
}
const rateChart = new Chart(document.getElementById('rateChart'), {
  type: 'line', data: { labels: [], datasets: [] }, options: lineOpts({ y: { beginAtZero: true } })
});
const sentChart = new Chart(document.getElementById('sentChart'), {
  type: 'line', data: { labels: [], datasets: [] },
  options: lineOpts({ legend: false, y: { min: -0.5, max: 0.5 } })
});

const tweens = {};
function tween(id, target, decimals, signed) {
  const el = document.getElementById(id);
  const from = tweens[id] ?? 0, t0 = performance.now();
  tweens[id] = target;
  function step(t) {
    const k = Math.min((t - t0) / 500, 1), v = from + (target - from) * (1 - Math.pow(1 - k, 3));
    el.textContent = (signed && v >= 0 ? '+' : '') + v.toFixed(decimals);
    if (k < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
const fmt = ts => new Date(ts * 1000).toLocaleTimeString('en-GB', { hour12: false });

function render() {
  if (!last) return;
  const { now, items } = last;
  const channels = [...new Set(items.map(i => i.channel))].sort();
  channels.forEach(colorOf);
  if (selected !== 'all' && !channels.includes(selected)) selected = 'all';

  const recentAll = items.filter(i => i.window >= now - 15);
  const cnt = ch => recentAll.filter(i => i.channel === ch).reduce((s, i) => s + i.count, 0);
  document.getElementById('tabs').innerHTML =
    `<span class="tab ${selected === 'all' ? 'on' : ''}" data-ch="all">All channels <span class="n">${recentAll.reduce((s, i) => s + i.count, 0)}/15s</span></span>` +
    channels.map(ch =>
      `<span class="tab ${selected === ch ? 'on' : ''}" data-ch="${ch}">` +
      `<span class="dot" style="background:${colorOf(ch)}"></span>${ch} <span class="n">${cnt(ch)}/15s</span></span>`
    ).join('');
  document.querySelectorAll('.tab').forEach(el =>
    el.onclick = () => { selected = el.dataset.ch; render(); });

  const view = selected === 'all' ? items : items.filter(i => i.channel === selected);
  const recent = view.filter(i => i.window >= now - 15);
  const total = recent.reduce((s, i) => s + i.count, 0);
  const sent = total ? recent.reduce((s, i) => s + i.avg_sentiment * i.count, 0) / total : 0;
  tween('m-count', total, 0);
  tween('m-rate', total / 15, 1);
  tween('m-sent', sent, 2, true);
  const sentEl = document.getElementById('m-sent');
  sentEl.style.color = sent > 0.05 ? 'var(--green)' : sent < -0.05 ? 'var(--red)' : 'var(--text)';
  document.getElementById('pin').style.left = (50 + Math.max(-1, Math.min(1, sent)) * 50) + '%';

  // Viewers (2nd topic): all = sum of channels' latest; single = that channel
  const vw = last.viewers || {};
  const viewerCount = selected === 'all'
    ? Object.values(vw).reduce((s, o) => s + o.viewers, 0)
    : (vw[selected] ? vw[selected].viewers : 0);
  tween('m-viewers', viewerCount, 0);
  document.getElementById('m-viewers-hint').textContent =
    (selected !== 'all' && vw[selected]) ? ('Playing ' + vw[selected].game) : 'All channels total';

  const emoteCount = {};
  for (const i of view) if (i.top_emote) emoteCount[i.top_emote] = (emoteCount[i.top_emote] || 0) + i.count;
  const ranked = Object.entries(emoteCount).sort((a, b) => b[1] - a[1]).slice(0, 7);
  const recentEmote = recent.map(i => i.top_emote).filter(Boolean).pop();
  document.getElementById('m-emote').textContent = recentEmote || (ranked[0] ? ranked[0][0] : '—');
  const max = ranked.length ? ranked[0][1] : 1;
  document.getElementById('emotes').innerHTML = ranked.map(([nm, n], i) =>
    `<div class="emote r${i + 1}"><div class="rank">${i + 1}</div>` +
    `<div class="name"><span>${nm}</span><span>${n}</span></div>` +
    `<div class="track"><div class="fill" data-w="${Math.round(n / max * 100)}"></div></div></div>`
  ).join('') || '<div class="empty">No emote data yet</div>';
  requestAnimationFrame(() =>
    document.querySelectorAll('.fill').forEach(el => el.style.width = el.dataset.w + '%'));

  const bucketOf = w => Math.floor(w / 15) * 15;
  const keys = [...new Set(view.map(i => bucketOf(i.window)))].sort((a, b) => a - b).slice(0, -1);
  const lbls = keys.map(fmt);

  // (1) Message rate: one separate line per channel (not stacked)
  const rateChans = selected === 'all' ? channels : [selected];
  rateChart.data.labels = lbls;
  rateChart.data.datasets = rateChans.map(ch => {
    const byB = {};
    for (const i of items) if (i.channel === ch) { const b = bucketOf(i.window); byB[b] = (byB[b] || 0) + i.count; }
    return {
      label: ch, data: keys.map(k => byB[k] || 0),
      borderColor: colorOf(ch), backgroundColor: colorOf(ch) + '22',
      borderWidth: 2.5, fill: true, tension: 0.4, pointRadius: 0, pointHoverRadius: 4
    };
  });
  rateChart.update();

  // (2) Sentiment: a single line
  const sentB = {};
  for (const i of view) {
    const b = bucketOf(i.window);
    (sentB[b] ||= { n: 0, s: 0 }); sentB[b].n += i.count; sentB[b].s += i.avg_sentiment * i.count;
  }
  sentChart.data.labels = lbls;
  sentChart.data.datasets = [{
    label: 'Sentiment', data: keys.map(k => sentB[k] && sentB[k].n ? +(sentB[k].s / sentB[k].n).toFixed(3) : 0),
    borderColor: '#fbbf24', backgroundColor: 'rgba(251,191,36,.14)',
    borderWidth: 2.5, fill: 'origin', tension: 0.4, pointRadius: 0, pointHoverRadius: 4
  }];
  sentChart.update();
  document.getElementById('rate-title').textContent =
    `Last 5 min · Message rate (per 15s)${selected === 'all' ? ' · by channel' : ' · ' + selected}`;

  // (3) Viewers: horizontal bars per channel (always all channels). vw declared above
  const vchs = Object.keys(vw).sort((a, b) => vw[b].viewers - vw[a].viewers);
  const vmax = vchs.length ? Math.max(...vchs.map(c => vw[c].viewers)) : 1;
  document.getElementById('viewerbars').innerHTML = vchs.length ? vchs.map(c =>
    `<div class="vbar"><div class="vbar-top">` +
    `<span><span class="dot" style="background:${colorOf(c)}"></span>${c}</span>` +
    `<span class="num">${vw[c].viewers.toLocaleString()}</span></div>` +
    `<div class="vtrack"><div class="vfill" data-w="${Math.round(vw[c].viewers / vmax * 100)}" style="background:${colorOf(c)}"></div></div>` +
    `<div class="vgame">${vw[c].game || ''}</div></div>`
  ).join('') : '<div class="empty">No viewer data yet</div>';
  requestAnimationFrame(() =>
    document.querySelectorAll('.vfill').forEach(el => el.style.width = el.dataset.w + '%'));

  document.getElementById('updated').textContent = fmt(now);
  const latest = items.length ? items[items.length - 1].window : 0;
  document.getElementById('stale').style.display = (now - latest > 30) ? 'block' : 'none';
}

async function tick() {
  try { last = await (await fetch('?api=1', { cache: 'no-store' })).json(); }
  catch (e) { return; }
  render();
}
tick();
setInterval(tick, 2000);
</script>
</body>
</html>"""
