"""The dashboard: one self-contained HTML file. No external scripts, styles, fonts or images; nothing is fetched.

Seven pages sit behind a small inline script: Overview, Holdings, News & world, Exposure, Scenarios, Views and
Record. Without the script every page shows, one after another. The page shows percentages only, never amounts,
so a screenshot of it is safe to share. Every text that came from a file, a feed or the AI is escaped, and only
http(s) links become links. The script reads attributes and writes textContent; it never builds HTML."""
from __future__ import annotations

import datetime as dt

from . import charts as ch
from .brief import INSIDE_SHARE
from .charts import DASH, e, gap, move, pct

PAGES = (("overview", "Overview"), ("holdings", "Holdings"), ("world", "News & world"), ("exposure", "Exposure"),
         ("scenarios", "Scenarios"), ("views", "Views"), ("record", "Record"))
RIPPLE_WORD = {"help": "helps", "hurt": "hurts", "unclear": "unclear"}
SCAN_WORD = {"hurt": "would hurt", "help": "would help", "mixed": "mixed"}
NO_BRIEF = "No brief today. Run /morning in Claude Code to have your AI read the news."
QUIET = "A quiet day: nothing in the news touched your themes, holdings or views."

CSS = """
:root{color-scheme:dark;--bg:#0E1117;--card:#161B26;--card2:#1C2331;--line:#262E3E;--axis:#3A4356;
--ink:#E6E6E6;--ink2:#B4BCCB;--ink3:#8A94A6;--you:#3987e5;--world:#8A94A6;--hurt:#d95926;--help:#199e70;
--mixed:#8A94A6;--up:#0ca30c;--down:#e66767;--pos:#3987e5;--neg:#e66767;--mid:#252C3B;--tint:rgba(57,135,229,.13);
--warn:#f2c26b;--warn-bg:rgba(242,194,107,.10);--shadow:none;--c0:#5A6478;--c1:#3987e5;--c2:#d95926;--c3:#199e70;
--c4:#c98500;--c5:#d55181;--c6:#008300;--c7:#9085e9}
:root[data-theme=light]{color-scheme:light;--bg:#F4F6F9;--card:#FFFFFF;--card2:#F2F4F8;--line:#E3E6EC;--axis:#C9CED8;
--ink:#141A26;--ink2:#4A5263;--ink3:#6B7385;--you:#2a78d6;--world:#8A94A6;--hurt:#eb6834;--help:#1baf7a;
--mixed:#8A94A6;--up:#006300;--down:#d03b3b;--pos:#2a78d6;--neg:#e34948;--mid:#EBEEF2;--tint:rgba(42,120,214,.08);
--warn:#7a4f00;--warn-bg:#fff4e0;--shadow:0 1px 2px rgba(16,24,40,.05);--c0:#A3ABB9;--c1:#2a78d6;--c2:#eb6834;
--c3:#1baf7a;--c4:#eda100;--c5:#e87ba4;--c6:#008300;--c7:#6250d6}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--you);text-decoration:none}
a:hover{text-decoration:underline}
h1{font-size:22px;line-height:1.25;margin:0;letter-spacing:-.01em}
h2{font-size:15px;line-height:1.35;margin:0}
h3{font-size:14px;line-height:1.4;margin:0 0 4px}
p{margin:6px 0}
ul{margin:6px 0;padding-left:18px}
.small{font-size:12.5px}
.muted{color:var(--ink3)}
.ink2{color:var(--ink2)}
.lead{font-size:15.5px;line-height:1.55;margin:0}
.row{display:flex;justify-content:space-between;gap:10px}
.ar{text-align:right}
.mt{margin-top:16px}
.mt8{margin-top:8px}
.shell{display:flex;min-height:100vh}
.side{position:sticky;top:0;height:100vh;width:228px;flex:none;display:flex;flex-direction:column;gap:18px;
padding:22px 14px;background:var(--card);border-right:1px solid var(--line)}
.brand{padding:0 10px;font-weight:700;font-size:17px;letter-spacing:-.02em}
.brand small{display:block;font-weight:500;font-size:12px;color:var(--ink3);letter-spacing:0;margin-top:2px}
.nav{display:flex;flex-direction:column;gap:2px}
.nav a{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;color:var(--ink2);font-weight:500}
.nav a:hover{background:var(--card2);color:var(--ink);text-decoration:none}
.nav a.on{background:var(--tint);color:var(--ink);box-shadow:inset 3px 0 0 var(--you)}
.nav .n{margin-left:auto;min-width:20px;text-align:center;font-size:11px;padding:0 6px;border-radius:999px;background:var(--card2);color:var(--ink2)}
.side-foot{margin-top:auto;padding:0 10px;font-size:12px;color:var(--ink3)}
.toggle{font:inherit;font-size:12.5px;color:var(--ink2);background:var(--card2);border:1px solid var(--line);border-radius:8px;padding:6px 10px;cursor:pointer;margin:0 10px}
main{flex:1;min-width:0;padding:26px 30px 70px}
.wrap{max-width:1220px;margin:0 auto}
.page>*+*{margin-top:16px}
.page+.page{margin-top:48px}
.js .page{display:none}
.js .page.on{display:block}
.js .page+.page{margin-top:0}
.ph{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;flex-wrap:wrap}
.ph p{margin:4px 0 0;color:var(--ink2);max-width:780px}
.sec{margin-top:28px}
.sec p{margin:2px 0 0}
.banner{background:var(--warn-bg);color:var(--warn);border-radius:10px;padding:9px 13px;font-size:13px;margin-bottom:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;box-shadow:var(--shadow);min-width:0}
.ch{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:12px;flex-wrap:wrap}
.sub{color:var(--ink2);font-size:13px}
.cols{display:grid;gap:16px}
.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.g21{grid-template-columns:minmax(0,1.7fr) minmax(0,1fr)}
.kpis{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(176px,1fr))}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);min-width:0}
.kpi[data-tip]{cursor:help}
.kpi .l{font-size:12px;color:var(--ink3);font-weight:500}
.kpi .v{font-size:24px;font-weight:650;letter-spacing:-.02em;line-height:1.25;margin-top:4px;overflow-wrap:anywhere}
.kpi .s{font-size:12.5px;color:var(--ink2);margin-top:2px}
.bignum{font-size:30px;font-weight:650;letter-spacing:-.02em;line-height:1.1}
.mv.up{color:var(--up)}
.mv.down{color:var(--down)}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:999px;padding:1px 9px;margin:2px 4px 2px 0;font-size:12px;font-weight:500;color:var(--ink);white-space:nowrap;background:var(--card2)}
.pill i{width:7px;height:7px;border-radius:50%;background:var(--ink3);flex:none}
.pill.for i,.pill.help i{background:var(--help)}
.pill.against i,.pill.hurt i{background:var(--hurt)}
.pill.unclear i,.pill.mixed i{background:var(--mixed)}
.pill.busy i{background:var(--you)}
.pill.active i{background:var(--you);opacity:.45}
.pill.quiet i{background:transparent;box-shadow:inset 0 0 0 1px var(--ink3)}
.pill.you i{background:var(--you)}
.pill.flag{border-color:transparent;background:var(--warn-bg);color:var(--warn)}
.pill.flag i{display:none}
.dec td:first-child{white-space:nowrap}
.dec td:nth-child(2){min-width:170px}
.dec .pill.flag{white-space:normal;border-radius:8px;line-height:1.35;padding:3px 9px}
.lab{font-size:11px;font-weight:600;color:var(--ink3);text-transform:uppercase;letter-spacing:.05em;margin-right:6px}
.src{font-size:12.5px;color:var(--ink2);margin:4px 0}
.src a{color:var(--ink2);text-decoration:underline;text-decoration-color:var(--axis)}
.ev{border-left:2px solid var(--line);padding:2px 0 2px 12px}
.ev+.ev{margin-top:16px}
.eff{margin-top:4px}
.list>*+*{margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--ink3);font-weight:600;white-space:nowrap}
th button{all:unset;cursor:pointer}
th button:focus-visible{outline:2px solid var(--you)}
th[aria-sort=descending] button::after{content:" \\2193"}
th[aria-sort=ascending] button::after{content:" \\2191"}
tbody tr:last-child td,tbody tr:last-child th{border-bottom:0}
td.n,th.n{text-align:right;white-space:nowrap}
details>summary{cursor:pointer}
details.twin{margin-top:10px}
details.twin>summary,details.more>summary{color:var(--ink3);font-size:12.5px}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.5px;color:var(--ink2);margin:0 0 10px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.key{display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--ink3)}
.key.ln{width:16px;height:3px;border-radius:2px}
.key.sw{border-radius:3px}
.key.you,.dot.you,.end.you{background:var(--you)}
.key.world,.dot.world,.end.world{background:var(--world)}
.key.hurt{background:var(--hurt)}
.key.help{background:var(--help)}
.key.unclear,.key.mixed{background:var(--mixed)}
.key.pos{background:var(--pos)}
.key.neg{background:var(--neg)}
.key.hm-mid{background:var(--mid);box-shadow:inset 0 0 0 1px var(--line)}
.key.seq-lo{background:var(--you);opacity:.4}
.key.seq-hi{background:var(--you)}
.c0{background:var(--c0)}.c1{background:var(--c1)}.c2{background:var(--c2)}.c3{background:var(--c3)}
.c4{background:var(--c4)}.c5{background:var(--c5)}.c6{background:var(--c6)}.c7{background:var(--c7)}
.lc{margin:0}
.lc-box{position:relative}
.lc-y{position:absolute;left:0;top:6px;bottom:24px;width:44px}
.lc-y span{position:absolute;right:8px;transform:translateY(-50%);font-size:11px;color:var(--ink3);font-variant-numeric:tabular-nums}
.lc-plot{position:absolute;left:48px;right:12px;top:6px;bottom:24px;touch-action:pan-y}
.lc-plot svg,.stepc svg,.spark svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.ln{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round;vector-effect:non-scaling-stroke}
.ln.you{stroke:var(--you)}.ln.world{stroke:var(--world)}
svg .grid{stroke:var(--line);stroke-width:1;vector-effect:non-scaling-stroke}
svg .grid.base{stroke:var(--axis)}
svg .now{stroke:var(--ink3);stroke-width:1;vector-effect:non-scaling-stroke}
.end{position:absolute;width:9px;height:9px;border-radius:50%;transform:translate(-50%,-50%);box-shadow:0 0 0 2px var(--card)}
.guide{position:absolute;top:0;bottom:0;width:1px;background:var(--ink3);pointer-events:none}
.lc-x{position:absolute;left:48px;right:12px;bottom:0;height:20px}
.lc-x span{position:absolute;top:3px;font-size:11px;color:var(--ink3);white-space:nowrap}
.lc-x .c{transform:translateX(-50%)}.lc-x .r{transform:translateX(-100%)}
.spark{position:relative;display:block;height:28px}
.spark polyline{fill:none;stroke:var(--ink3);stroke-width:1.5;vector-effect:non-scaling-stroke}
.spark i{position:absolute;right:0;width:6px;height:6px;border-radius:50%;background:var(--you);transform:translate(50%,-50%)}
.stepc{position:relative;height:56px;margin:8px 0 2px}
.stepc-l{position:absolute;left:0;transform:translateY(-120%);font-size:10.5px;color:var(--ink3)}
.dumbbell{display:flex;flex-direction:column;gap:2px}
.db{display:grid;grid-template-columns:minmax(110px,1.1fr) minmax(90px,2.2fr) 112px;align-items:center;gap:12px;padding:5px 6px;border-radius:6px}
.db:hover,.db:focus{background:var(--card2);outline:0}
.db-l{font-size:13px}
.db-t{position:relative;height:16px}
.db-t::before{content:"";position:absolute;left:0;right:0;top:50%;height:1px;background:var(--line)}
.db-c{position:absolute;top:calc(50% - 1px);height:2px;background:var(--ink3);opacity:.5}
.dot{position:absolute;top:50%;width:10px;height:10px;border-radius:50%;transform:translate(-50%,-50%);box-shadow:0 0 0 2px var(--card)}
.db-v,.dv-v{text-align:right;font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap}
.dvs{display:flex;flex-direction:column}
.dv{display:grid;grid-template-columns:minmax(120px,1.2fr) minmax(100px,2fr) 128px;gap:12px;align-items:center;padding:8px 6px;border-bottom:1px solid var(--line)}
.dv:last-child{border-bottom:0}
.dv:hover,.dv:focus{background:var(--card2);outline:0}
.dv-l small{display:block;color:var(--ink3);font-size:11.5px}
.dv-t{position:relative;display:flex;flex-direction:column;gap:3px}
.dv-t::before{content:"";position:absolute;left:50%;top:-5px;bottom:-5px;width:1px;background:var(--axis)}
.dv-r{position:relative;height:8px}
.dv-b{position:absolute;top:0;height:8px}
.dv-b.pos{border-radius:0 4px 4px 0}.dv-b.neg{border-radius:4px 0 0 4px}
.dv-b.you{background:var(--you)}.dv-b.world{background:var(--world)}.dv-b.hurt{background:var(--hurt)}.dv-b.help{background:var(--help)}
.dv-na{position:absolute;left:52%;top:-5px;font-size:11px;color:var(--ink3);white-space:nowrap}
.stack{display:flex;flex-direction:column;gap:10px}
.st{display:grid;grid-template-columns:96px minmax(0,1fr);gap:12px;align-items:center}
.st-l{font-size:13px;color:var(--ink2)}
.st-bar{display:flex;gap:2px;height:28px}
.seg{position:relative;min-width:0;flex-basis:0;border-radius:4px;display:flex;align-items:center;overflow:hidden}
.seg b{padding:0 6px;font-size:11.5px;font-weight:600;color:#fff;white-space:nowrap}
.seg.c4 b,:root[data-theme=light] .seg.c0 b{color:#0b0b0b}
.hmap{display:grid;gap:3px;align-items:center}
.hm-l{font-size:12.5px;color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:8px}
.hm-x{font-size:11px;color:var(--ink3);white-space:nowrap}
.hm-x.r{direction:rtl}
.hm{position:relative;display:block;height:20px;border-radius:3px;background:var(--mid)}
.hm::after{content:"";position:absolute;inset:0;border-radius:3px;opacity:var(--a,0)}
.hm.pos::after{background:var(--pos)}.hm.neg::after{background:var(--neg)}.hm.seq::after{background:var(--you)}
.hm.na{background:transparent;box-shadow:inset 0 0 0 1px var(--line)}
.hm:hover{box-shadow:0 0 0 1px var(--ink2)}
.strip{display:grid;gap:2px;margin-top:4px}
.strip .hm{height:14px}
.ht th[scope=row]{font-size:13px;font-weight:600;color:var(--ink)}
.ht thead th{white-space:normal;vertical-align:bottom;min-width:64px;line-height:1.3}
.hc{position:relative}
.hc::before{content:"";position:absolute;inset:3px 2px;border-radius:4px;background:var(--you);opacity:var(--a,0)}
.hc span{position:relative}
.ht tfoot th,.ht tfoot td{border-top:1px solid var(--axis);border-bottom:0}
.bmap{display:flex;flex-wrap:wrap;justify-content:space-around;align-items:flex-start;gap:16px 20px;margin-top:8px}
.bm-c{margin:0;min-width:0;max-width:100%}
.bm-c figcaption{display:block;text-align:center;margin:0 0 6px;font-size:12.5px}
.bm-c svg{display:block;margin:0 auto;max-width:100%;height:auto;overflow:visible}
.bm-b{cursor:default}.bm-b:focus{outline:none}
.bm-y{stroke:var(--card);stroke-width:1.5}
.bm-b.hurt .bm-y{fill:var(--hurt)}.bm-b.help .bm-y{fill:var(--help)}.bm-b.mixed .bm-y{fill:var(--mixed)}
.bm-b.s-high .bm-y{fill-opacity:.9}.bm-b.s-medium .bm-y{fill-opacity:.6}.bm-b.s-low .bm-y{fill-opacity:.32}
.bm-b:hover .bm-y,.bm-b:focus .bm-y{stroke:var(--ink);stroke-width:2}
.bm-w{fill:none;stroke:var(--ink2);stroke-width:1.2;stroke-dasharray:3 3;pointer-events:none}
.bm-t{fill:var(--ink);font-size:11px;font-weight:600;text-anchor:middle;paint-order:stroke;stroke:var(--card);stroke-width:3px;stroke-linejoin:round}
.bm-t.v{font-size:10.5px;font-weight:500}
.bm-l{fill:var(--ink2);font-size:10.5px}
.bm-l .v{fill:var(--ink3)}
.bm-list{list-style:none;margin:4px 0 0;padding:0;display:flex;flex-wrap:wrap;justify-content:center;gap:2px 12px;font-size:12px;color:var(--ink2)}
.bm-list li{display:inline-flex;align-items:center;gap:5px}
.bm-list i{width:9px;height:9px;border-radius:50%}
.bm-list i.hurt{background:var(--hurt)}.bm-list i.help{background:var(--help)}.bm-list i.mixed{background:var(--mixed)}
.bm-list i.s-medium{opacity:.7}.bm-list i.s-low{opacity:.4}
figcaption{display:flex;justify-content:space-between;gap:10px;font-size:12px;color:var(--ink2);margin-top:6px}
.net{position:relative;width:100%;max-width:660px;margin:0 auto 8px;aspect-ratio:140/100;container-type:inline-size}
.net svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.edge{fill:none;stroke-width:.55;stroke-linecap:round}
.edge.hurt{stroke:var(--hurt)}.edge.help{stroke:var(--help)}.edge.unclear{stroke:var(--mixed)}
.ah.hurt{fill:var(--hurt)}.ah.help{fill:var(--help)}.ah.unclear{fill:var(--mixed)}
.hit{fill:none;stroke:transparent;stroke-width:4;pointer-events:stroke}
.node{fill:var(--card2);stroke:var(--ink3);stroke-width:.35}
.node.hub{fill:var(--tint);stroke:var(--you);stroke-width:.6}
.nl{position:absolute;width:max-content;max-width:96px;font-size:11.5px;line-height:1.2;pointer-events:none}
.nl.r{transform:translate(calc(var(--r,2) * .7143cqw + 5px),-50%)}
.nl.l{transform:translate(calc(-100% - var(--r,2) * .7143cqw - 5px),-50%);text-align:right}
.nl.c{text-align:center}
.nl.c.above{transform:translate(-50%,calc(-100% - var(--r,2) * .7143cqw - 4px))}
.nl.c.below{transform:translate(-50%,calc(var(--r,2) * .7143cqw + 4px))}
.nl.dr{transform:translate(calc(var(--r,2) * .5051cqw + 3px),calc(var(--r,2) * .5051cqw + 1px))}
.nl.ur{transform:translate(calc(var(--r,2) * .5051cqw + 3px),calc(-100% - var(--r,2) * .5051cqw - 1px))}
.nl.dl{transform:translate(calc(-100% - var(--r,2) * .5051cqw - 3px),calc(var(--r,2) * .5051cqw + 1px));text-align:right}
.nl.ul{transform:translate(calc(-100% - var(--r,2) * .5051cqw - 3px),calc(-100% - var(--r,2) * .5051cqw - 1px));text-align:right}
.tl{position:relative;height:64px;margin:26px 14px 4px}
.tl::before{content:"";position:absolute;left:0;right:0;top:40px;height:1px;background:var(--axis)}
.tl-d{position:absolute;width:20px;height:20px;border-radius:50%;background:var(--you);color:#fff;font-size:11px;font-weight:650;
display:grid;place-items:center;transform:translateX(-50%);box-shadow:0 0 0 2px var(--card)}
.tl-t{position:absolute;top:46px;transform:translateX(-50%);font-size:11px;color:var(--ink3);white-space:nowrap}
.tl-t.l{transform:none}.tl-t.r{transform:translateX(-100%)}
.watch{list-style:none;padding:0;margin:0}
.watch li{display:grid;grid-template-columns:22px 112px minmax(0,1fr);gap:10px;padding:8px 0;border-top:1px solid var(--line)}
.watch li:first-child{border-top:0}
.watch .num{width:20px;height:20px;border-radius:50%;background:var(--you);color:#fff;font-size:11px;font-weight:650;display:grid;place-items:center}
.watch .num.rec{background:var(--card2);color:var(--ink2);box-shadow:inset 0 0 0 1px var(--axis)}
.watch .wd b{display:block;font-weight:600;font-size:13px}
.watch .wd small{color:var(--ink3);font-size:12px}
.segctl{display:inline-flex;background:var(--card2);border:1px solid var(--line);border-radius:9px;padding:2px;gap:2px}
.segctl button{font:inherit;font-size:12.5px;color:var(--ink2);background:transparent;border:0;border-radius:7px;padding:4px 10px;cursor:pointer}
.segctl button.on{background:var(--card);color:var(--ink);box-shadow:0 0 0 1px var(--line)}
.hl-head,.hold>summary{display:grid;grid-template-columns:minmax(150px,2fr) minmax(110px,1.3fr) repeat(4,minmax(56px,.7fr)) minmax(80px,1.1fr) minmax(130px,1.7fr);gap:10px;align-items:center}
.hl-head{padding:0 16px 2px;font-size:12px;color:var(--ink3);font-weight:600}
.hl-head span:nth-child(n+3):nth-child(-n+6){text-align:right}
.hold{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-top:8px;box-shadow:var(--shadow)}
.hold>summary{list-style:none;padding:12px 16px;border-radius:12px}
.hold>summary::-webkit-details-marker{display:none}
.hold>summary:hover{background:var(--card2)}
.hold[open]>summary{border-bottom:1px solid var(--line);border-radius:12px 12px 0 0}
.h-name{min-width:0}
.h-name b{display:block}
.h-name small{display:block;color:var(--ink3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.h-w{font-variant-numeric:tabular-nums;font-size:13px}
.wbar{display:block;height:6px;border-radius:3px;background:var(--card2);margin-bottom:4px}
.wbar i{display:block;height:100%;background:var(--you);border-radius:0 3px 3px 0}
.h-r{text-align:right;font-variant-numeric:tabular-nums}
.h-t{min-width:0;overflow:hidden;white-space:nowrap}
.h-body{padding:16px}
.mb{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(50px,1fr) 52px;gap:8px;align-items:center;font-size:12.5px;padding:3px 0}
.mb span:first-child{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mb-t{height:6px;background:var(--card2);border-radius:3px}
.mb-t i{display:block;height:100%;border-radius:0 3px 3px 0;background:var(--you)}
.mb-t i.world{background:var(--world)}
.mb-v{text-align:right;font-variant-numeric:tabular-nums;color:var(--ink2)}
.tcard h2{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px}
.share{display:grid;grid-template-columns:44px minmax(0,1fr) 50px;gap:8px;align-items:center;font-size:12px;color:var(--ink2);margin:2px 0}
.share b,.share span:last-child{text-align:right;font-variant-numeric:tabular-nums}
.scan-pick{font:inherit;color:var(--ink);background:var(--card2);border:1px solid var(--line);border-radius:8px;padding:6px 10px;max-width:100%}
footer{margin-top:48px;color:var(--ink3);font-size:12.5px;border-top:1px solid var(--line);padding-top:14px}
#tip{position:fixed;z-index:50;max-width:320px;padding:8px 10px;border-radius:8px;background:var(--ink);color:var(--bg);
font-size:12.5px;line-height:1.45;white-space:pre-line;pointer-events:none;box-shadow:0 8px 24px rgba(0,0,0,.28)}
@media (max-width:1100px){.g3{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:900px){
.shell{display:block}
.side{position:sticky;top:0;z-index:20;height:auto;width:auto;flex-direction:row;align-items:center;gap:8px;padding:10px 12px;border-right:0;border-bottom:1px solid var(--line)}
.brand{padding:0;font-size:15px}.brand small{display:none}
.nav{flex-direction:row;overflow-x:auto;scrollbar-width:none;flex:1;min-width:0;padding-right:28px;
-webkit-mask-image:linear-gradient(to right,#000 calc(100% - 28px),transparent);mask-image:linear-gradient(to right,#000 calc(100% - 28px),transparent)}
.nav::-webkit-scrollbar{display:none}
.nav a{white-space:nowrap;padding:6px 10px}
.nav a.on{box-shadow:inset 0 -2px 0 var(--you)}
.nav .n{display:none}
.side-foot{display:none}
.toggle{margin:0;padding:5px 8px}
main{padding:16px 16px 56px}
.g2,.g3,.g21{grid-template-columns:minmax(0,1fr)}
.db{grid-template-columns:minmax(84px,1fr) minmax(64px,1.3fr) 96px;gap:8px}
.dv{grid-template-columns:minmax(88px,1fr) minmax(70px,1.3fr) 100px;gap:8px}
.st{grid-template-columns:70px minmax(0,1fr)}
.kpi .v{font-size:21px}
.hl-head,.hold>summary{grid-template-columns:minmax(0,1.5fr) minmax(64px,1fr) 58px 58px}
.hide-sm{display:none}
.watch li{grid-template-columns:22px 92px minmax(0,1fr)}
.nl{max-width:76px;font-size:10.5px}
}
@media (max-width:600px){
.kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.kpi{padding:12px 14px}
.kpi .v{font-size:19px}
}
"""

