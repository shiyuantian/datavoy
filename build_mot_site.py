#!/usr/bin/env python3
"""
Build the MOT Spring Festival travel data dashboard from the local SQLite database.

Usage:
    python build_mot_site.py

Reads: data/mot_chunyun.db
Writes: mot.html
"""

import json
import os
import sqlite3

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT_DIR, "data", "mot_chunyun.db")
OUT_PATH = os.path.join(ROOT_DIR, "mot.html")

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>中国交通行业数据看板 · 2025年春运出行数据</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root {{ --primary:#2563eb; --primary-light:#eff6ff; --success:#16a34a; --warning:#f59e0b; --danger:#dc2626; --text:#111827; --muted:#6b7280; --bg:#f8fafc; --card:#fff; --border:#e5e7eb; }}
* {{ box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif; margin:0; background:var(--bg); color:var(--text); line-height:1.5; }}
header {{ background:var(--card); border-bottom:1px solid var(--border); padding:16px 24px; position:sticky; top:0; z-index:50; }}
.nav {{ max-width:1200px; margin:0 auto; display:flex; align-items:center; justify-content:space-between; gap:16px; }}
.brand {{ display:flex; align-items:center; gap:10px; font-weight:700; font-size:18px; color:var(--primary); }}
.brand-icon {{ width:32px; height:32px; background:linear-gradient(135deg,var(--primary),#3b82f6); border-radius:8px; display:grid; place-items:center; color:#fff; font-size:16px; }}
.nav-links {{ display:flex; gap:20px; font-size:14px; color:var(--muted); }}
.nav-links a {{ color:var(--muted); text-decoration:none; }}
.nav-links a:hover {{ color:var(--primary); }}
main {{ max-width:1200px; margin:0 auto; padding:28px 24px; }}
.hero {{ margin-bottom:28px; }}
.hero h1 {{ margin:0 0 8px; font-size:28px; }}
.hero p {{ margin:0; color:var(--muted); font-size:15px; }}
.card {{ background:var(--card); border-radius:12px; padding:20px; box-shadow:0 1px 3px rgba(0,0,0,.06); margin-bottom:20px; }}
.filter-bar {{ display:flex; flex-wrap:wrap; gap:24px; align-items:flex-start; }}
.filter-group {{ display:flex; flex-direction:column; gap:10px; flex:1; min-width:220px; }}
.filter-group label {{ font-weight:600; font-size:13px; color:#374151; }}
.filter-options {{ display:flex; flex-wrap:wrap; gap:8px; }}
.filter-chip {{ display:inline-flex; align-items:center; gap:5px; padding:6px 12px; border-radius:20px; border:1px solid var(--border); background:#f9fafb; cursor:pointer; font-size:13px; color:#4b5563; transition:all .15s ease; user-select:none; }}
.filter-chip:hover {{ border-color:var(--primary); color:var(--primary); }}
.filter-chip.active {{ background:var(--primary-light); border-color:var(--primary); color:var(--primary); }}
.btn {{ padding:6px 12px; font-size:12px; border-radius:6px; border:1px solid var(--border); background:#fff; cursor:pointer; color:#4b5563; }}
.btn:hover {{ background:#f3f4f6; }}
.count {{ margin-bottom:12px; font-size:13px; color:var(--muted); }}
table {{ width:100%; border-collapse:collapse; background:var(--card); border-radius:12px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
th,td {{ padding:12px 14px; text-align:left; font-size:13px; border-bottom:1px solid #f3f4f6; }}
th {{ background:#f9fafb; font-weight:600; color:#374151; }}
tbody tr:hover {{ background:#f9fafb; }}
.metric {{ display:flex; flex-direction:column; gap:2px; }}
.metric-value {{ font-weight:600; }}
.metric-unit {{ font-size:11px; color:var(--muted); }}
.yoy {{ font-size:12px; font-weight:500; }}
.yoy.positive {{ color:var(--success); }}
.yoy.negative {{ color:var(--danger); }}
.yoy.neutral {{ color:var(--muted); }}
a {{ color:inherit; text-decoration:none; }}
a:hover {{ color:var(--primary); text-decoration:underline; }}
.empty {{ padding:50px; text-align:center; color:var(--muted); }}
.chart-header {{ display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:16px; margin-bottom:16px; }}
.chart-title {{ font-size:16px; font-weight:600; }}
.chart-subtitle {{ font-size:12px; color:var(--muted); margin-top:2px; }}
.chart-canvas-wrap {{ position:relative; height:360px; }}
.metric-toggle {{ display:flex; flex-wrap:wrap; gap:12px; }}
.metric-toggle label {{ display:inline-flex; align-items:center; gap:6px; font-size:13px; color:#4b5563; cursor:pointer; }}
.chart-divider {{ border:none; border-top:1px solid #f3f4f6; margin:28px 0; }}
footer {{ max-width:1200px; margin:0 auto; padding:0 24px 40px; font-size:12px; color:var(--muted); text-align:center; }}
</style>
</head>
<body>
<header>
  <div class="nav">
    <div class="brand"><div class="brand-icon">🚄</div><div>中国交通行业数据看板</div></div>
    <div class="nav-links">
      <a href="index.html">文旅部 · 假期出行</a>
      <a href="mot.html">交通部 · 春运数据</a>
    </div>
  </div>
</header>
<main>
  <section class="hero" id="data">
    <h1>2025年春运交通数据</h1>
    <p>汇总交通运输部官网披露的春运每日全社会跨区域人员流动量及铁路、公路、水路、民航客运量，每个数字均可追溯原文出处。</p>
  </section>

  <section class="card">
    <div class="filter-bar">
      <div class="filter-group">
        <label>运输方式（多选）</label>
        <div class="filter-options" id="modeFilters"></div>
      </div>
      <div class="filter-group" style="justify-content:flex-end;flex:0;">
        <label>&nbsp;</label>
        <div><button class="btn" onclick="selectAll(true)">全选</button> <button class="btn" onclick="selectAll(false)">清空</button></div>
      </div>
    </div>
  </section>

  <div class="count" id="count"></div>
  <table>
    <thead>
      <tr>
        <th>日期</th><th>春运第几天</th><th>发布日期</th>
        <th>全社会跨区域<br>人员流动量</th><th>同比</th>
        <th>铁路</th><th>同比</th>
        <th>公路</th><th>同比</th>
        <th>水路</th><th>同比</th>
        <th>民航</th><th>同比</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>

  <section class="card" id="charts" style="margin-top:28px;">
    <div class="chart-header">
      <div><div class="chart-title">客运量绝对值趋势</div><div class="chart-subtitle">单位：万人次</div></div>
      <div class="metric-toggle" id="absoluteMetricToggles"></div>
    </div>
    <div class="chart-canvas-wrap"><canvas id="absoluteChart"></canvas></div>
    <hr class="chart-divider">
    <div class="chart-header">
      <div><div class="chart-title">同比增速趋势</div><div class="chart-subtitle">单位：%</div></div>
      <div class="metric-toggle" id="growthMetricToggles"></div>
    </div>
    <div class="chart-canvas-wrap"><canvas id="growthChart"></canvas></div>
  </section>
</main>
<footer>
  中国交通行业数据看板 · 数据来源：交通运输部官网
</footer>
<script>
const allData = {data_json};
const MODES = [
  {{ key: 'total_flow', label: '全社会跨区域人员流动量', color: '#111827' }},
  {{ key: 'railway', label: '铁路', color: '#2563eb' }},
  {{ key: 'highway', label: '公路', color: '#16a34a' }},
  {{ key: 'waterway', label: '水路', color: '#f59e0b' }},
  {{ key: 'aviation', label: '民航', color: '#dc2626' }},
];
function renderFilters(){{
  document.getElementById('modeFilters').innerHTML = MODES.map((m,i)=>`<label class="filter-chip active" data-type="mode"><input type="checkbox" value="${{m.key}}" checked onchange="toggle(this)"> ${{m.label}}</label>`).join('');
  document.getElementById('absoluteMetricToggles').innerHTML = MODES.slice(1).map((m,i)=>`<label><input type="checkbox" value="${{m.key}}" ${{i<4?'checked':''}} onchange="renderCharts()"> <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${{m.color}};margin-right:4px;"></span>${{m.label}}</label>`).join('');
  document.getElementById('growthMetricToggles').innerHTML = MODES.map((m,i)=>`<label><input type="checkbox" value="${{m.key}}_yoy" ${{i<5?'checked':''}} onchange="renderCharts()"> <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${{m.color}};margin-right:4px;"></span>${{m.label}}同比</label>`).join('');
}}
function toggle(cb){{ cb.parentElement.classList.toggle('active', cb.checked); render(); }}
function selectAll(checked){{ document.querySelectorAll('.filter-chip input').forEach(cb=>{{cb.checked=checked; cb.parentElement.classList.toggle('active',checked);}}); render(); }}
function selectedModes(){{ return [...document.querySelectorAll('.filter-chip[data-type="mode"] input:checked')].map(cb=>cb.value); }}
function selectedAbsolute(){{ return [...document.querySelectorAll('#absoluteMetricToggles input:checked')].map(cb=>cb.value); }}
function selectedGrowth(){{ return [...document.querySelectorAll('#growthMetricToggles input:checked')].map(cb=>cb.value); }}
function fmtNum(v,d=1){{ return v===null||v===undefined?'—':Number(v).toLocaleString('zh-CN',{{minimumFractionDigits:d,maximumFractionDigits:d}}); }}
function fmtDateSlash(date){{ return date?date.replace(/-/g,'/'):''; }}
function fmtYoy(v){{
  if(v===null||v===undefined) return '<span class="yoy neutral">—</span>';
  const s=v>0?'+':''; const c=v>0?'positive':(v<0?'negative':'neutral');
  return `<span class="yoy ${{c}}">${{s}}${{v}}%</span>`;
}}
let absoluteChart=null, growthChart=null;
function getFiltered(){{
  const modes=selectedModes();
  return allData.filter(d=>modes.length===0||modes.some(m=>d[m]!==null));
}}
function render(){{
  const filtered=getFiltered();
  document.getElementById('count').textContent=`共 ${{filtered.length}} 条记录`;
  const tb=document.getElementById('tbody');
  if(!filtered.length){{ tb.innerHTML='<tr><td colspan="13" class="empty">没有符合条件的记录</td></tr>'; renderCharts(filtered); return; }}
  tb.innerHTML = filtered.map(d=>`<tr>
    <td>${{fmtDateSlash(d.date)}}</td>
    <td>${{d.chunyun_day!==null&&d.chunyun_day!==undefined?d.chunyun_day:'—'}}</td>
    <td>${{fmtDateSlash(d.publish_date)}}</td>
    <td>${{d.source_url?`<a href="${{d.source_url}}" target="_blank">`:''}}<div class="metric"><span class="metric-value">${{fmtNum(d.total_flow)}}</span><span class="metric-unit">万人次</span></div>${{d.source_url?'</a>':''}}</td>
    <td>${{d.source_url?`<a href="${{d.source_url}}" target="_blank">`:''}}${{fmtYoy(d.total_flow_yoy)}}${{d.source_url?'</a>':''}}</td>
    <td>${{d.source_url?`<a href="${{d.source_url}}" target="_blank">`:''}}<div class="metric"><span class="metric-value">${{fmtNum(d.railway)}}</span><span class="metric-unit">万人次</span></div>${{d.source_url?'</a>':''}}</td>
    <td>${{d.source_url?`<a href="${{d.source_url}}" target="_blank">`:''}}${{fmtYoy(d.railway_yoy)}}${{d.source_url?'</a>':''}}</td>
    <td>${{d.source_url?`<a href="${{d.source_url}}" target="_blank">`:''}}<div class="metric"><span class="metric-value">${{fmtNum(d.highway)}}</span><span class="metric-unit">万人次</span></div>${{d.source_url?'</a>':''}}</td>
    <td>${{d.source_url?`<a href="${{d.source_url}}" target="_blank">`:''}}${{fmtYoy(d.highway_yoy)}}${{d.source_url?'</a>':''}}</td>
    <td>${{d.source_url?`<a href="${{d.source_url}}" target="_blank">`:''}}<div class="metric"><span class="metric-value">${{fmtNum(d.waterway)}}</span><span class="metric-unit">万人次</span></div>${{d.source_url?'</a>':''}}</td>
    <td>${{d.source_url?`<a href="${{d.source_url}}" target="_blank">`:''}}${{fmtYoy(d.waterway_yoy)}}${{d.source_url?'</a>':''}}</td>
    <td>${{d.source_url?`<a href="${{d.source_url}}" target="_blank">`:''}}<div class="metric"><span class="metric-value">${{fmtNum(d.aviation)}}</span><span class="metric-unit">万人次</span></div>${{d.source_url?'</a>':''}}</td>
    <td>${{d.source_url?`<a href="${{d.source_url}}" target="_blank">`:''}}${{fmtYoy(d.aviation_yoy)}}${{d.source_url?'</a>':''}}</td>
  </tr>`).join('');
  renderCharts(filtered);
}}
function renderCharts(filtered){{
  if(!filtered) filtered=getFiltered();
  const sorted=[...filtered].sort((a,b)=>(a.date||'').localeCompare(b.date||''));
  const labels=sorted.map(d=>`${{fmtDateSlash(d.date)}}`);
  renderAbsoluteChart(sorted,labels);
  renderGrowthChart(sorted,labels);
}}
function makeDatasets(sorted,metrics){{
  return metrics.map(m=>({{
    label:m.label, data:sorted.map(d=>d[m.key]), borderColor:m.color, backgroundColor:m.color, yAxisID:'y',
    tension:0.25, pointRadius:4, pointHoverRadius:6, spanGaps:true
  }}));
}}
function commonOptions(sorted){{
  return {{
    responsive:true, maintainAspectRatio:false, interaction:{{mode:'index',intersect:false}},
    plugins:{{
      legend:{{position:'bottom'}},
      tooltip:{{callbacks:{{label:function(ctx){{ let l=ctx.dataset.label||''; if(l) l+=': '; if(ctx.parsed.y!==null&&ctx.parsed.y!==undefined) l+=ctx.parsed.y; else l+='—'; return l; }}}}}
    }},
    onClick:(e,elements)=>{{ if(!elements||!elements.length)return; const d=sorted[elements[0].index]; if(d&&d.source_url)window.open(d.source_url,'_blank'); }}
  }};
}}
function renderAbsoluteChart(sorted,labels){{
  const selected=selectedAbsolute();
  const metrics=MODES.slice(1).filter(m=>selected.includes(m.key));
  const datasets=makeDatasets(sorted,metrics);
  const ctx=document.getElementById('absoluteChart').getContext('2d');
  if(absoluteChart){{ absoluteChart.data.labels=labels; absoluteChart.data.datasets=datasets; absoluteChart.update(); return; }}
  absoluteChart=new Chart(ctx,{{type:'line', data:{{labels,datasets}}, options:{{...commonOptions(sorted), scales:{{y:{{type:'linear',display:true,position:'left',title:{{display:true,text:'万人次'}},grid:{{color:'#f3f4f6'}}}}, x:{{grid:{{display:false}}}}}}}});
}}
function renderGrowthChart(sorted,labels){{
  const selected=selectedGrowth();
  const metrics=MODES.map(m=>{{ return {{key:m.key+'_yoy', label:m.label+'同比', color:m.color}}; }}).filter(m=>selected.includes(m.key));
  const datasets=makeDatasets(sorted,metrics);
  const ctx=document.getElementById('growthChart').getContext('2d');
  if(growthChart){{ growthChart.data.labels=labels; growthChart.data.datasets=datasets; growthChart.update(); return; }}
  growthChart=new Chart(ctx,{{type:'line', data:{{labels,datasets}}, options:{{...commonOptions(sorted), scales:{{y:{{type:'linear',display:true,position:'left',title:{{display:true,text:'同比（%）'}},grid:{{color:'#f3f4f6'}},ticks:{{callback:v=>v+'%'}}}}, x:{{grid:{{display:false}}}}}}}});
}}
renderFilters(); render();
</script>
</body>
</html>'''


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM mot_chunyun_data ORDER BY date ASC").fetchall()
    records = [dict(r) for r in rows]
    conn.close()

    rendered = HTML_TEMPLATE.replace("{data_json}", json.dumps(records, ensure_ascii=False))
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(rendered)
    print(f"Generated {OUT_PATH} ({len(records)} records)")


if __name__ == "__main__":
    main()