HEAD_JS = (
    "(function(){var r=document.documentElement;r.classList.add('js');try{var t=localStorage.getItem('whatstocks-theme');"
    "if(t==='light'||t==='dark')r.setAttribute('data-theme',t);}catch(err){}})();"
)

JS = r"""
(function () {
  var d = document, root = d.documentElement;
  var toggle = d.getElementById('theme');
  if (toggle) toggle.addEventListener('click', function () {
    var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('whatstocks-theme', next); } catch (err) {}
  });

  function route(hash) {
    var parts = (hash || '#overview').slice(1).split('/');
    var page = d.getElementById('p-' + parts[0]) ? parts[0] : 'overview';
    d.querySelectorAll('.page').forEach(function (p) { p.classList.toggle('on', p.id === 'p-' + page); });
    d.querySelectorAll('.nav a').forEach(function (a) {
      var on = a.getAttribute('href') === '#' + page;
      a.classList.toggle('on', on);
      if (on) {
        a.setAttribute('aria-current', 'page');
        // On a phone the tabs scroll sideways: keep the open one in view.
        if (a.scrollIntoView) a.scrollIntoView({block: 'nearest', inline: 'nearest'});
      } else {
        a.removeAttribute('aria-current');
      }
    });
    var target = parts.length > 1 ? d.getElementById(decodeURIComponent(parts.slice(1).join('/'))) : null;
    if (target) {
      if (target.tagName === 'DETAILS') target.open = true;
      target.scrollIntoView({block: 'start'});
    } else {
      window.scrollTo(0, 0);
    }
  }
  // Tabs are handled on click, so they work even where the page's address cannot change
  // (a page opened as a data: URL or in a sandboxed frame); the address follows when it can.
  d.addEventListener('click', function (ev) {
    if (ev.defaultPrevented || ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    var a = ev.target.closest ? ev.target.closest('a[href^="#"]') : null;
    if (!a) return;
    var hash = a.getAttribute('href');
    if (!d.getElementById('p-' + hash.slice(1).split('/')[0])) return;
    ev.preventDefault();
    try { history.pushState(null, '', hash); } catch (err) {}
    route(hash);
  });
  function fromAddress() { route(location.hash); }
  window.addEventListener('hashchange', fromAddress);
  window.addEventListener('popstate', fromAddress);
  fromAddress();

  var tip = d.getElementById('tip');
  function place(x, y) {
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var left = Math.min(x + 14, window.innerWidth - w - 8), top = y + 18;
    if (top + h > window.innerHeight - 8) top = y - h - 12;
    tip.style.left = Math.max(8, left) + 'px';
    tip.style.top = Math.max(8, top) + 'px';
  }
  function showTip(text, x, y) { tip.textContent = text; tip.hidden = false; place(x, y); }
  function hideTip() { tip.hidden = true; }
  var over = null;
  d.addEventListener('pointerover', function (ev) {
    over = ev.target.closest ? ev.target.closest('[data-tip]') : null;
    if (over) showTip(over.getAttribute('data-tip'), ev.clientX, ev.clientY); else hideTip();
  });
  d.addEventListener('pointermove', function (ev) { if (over && !tip.hidden) place(ev.clientX, ev.clientY); });
  d.addEventListener('focusin', function (ev) {
    var el = ev.target.closest ? ev.target.closest('[data-tip]') : null;
    if (!el) return;
    var r = el.getBoundingClientRect();
    showTip(el.getAttribute('data-tip'), r.left, r.bottom);
  });
  d.addEventListener('focusout', hideTip);
  window.addEventListener('scroll', hideTip, {passive: true});

  d.querySelectorAll('.lc-box').forEach(function (box) {
    var data;
    try { data = JSON.parse(box.getAttribute('data-line')); } catch (err) { return; }
    var plot = box.querySelector('.lc-plot'), guide = box.querySelector('.guide');
    function since(v) {
      if (v === null || v === undefined) return '–';
      var c = v - data.b;
      return (c >= 0 ? '+' : '') + c.toFixed(1) + '%';
    }
    plot.addEventListener('pointermove', function (ev) {
      var r = plot.getBoundingClientRect(), fx = (ev.clientX - r.left) / r.width * 100, best = 0, gapBest = 1e9;
      for (var i = 0; i < data.x.length; i++) {
        var g = Math.abs(data.x[i] - fx);
        if (g < gapBest) { gapBest = g; best = i; }
      }
      guide.hidden = false;
      guide.style.left = data.x[best] + '%';
      var lines = [data.d[best]];
      data.s.forEach(function (s) { lines.push(since(s.v[best]) + '  ' + s.n); });
      showTip(lines.join('\n'), ev.clientX, ev.clientY);
    });
    plot.addEventListener('pointerleave', function () { guide.hidden = true; hideTip(); });
  });

  function num(el, k) { var v = parseFloat(el.getAttribute('data-' + k)); return isNaN(v) ? -Infinity : v; }
  d.querySelectorAll('[data-sort-list]').forEach(function (ctl) {
    var list = d.getElementById(ctl.getAttribute('data-sort-list'));
    ctl.addEventListener('click', function (ev) {
      var b = ev.target.closest('button[data-k]');
      if (!b || !list) return;
      var k = b.getAttribute('data-k');
      ctl.querySelectorAll('button').forEach(function (x) {
        x.classList.toggle('on', x === b);
        x.setAttribute('aria-pressed', x === b ? 'true' : 'false');
      });
      var items = Array.prototype.slice.call(list.children).filter(function (c) { return c.hasAttribute('data-weight'); });
      items.sort(function (a, c) { return num(c, k) - num(a, k); });
      items.forEach(function (it) { list.appendChild(it); });
    });
  });

  function cellValue(row, i) { var v = parseFloat(row.cells[i].getAttribute('data-v')); return isNaN(v) ? -Infinity : v; }
  d.querySelectorAll('table.sortable').forEach(function (t) {
    t.querySelectorAll('th[data-col]').forEach(function (th) {
      th.addEventListener('click', function () {
        var i = +th.getAttribute('data-col'), body = t.tBodies[0], desc = th.getAttribute('aria-sort') !== 'descending';
        t.querySelectorAll('th').forEach(function (x) { x.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort', desc ? 'descending' : 'ascending');
        var rows = Array.prototype.slice.call(body.rows);
        rows.sort(function (a, b) { return desc ? cellValue(b, i) - cellValue(a, i) : cellValue(a, i) - cellValue(b, i); });
        rows.forEach(function (r) { body.appendChild(r); });
      });
    });
  });

  var pick = d.getElementById('scan-pick');
  if (pick) pick.addEventListener('change', function () {
    d.querySelectorAll('.scan').forEach(function (s) { s.hidden = s.getAttribute('data-scan') !== pick.value; });
  });
})();
"""


# ---------------------------------------------------------------- small pieces


def _link(item: dict | None) -> str:
    if not item:
        return ""
    source = str(item.get("source", ""))
    raw = str(item["title"])
    if source and raw.endswith(" - " + source):  # Google News adds the source to the title; the line shows it anyway
        raw = raw[: -len(" - " + source)]
    title = e(raw)
    url = str(item.get("url", ""))
    if url.startswith(("http://", "https://")):
        title = f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">{title}</a>'
    return f'{title} <span class="muted">· {e(source)}</span>'


def _sources(ids, news: dict) -> str:
    links = [link for link in (_link(news.get(i)) for i in ids or []) if link]
    return f'<div class="src">{"<br>".join(links)}</div>' if links else ""


def _pill(html: str, cls: str = "", tip: str = "") -> str:
    """html is already escaped by the caller; tip is plain text."""
    attrs = f' tabindex="0" data-tip="{e(tip)}"' if tip else ""
    return f'<span class="pill {e(cls)}"{attrs}><i></i>{html}</span>'


def _kpi(label: str, value: str, sub: str = "", tip: str = "") -> str:
    """label and tip are plain text; value and sub are HTML the caller already escaped."""
    attrs = f' tabindex="0" data-tip="{e(tip)}"' if tip else ""
    return (f'<div class="kpi"{attrs}><div class="l">{e(label)}</div><div class="v">{value}</div>'
            f'<div class="s">{sub}</div></div>')


def _card(body: str, title: str = "", sub: str = "", right: str = "", cls: str = "", anchor: str = "") -> str:
    """title is plain text; body, sub and right are HTML the caller already escaped."""
    head = ""
    if title or right:
        sub_html = f'<div class="sub">{sub}</div>' if sub else ""
        head = f'<div class="ch"><div><h2>{e(title)}</h2>{sub_html}</div>{right}</div>'
    ident = f' id="{e(anchor)}"' if anchor else ""
    return f'<div class="card {cls}"{ident}>{head}{body}</div>'


def _ph(title: str, sub: str = "", right: str = "") -> str:
    sub_html = f"<p>{sub}</p>" if sub else ""
    return f'<div class="ph"><div><h1>{e(title)}</h1>{sub_html}</div>{right}</div>'


def _heat(n: int) -> tuple[str, str]:
    """How busy a theme is in today's brief: a pill class and plain words."""
    if n >= 2:
        return "busy", f"busy · {n} events today"
    if n == 1:
        return "active", "active · 1 event today"
    return "quiet", "quiet today"


def _label(ctx: dict, tid: str) -> str:
    return ctx["theme_labels"].get(tid, tid)


def _v(x) -> str:
    """A sort key for a table cell."""
    return "" if x is None else f"{x:.6f}"


def _lead(ctx: dict) -> str:
    brief = ctx["brief"]
    if brief is None:
        return f'<p class="muted">{NO_BRIEF}</p>'
    if brief.get("summary"):
        return f'<p class="lead">{e(brief["summary"])}</p>'
    return f'<p class="muted">{QUIET}</p>'


def _mini_bars(rows: list) -> str:
    """rows: [(label, share)] as small bars on one scale."""
    if not rows:
        return '<p class="muted small">None.</p>'
    top = max([v for _, v in rows] + [1e-9])
    return "".join(
        f'<div class="mb"><span>{e(label)}</span><span class="mb-t"><i style="width:{100 * v / top:.1f}%"></i></span>'
        f'<span class="mb-v">{pct(v)}</span></div>'
        for label, v in rows
    )


def _matter(ctx: dict) -> list[str]:
    """The themes that matter to this user today: 2% or more of the portfolio or named by an open view (the code's
    floor), any theme the AI chose to cover, and this week's blind spots. Busiest first, then the biggest."""
    covered = [t["id"] for t in (ctx["brief"] or {}).get("themes", [])]
    blind = [b["id"] for b in ctx["blind_spots"]]
    themes = ctx["exposure"]["themes"]
    ids = [t for t in dict.fromkeys(ctx["must_cover"] + covered + blind) if t in themes]
    return sorted(ids, key=lambda t: (-ctx["heat"].get(t, 0), -themes[t]["you"]))


def _watch_items(ctx: dict) -> list[dict]:
    """What the brief says to watch, and the dates from the user's own record, numbered in date order."""
    items = [{"date": w.get("when"), "what": w["what"], "news_ids": w.get("news_ids") or [],
              "themes": w.get("themes") or [], "holdings": w.get("holdings") or [], "record": False}
             for w in (ctx["brief"] or {}).get("watch", [])]
    items += [{"date": w["date"], "what": w["what"], "news_ids": [], "themes": [], "holdings": [], "record": True}
              for w in ctx["record_watch"]]
    items.sort(key=lambda w: (w["date"] is None, w["date"] or ""))
    for n, w in enumerate(items, start=1):
        w["n"] = n
    return items


def _when(day: str | None, today: dt.date) -> str:
    if not day:
        return '<span class="wd"><b>No date</b><small>ongoing</small></span>'
    days = (dt.date.fromisoformat(day) - today).days
    if days == 0:
        note = "today"
    elif days == 1:
        note = "tomorrow"
    elif days > 0:
        note = f"in {days} days"
    else:
        note = f"{-days} days overdue"
    return f'<span class="wd"><b>{e(day)}</b><small>{note}</small></span>'


def _watch_list(items: list[dict], ctx: dict) -> str:
    if not items:
        return '<p class="muted">Nothing to watch yet.</p>'
    today = dt.date.fromisoformat(ctx["date"])
    rows = []
    for w in items:
        tags = "".join(_pill(e(_label(ctx, t))) for t in w["themes"])
        tags += "".join(_pill(e(s), "you") for s in w["holdings"])
        origin = '<div class="small muted">From your own record</div>' if w["record"] else ""
        num = "num rec" if w["record"] else "num"
        tag_html = f"<div>{tags}</div>" if tags else ""
        rows.append(f'<li><span class="{num}">{w["n"]}</span>{_when(w["date"], today)}<div><div>{e(w["what"])}</div>'
                    f'{origin}{_sources(w["news_ids"], ctx["news"])}{tag_html}</div></li>')
    return f'<ol class="watch">{"".join(rows)}</ol>'


def _event(ev: dict, ctx: dict, full: bool = True) -> str:
    """One event. Full: the four questions. Short: what happened and the money, for the overview and holdings."""
    sources = _sources(ev.get("news_ids"), ctx["news"])
    if not full:
        return f'<article class="ev"><h3>{e(ev["what"])}</h3><p class="small ink2">{e(ev["money"])}</p>{sources}</article>'
    touches = ev.get("touches") or {}
    chips = "".join(_pill(e(_label(ctx, t))) for t in touches.get("themes") or [])
    chips += "".join(_pill(f'{e(s)} · {pct(ctx["weights"].get(s))}', "you") for s in touches.get("holdings") or [])
    chips = chips or '<span class="muted">nothing you hold</span>'
    effects = "".join(
        f'<div class="small eff">{_pill(e(v["effect"]), v["effect"])}<b>{e(v["view_id"])}</b>: {e(v.get("why", ""))}</div>'
        for v in ev.get("views") or []
    )
    return (f'<article class="ev"><h3>{e(ev["what"])}</h3>{sources}'
            f'<p><span class="lab">Money</span>{e(ev["money"])}</p>'
            f'<div><span class="lab">Touches</span>{chips}</div>{effects}</article>')


# ---------------------------------------------------------------- Overview


def _overview(ctx: dict) -> str:
    perf, brief = ctx["perf"], ctx["brief"] or {}
    ret = perf.get("returns", {})
    you, world = ret.get("portfolio", {}), ret.get("world", {})
    themes = ctx["exposure"]["themes"]
    tilt = max(themes.values(), key=lambda r: abs(r["you"] - r["world"]))
    events = brief.get("events", [])
    views = ctx["views"]
    nxt = min(views, key=lambda v: v["resolves_by"]) if views else None
    busiest = max(ctx["heat"].items(), key=lambda kv: kv[1], default=None)
    if busiest:
        news_sub = "Busiest: " + e(_label(ctx, busiest[0]))
    else:
        news_sub = "A quiet day" if ctx["brief"] else "No brief yet today"
    kpis = "".join([
        _kpi("Today", move(you.get("1D")), "World index " + move(world.get("1D"))),
        _kpi("Past year, today's mix", move(you.get("1Y")), "World index " + move(world.get("1Y")),
             tip="Today's holdings at today's weights, replayed over the past year. It is not your actual past return."),
        _kpi("Biggest tilt", e(tilt["label"]), f"You {pct(tilt['you'])} · world {pct(tilt['world'])}"),
        _kpi("News today", f"{len(events)} event{'' if len(events) == 1 else 's'}", news_sub),
        _kpi("Open views", str(len(views)), f"Next deadline {e(nxt['resolves_by'])}" if nxt else "Write one with /setup"),
    ])

    lines = perf.get("lines", {})
    line = ch.line_chart([
        {"name": "You (today's mix)", "cls": "you", "points": lines.get("portfolio", [])},
        {"name": f"World index ({ctx['benchmark']})", "cls": "world", "points": lines.get("world", [])},
    ], height=250, label="Your portfolio against the world index over the past year")
    chart = _card(line, "Past year: your mix against the world index",
                  sub=f"In {e(ctx['home'])}, indexed to the first day. Prices cover {pct(perf.get('coverage'), 0)} of your portfolio.")

    chips = []
    for t in _matter(ctx):
        cls, words = _heat(ctx["heat"].get(t, 0))
        chips.append(_pill(e(_label(ctx, t)), cls, tip=f"{_label(ctx, t)}: {words}"))
    brief_card = _card(
        f'{_lead(ctx)}<div class="sub mt">Themes that matter to you today</div><div class="mt8">{"".join(chips)}</div>'
        '<div class="small muted mt8">Filled dot: two or more events today. Faint: one. Hollow: none.</div>',
        "Morning brief", right='<a href="#world">News &amp; world &rarr;</a>')

    evs = "".join(_event(ev, ctx, full=False) for ev in events[:3]) or '<p class="muted">No events today.</p>'
    more = f'<a href="#world">All {len(events)} &rarr;</a>' if len(events) > 3 else ""
    watch = _watch_items(ctx)
    watch_more = '<a href="#world/world-watch">All &rarr;</a>' if len(watch) > 5 else ""
    biggest = sorted(themes.values(), key=lambda r: -max(r["you"], r["world"]))[:6]
    tilt_card = _card(ch.dumbbell([(r["label"], r["you"], r["world"]) for r in biggest]), "Your biggest themes",
                      sub="Share of your portfolio, looked through funds, next to a world index fund.",
                      right='<a href="#exposure">Exposure &rarr;</a>')
    if ctx["scans"]:
        s = ctx["scans"][0]
        t = s["totals"]
        body = (f'<p class="lead">{e(s["conflict"])}</p><p class="small muted">Scanned {e(s["date"])}</p>'
                '<div class="kpis mt8">'
                + _kpi("Where it would hurt", pct(t["you"]["hurt_share"]), "World index " + pct(t["world"]["hurt_share"]))
                + _kpi("Where it would help", pct(t["you"]["help_share"]), "World index " + pct(t["world"]["help_share"]))
                + "</div>")
        side = _card(body, "Latest conflict scan", right='<a href="#scenarios">Scenarios &rarr;</a>')
    else:
        side = _card('<p class="muted">No scans yet. In Claude Code, run <b>/scan</b> with any conflict, for example '
                     '<i>China blockade of Taiwan</i>, to see where it would reach your money.</p>',
                     "Conflict scans", right='<a href="#scenarios">Scenarios &rarr;</a>')
    return (
        _ph("Overview", f"{e(ctx['date'])} · shares of your portfolio, valued in {e(ctx['home'])}, next to a world index fund")
        + f'<div class="kpis">{kpis}</div>'
        + f'<div class="cols g21">{chart}{brief_card}</div>'
        + '<div class="cols g2">' + _card(evs, "Top events today", right=more)
        + _card(_watch_list(watch[:5], ctx), "Things to watch", right=watch_more) + "</div>"
        + f'<div class="cols g2">{tilt_card}{side}</div>'
    )


# ---------------------------------------------------------------- Holdings


def _holding(h: dict, ctx: dict, top: float, brief_themes: dict) -> str:
    r, sym = h["returns"], h["symbol"]
    keys = (("weight", h["weight"]), ("d1", r.get("1D")), ("m1", r.get("1M")), ("ytd", r.get("YTD")), ("y1", r.get("1Y")))
    attrs = " ".join(f'data-{k}="{v:.6f}"' for k, v in keys if v is not None)
    inside_themes = sorted(((t, s) for t, s in h["themes"].items() if s >= INSIDE_SHARE), key=lambda kv: -kv[1])
    pills = "".join(_pill(e(_label(ctx, t))) for t, _ in inside_themes[:2])
    spark = ch.spark(h["spark"], f"{sym}, last 90 days")
    summary = (
        f'<summary><span class="h-name"><b>{e(sym)}</b><small>{e(h["name"])}</small></span>'
        f'<span class="h-w"><span class="wbar"><i style="width:{100 * h["weight"] / top:.1f}%"></i></span>{pct(h["weight"])}</span>'
        f'<span class="h-r">{move(r.get("1D"))}</span><span class="h-r">{move(r.get("1M"))}</span>'
        f'<span class="h-r hide-sm">{move(r.get("YTD"))}</span><span class="h-r hide-sm">{move(r.get("1Y"))}</span>'
        f'<span class="h-s hide-sm">{spark}</span><span class="h-t hide-sm">{pills}</span></summary>'
    )
    if h["kind"] == "cash":
        chart = '<p class="muted">Cash has no price line. It counts as a zero return in every replay.</p>'
    else:
        chart = ch.line_chart([{"name": sym, "cls": "you", "points": h["line"]},
                               {"name": "World index", "cls": "world", "points": ctx["perf"].get("world_weekly", [])}],
                              height=200, label=f"{sym} against the world index, past year, weekly")
    events = (ctx["brief"] or {}).get("events", [])
    today = ""
    if h["note"]:
        today += f'<p>{e(h["note"]["note"])}</p>{_sources(h["note"].get("news_ids"), ctx["news"])}'
    today += "".join(_event(events[i], ctx, full=False) for i in h["events"])
    today = today or '<p class="muted small">Nothing in today\'s brief touches it directly.</p>'
    env = []
    for t, s in inside_themes:
        entry = brief_themes.get(t)
        cls, words = _heat(ctx["heat"].get(t, 0))
        state = (f'<p class="small">{e(entry["state"])}</p>' if entry
                 else '<p class="small muted">Not covered in today\'s brief.</p>')
        env.append(f'<div><b>{e(_label(ctx, t))}</b> {_pill(e(words), cls)}'
                   f'<span class="small muted">{pct(s, 0)} of this holding</span>{state}</div>')
    env_html = f'<div class="list">{"".join(env)}</div>' if env else '<p class="muted small">In no theme above 2%.</p>'
    if h["kind"] == "fund":
        inside = (f'<h3>Largest companies inside</h3>{_mini_bars(h["inside"])}'
                  f'<h3 class="mt">Countries inside</h3>{_mini_bars(h["countries"])}')
    elif h["kind"] == "cash":
        inside = ""
    else:
        inside = f'<h3>Where it is listed or based</h3>{_mini_bars(h["countries"])}'
    return (
        f'<details class="hold" id="h-{e(sym)}" {attrs}>{summary}<div class="h-body cols g2">'
        f'<div>{chart}<div class="mt">{inside}</div></div>'
        f'<div><h3>In today\'s brief</h3>{today}<h3 class="mt">The world around it</h3>{env_html}</div>'
        f'</div></details>'
    )


def _holdings(ctx: dict) -> str:
    rows = ctx["holdings"]
    ret = ctx["perf"].get("returns", {})
    periods = ("1D", "1W", "1M", "3M", "YTD", "1Y")
    head = "".join(f'<th class="n">{p}</th>' for p in periods)
    pairs = (("You (today's mix)", ret.get("portfolio", {})), (f"World index ({ctx['benchmark']})", ret.get("world", {})))
    body = "".join(
        f"<tr><td>{e(name)}</td>" + "".join(f'<td class="n">{move(r.get(p))}</td>' for p in periods) + "</tr>"
        for name, r in pairs
    )
    period_card = _card(f'<div class="tw"><table><thead><tr><th></th>{head}</tr></thead><tbody>{body}</tbody></table></div>',
                        "Your mix against the world index",
                        sub=f"Price moves in {e(ctx['home'])}. Your mix is today's holdings at today's weights.")
    top = max([h["weight"] for h in rows] + [1e-9])
    buttons = []
    for k, label in (("weight", "Weight"), ("d1", "1D"), ("m1", "1M"), ("ytd", "YTD"), ("y1", "1Y")):
        on = ' class="on" aria-pressed="true"' if k == "weight" else ' aria-pressed="false"'
        buttons.append(f'<button type="button" data-k="{k}"{on}>{label}</button>')
    sort = f'<div class="segctl" role="group" aria-label="Sort holdings by" data-sort-list="hold-list">{"".join(buttons)}</div>'
    brief_themes = {t["id"]: t for t in (ctx["brief"] or {}).get("themes", [])}
    header = ('<div class="hl-head"><span>Holding</span><span>Weight</span><span>1D</span><span>1M</span>'
              '<span class="hide-sm">YTD</span><span class="hide-sm">1Y</span><span class="hide-sm">90 days</span>'
              '<span class="hide-sm">Themes</span></div>')
    items = "".join(_holding(h, ctx, top, brief_themes) for h in rows)
    return (
        _ph("Holdings", "Open a holding to see its price line, what is inside it, today's news on it and the themes around it.",
            sort)
        + period_card
        + f'<div id="hold-list">{header}{items}</div>'
    )


# ---------------------------------------------------------------- News & world


def _theme_card(tid: str, ctx: dict, entry: dict | None, blind: bool) -> str:
    x = ctx["exposure"]["themes"][tid]
    cls, words = _heat(ctx["heat"].get(tid, 0))
    proxy = ctx["theme_proxies"].get(tid, "")
    pr = ctx["perf"].get("proxies", {}).get(proxy, {})
    wr = ctx["perf"].get("returns", {}).get("world", {})
    weeks = ctx["perf"].get("theme_weeks", {}).get(tid, [])
    top = max(x["you"], x["world"], 1e-9)
    shares = (
        f'<div class="share"><span>You</span><span class="mb-t"><i style="width:{100 * x["you"] / top:.1f}%"></i></span>'
        f'<b>{pct(x["you"])}</b></div>'
        f'<div class="share"><span>World</span><span class="mb-t"><i class="world" style="width:{100 * x["world"] / top:.1f}%">'
        f'</i></span><span>{pct(x["world"])}</span></div>'
    )
    if entry:
        words_html = (f'<p>{e(entry["state"])}</p><p class="small ink2"><span class="lab">For you</span>'
                      f'{e(entry["why_it_matters"])}</p>' + _sources(entry.get("news_ids"), ctx["news"]))
    else:
        words_html = '<p class="muted small">Not covered in today\'s brief.</p>'
    flag = '<div class="mt8"><span class="pill flag">Blind spot: busy in the news, little of it in your portfolio</span></div>' if blind else ""
    moves = (f'<div class="small ink2 mt8">{e(proxy)}: 1W {move(pr.get("1W"))} · 1M {move(pr.get("1M"))} '
             f'<span class="muted">(world index 1W {pct(wr.get("1W"), signed=True)}, 1M {pct(wr.get("1M"), signed=True)})</span></div>')
    strip = ""
    if weeks:
        tips = [f"Week to {w[0]}: {proxy} {gap(w[1])} against the world index" for w in weeks]
        strip = (f'<div class="small muted mt8">Last {len(weeks)} weeks, {e(proxy)} against the world index</div>'
                 + ch.strip([w[1] for w in weeks], tips))
    views = [v for v in ctx["views"] if any(t["id"] == tid for t in v["themes"])]
    view_pills = "".join(_pill(f'{e(v["id"])} · {v["probability"] * 100:.0f}%', "you") for v in views)
    views_html = f'<div class="mt8">{view_pills}</div>' if view_pills else ""
    return (f'<div class="card tcard"><h2>{e(x["label"])} {_pill(e(words), cls)}</h2>{shares}{words_html}{flag}'
            f'{moves}{strip}{views_html}</div>')


def _ripples(ctx: dict) -> str:
    ripples = (ctx["brief"] or {}).get("ripples", [])
    sub = ("How today's events spread from one theme to another, as your AI traced them from the news. "
           "AI build-out sits in the middle when a ripple reaches it.")
    if not ripples:
        return _card('<p class="muted">No ripples traced today.</p>', "Ripple map", sub=sub)
    themes = ctx["exposure"]["themes"]
    ids = list(dict.fromkeys([r["from"] for r in ripples] + [r["to"] for r in ripples]))
    center = "ai_buildout" if "ai_buildout" in ids else None
    nodes = [{"id": t, "label": _label(ctx, t), "weight": themes.get(t, {}).get("you", 0)} for t in ids]
    edges = [{"from": r["from"], "to": r["to"], "cls": r["effect"],
              "tip": f'{_label(ctx, r["from"])} to {_label(ctx, r["to"])}: {RIPPLE_WORD[r["effect"]]}. {r["why"]}'}
             for r in ripples]
    rows = "".join(
        f'<div><div><b>{e(_label(ctx, r["from"]))}</b> &rarr; <b>{e(_label(ctx, r["to"]))}</b> '
        f'{_pill(RIPPLE_WORD[r["effect"]], r["effect"])}</div><p class="small">{e(r["why"])}</p>'
        f'{_sources(r.get("news_ids"), ctx["news"])}</div>'
        for r in ripples
    )
    graph = (f'<div>{ch.network(nodes, edges, center=center, uid="rip")}'
             '<p class="small muted">A bigger circle is a bigger share of your portfolio.</p></div>')
    return _card(f'<div class="cols g2">{graph}<div class="list">{rows}</div></div>', "Ripple map", sub=sub)


def _world(ctx: dict) -> str:
    brief = ctx["brief"] or {}
    themes = ctx["exposure"]["themes"]
    matter = _matter(ctx)
    entries = {t["id"]: t for t in brief.get("themes", [])}
    blind_ids = {b["id"] for b in ctx["blind_spots"]}
    events = brief.get("events", [])
    lead_card = _card(_lead(ctx), "Morning brief",
                      sub=f"{len(events)} events from today's headlines. Every claim links to its source.")
    cards = "".join(_theme_card(t, ctx, entries.get(t), t in blind_ids) for t in matter)
    matter_html = (f'<div class="cols g3">{cards}</div>' if cards
                   else '<p class="muted">No theme is 2% of your portfolio, and no open view names one.</p>')

    watch = _watch_items(ctx)
    dated = [{"date": w["date"], "n": w["n"], "tip": f'{w["date"]}: {w["what"]}'} for w in watch if w["date"]]
    watch_card = _card(ch.timeline(dated, dt.date.fromisoformat(ctx["date"])) + _watch_list(watch, ctx), "Things to watch",
                       sub="Dates and developments from the news, and deadlines from your own record. "
                           "The numbered dots are the next 90 days.", anchor="world-watch")
    evs = "".join(_event(ev, ctx) for ev in events) or '<p class="muted">No events today.</p>'
    events_card = _card(evs, "Today's events",
                        sub="1. What happened · 2. Who pays, who gets paid · 3. What it touches · 4. For or against your views")

    weeks_by = ctx["perf"].get("theme_weeks", {})
    cols = sorted({w[0] for rows in weeks_by.values() for w in rows})
    order = sorted(themes, key=lambda t: -themes[t]["you"])
    heat_rows = []
    for t in order:
        m = {w[0]: w[1] for w in weeks_by.get(t, [])}
        proxy = ctx["theme_proxies"].get(t, "")
        tips = [f"{_label(ctx, t)} ({proxy}), week to {c}: {gap(m[c])} against the world index" if c in m
                else f"{_label(ctx, t)}: no prices for the week to {c}" for c in cols]
        heat_rows.append((_label(ctx, t), [m.get(c) for c in cols], tips))
    short = [dt.date.fromisoformat(c).strftime("%d %b") for c in cols]
    heat = (ch.heatmap(cols, heat_rows, "diverging", col_labels=short, vmax=0.05) if cols
            else '<p class="muted">Not enough prices yet.</p>')
    heat_card = _card(heat, "Theme proxies against the world index, last 12 weeks",
                      sub="Each proxy ETF's weekly return minus the world index's, in your currency. "
                          "Full colour is 5 points or more.")

    nh = ctx["news_heat"]
    busy_rows = []
    for t, counts in nh["rows"].items():
        if any(counts):
            tips = [f"{_label(ctx, t)}, {d}: {c} event{'' if c == 1 else 's'}" for d, c in zip(nh["dates"], counts)]
            busy_rows.append((_label(ctx, t), counts, tips))
    days_short = [dt.date.fromisoformat(d).strftime("%d %b") for d in nh["dates"]]
    busy = (ch.heatmap(nh["dates"], busy_rows, "sequential", col_labels=days_short, fmt=lambda v: f"{v:g}")
            if busy_rows else '<p class="muted">No events logged in the last two weeks yet.</p>')
    busy_card = _card(busy, "Events per theme, last 14 days",
                      sub="From your evidence log: one count for each event that touched the theme.")

    proxies = ctx["perf"].get("proxies", {})
    others = [t for t in order if t not in matter]
    if others:
        rows_html = "".join(
            f'<tr><td>{e(themes[t]["label"])}</td><td class="n">{pct(themes[t]["you"])}</td>'
            f'<td class="n muted">{pct(themes[t]["world"])}</td>'
            f'<td class="n">{move(proxies.get(ctx["theme_proxies"].get(t), {}).get("1W"))}</td></tr>'
            for t in others
        )
        other_body = ('<div class="tw"><table><thead><tr><th>Theme</th><th class="n">You</th><th class="n">World</th>'
                      f'<th class="n">Proxy 1W</th></tr></thead><tbody>{rows_html}</tbody></table></div>')
    else:
        other_body = '<p class="muted">None: every theme matters to you today.</p>'
    other_card = _card(other_body, "Other themes",
                       sub="Under 2% of your portfolio, named by no open view, and not in today's brief.")
    blind = "".join(
        f'<div><b>{e(b["label"])}</b><p class="small">{b["events"]} events in the news this week. You: {pct(b["you"])}. '
        f'World index: {pct(b["world"])}.</p><ul class="small">{"".join(f"<li>{e(w)}</li>" for w in b["recent"])}</ul></div>'
        for b in ctx["blind_spots"]
    )
    blind_card = _card(f'<div class="list">{blind}</div>' if blind else '<p class="muted small">None this week.</p>',
                       "Blind spots", sub="Busy in the news this week, where you hold nothing or under a quarter of the "
                                          "world index's share. Where to look, not what to buy.")
    return (
        _ph("News & world", "Today's news, read through four questions, for the themes that matter to your money.")
        + lead_card
        + '<div class="sec"><h2>Themes that matter to you</h2><p class="sub">2% or more of your portfolio, named by one of '
          'your open views, covered by your AI today, or a blind spot. Busiest first.</p></div>'
        + matter_html + _ripples(ctx) + watch_card + events_card
        + f'<div class="cols g2">{heat_card}{busy_card}</div>'
        + f'<div class="cols g2">{other_card}{blind_card}</div>'
    )


# ---------------------------------------------------------------- Exposure


def _exposure(ctx: dict) -> str:
    x = ctx["exposure"]
    themes = x["themes"]
    order = sorted(themes, key=lambda t: -max(themes[t]["you"], themes[t]["world"]))
    over = max(themes.values(), key=lambda r: r["you"] - r["world"])
    under = min(themes.values(), key=lambda r: r["you"] - r["world"])
    kpis = "".join([
        _kpi("Most over the world index", e(over["label"]), gap(over["you"] - over["world"])),
        _kpi("Most under the world index", e(under["label"]), gap(under["you"] - under["world"])),
        _kpi("Theme betas cover", pct(x.get("beta_coverage"), 0), "of your portfolio, from 2 years of weekly prices"),
        _kpi("Not looked through", pct(x.get("unresolved") or 0), "of your portfolio, in funds the tool cannot open"),
    ])
    dumb = _card(ch.dumbbell([(themes[t]["label"], themes[t]["you"], themes[t]["world"]) for t in order]),
                 "Every theme: you against the world index",
                 sub="Funds are broken into the companies they hold. Core members count in full, partial members half.")
    sells = _card(
        ch.diverging([(s["name"], f'{s["start"]} to {s["end"]} · covers {pct(s["coverage"], 0)}', s["you"], s["world"])
                      for s in x["sell_offs"]]),
        "Past sell-offs, replayed on today's holdings",
        sub="Today's mix held through each window, next to the world index, in your currency.")

    held = [h for h in ctx["holdings"] if h["themes"]]
    cols = [t for t in sorted(themes, key=lambda t: -themes[t]["you"]) if themes[t]["you"] > 0]
    if held and cols:
        rows = [(h["symbol"], [h["weight"] * h["themes"].get(t, 0.0) for t in cols]) for h in held]
        matrix = ch.heat_table([_label(ctx, t) for t in cols], rows, total=("All holdings", [themes[t]["you"] for t in cols]))
    else:
        matrix = '<p class="muted">No holding sits in a theme yet.</p>'
    matrix_card = _card(matrix, "Where each theme comes from",
                        sub="Each cell is the share of your whole portfolio that one holding puts into one theme. "
                            "Deeper blue is more.")

    body = []
    for t in order:
        r = themes[t]
        ww = r.get("worst_weeks") or {}
        names_you = ", ".join(f"{e(m)} {pct(s)}" for m, s in r["names_you"][:10]) or "none"
        names_world = ", ".join(f"{e(m)} {pct(s)}" for m, s in r["names_world"][:10]) or "none"
        beta_you = DASH if r["beta_you"] is None else f"{r['beta_you']:.2f}"
        beta_world = DASH if r["beta_world"] is None else f"{r['beta_world']:.2f}"
        diff = r["you"] - r["world"]
        body.append(
            f'<tr><td><b>{e(r["label"])}</b><details class="more"><summary>names counted</summary><div class="small">'
            f'<b>You:</b> {names_you}<br><b>World:</b> {names_world}</div></details></td>'
            f'<td class="n" data-v="{_v(r["you"])}">{pct(r["you"])}</td>'
            f'<td class="n muted" data-v="{_v(r["world"])}">{pct(r["world"])}</td>'
            f'<td class="n" data-v="{_v(diff)}">{gap(diff)}</td>'
            f'<td class="n" data-v="{_v(r["beta_you"])}">{beta_you}</td>'
            f'<td class="n muted">{beta_world}</td>'
            f'<td class="n" data-v="{_v(ww.get("you"))}">{pct(ww.get("you"), signed=True)}</td>'
            f'<td class="n muted">{pct(ww.get("world"), signed=True)}</td>'
            f'<td class="n muted">{e(r["proxy"])} {pct(ww.get("proxy"), signed=True)}</td></tr>'
        )
    spec = (("Theme", None), ("You", 1), ("World", 2), ("Gap", 3), ("Beta you", 4), ("Beta world", None),
            ("Worst weeks you", 6), ("World", None), ("Proxy", None))
    head = "".join(
        "<th>Theme</th>" if name == "Theme"
        else f'<th class="n" data-col="{i}"><button type="button">{e(name)}</button></th>' if i is not None
        else f'<th class="n">{e(name)}</th>'
        for name, i in spec
    )
    table = _card(
        f'<div class="tw"><table class="sortable"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
        f'<p class="small muted">Theme beta: how much the portfolio moved per 1% move in the theme\'s proxy ETF, weekly over '
        f'2 years, in {e(ctx["home"])}. Worst weeks: the average return in the proxy\'s 10 worst weeks of those 2 years. '
        'Betas from calm years understate how closely things move together in a real crash.</p>',
        "Theme details", sub="Select a column heading to sort.")

    countries = x.get("countries") or {"you": dict(x["regions"]["you"]), "world": dict(x["regions"]["world"])}
    regions = _card(ch.stacked([("You", countries["you"]), ("World index", countries["world"])]),
                    "Where your companies are based", sub="Look-through shares by country. Smaller ones fold into Other.")
    currencies = _card(ch.stacked([("You", dict(x["currencies"]["you"]))]), "Currencies under your holdings",
                       sub="The currency of each company's listing, after looking through funds.")
    notes = "".join(f"<li>{e(n)}</li>" for n in ctx["notes"]) or "<li>None</li>"
    return (
        _ph("Exposure", "Where your money actually sits, looked through funds, next to a world index fund.")
        + f'<div class="kpis">{kpis}</div>'
        + f'<div class="cols g2">{dumb}{sells}</div>'
        + matrix_card
        + table
        + f'<div class="cols g2">{regions}{currencies}</div>'
        + _card(f'<ul class="small">{notes}</ul>', "Data notes")
    )


# ---------------------------------------------------------------- Scenarios


def _scan(s: dict, hidden: bool) -> str:
    t = s["totals"]
    news = {n["id"]: n for n in s.get("news", [])}
    kpis = "".join([
        _kpi("Where it would hurt", pct(t["you"]["hurt_share"]), "World index " + pct(t["world"]["hurt_share"]),
             tip="Share of the portfolio in any theme or region the scan marks as hurt. Each company counts once."),
        _kpi("Where it would help", pct(t["you"]["help_share"]), "World index " + pct(t["world"]["help_share"])),
        _kpi("Hurt, weighted by strength", pct(t["you"]["hurt_score"]), "World index " + pct(t["world"]["hurt_score"]),
             tip="Each share counted at the strength of the strongest channel reaching it: low a third, medium two thirds, "
                 "high in full."),
        _kpi("Mixed", pct(t["you"]["mixed_share"]), "World index " + pct(t["world"]["mixed_share"])),
    ])
    points = [{"group": c["effect"], "label": c["label"], "you": c["you"], "world": c["world"],
               "cls": f'{c["effect"]} s-{c["strength"]}',
               "tip": f'{c["label"]} ({c["kind"]}): {SCAN_WORD.get(c["effect"], c["effect"])}, {c["strength"]} strength. '
                      f'You {pct(c["you"])}, world index {pct(c["world"])}. {c["why"]}'}
              for c in s["channels"]]
    groups = [(effect, f'{name}: {pct(t["you"][key])} of your portfolio, world index {pct(t["world"][key])}')
              for effect, name, key in (("hurt", "Would hurt", "hurt_share"), ("mixed", "Mixed", "mixed_share"),
                                        ("help", "Would help", "help_share"))]
    bubbles = _card(
        ch.legend([("hurt", "would hurt"), ("help", "would help"), ("mixed", "mixed")])
        + ch.bubble_map(points, groups)
        + '<p class="small muted mt8">A bubble\'s area is your share of the portfolio in that theme or region; the dashed '
          'ring is the world index\'s share on the same scale, so a ring outside the bubble means the world index holds '
          'more of it than you. Solid, lighter and faint fills are high, medium and low strength. Hover a bubble for '
          'your AI\'s reason.</p>',
        "Where the conflict reaches you", sub="Every theme and region the conflict reaches, sized by your money in it.")
    reach_rows = [(h["symbol"], f'{pct(h["weight"])} of your portfolio', h["hurt_share"], h["help_share"])
                  for h in s["holdings"] if h["weight"] > 0]
    holdings = _card(ch.balance(reach_rows), "Which holdings it reaches",
                     sub="The share of each holding that sits in a channel the conflict would hurt, or help.")

    analogs = s.get("analogs") or []
    if analogs:
        moves = ch.diverging([(a["name"], f'{a["start"]} to {a["end"]}', a["you"], a["world"]) for a in analogs])
        proxy_ids = [c["id"] for c in s["channels"] if c.get("proxy")]
        labels = {c["id"]: c["label"] for c in s["channels"]}
        table = ""
        if proxy_ids:
            head = "".join(f'<th class="n">{e(labels[i])}</th>' for i in proxy_ids)
            rows = "".join(
                f'<tr><td>{e(a["name"])}<div class="small muted">{e(a["why"])}</div></td>'
                + "".join(f'<td class="n">{move(a["proxies"].get(i))}</td>' for i in proxy_ids) + "</tr>"
                for a in analogs
            )
            table = (f'<div class="tw mt"><table><thead><tr><th>Window</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
                     '<p class="small muted">Each theme channel\'s proxy ETF over the same windows.</p>')
        analog_card = _card(moves + table, "Past episodes that looked like it",
                            sub="Today's holdings replayed over windows your AI picked. Every move computed in code.")
    else:
        analog_card = _card('<p class="muted">No past episodes given.</p>', "Past episodes")
    watch = "".join(f'<li><div>{e(w["what"])}</div>{_sources(w.get("news_ids"), news)}</li>' for w in s.get("watch") or [])
    watch_card = _card(f"<ul>{watch}</ul>" if watch else '<p class="muted">None given.</p>', "What to watch")
    ch_rows = "".join(
        f'<tr><td><b>{e(c["label"])}</b><div class="small muted">{e(c["kind"])}</div></td>'
        f'<td>{_pill(SCAN_WORD.get(c["effect"], e(c["effect"])), c["effect"])}</td><td>{e(c["strength"])}</td>'
        f'<td class="n" data-v="{_v(c["you"])}">{pct(c["you"])}</td>'
        f'<td class="n muted" data-v="{_v(c["world"])}">{pct(c["world"])}</td>'
        f'<td class="small">{e(c["why"])}</td></tr>'
        for c in s["channels"]
    )
    channel_table = _card(
        '<div class="tw"><table class="sortable"><thead><tr><th>Channel</th><th>Effect</th><th>Strength</th>'
        '<th class="n" data-col="3"><button type="button">You</button></th>'
        '<th class="n" data-col="4"><button type="button">World</button></th><th>Why</th></tr></thead>'
        f'<tbody>{ch_rows}</tbody></table></div>', "Channels",
        sub="Effect and strength are your AI's judgment; every share is computed in code.")
    banner = ('<div class="banner">Parts of this scan read like advice. They were let through with --allow-advice.</div>'
              if s.get("advice") else "")
    hide = " hidden" if hidden else ""
    asof = e(s.get("exposure_date") or s["date"])
    intro = _card(
        f'<p class="lead">{e(s["summary"])}</p>{_sources(s.get("news_ids"), news)}'
        '<p class="small muted mt8">A scan maps where a conflict would reach your money. It is not a forecast of whether '
        'it happens or of what prices do.</p>',
        s["conflict"], sub=f'Scanned {e(s["date"])}, from the past week\'s news and your holdings as of {asof}.')
    return (
        f'<div class="scan" data-scan="{e(s["slug"])}"{hide}>{banner}{intro}'
        f'<div class="kpis mt">{kpis}</div>'
        f'<div class="cols g2 mt">{bubbles}{holdings}</div>'
        f'<div class="cols g2 mt">{analog_card}{watch_card}</div>'
        f'<div class="mt">{channel_table}</div></div>'
    )


def _scenarios(ctx: dict) -> str:
    scans = ctx["scans"]
    intro = ("Name any conflict and your AI maps where it would reach your money, theme by theme and region by region, "
             "next to the world index.")
    if not scans:
        how = ('<p>In Claude Code, run <b>/scan</b> and name a conflict, for example <i>China blockade of Taiwan</i> or '
               '<i>Iran war and the Strait of Hormuz</i>.</p><p class="small muted">The code searches the past week\'s news '
               'for it and sends your AI the themes, regions and holdings as percentages. Your AI marks which ones the '
               'conflict would hurt or help, and how strongly; the code computes every number and draws the map here.</p>')
        return _ph("Scenarios", intro) + _card(how, "No scans yet")
    options = "".join(f'<option value="{e(s["slug"])}">{e(s["conflict"])} ({e(s["date"])})</option>' for s in scans)
    picker = (f'<label class="small muted">Scan <select id="scan-pick" class="scan-pick">{options}</select></label>'
              if len(scans) > 1 else "")
    return _ph("Scenarios", intro, picker) + "".join(_scan(s, i > 0) for i, s in enumerate(scans))


# ---------------------------------------------------------------- Views and Record


def _views(ctx: dict) -> str:
    head = _ph("Views", "Your calls, in your words. The evidence counts come from the briefs; only you change a probability.")
    if not ctx["views"]:
        return head + _card('<p class="muted">No open views. Run /setup to write your first ones.</p>')
    cards = []
    for v in ctx["views"]:
        ev = v["evidence"]
        week = "".join(_pill(f"{k} {ev['7'][k]}", k) for k in ("for", "against", "unclear"))
        month = f"{ev['30']['for']} for, {ev['30']['against']} against, {ev['30']['unclear']} unclear"
        themes = "".join(
            _pill(f"{e(t['label'])} {'&uarr;' if t['direction'] == 'up' else '&darr;'} · you {pct(t['you'])} · world {pct(t['world'])}")
            for t in v["themes"]
        )
        today = "".join(
            f'<div class="small eff">{_pill(e(x["effect"]), x["effect"])}{e(x["what"])} <span class="muted">{e(x["why"])}</span></div>'
            for x in v.get("today", [])
        )
        today_html = f'<div class="mt8"><span class="lab">Today</span>{today}</div>' if today else ""
        due = '<div class="banner">Past its deadline: resolve it now.</div>' if v["due"] else ""
        cards.append(_card(
            f'{due}<div class="row"><div class="bignum">{v["probability"] * 100:.0f}%</div>'
            f'<div class="small muted ar">resolves by {e(v["resolves_by"])}<br>{max(v["days_left"], 0)} days left</div></div>'
            f'<p>{e(v["statement"])}</p>{ch.step(v["created"], v["resolves_by"], v["forecasts"], ctx["date"])}'
            f'<p class="small">Last 7 days {week}<br><span class="muted">Last 30 days: {month}</span></p>'
            f'{today_html}<div class="mt8">{themes}</div><div class="small muted mt8">{e(v["id"])}</div>'
        ))
    return head + f'<div class="cols g3">{"".join(cards)}</div>'


def _decision_row(d: dict) -> str:
    size = f" · {d['size_pct']:g}%" if d["size_pct"] is not None else ""
    views = "".join(_pill(e(v)) for v in d["views"]) or '<span class="muted">none</span>'
    flags = "".join(f'<span class="pill flag">{e(f)}</span>' for f in d["flags"]) or '<span class="muted small">none</span>'
    return (f'<tr><td class="n">{e(d["date"])}</td><td>{e(d["action"])} <b>{e(d["symbol"])}</b>{size}'
            f'<div class="small muted">{e(d["reason"])}</div></td><td>{views}</td><td>{flags}</td></tr>')


def _record(ctx: dict) -> str:
    s = ctx["scores"]
    if s["count"]:
        sub = f"over {s['count']} resolved views. Lower is better; always saying 50% scores {s['coin_flip']}."
        score = f'<div class="kpis">{_kpi("Mean Brier score", format(s["mean"], ".3f"), sub)}</div>'
        if s["luck"]:
            score += '<p class="small muted">Under 20 resolved views, the score is mostly luck.</p>'
    else:
        score = '<p class="muted">No views have resolved yet. The score starts with the first one.</p>'
    parts = [_card(score, "Your calls, scored", sub="A time-weighted Brier score: every day's probability against what happened.")]
    resolved = "".join(
        f'<tr><td>{e(v["statement"])}</td><td>{e(v["result"])}</td>'
        f'<td class="n">{DASH if v["brier"] is None else format(v["brier"], ".3f")}</td></tr>'
        for v in s["views"]
    )
    if resolved:
        parts.append(_card('<div class="tw"><table><thead><tr><th>Resolved view</th><th>Outcome</th><th class="n">Brier</th>'
                           f'</tr></thead><tbody>{resolved}</tbody></table></div>', "Resolved views"))
    decisions = "".join(_decision_row(d) for d in reversed(ctx["decisions"]))
    decisions = decisions or '<tr><td colspan="4" class="muted">No decisions logged yet.</td></tr>'
    parts.append(_card(
        '<div class="tw"><table class="dec"><thead><tr><th class="n">Date</th><th>Decision</th><th>Views cited</th><th>Flags</th></tr></thead>'
        f'<tbody>{decisions}</tbody></table></div>',
        "Decisions", sub="Your trades, next to the views they cite. Flags are shown, never blocking."))
    reviews = "".join(
        f'<tr><td>{e(r["action"])} {e(r["symbol"])} on {e(r["date"])}</td><td class="n">{move(r["since"])}</td>'
        f'<td class="n">{move(r["world"])}</td></tr>'
        for r in ctx["reviews"]
    )
    if reviews:
        parts.append(_card(
            '<div class="tw"><table><thead><tr><th>Decision</th><th class="n">Stock since</th><th class="n">World since</th>'
            f'</tr></thead><tbody>{reviews}</tbody></table></div>'
            '<p class="small muted">One trade\'s outcome is mostly noise. This is a record, not a verdict.</p>',
            "What happened after"))
    return _ph("Record", "Were your calls right, and did your trades follow your own views?") + "".join(parts)


# ---------------------------------------------------------------- the page


def page(ctx: dict) -> str:
    counts = {"world": len((ctx["brief"] or {}).get("events", [])), "scenarios": len(ctx["scans"])}
    nav = "".join(
        f'<a href="#{pid}">{e(name)}' + (f'<span class="n">{counts[pid]}</span>' if counts.get(pid) else "") + "</a>"
        for pid, name in PAGES
    )
    builders = {"overview": _overview, "holdings": _holdings, "world": _world, "exposure": _exposure,
                "scenarios": _scenarios, "views": _views, "record": _record}
    pages = "".join(
        f'<section class="page{" on" if pid == "overview" else ""}" id="p-{pid}" aria-label="{e(name)}">'
        f'{builders[pid](ctx)}</section>'
        for pid, name in PAGES
    )
    banners = "".join(f'<div class="banner">{e(b)}</div>' for b in ctx["banners"])
    footer = ("<footer>whatstocks describes your own portfolio and your own stated views. It makes no recommendations "
              "and is not financial advice. Numbers are computed in code; the words are written by your AI from the linked "
              f"sources. Built {e(ctx['date'])}.</footer>")
    return (
        '<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>whatstocks {e(ctx["date"])}</title><style>{CSS}</style><script>{HEAD_JS}</script></head>'
        '<body><div class="shell">'
        f'<aside class="side"><div class="brand">whatstocks<small>{e(ctx["date"])} · {e(ctx["home"])}</small></div>'
        f'<nav class="nav" aria-label="Pages">{nav}</nav>'
        '<button type="button" class="toggle" id="theme" aria-label="Switch between light and dark">&#9680; Theme</button>'
        '<div class="side-foot">Percentages only: no amounts leave your computer.</div></aside>'
        f'<main><div class="wrap">{banners}{pages}{footer}</div></main></div>'
        f'<div id="tip" role="tooltip" hidden></div><script>{JS}</script></body></html>'
    )
