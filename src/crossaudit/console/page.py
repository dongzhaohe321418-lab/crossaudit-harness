"""The local CrossAudit workspace.

One centre of gravity: conversation and deliverables.  A narrow left rail
holds pins, recent chats and search; the centre is one chronological run that
narrates six user-visible states (understanding, working, checking, revising,
completed, needs your decision) projected from typed run-journal events; a
right context panel surfaces files, audit evidence, models, usage and compute
on demand.  The ledger remains the source of truth; the page only reshapes
committed evidence and ephemeral in-flight progress, and the independent
review stays collapsed until the person asks for the full record.

There is still one task write path. The composer uploads explicitly confirmed
files in bounded chunks, then posts only one opaque batch ID to ``/api/say``;
every task is routed through the same code as ``crossaudit talk``. Generated
files are downloadable only when the ledger's generator history names that
exact project-relative path.
"""
from __future__ import annotations

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CrossAudit</title>
<style>
/* CrossAudit console design system.
   Dark is the primary visual; light is a complete first-class variant.
   One centre of gravity: conversation and deliverables. Glass is reserved
   for navigation and transient chrome; work, evidence and deliverables stay
   on calm opaque surfaces so the audit record remains legible. */
:root,:root[data-theme="dark"]{
  color-scheme:dark;
  --bg:#100F0D;--panel:rgba(28,25,20,.72);--surface:#1A1712;--surface-2:#231F19;
  --surface-3:#2C271F;--text:#F1EDE6;--text-2:#ADA69B;--text-3:#79726A;
  --line:rgba(244,237,226,.09);--line-strong:rgba(244,237,226,.17);
  --hover:rgba(230,206,168,.09);--scrim-bg:rgba(10,8,5,.55);
  --state-understand:#98A1B0;--state-understand-bg:rgba(152,161,176,.12);
  --state-work:#6CA8F8;--state-work-bg:rgba(108,168,248,.14);
  --state-check:#AD97F4;--state-check-bg:rgba(173,151,244,.14);
  --state-revise:#5EC4DE;--state-revise-bg:rgba(94,196,222,.13);
  --state-done:#57C795;--state-done-bg:rgba(87,199,149,.13);
  --state-decide:#E9B45C;--state-decide-bg:rgba(233,180,92,.14);
  --pass:#57C795;--pass-bg:rgba(87,199,149,.13);
  --blocked:#F27E72;--blocked-bg:rgba(242,126,114,.14);
  --escalated:#E9B45C;--escalated-bg:rgba(233,180,92,.14);
  --role-g:#6CA8F8;--role-g-bg:rgba(108,168,248,.14);
  --role-a:#AD97F4;--role-a-bg:rgba(173,151,244,.14);
  --accent:#6CA8F8;--accent-bg:rgba(108,168,248,.14);
  --shadow-1:0 1px 2px rgba(4,8,16,.28);
  --shadow-2:0 2px 6px rgba(4,8,16,.28),0 8px 24px rgba(4,8,16,.24);
  --shadow-3:0 4px 12px rgba(3,6,12,.32),0 16px 48px rgba(3,6,12,.30);
  --shadow-4:0 8px 24px rgba(2,4,10,.38),0 32px 90px rgba(2,4,10,.34);
  --edge-highlight:inset 0 1px 0 rgba(255,250,240,.06);
  --glass-nav-bg:rgba(26,23,18,.74);--glass-sheet-bg:rgba(30,27,21,.82);
  --glass-palette-bg:rgba(34,30,23,.88);--glass-border:rgba(255,250,242,.08);
  --tint-a:rgba(108,168,248,.09);--tint-b:rgba(173,151,244,.06);
  /* Legacy aliases: ported flows resolve to the same token system. */
  --muted:var(--text-2);--faint:var(--text-3);
  --blue:var(--accent);--blue-bg:var(--accent-bg);
  --green:var(--pass);--green-bg:var(--pass-bg);
  --red:var(--blocked);--red-bg:var(--blocked-bg);
  --amber:var(--escalated);--amber-bg:var(--escalated-bg);
  --violet:var(--role-a);--violet-bg:var(--role-a-bg);
  --header-bg:var(--glass-nav-bg);--audit-border:rgba(173,151,244,.20);
  --glass:var(--glass-nav-bg);--glass-strong:var(--surface-2);
  --glass-edge:var(--glass-border);
  --glass-shadow:var(--edge-highlight),var(--shadow-3);
  --shadow:var(--shadow-2);--inverse:#EDF0F5;--inverse-text:#161B23;
  --send-hover:color-mix(in srgb,var(--accent) 86%,#fff);
  --font-ui:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display","Segoe UI","PingFang SC","Hiragino Sans GB",sans-serif;
  --font-mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  --font-label:var(--font-ui);
  --fs-caption:0.6875rem;--fs-label:0.75rem;--fs-body:0.8125rem;--fs-prose:0.875rem;
  --fs-title:0.9375rem;--fs-h2:1.125rem;--fs-h1:1.375rem;--fs-display:1.75rem;
  --sp-1:4px;--sp-2:8px;--sp-3:12px;--sp-4:16px;--sp-5:20px;--sp-6:24px;
  --sp-7:32px;--sp-8:40px;--sp-9:56px;--sp-10:72px;
  --r-xs:6px;--r-sm:8px;--r-md:10px;--r-lg:14px;--r-xl:18px;--r-pill:999px;
  --radius:var(--r-lg);
  --dur-instant:100ms;--dur-fast:180ms;--dur-base:240ms;--dur-slow:320ms;--dur-story:480ms;
  --ease-out:cubic-bezier(0.16,1,0.3,1);--ease-in:cubic-bezier(0.55,0,0.85,0.4);
  --spring:cubic-bezier(0.22,0.9,0.28,1);--spring-soft:cubic-bezier(0.3,1.12,0.3,1);
  --rail-w:264px;--ctx-w:320px;--topbar-h:52px;--thread-max:760px;
  --sidebar:var(--rail-w);--inspector:0px;--topbar-height:var(--topbar-h);
  --z-content:1;--z-chrome:40;--z-composer:50;--z-overlay:100;
  --z-sheet:60;--z-palette:80;--z-toast:90;
}
:root[data-theme="light"]{
  color-scheme:light;
  --bg:#EEF1F6;--panel:rgba(248,250,253,.74);--surface:#FFFFFF;--surface-2:#F2F5F9;
  --surface-3:#E8ECF2;--text:#1A1F27;--text-2:#5C6472;--text-3:#8C94A2;
  --line:rgba(52,64,84,.11);--line-strong:rgba(52,64,84,.22);
  --hover:rgba(38,92,178,.07);--scrim-bg:rgba(18,24,34,.38);
  --state-understand:#5F6875;--state-understand-bg:rgba(95,104,117,.10);
  --state-work:#2266D4;--state-work-bg:rgba(34,102,212,.10);
  --state-check:#6A4FC9;--state-check-bg:rgba(106,79,201,.10);
  --state-revise:#0E7E9E;--state-revise-bg:rgba(14,126,158,.10);
  --state-done:#177A53;--state-done-bg:rgba(23,122,83,.10);
  --state-decide:#96650E;--state-decide-bg:rgba(150,101,14,.10);
  --pass:#177A53;--pass-bg:rgba(23,122,83,.10);
  --blocked:#C33D33;--blocked-bg:rgba(195,61,51,.10);
  --escalated:#96650E;--escalated-bg:rgba(150,101,14,.10);
  --role-g:#2266D4;--role-g-bg:rgba(34,102,212,.10);
  --role-a:#6A4FC9;--role-a-bg:rgba(106,79,201,.10);
  --accent:#2266D4;--accent-bg:rgba(34,102,212,.10);
  --shadow-1:0 1px 2px rgba(38,50,70,.08);
  --shadow-2:0 2px 6px rgba(38,50,70,.07),0 8px 24px rgba(38,50,70,.07);
  --shadow-3:0 4px 12px rgba(30,42,62,.09),0 16px 48px rgba(30,42,62,.10);
  --shadow-4:0 8px 24px rgba(24,34,52,.12),0 32px 90px rgba(24,34,52,.14);
  --edge-highlight:inset 0 1px 0 rgba(255,255,255,.70);
  --glass-nav-bg:rgba(248,250,253,.74);--glass-sheet-bg:rgba(250,252,254,.82);
  --glass-palette-bg:rgba(252,253,255,.88);--glass-border:rgba(255,255,255,.65);
  --tint-a:rgba(73,145,246,.09);--tint-b:rgba(134,107,217,.06);
  --audit-border:rgba(106,79,201,.20);
  --inverse:#1A1F27;--inverse-text:#FFFFFF;
}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{margin:0;height:100%;overflow:hidden}
html{background:var(--bg)}
body{color:var(--text);background:
  radial-gradient(72% 62% at 88% -8%,var(--tint-a),transparent 66%),
  radial-gradient(55% 54% at -8% 96%,var(--tint-b),transparent 70%),var(--bg);
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display",
    "Segoe UI","PingFang SC","Hiragino Sans GB",sans-serif;
  font-size:13px;line-height:1.55;font-optical-sizing:auto;-webkit-font-smoothing:antialiased}
button,textarea,input,select{font:inherit;color:inherit}
button{cursor:pointer}
button,input,select,textarea{-webkit-tap-highlight-color:transparent;touch-action:manipulation}
button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,
a:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
  clip:rect(0,0,0,0);white-space:nowrap;border:0}
.spacer{margin-left:auto}
::selection{background:var(--accent-bg)}

/* A single outline icon language avoids font-dependent symbols in application chrome. */
.ui-icon,#hub-settings,#settings-open,#hub-theme,#theme-toggle,#sidebar-toggle,#back-projects,
#current-project-pin,#inspect-toggle,#inspect-close,#palette-open,.pin-button,.project-pin,.nav-icon,
.new-task>span:first-child,.hpc-host-intro-icon,.project-delete,.task-delete,.project-arrow,
[data-preview].artifact-action,.artifact-action[download],.pill-glyph,.review-mark,.review-chevron,
.deliverable-icon,.group-chevron,.decision-glyph,.banner-glyph,.rail-search-icon,.attach-glyph,
.send-glyph,.stop-glyph{font-size:0}
.ui-icon:before,#hub-settings:before,#settings-open:before,#hub-theme:before,#theme-toggle:before,
#sidebar-toggle:before,#back-projects:before,#current-project-pin:before,#inspect-toggle:before,
#inspect-close:before,#palette-open:before,.pin-button:before,.project-pin:before,.nav-icon:before,
.new-task>span:first-child:before,.hpc-host-intro-icon:before,.project-delete:before,
.task-delete:before,.project-arrow:before,[data-preview].artifact-action:before,
.artifact-action[download]:before,.pill-glyph:before,.review-mark:before,.review-chevron:before,
.deliverable-icon:before,.group-chevron:before,.decision-glyph:before,.banner-glyph:before,
.rail-search-icon:before,.attach-glyph:before,.send-glyph:before,.stop-glyph:before,
.top-project:after{content:"";display:block;width:17px;height:17px;background:currentColor;
  -webkit-mask:var(--ui-icon) center/contain no-repeat;mask:var(--ui-icon) center/contain no-repeat}
#hub-settings,#settings-open{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3Cpath d='M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21h-4v-.09A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3v-4h.09A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3h4v.09A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.14.36.35.7.6 1 .28.28.66.42 1.1.4H21v4h-.09A1.7 1.7 0 0 0 19.4 15Z'/%3E%3C/svg%3E")}
#hub-theme,#theme-toggle{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M20.7 15.1A9 9 0 1 1 8.9 3.3a7 7 0 0 0 11.8 11.8Z'/%3E%3C/svg%3E")}
:root[data-theme="dark"] #hub-theme,:root[data-theme="dark"] #theme-toggle{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'/%3E%3C/svg%3E")}
#sidebar-toggle{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M4 6h16M4 12h11M4 18h16'/%3E%3C/svg%3E")}
#back-projects{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m15 18-6-6 6-6'/%3E%3C/svg%3E")}
#current-project-pin,.pin-button,.project-pin{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m14 4 6 6-3 1-4 4-1 5-3-3-3-3 5-1 4-4 1-3Z'/%3E%3Cpath d='m5 19 4-4'/%3E%3C/svg%3E")}
#inspect-toggle{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='4' width='18' height='16' rx='3'/%3E%3Cpath d='M15 4v16'/%3E%3C/svg%3E")}
#inspect-close{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M6 6l12 12M18 6 6 18'/%3E%3C/svg%3E")}
#palette-open,.rail-search-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='6'/%3E%3Cpath d='m20 20-4.2-4.2'/%3E%3C/svg%3E")}
.new-task>span:first-child{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M12 5v14M5 12h14'/%3E%3C/svg%3E")}
.top-project{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E")}.top-project:after{width:13px;height:13px}
.nav-item[data-view="artifacts"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linejoin='round'%3E%3Cpath d='M6 3h8l4 4v14H6V3Z'/%3E%3Cpath d='M14 3v5h4M9 12h6M9 16h6'/%3E%3C/svg%3E")}
.nav-item[data-view="audits"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3 19 6v5c0 4.5-2.8 7.9-7 10-4.2-2.1-7-5.5-7-10V6l7-3Z'/%3E%3Cpath d='m9 12 2 2 4-4'/%3E%3C/svg%3E")}
.nav-item[data-view="models"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='6' y='6' width='12' height='12' rx='2'/%3E%3Cpath d='M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4'/%3E%3C/svg%3E")}
.nav-item[data-view="usage"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M5 19V9M12 19V5M19 19v-7'/%3E%3C/svg%3E")}
.nav-item[data-view="compute"] .nav-icon,.hpc-host-intro-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='4' width='18' height='16' rx='3'/%3E%3Cpath d='m7 9 3 3-3 3M13 15h4'/%3E%3C/svg%3E")}
.nav-item[data-view="tools"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Ccircle cx='7' cy='7' r='3'/%3E%3Ccircle cx='17' cy='7' r='3'/%3E%3Ccircle cx='7' cy='17' r='3'/%3E%3Cpath d='M14 17h6M17 14v6'/%3E%3C/svg%3E")}
.nav-item[data-view="evidence"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3 5 6v5c0 4.5 2.8 7.9 7 10 4.2-2.1 7-5.5 7-10V6l-7-3Z'/%3E%3Cpath d='M9 12h6M12 9v6'/%3E%3C/svg%3E")}
.nav-item[data-view="plan"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 4h14v16H5z'/%3E%3Cpath d='M9 9h6M9 13h6M9 17h4'/%3E%3C/svg%3E")}
.project-delete,.task-delete{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6'/%3E%3C/svg%3E")}
.project-arrow{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m9 6 6 6-6 6'/%3E%3C/svg%3E")}
[data-preview].artifact-action{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 12s3.3-6 9-6 9 6 9 6-3.3 6-9 6-9-6-9-6Z'/%3E%3Ccircle cx='12' cy='12' r='2.5'/%3E%3C/svg%3E")}
.artifact-action[download]{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3v12M7 10l5 5 5-5M5 20h14'/%3E%3C/svg%3E")}
.pill-understand .pill-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linejoin='round'%3E%3Cpath d='M5 5h14v11H9l-4 3V5Z'/%3E%3Cpath d='M8.5 10.5h.01M12 10.5h.01M15.5 10.5h.01'/%3E%3C/svg%3E")}
.pill-work .pill-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M13 5.5 18.5 11 8 21.5H2.5V16L13 5.5Z'/%3E%3Cpath d='m15.5 3 5.5 5.5'/%3E%3C/svg%3E")}
.pill-check .pill-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3 19 6v5c0 4.5-2.8 7.9-7 10-4.2-2.1-7-5.5-7-10V6l7-3Z'/%3E%3Cpath d='m9 12 2 2 4-4'/%3E%3C/svg%3E")}
.pill-revise .pill-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M20 11a8 8 0 0 0-14.9-3M4 13a8 8 0 0 0 14.9 3'/%3E%3Cpath d='M5 4v4h4M19 20v-4h-4'/%3E%3C/svg%3E")}
.pill-done .pill-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m5 13 4 4L19 7'/%3E%3C/svg%3E")}
.pill-decide .pill-glyph,.decision-glyph,.banner-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 11V6a1.5 1.5 0 0 1 3 0v4V4.5a1.5 1.5 0 0 1 3 0V10V6a1.5 1.5 0 0 1 3 0v5l2.2-2.2a1.4 1.4 0 0 1 2 2L16 15.5c-1 3-2.5 5-6 5-4 0-6-3-6-7V8a1.5 1.5 0 0 1 3 0v3'/%3E%3C/svg%3E")}
.review-mark{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3 19 6v5c0 4.5-2.8 7.9-7 10-4.2-2.1-7-5.5-7-10V6l7-3Z'/%3E%3Cpath d='m9 12 2 2 4-4'/%3E%3C/svg%3E")}
.review-chevron,.group-chevron{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E")}
.deliverable-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linejoin='round'%3E%3Cpath d='M8 6h6l4 4v10H8V6Z'/%3E%3Cpath d='M14 6v4h4M5 3h7'/%3E%3C/svg%3E")}
.attach-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M12 5v14M5 12h14'/%3E%3C/svg%3E")}
.send-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 19V5M6 11l6-6 6 6'/%3E%3C/svg%3E")}
.stop-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='black' stroke='none'%3E%3Crect x='7' y='7' width='10' height='10' rx='1.5'/%3E%3C/svg%3E")}
/* Application shell: glass chrome around one opaque centre of gravity. */
.app{height:100vh;display:grid;grid-template-columns:var(--sidebar) minmax(0,1fr);
  grid-template-rows:var(--topbar-h) minmax(0,1fr);background:transparent}
.topbar,.hub-bar{display:flex;align-items:center;gap:var(--sp-2);min-width:0;
  background:var(--glass-nav-bg);border:1px solid var(--glass-border);border-radius:var(--r-xl);
  box-shadow:var(--edge-highlight),var(--shadow-2);
  -webkit-backdrop-filter:blur(20px) saturate(150%);backdrop-filter:blur(20px) saturate(150%)}
.topbar{grid-column:1/-1;height:44px;margin:8px 8px 0;padding:0 var(--sp-3);z-index:var(--z-chrome)}
.hub-bar{height:48px;margin:8px 8px 0;padding:0 var(--sp-4);position:sticky;top:8px;z-index:var(--z-chrome)}
/* One-time shell entrance: plays once when `booted` is set on the first paint,
   never on an SSE snapshot. The default (no class) is the natural resting
   state, so a page that never boots is fully visible — no blank-shell risk. */
@media (prefers-reduced-motion:no-preference){
  body.booted .topbar{animation:shell-in .46s var(--ease-out) both}
  body.booted .sidebar{animation:shell-in .5s var(--ease-out) .06s both}
  body.booted .thread{animation:shell-rise .5s var(--ease-out) .10s both}
  body.booted .composer-wrap{animation:shell-rise .54s var(--ease-out) .16s both}
}
@keyframes shell-in{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}
@keyframes shell-rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.brand{display:flex;align-items:center;gap:9px;font-weight:600;letter-spacing:-.01em}
.brand-button{border:0;background:transparent;padding:0 var(--sp-2) 0 3px;height:34px;
  display:flex;align-items:center;gap:9px;font-weight:600;letter-spacing:-.01em;border-radius:var(--r-md);
  transition:background var(--dur-instant) ease}
.brand-button:hover{background:var(--hover)}.brand-button:active{transform:scale(.97)}
.brand-mark{width:26px;height:26px;border-radius:var(--r-sm);display:grid;place-items:center;
  background:var(--surface-2);border:1px solid var(--line);box-shadow:var(--shadow-1)}
.brand-mark,.welcome-mark{font-size:0}.brand-mark:before,.welcome-mark:before{content:"";width:11px;height:11px;
  border:1.8px solid var(--accent);border-radius:4px;transform:rotate(45deg)}
.version{font-size:var(--fs-caption);font-family:var(--font-label);color:var(--text-2);
  padding:2px 7px;border-radius:var(--r-pill);background:var(--surface-2)}
.top-project{height:32px;margin-left:2px;padding:0 var(--sp-3);border:0;border-radius:var(--r-md);
  background:transparent;display:flex;align-items:center;gap:6px;color:var(--text-2);cursor:pointer;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.top-project:hover{background:var(--hover);color:var(--text)}
.top-project b{color:var(--text);font-weight:500;overflow:hidden;text-overflow:ellipsis}
.icon-button{border:0;background:transparent;border-radius:var(--r-sm);width:32px;height:32px;
  display:grid;place-items:center;color:var(--text-2);flex:none;
  transition:background var(--dur-instant) ease,color var(--dur-instant) ease}
.icon-button:hover{background:var(--hover);color:var(--text)}
.icon-button:active{transform:scale(.97)}
.icon-button.pinned,.pin-button.pinned,.project-pin.pinned{color:var(--accent)}
.icon-button:disabled,.nav-item:disabled,.secondary:disabled{cursor:not-allowed;opacity:.45}
#hub-locale,#locale-toggle{width:auto;min-width:40px;padding:0 var(--sp-2);white-space:nowrap;font-size:var(--fs-caption);font-weight:500}
.live-pill{height:28px;display:flex;align-items:center;gap:6px;padding:0 10px;flex:none;
  border:1px solid var(--line);border-radius:var(--r-pill);color:var(--text-2);font-size:var(--fs-caption)}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--text-3)}
.live-dot.on{background:var(--pass)}

/* Usage pill: one element, no decoration; colour is the only state signal. */
.usage-pill{height:28px;display:inline-flex;align-items:center;padding:0 10px;flex:none;
  border:1px solid var(--line);border-radius:var(--r-pill);background:transparent;color:var(--text-2);
  font-family:var(--font-label);font-size:var(--fs-caption);white-space:nowrap;cursor:pointer}
.usage-pill:hover{color:var(--text)}
.usage-pill.warning{border-color:var(--state-revise);color:color-mix(in srgb,var(--state-revise) 60%,var(--text))}
.usage-pill.blocked{border-color:var(--blocked);color:var(--blocked)}
/* Usage banner: a soft threshold notice, dismissable for the period. */
.usage-banner{grid-column:1/-1;display:flex;align-items:center;gap:var(--sp-3);
  margin:6px 8px 0;padding:var(--sp-2) var(--sp-4);min-height:40px;
  background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--state-revise);
  border-radius:var(--r-md);box-shadow:var(--shadow-1);z-index:var(--z-chrome)}
.usage-banner b{font-weight:500}
.usage-banner span{color:var(--text-2);font-size:var(--fs-caption)}
.usage-banner button{margin-left:auto}
.run-cost{display:flex;flex-wrap:wrap;gap:var(--sp-3);padding:8px var(--sp-4);border-top:1px solid var(--line);
  color:var(--text-3);font-family:var(--font-label);font-size:var(--fs-caption)}
.run-cost .run-reset{color:color-mix(in srgb,var(--state-revise) 60%,var(--text))}
.turn-cost{margin-top:6px;color:var(--text-3);font-family:var(--font-label);font-size:var(--fs-caption)}
.usage-mode{display:inline-flex;border:1px solid var(--line);border-radius:var(--r-pill);overflow:hidden;margin-left:auto;flex:none}
.usage-mode button{border:0;background:transparent;padding:3px 10px;font-size:var(--fs-caption);color:var(--text-3);cursor:pointer}
.usage-mode button[aria-pressed="true"]{background:var(--surface-2);color:var(--text)}
.usage-heading{display:flex;align-items:flex-start;gap:var(--sp-3)}
.usage-report{width:100%;border-collapse:collapse;font-size:var(--fs-caption);margin-bottom:10px}
.usage-report th,.usage-report td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.usage-report th{color:var(--text-3);font-weight:600}
.usage-report td:not(:first-child),.usage-report th:not(:first-child){text-align:right;font-family:var(--font-label)}
.usage-report tr.total td,.usage-report tr.total th{border-top:2px solid var(--line);color:var(--text);font-weight:600}
.usage-note.unpriced span:first-child,.unpriced-note span:first-child{color:var(--state-revise)}
.unpriced-note{display:flex;align-items:flex-start;gap:9px;margin-top:10px;padding:10px 11px;
  border:1px solid var(--line);border-left:3px solid var(--state-revise);border-radius:var(--r-md);
  background:var(--surface-2);color:var(--text-2);font-size:var(--fs-caption);line-height:1.5}
.price-head,.price-row{display:grid;grid-template-columns:minmax(0,1.6fr) repeat(4,minmax(0,1fr)) 28px;gap:7px;align-items:center}
.price-head{margin-top:10px;color:var(--text-3);font-size:var(--fs-caption)}
.price-rows{display:grid;gap:8px;margin-top:6px}
.price-row input{min-height:34px;padding:6px 8px;font-size:var(--fs-caption);min-width:0}
.settings-usage-rollup{margin-top:14px}

/* Decision banner: protocol state is never hidden or transient. */
.decision-banner{grid-column:1/-1;display:flex;align-items:center;gap:var(--sp-3);
  margin:6px 8px 0;padding:var(--sp-2) var(--sp-4);min-height:40px;
  background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--state-decide);
  border-radius:var(--r-md);box-shadow:var(--shadow-1);z-index:var(--z-chrome)}
.decision-banner .banner-glyph{color:var(--state-decide)}
.decision-banner b{font-weight:500}
.decision-banner button{margin-left:auto}
.app:has(.decision-banner:not([hidden])){grid-template-rows:var(--topbar-h) auto minmax(0,1fr)}

/* Sample-demo banner: honesty is never hidden. Shown on every surface of the
   seeded local demo so it can't be mistaken for a real audit. */
.sample-banner{grid-column:1/-1;display:flex;align-items:center;gap:var(--sp-3);flex-wrap:wrap;
  margin:6px 8px 0;padding:var(--sp-2) var(--sp-4);min-height:40px;
  background:var(--state-decide-bg);border:1px solid var(--state-decide);
  border-left:3px solid var(--state-decide);
  border-radius:var(--r-md);box-shadow:var(--shadow-1);color:var(--text);z-index:var(--z-chrome)}
.sample-banner .sample-badge{flex:none;padding:2px 8px;border-radius:var(--r-pill);
  font-size:var(--fs-caption);font-weight:700;letter-spacing:.06em;
  background:var(--state-decide);color:var(--surface)}
.sample-banner b{font-weight:600}
.sample-banner span.sample-detail{color:var(--text-2)}
.app:has(#sample-banner:not([hidden])){grid-template-rows:var(--topbar-h) auto minmax(0,1fr)}
.app:has(#sample-banner:not([hidden])):has(.decision-banner:not([hidden])){
  grid-template-rows:var(--topbar-h) auto auto minmax(0,1fr)}

/* Left rail: projects, pins, recent chats, search. Nav glass shell. */
.sidebar,.inspector{min-width:0;display:flex;flex-direction:column;overflow:hidden}
.sidebar{grid-row:-2;margin:8px 0 8px 8px;padding:var(--sp-3) 10px var(--sp-3);
  background:var(--glass-nav-bg);border:1px solid var(--glass-border);border-radius:var(--r-xl);
  box-shadow:var(--edge-highlight),var(--shadow-2);
  -webkit-backdrop-filter:blur(20px) saturate(150%);backdrop-filter:blur(20px) saturate(150%)}
.rail-search{position:relative;display:flex;align-items:center;margin-bottom:var(--sp-2)}
.rail-search-icon{position:absolute;left:9px;color:var(--text-3);pointer-events:none}
.rail-search-icon:before{width:14px;height:14px}
.rail-search input{width:100%;height:34px;border:1px solid transparent;border-radius:var(--r-sm);
  background:color-mix(in srgb,var(--surface-2) 60%,transparent);padding:0 40px 0 30px;outline:0;
  font-size:var(--fs-body);color:var(--text)}
.rail-search input::placeholder{color:var(--text-3)}
.rail-search input:focus{border-color:var(--line-strong);background:var(--surface-2)}
.rail-search kbd{position:absolute;right:9px;font:var(--fs-caption) var(--font-mono);
  color:var(--text-3);pointer-events:none}
.new-task{height:38px;border:1px solid var(--line);background:var(--surface-2);flex:none;
  border-radius:var(--r-md);padding:0 var(--sp-3);display:flex;align-items:center;gap:var(--sp-2);
  font-weight:500;box-shadow:var(--shadow-1);transition:background var(--dur-instant) ease}
.new-task:hover{background:var(--surface-3)}.new-task:active{transform:scale(.985)}
.new-task span:last-child{margin-left:auto;color:var(--text-3);font-size:var(--fs-caption);
  font-family:var(--font-mono)}
.side-label{font-size:var(--fs-caption);color:var(--text-3);padding:var(--sp-5) 10px var(--sp-1);
  font-weight:600}
.task-list{overflow:auto;min-height:0;flex:1;margin-top:var(--sp-1)}
.task{min-height:40px;padding:var(--sp-2) 6px var(--sp-2) 10px;border-radius:var(--r-md);
  margin-bottom:2px;display:flex;align-items:center;gap:8px;cursor:pointer}
.task:hover{background:var(--hover)}
.task.active{background:var(--surface);box-shadow:var(--shadow-1)}
.task.active .task-title{font-weight:500}
.task-copy{min-width:0;flex:1;display:flex;align-items:center;gap:8px}
.task-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:var(--fs-body);min-width:0;flex:1}
.task-meta{display:flex;align-items:center;gap:6px;color:var(--text-3);font-size:var(--fs-caption);flex:none}
.pin-button,.task-delete{width:28px;height:28px;border:0;border-radius:var(--r-xs);background:transparent;
  color:var(--text-3);opacity:0;flex:none;display:grid;place-items:center}
.pin-button:before,.task-delete:before{width:14px;height:14px}
.task:hover .pin-button,.task.active .pin-button,.pin-button.pinned,.task:focus-within .pin-button,
.task:hover .task-delete,.task.active .task-delete,.task:focus-within .task-delete{opacity:1}
.pin-button:hover{background:var(--hover);color:var(--text)}
.task-delete:hover{background:var(--blocked-bg);color:var(--blocked)}
.task-act{width:28px;height:28px;border:0;border-radius:var(--r-xs);background:transparent;
  color:var(--text-3);opacity:0;flex:none;display:grid;place-items:center;font-size:0;cursor:pointer}
.task-act:before{content:"";display:block;width:14px;height:14px;background:currentColor;
  -webkit-mask:var(--ui-icon) center/contain no-repeat;mask:var(--ui-icon) center/contain no-repeat}
.task:hover .task-act,.task.active .task-act,.task:focus-within .task-act{opacity:1}
.task-act:hover{background:var(--hover);color:var(--text)}
.task-act[aria-expanded="true"]{opacity:1;background:var(--hover);color:var(--text)}
.task-act.more{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='black'%3E%3Ccircle cx='5' cy='12' r='2'/%3E%3Ccircle cx='12' cy='12' r='2'/%3E%3Ccircle cx='19' cy='12' r='2'/%3E%3C/svg%3E")}
.task-act.unarchive{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='4' width='18' height='4' rx='1'/%3E%3Cpath d='M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8'/%3E%3Cpath d='M12 17v-5M9.5 14 12 11.5 14.5 14'/%3E%3C/svg%3E")}
.chat-menu{position:fixed;z-index:var(--z-overlay);min-width:180px;padding:var(--sp-1);
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r-md);
  box-shadow:var(--shadow-2);display:flex;flex-direction:column;gap:1px;
  animation:chatmenu-in var(--dur-fast) ease}
.chat-menu[hidden]{display:none}
.chat-menu button{display:flex;align-items:center;gap:9px;width:100%;border:0;background:transparent;
  color:var(--text);font-size:var(--fs-body);text-align:left;padding:7px 10px;border-radius:var(--r-xs);cursor:pointer}
.chat-menu button:before{content:"";display:block;width:15px;height:15px;flex:none;background:currentColor;
  -webkit-mask:var(--ui-icon) center/contain no-repeat;mask:var(--ui-icon) center/contain no-repeat}
.chat-menu button:hover,.chat-menu button:focus-visible{background:var(--hover);outline:0}
.chat-menu .chat-menu-sep{height:1px;margin:var(--sp-1) 6px;background:var(--line)}
.chat-menu button.danger{color:var(--blocked)}
.chat-menu button.danger:hover,.chat-menu button.danger:focus-visible{background:var(--blocked-bg)}
.chat-menu button[data-chat-menu="rename"]{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 20h9'/%3E%3Cpath d='M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z'/%3E%3C/svg%3E")}
.chat-menu button[data-chat-menu="duplicate"]{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='9' y='9' width='11' height='11' rx='2'/%3E%3Cpath d='M5 15V5a2 2 0 0 1 2-2h10'/%3E%3C/svg%3E")}
.chat-menu button[data-chat-menu="pin"]{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m14 4 6 6-3 1-4 4-1 5-3-3-3-3 5-1 4-4 1-3Z'/%3E%3Cpath d='m5 19 4-4'/%3E%3C/svg%3E")}
.chat-menu button[data-chat-menu="archive"]{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='4' width='18' height='4' rx='1'/%3E%3Cpath d='M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8'/%3E%3Cpath d='M10 12h4'/%3E%3C/svg%3E")}
.chat-menu button[data-chat-menu="delete"]{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6'/%3E%3C/svg%3E")}
@keyframes chatmenu-in{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
.archived-toggle{display:flex;align-items:center;gap:6px;width:100%;border:0;background:transparent;
  cursor:pointer;padding:var(--sp-5) 10px var(--sp-1);font-size:var(--fs-caption);font-weight:600;
  color:var(--text-3);text-align:left}
.archived-toggle:hover{color:var(--text-2)}
.archived-count{margin-left:auto;font-family:var(--font-label);color:var(--text-3)}
.archived-chevron{width:12px;height:12px;flex:none;color:var(--text-3);font-size:0;
  transition:transform var(--dur-base) ease}
.archived-chevron:before{content:"";display:block;width:12px;height:12px;background:currentColor;
  -webkit-mask:var(--ui-icon) center/contain no-repeat;mask:var(--ui-icon) center/contain no-repeat;
  --ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m9 6 6 6-6 6'/%3E%3C/svg%3E")}
.archived-toggle[aria-expanded="true"] .archived-chevron{transform:rotate(90deg)}
.task.is-archived .task-title{color:var(--text-2)}
.state-dot{width:6px;height:6px;border-radius:50%;background:transparent;flex:none;
  transition:background var(--dur-base) ease}
.state-dot.understand{background:var(--state-understand)}
.state-dot.work,.state-dot.running{background:var(--state-work)}
.state-dot.check{background:var(--state-check)}
.state-dot.revise{background:var(--state-revise)}
.state-dot.done,.state-dot.passed,.state-dot.consumed,.state-dot.PASSED,.state-dot.CONSUMED{background:var(--state-done)}
.state-dot.decide,.state-dot.escalated,.state-dot.ESCALATED{background:var(--state-decide)}
.state-dot.blocked,.state-dot.BLOCKED{background:var(--blocked)}
.sidebar-foot{margin-top:auto;border-top:1px solid var(--line);padding:10px 10px 0;flex:none;
  color:var(--text-2);font-size:var(--fs-caption)}
.sidebar-foot b{display:block;color:var(--text);font-weight:500;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}

/* Centre: one chronological run on an opaque surface. */
.workspace{grid-row:-2;min-width:0;min-height:0;display:flex;flex-direction:column;position:relative;
  z-index:var(--z-content);margin:8px 8px 8px;border:1px solid var(--line);
  border-radius:var(--r-xl);background:var(--surface);overflow:hidden;box-shadow:var(--shadow-1)}
.thread-head{min-height:56px;flex:none;display:flex;align-items:center;padding:0 var(--sp-6);gap:var(--sp-3);
  position:relative}
.thread-head:after{content:"";position:absolute;left:0;right:0;bottom:-24px;height:24px;
  pointer-events:none;background:linear-gradient(var(--surface),transparent)}
.thread-title{min-width:0}
.thread-title h1{font-size:var(--fs-title);line-height:1.35;margin:0;font-weight:600;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;letter-spacing:-.01em}
.runtime-button{height:30px;border:1px solid var(--line);border-radius:var(--r-sm);background:var(--surface);
  color:var(--text-2);padding:0 10px;font-size:var(--fs-label);white-space:nowrap;flex:none}
.runtime-button:hover{background:var(--hover);color:var(--text)}

/* Six-state indicator: the one element that answers "what is happening". */
.state-pill{display:inline-flex;align-items:center;height:26px;padding:0 10px 0 8px;gap:6px;
  border-radius:var(--r-pill);font-size:var(--fs-label);font-weight:500;flex:none;
  background:var(--surface-2);color:var(--text-2);border:1px solid transparent;
  transition:background var(--dur-base) ease,color var(--dur-base) ease}
.state-pill .pill-glyph{width:14px;height:14px;flex:none}
.state-pill .pill-glyph:before{width:14px;height:14px}
.state-pill .pill-detail{font-family:var(--font-label);font-size:var(--fs-caption);
  font-variant-numeric:tabular-nums;opacity:.8}
.state-pill.pill-understand{background:var(--state-understand-bg);color:color-mix(in srgb,var(--state-understand) 55%,var(--text))}
.state-pill.pill-work{background:var(--state-work-bg);color:color-mix(in srgb,var(--state-work) 55%,var(--text))}
.state-pill.pill-check{background:var(--state-check-bg);color:color-mix(in srgb,var(--state-check) 55%,var(--text))}
.state-pill.pill-revise{background:var(--state-revise-bg);color:color-mix(in srgb,var(--state-revise) 55%,var(--text))}
.state-pill.pill-done{background:var(--state-done-bg);color:color-mix(in srgb,var(--state-done) 55%,var(--text))}
.state-pill.pill-decide{background:var(--state-decide-bg);color:color-mix(in srgb,var(--state-decide) 55%,var(--text));
  border-color:var(--state-decide)}
.state-pill.pill-understand .pill-glyph{color:var(--state-understand)}
.state-pill.pill-work .pill-glyph{color:var(--state-work)}
.state-pill.pill-check .pill-glyph{color:var(--state-check)}
.state-pill.pill-revise .pill-glyph{color:var(--state-revise)}
.state-pill.pill-done .pill-glyph{color:var(--state-done)}
.state-pill.pill-decide .pill-glyph{color:var(--state-decide)}
.state-pill.pill-live .pill-glyph{animation:breathe 2.4s ease-in-out infinite}
@keyframes breathe{0%,100%{opacity:.55}50%{opacity:1}}
.pill-swap{animation:pill-in var(--dur-base) var(--ease-out)}
@keyframes pill-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

.thread{flex:1;overflow:auto;min-height:0;scrollbar-gutter:stable;overscroll-behavior:contain;
  scroll-padding-bottom:var(--composer-clearance,180px);scrollbar-width:thin;
  scrollbar-color:color-mix(in srgb,var(--text-2) 34%,transparent) transparent}
:is(.project-hub,.thread,.task-list,.inspector,.panel-body,.wizard,.attachments,.preview-body,.palette-list){
  scrollbar-width:thin;scrollbar-color:color-mix(in srgb,var(--text-2) 34%,transparent) transparent}
:is(.project-hub,.thread,.task-list,.inspector,.panel-body,.wizard,.attachments,.preview-body,.palette-list)::-webkit-scrollbar{width:10px;height:10px}
:is(.project-hub,.thread,.task-list,.inspector,.panel-body,.wizard,.attachments,.preview-body,.palette-list)::-webkit-scrollbar-track{background:transparent}
:is(.project-hub,.thread,.task-list,.inspector,.panel-body,.wizard,.attachments,.preview-body,.palette-list)::-webkit-scrollbar-thumb{
  min-height:36px;border:3px solid transparent;border-radius:var(--r-pill);
  background:color-mix(in srgb,var(--text-2) 42%,transparent);background-clip:padding-box}
.thread-inner{width:min(var(--thread-max),calc(100% - 48px));margin:0 auto;
  padding:var(--sp-7) 0 calc(var(--composer-clearance,180px) + var(--sp-6))}
.welcome{padding:var(--sp-9) var(--sp-5) var(--sp-6);text-align:center}
.welcome-mark{width:40px;height:40px;margin:0 auto var(--sp-4);border-radius:var(--r-lg);
  background:var(--surface-2);border:1px solid var(--line);display:grid;place-items:center;
  box-shadow:var(--shadow-1)}
.welcome h2{font-size:var(--fs-h2);margin:0;letter-spacing:-.015em;font-weight:600}
.welcome p{color:var(--text-2);max-width:460px;margin:var(--sp-2) auto 0;line-height:1.6;font-size:var(--fs-prose)}

/* Message rows: a work record, not a chat app. */
.turn{margin-bottom:var(--sp-6)}
.turn.user{display:flex;justify-content:flex-end}
.turn.draft .turn-main{border:1px dashed var(--line-strong);border-radius:var(--r-md);
  padding:10px 12px;background:transparent}
.turn.draft .draft-label{font-weight:500;color:var(--text-2);font-size:var(--fs-caption)}
.turn.draft .draft-body{white-space:pre-wrap;color:var(--text-2)}
.turn.user .turn-main{max-width:85%;min-width:0}
.turn.user .turn-body{background:var(--surface-2);border-radius:var(--r-lg) var(--r-lg) 6px var(--r-lg);
  padding:var(--sp-3) var(--sp-4)}
.turn.user .turn-meta{justify-content:flex-end}
.turn-main{min-width:0}
.turn-meta{display:flex;align-items:center;gap:7px;margin-bottom:6px;
  font-size:var(--fs-caption);color:var(--text-3)}
.turn-meta b{color:var(--text);font-weight:600;font-size:var(--fs-label)}
.turn-time{margin-left:auto}
.turn.user .turn-time{margin-left:0}
.turn-body{font-size:var(--fs-prose);white-space:pre-wrap;word-break:break-word;line-height:1.6}
/* Context-condensation notice: the RUNTIME narrating what it reduced before
   sending the prompt. Deliberately not shaped like a turn — no round avatar, no
   speaker name — because nothing said this; attributing it to the generator
   would be a claim about who produced the words. */
.turn.system-note{margin-bottom:var(--sp-5)}
.report-provenance{margin:10px 0 0;padding:8px 10px;border-radius:var(--r-sm);
  background:var(--surface-2);color:var(--text-2);font-size:var(--fs-caption);
  border-left:2px solid var(--warn,var(--line-strong))}
.turn.system-note .turn-main{border-left:2px solid var(--line-strong);
  padding:2px 0 2px var(--sp-4)}
.turn.system-note .turn-meta{margin-bottom:4px;color:var(--text-3)}
.turn.system-note .turn-meta b{font-size:var(--fs-caption);font-weight:600;
  color:var(--text-2);letter-spacing:.02em;text-transform:uppercase}
.system-mark{flex:none;font-size:var(--fs-caption);color:var(--text-3)}
.turn.system-note .turn-body{font-size:var(--fs-label);color:var(--text-2);
  white-space:normal;line-height:1.55}
.condense-paths{margin-top:5px;display:flex;flex-wrap:wrap;gap:4px}
.condense-path{font-size:var(--fs-caption);color:var(--text-3);background:var(--surface-2);
  border:1px solid var(--line);border-radius:var(--r-xs);padding:1px 6px;
  overflow-wrap:anywhere;max-width:100%}
.event-mark.runtime{background:var(--surface-2);color:var(--text-3)}
/* The optimistic "working" indicator shown the instant a message is sent. */
.thinking-dots{display:inline-flex;gap:5px;align-items:center;height:20px}
.thinking-dots i{width:6px;height:6px;border-radius:50%;background:var(--text-3);
  animation:think 1.15s ease-in-out infinite}
.thinking-dots i:nth-child(2){animation-delay:.15s}
.thinking-dots i:nth-child(3){animation-delay:.3s}
@keyframes think{0%,70%,100%{opacity:.28;transform:translateY(0)}35%{opacity:1;transform:translateY(-4px)}}
@media (prefers-reduced-motion:reduce){.thinking-dots i{animation:none;opacity:.55}}
.turn-sub{margin-top:7px;color:var(--text-2);font-size:var(--fs-label)}
/* Phase narration under the working indicator: quiet, one line each, the
   latest a shade darker. No card, no mark — it is the indicator's caption. */
.intake{margin-top:6px}
.intake-line{color:var(--text-3);font-size:var(--fs-label);line-height:1.5}
.intake-line.latest{color:var(--text-2)}
.role-mark{width:24px;height:24px;border-radius:var(--r-sm);display:grid;place-items:center;flex:none;
  font-size:10px;font-weight:600;background:var(--surface-2);color:var(--text-2)}
.role-mark.generator{background:var(--role-g-bg);color:var(--role-g)}
.role-mark.auditor{background:var(--role-a-bg);color:var(--role-a)}
.avatar{width:24px;height:24px;border-radius:var(--r-sm);display:grid;place-items:center;flex:none;
  font-size:10px;font-weight:600;background:var(--surface-2);color:var(--text-2);border:0}
.turn.audit .avatar{background:var(--role-a-bg);color:var(--role-a)}
.direct-mark{font-size:var(--fs-caption);padding:2px 6px;border-radius:var(--r-xs);
  background:var(--accent-bg);color:var(--accent);font-weight:500}
.route-note{margin-top:8px;padding:8px 10px;border-left:2px solid var(--line-strong);
  color:var(--text-2);font-size:var(--fs-label);white-space:pre-wrap;word-break:break-word}

/* Verdict badges: real ledger words, colored and always labelled. */
.status{font-size:var(--fs-caption);line-height:1;padding:5px 8px;border-radius:var(--r-xs);
  font-weight:600;background:var(--surface-2);color:var(--text-2);white-space:nowrap}
.status.PASS,.status.PASSED,.status.CONSUMED,.status.passed,.status.consumed,.status.completed,.status.complete{background:var(--pass-bg);color:var(--pass)}
.status.BLOCKED,.status.blocked,.status.failed,.status.refused{background:var(--blocked-bg);color:var(--blocked)}
.status.ESCALATED,.status.escalated{background:var(--escalated-bg);color:var(--escalated)}
.status.running{background:var(--state-work-bg);color:var(--state-work)}

/* Independent review card: invisible by default, expandable in full. */
.review-card{border:1px solid var(--line);border-radius:var(--r-lg);background:var(--surface);
  box-shadow:var(--shadow-1);margin:var(--sp-2) 0 var(--sp-6);overflow:hidden}
.review-summary{width:100%;border:0;background:transparent;text-align:left;padding:var(--sp-4);
  display:block;color:inherit}
.review-summary:hover{background:var(--hover)}
.review-top{display:flex;align-items:center;gap:10px}
.review-mark{width:22px;height:22px;border-radius:var(--r-xs);display:grid;place-items:center;
  background:var(--role-a-bg);color:var(--role-a);flex:none}
.review-mark:before{width:14px;height:14px}
.review-top b{font-size:var(--fs-title);font-weight:600;flex:1;min-width:0}
.review-chevron{color:var(--text-3);transition:transform var(--dur-fast) var(--ease-out)}
.review-card.open .review-chevron{transform:rotate(180deg)}
.review-checks{margin:var(--sp-3) 0 0;padding:0;list-style:none;display:grid;gap:5px}
.review-checks li{display:flex;align-items:baseline;gap:8px;font-size:var(--fs-body);color:var(--text-2)}
.review-checks li:before{content:"";width:12px;height:12px;flex:none;background:var(--pass);
  align-self:center;
  -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m5 13 4 4L19 7'/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m5 13 4 4L19 7'/%3E%3C/svg%3E") center/contain no-repeat}
.review-rounds{margin-top:var(--sp-3);font-size:var(--fs-caption);color:var(--text-3)}
.review-rounds b{font-family:var(--font-label);font-weight:500;color:var(--text-2)}
.review-detail{display:grid;grid-template-rows:0fr;transition:grid-template-rows var(--dur-base) var(--spring)}
.review-card.open .review-detail{grid-template-rows:1fr}
.review-detail-inner{min-height:0;overflow:hidden}
.review-section{border-top:1px solid var(--line);padding:var(--sp-4)}
.review-section-title{font-size:var(--fs-caption);font-weight:600;color:var(--text-3);margin-bottom:var(--sp-2)}
.review-round-row{display:flex;align-items:baseline;gap:10px;padding:4px 0;font-size:var(--fs-body)}
.review-round-row .round-n{font-family:var(--font-label);font-size:var(--fs-caption);color:var(--text-3);flex:none}
.review-record{display:grid;gap:6px}
.review-record-row{display:flex;align-items:center;gap:8px;font-size:var(--fs-label)}
.review-record-row span:first-child{color:var(--text-2);min-width:88px}
.review-record-row code{font-family:var(--font-mono);font-size:var(--fs-caption);color:var(--text);
  overflow-wrap:anywhere}
.review-actions{border-top:1px solid var(--line);padding:var(--sp-2) var(--sp-3);display:flex;
  justify-content:flex-end}
.review-action{border:0;background:transparent;color:var(--text-2);font-size:var(--fs-label);
  padding:6px 8px;border-radius:var(--r-xs)}
.review-action:hover{background:var(--hover);color:var(--text)}
.finding{margin-top:9px;border:1px solid var(--line);border-radius:var(--r-md);padding:10px 12px;
  background:var(--surface)}
.finding-head{display:flex;align-items:center;gap:7px;font-size:var(--fs-caption);color:var(--text-2)}
.severity{font-weight:600;color:var(--blocked)}
.finding-where{overflow-wrap:anywhere}
/* the rule id is provenance, not the message — small, dim, out of the way */
.finding-rule{font-size:var(--fs-micro,10px);color:var(--text-3);font-variant-numeric:tabular-nums;opacity:.75}
.finding p{margin:5px 0 0;line-height:1.5;font-size:var(--fs-body)}
.finding-tier{display:block;margin-top:6px;font-size:var(--fs-caption);color:var(--text-3)}
.finding-tier.verified{color:var(--text-2)}
/* R2. A finding leads with the observation; severity, place, evidence tier and
   rule id share one muted details line under it. */
.finding-observation{margin:0 0 4px}
.finding-details{display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:var(--fs-caption);color:var(--text-3)}
.finding-details .finding-tier{display:inline;margin:0}
.finding-details .severity.suggestion{color:var(--text-2)}
.finding-sep{opacity:.5}
/* R3. The record (commit, cycle, models) sits behind a closed disclosure. */
.review-details>summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:6px}
.review-details>summary::-webkit-details-marker{display:none}
.review-details>summary::after{content:'';width:5px;height:5px;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(-45deg);transition:transform var(--dur-base)}
.review-details[open]>summary::after{transform:rotate(45deg)}
.review-details .review-record{margin-top:var(--sp-2)}
/* R4. One forecast line at task start and in the run card header. */
.run-forecast,.turn-forecast{color:var(--text-3);font-size:var(--fs-caption)}
.turn-forecast{margin-top:6px}
/* .dt — a reusable clean data table (Claude-Code-style: muted header, hairline
   rows, hover, generous rows). Used for Skills, Connectors/MCP, and other lists. */
.dt{width:100%;border-collapse:collapse;margin-top:6px;font-size:var(--fs-body)}
.dt th{text-align:left;font-weight:500;color:var(--text-3);font-size:var(--fs-caption);
  letter-spacing:.01em;padding:7px 12px;border-bottom:1px solid var(--line)}
.dt td{padding:12px;border-bottom:1px solid var(--line);color:var(--text-2);vertical-align:middle}
.dt tbody tr:last-child td{border-bottom:0}
.dt tbody tr:hover{background:var(--hover)}
.dt .dt-name{color:var(--text);font-weight:500}
.dt .dt-muted{color:var(--text-3);font-size:var(--fs-caption)}
.dt .dt-num{text-align:right;font-variant-numeric:tabular-nums}

/* Deliverables: opaque cards, pass-gated, grouped when plural. */
.output-files{margin-top:var(--sp-3)}
.output-head{display:flex;align-items:center;gap:7px;margin-bottom:6px;
  color:var(--text-2);font-size:var(--fs-caption);font-weight:600}
.output-count{font-weight:400;color:var(--text-3);font-family:var(--font-label)}
.artifact-list{display:grid;gap:6px}
.output-file{min-width:0;border:1px solid var(--line);border-radius:var(--r-lg);padding:0;
  display:flex;align-items:stretch;gap:0;background:var(--surface);color:inherit;
  text-decoration:none;box-shadow:var(--shadow-1);position:relative;
  transition:border-color var(--dur-instant) ease,box-shadow var(--dur-instant) ease,transform var(--dur-instant) ease}
.output-file:hover{border-color:var(--line-strong);box-shadow:var(--shadow-2);transform:translateY(-1px)}
.output-file.passed:before,.output-file.consumed:before{content:"";position:absolute;left:0;top:8px;bottom:8px;
  width:3px;border-radius:0 3px 3px 0;background:var(--pass)}
.output-file.unavailable{opacity:.62;box-shadow:none}
.output-file.unavailable:hover{border-color:var(--line);transform:none;box-shadow:none}
.artifact-main{display:flex;align-items:center;gap:10px;min-width:0;flex:1;padding:10px 12px;
  color:inherit;text-decoration:none;border:0;background:transparent;text-align:left;cursor:pointer;
  border-radius:var(--r-lg) 0 0 var(--r-lg)}
.artifact-actions{display:flex;align-items:center;gap:2px;padding:0 6px;border-left:1px solid var(--line)}
.artifact-icon{width:34px;height:34px;flex:none;border-radius:var(--r-sm);background:var(--surface-2);
  color:var(--text-2);display:grid;place-items:center;font-size:8.5px;font-weight:600;
  font-family:var(--font-mono);letter-spacing:.02em}
.artifact-copy{min-width:0}
.artifact-name{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  font-family:var(--font-mono);font-size:var(--fs-body)}
.artifact-context{display:block;font-size:var(--fs-caption);color:var(--text-3);margin-top:2px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.artifact-action{width:32px;height:32px;display:grid;place-items:center;flex:none;color:var(--text-2);
  text-decoration:none;border-radius:var(--r-xs);border:0;background:transparent}
.artifact-action:hover{background:var(--hover);color:var(--text)}
.output-more{margin-top:6px;padding:2px 0;border:0;background:transparent;color:var(--accent);
  font:inherit;font-size:var(--fs-label);cursor:pointer}
.output-more:hover{text-decoration:underline}
.deliverable-group{border:1px solid var(--line);border-radius:var(--r-lg);background:var(--surface);
  box-shadow:var(--shadow-1);overflow:hidden}
.group-head{width:100%;border:0;background:transparent;display:flex;align-items:center;gap:10px;
  padding:10px 12px;min-height:56px;text-align:left;color:inherit}
.group-head:hover{background:var(--hover)}
.group-title{min-width:0;flex:1}
.group-title b{display:block;font-size:var(--fs-body);font-weight:500}
.group-title span{display:block;font-size:var(--fs-caption);color:var(--text-3);margin-top:2px}
.group-chevron{color:var(--text-3);transition:transform var(--dur-fast) var(--ease-out)}
.deliverable-group.open .group-chevron{transform:rotate(180deg)}
.group-detail{display:grid;grid-template-rows:0fr;transition:grid-template-rows var(--dur-base) var(--spring)}
.deliverable-group.open .group-detail{grid-template-rows:1fr}
.group-detail-inner{min-height:0;overflow:hidden}
.group-detail-inner .output-file{border:0;border-top:1px solid var(--line);border-radius:0;
  box-shadow:none;margin:0}
.group-detail-inner .output-file:hover{transform:none;box-shadow:none;background:var(--hover)}
.deliverable-icon{width:34px;height:34px;border-radius:var(--r-sm);background:var(--surface-2);
  color:var(--text-2);display:grid;place-items:center;flex:none}

/* Delivery status band and stop banners. */
.delivery-status{margin:2px 0 var(--sp-6);border:1px solid var(--line);border-radius:var(--r-md);
  padding:10px var(--sp-3);background:var(--surface);display:flex;align-items:center;gap:9px;
  color:var(--text-2);font-size:var(--fs-label)}
.delivery-status .delivery-dot{width:7px;height:7px;border-radius:50%;background:var(--state-work);flex:none}
.delivery-status.passed .delivery-dot,.delivery-status.consumed .delivery-dot{background:var(--pass)}
.delivery-status.blocked .delivery-dot{background:var(--blocked)}
.delivery-status.escalated .delivery-dot,.delivery-status.provider_unavailable .delivery-dot{background:var(--state-decide)}
.delivery-status b{color:var(--text);font-weight:500}
.delivery-status button{margin-left:auto;border:0;background:transparent;color:var(--text-2);
  font-size:var(--fs-label);flex:none}
.delivery-status button:hover{color:var(--text)}
/* §41.9 admission explanation card — a refusal that answers, not a dead end. */
.admission-card{margin:2px 0 var(--sp-6);border:1px solid var(--line);border-left:3px solid var(--escalated);
  border-radius:var(--r-md);padding:12px var(--sp-3);background:var(--surface);font-size:var(--fs-label)}
.admission-card.ok{border-left-color:var(--pass)}
.admission-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.admission-head b{color:var(--text);font-weight:600}
.admission-head span{color:var(--text-3);font-size:var(--fs-caption)}
.admission-signed{border:1px solid var(--pass);border-radius:999px;padding:1px 8px;color:var(--pass);font-size:var(--fs-caption);white-space:nowrap;cursor:default}
.admission-repro{border:1px solid var(--line);border-radius:999px;padding:1px 8px;color:var(--text-2);font-size:var(--fs-caption);white-space:nowrap;cursor:default}
.admission-why{margin:7px 0 0;color:var(--text-2);line-height:1.55}
.admission-safe{margin:6px 0 0;color:var(--text-3);font-size:var(--fs-caption)}
.admission-tier{margin:7px 0 0;color:var(--text-2)}
.admission-options{margin-top:9px}
.admission-options b{color:var(--text);font-weight:500;font-size:var(--fs-caption)}
.admission-options ul{margin:5px 0 0;padding-left:18px;color:var(--text-2)}
.admission-options li{margin-top:3px;line-height:1.5}
.admission-actions{display:flex;gap:10px;margin-top:11px}
.admission-actions button{border:1px solid var(--line-strong);background:transparent;color:var(--text-2);
  border-radius:var(--r-sm);padding:5px 12px;font-size:var(--fs-label)}
.admission-actions button:hover{color:var(--text);border-color:var(--text-3)}
.interrupted{margin-bottom:var(--sp-5);padding:var(--sp-3) var(--sp-4);background:var(--surface);
  border:1px solid var(--line);border-left:3px solid var(--escalated);color:var(--text);
  border-radius:var(--r-md);font-size:var(--fs-body);display:none;box-shadow:var(--shadow-1)}
.interrupted.on{display:block}
.interrupted b{color:var(--escalated)}
.interrupted-detail{display:block;margin:7px 0;padding:7px 8px;border-radius:var(--r-xs);
  background:var(--surface-2);color:var(--text);font-size:var(--fs-label);line-height:1.45;
  overflow-wrap:anywhere}
.interrupted-actions{display:flex;gap:7px;margin-top:9px}
.interrupted-actions button{height:30px;border-radius:var(--r-sm);border:1px solid var(--line-strong);
  background:var(--surface);color:var(--text);padding:0 10px;cursor:pointer;font-size:var(--fs-label)}
.interrupted-actions button:hover{background:var(--hover)}
/* Per-call approval: a paused Level 3+ action awaiting the user's decision. */
.approval-card{margin:var(--sp-2) 0 var(--sp-5);padding:var(--sp-3) var(--sp-4);
  background:var(--state-decide-bg);border:1px solid var(--line);
  border-left:3px solid var(--state-decide);border-radius:var(--r-md);
  box-shadow:var(--shadow-1);animation:approval-in .28s var(--ease,ease) both}
@keyframes approval-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.approval-card{animation:none}}
.approval-head{display:flex;align-items:center;gap:8px}
.approval-head b{font-size:var(--fs-label);color:var(--state-decide)}
.approval-badge{font-size:var(--fs-caption);font-weight:600;color:var(--state-decide);
  border:1px solid var(--state-decide);border-radius:999px;padding:1px 8px;letter-spacing:.02em}
.approval-tool{margin-top:7px;font-family:var(--font-mono);font-size:var(--fs-label);
  color:var(--text);overflow-wrap:anywhere}
.approval-why{margin:4px 0 0;font-size:var(--fs-caption);color:var(--text-2);line-height:1.45}
.approval-facts{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:8px}
.approval-facts span{font-size:var(--fs-caption);color:var(--text-3)}
.approval-facts strong{color:var(--text-2);font-weight:600}
.approval-preview{margin:9px 0 0;padding:9px 11px;max-height:220px;overflow:auto;
  background:var(--surface-2);border:1px solid var(--line);border-radius:var(--r-sm);
  font-family:var(--font-mono);font-size:var(--fs-caption);line-height:1.5;color:var(--text-2);
  white-space:pre;overflow-wrap:normal;tab-size:2}
.approval-preview .pl-add{color:var(--pass)}
.approval-preview .pl-del{color:var(--blocked)}
.approval-preview .pl-hunk,.approval-preview .pl-meta{color:var(--text-3)}
/* Governed-actions (evidence) panel: the visible audit trail. */
.gov-list{display:flex;flex-direction:column;gap:8px}
.gov-row{padding:10px 12px;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-sm)}
.gov-top{display:flex;align-items:center;gap:8px}
.gov-top b{font-family:var(--font-mono);font-size:var(--fs-label);color:var(--text);overflow-wrap:anywhere}
.gov-top .status{margin-left:auto;flex:none}
.gov-level{font-size:var(--fs-caption);color:var(--text-3);border:1px solid var(--line-strong);
  border-radius:999px;padding:1px 7px;flex:none}
.gov-meta{margin-top:5px;font-size:var(--fs-caption);color:var(--text-2)}
.gov-reason{margin-top:3px;font-size:var(--fs-caption);color:var(--text-3)}
.gov-hashes{margin-top:5px;font-family:var(--font-mono);font-size:var(--fs-caption);
  color:var(--text-3);overflow-wrap:anywhere}
.gov-flag{margin-top:6px;font-size:var(--fs-caption);color:var(--escalated);font-weight:600}
/* Goal & plan panel (Slice C): the stated goal + the audited loop as plan v1. */
.plan-goal,.plan-plan{padding:12px 14px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--r-md);margin-bottom:10px;font-size:var(--fs-label)}
.plan-sec-title{font-size:var(--fs-caption);font-weight:600;color:var(--text-3);
  text-transform:uppercase;letter-spacing:.04em;margin:10px 0 5px}
.plan-goal .plan-sec-title:first-child,.plan-plan .plan-sec-title:first-child{margin-top:0}
.plan-task{margin:0;color:var(--text);line-height:1.55;white-space:pre-wrap;word-break:break-word}
.plan-list{margin:0;padding-left:18px;color:var(--text-2)}
.plan-list li{margin-top:3px}
.plan-const{display:flex;justify-content:space-between;gap:10px;padding:3px 0;color:var(--text-2)}
.plan-const b{color:var(--text);font-weight:500}
.plan-note{margin:4px 0 8px;color:var(--text-3);font-size:var(--fs-caption)}
.plan-step{display:flex;align-items:center;gap:8px;padding:6px 0;color:var(--text-2)}
.plan-step b{color:var(--text);font-weight:500;flex:none}
.plan-step span:last-child{font-size:var(--fs-caption);color:var(--text-3);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.plan-dot{width:8px;height:8px;border-radius:50%;background:var(--line-strong);flex:none}
.plan-step.current .plan-dot{background:var(--accent)}
.plan-step.done .plan-dot,.plan-step.passed .plan-dot{background:var(--pass)}
.plan-round{padding:3px 0;color:var(--text-2);font-size:var(--fs-caption)}
.approval-actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:11px}
.approval-actions button{height:30px;border-radius:var(--r-sm);border:1px solid var(--line-strong);
  background:var(--surface);color:var(--text);padding:0 12px;cursor:pointer;
  font-size:var(--fs-label);transition:background .15s ease,border-color .15s ease}
.approval-actions button:hover{background:var(--hover)}
.approval-actions button.allow{border-color:var(--state-decide);color:var(--state-decide);font-weight:600}
.approval-actions button.allow:hover{background:var(--state-decide);color:var(--on-accent,#fff)}
.approval-actions button.deny:hover{border-color:var(--escalated);color:var(--escalated)}
/* Live run card: six-state progress over the audited gate pipeline. */
.run-card{border:1px solid var(--line);margin:var(--sp-1) 0 var(--sp-6);overflow:hidden;
  box-shadow:var(--shadow-2)}
.run-card{border-color:var(--line);border-radius:var(--r-lg);background:var(--surface)}
.run-overview{padding:var(--sp-4) var(--sp-4) var(--sp-3);border-bottom:1px solid var(--line)}
.run-top{display:flex;align-items:center;gap:8px}
.run-eyebrow{font-size:var(--fs-caption);color:var(--text-3);font-weight:600}
.run-top .status{margin-left:auto}
/* An always-visible Stop while a run is live — sits at the head of the card. */
.run-stop{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 11px;
  border:1px solid var(--blocked);border-radius:999px;background:var(--blocked-bg);
  color:var(--blocked);font-size:var(--fs-caption);font-weight:600;cursor:pointer;
  transition:background var(--dur-fast) ease,color var(--dur-fast) ease}
.run-stop:hover{background:var(--blocked);color:var(--inverse-text)}
.run-stop:disabled{opacity:.6;cursor:wait}
.run-stop-glyph{width:9px;height:9px;border-radius:2px;background:currentColor;flex:none}
.run-task{font-size:var(--fs-title);line-height:1.35;font-weight:600;letter-spacing:-.01em;
  margin:8px 0 7px;overflow-wrap:anywhere}
.run-meta{display:flex;align-items:center;gap:var(--sp-3);color:var(--text-3);font-size:var(--fs-caption)}
.run-meta span{display:flex;align-items:center;gap:4px}
.run-meta strong{color:var(--text-2);font-weight:500;font-family:var(--font-label);
  font-variant-numeric:tabular-nums}
.run-handoff{position:relative;height:8px;margin-top:10px;display:none}
.run-card[data-handoff] .run-handoff{display:block}
.run-handoff i{position:absolute;top:0;left:0;width:8px;height:8px;border-radius:50%;background:var(--role-g)}
.run-card[data-handoff="check"] .run-handoff i{animation:handoff var(--dur-story) var(--spring-soft) both}
.run-card[data-handoff="revise"] .run-handoff i{left:auto;right:0;background:var(--role-a);
  animation:handoff-back var(--dur-story) var(--spring-soft) both}
@keyframes handoff{from{transform:translateX(0);opacity:0}20%{opacity:1}to{transform:translateX(120px);opacity:1}}
@keyframes handoff-back{from{transform:translateX(0);opacity:0}20%{opacity:1}to{transform:translateX(-120px);opacity:1}}
.run-meter{height:3px;border-radius:var(--r-pill);background:var(--surface-2);overflow:hidden;margin-top:11px}
.run-meter i{height:100%;display:block;border-radius:inherit;background:var(--accent);
  transition:width var(--dur-fast) linear}
.run-card.passed .run-meter i,.run-card.consumed .run-meter i{background:var(--pass)}
.run-card.blocked .run-meter i,.run-card.refused .run-meter i{background:var(--blocked)}
.run-card.escalated .run-meter i{background:var(--state-decide)}
.loop{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));padding:var(--sp-4) var(--sp-4) var(--sp-3);gap:0}
.loop-step{min-width:0;position:relative;padding-right:12px}
.loop-step:last-child{padding-right:0}
.loop-track{height:24px;position:relative}
.loop-step:not(:last-child) .loop-track:after{content:'';position:absolute;top:11px;left:27px;right:4px;
  height:1px;background:var(--line-strong)}
.loop-step.done:not(:last-child) .loop-track:after{background:var(--pass)}
.loop-mark{position:relative;z-index:1;width:22px;height:22px;border-radius:50%;background:var(--surface);
  border:1.5px solid var(--line-strong);display:grid;place-items:center;font-size:9px;color:var(--text-3);
  font-weight:600;box-shadow:0 0 0 3px var(--surface)}
.loop-step.done .loop-mark{background:var(--pass);border-color:var(--pass);color:var(--surface)}
.loop-step.failed .loop-mark{background:var(--blocked);border-color:var(--blocked);color:var(--surface)}
.loop-step.current .loop-mark{background:var(--accent);border-color:var(--accent);color:var(--surface)}
.loop-name{font-size:var(--fs-label);margin-top:7px;font-weight:500;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.loop-detail{font-size:var(--fs-caption);color:var(--text-3);margin-top:3px;line-height:1.35;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:26px}
.loop-state{font-size:var(--fs-caption);margin-top:5px;color:var(--text-3);font-weight:500}
.loop-step.done .loop-state{color:var(--pass)}
.loop-step.failed .loop-state{color:var(--blocked)}
.loop-step.current .loop-state{color:var(--accent)}
.loop-focus{margin:0 var(--sp-4) var(--sp-4);padding:10px 12px;border:1px solid var(--line);
  border-radius:var(--r-md);background:var(--surface-2);display:grid;
  grid-template-columns:88px minmax(0,1fr);gap:8px 12px;align-items:start}
.loop-focus-label{font-size:var(--fs-caption);color:var(--text-3);font-weight:600;padding-top:2px}
.loop-focus-copy b{display:block;font-size:var(--fs-label);font-weight:600}
.loop-focus-copy p{margin:2px 0 0;color:var(--text-2);font-size:var(--fs-caption);line-height:1.45}
.loop-focus.current{border-color:color-mix(in srgb,var(--accent) 40%,var(--line));background:var(--accent-bg)}
.loop-focus.failed{border-color:color-mix(in srgb,var(--blocked) 40%,var(--line));background:var(--blocked-bg)}
.loop-focus.done{border-color:color-mix(in srgb,var(--pass) 40%,var(--line));background:var(--pass-bg)}
.activity{border-top:1px solid var(--line);padding:var(--sp-3) var(--sp-4) var(--sp-4);background:var(--surface)}
.activity-head{display:flex;align-items:center;margin-bottom:7px;font-size:var(--fs-caption);
  font-weight:600;color:var(--text-2)}
.activity-head span{margin-left:auto;color:var(--text-3);font-weight:400}
.activity-list{display:grid;gap:2px;max-height:190px;overflow:auto}
.audit-event{display:grid;grid-template-columns:24px minmax(0,1fr) auto;gap:9px;align-items:start;
  padding:6px 5px;border-radius:var(--r-xs)}
.audit-event:hover{background:var(--hover)}
.event-mark{width:22px;height:22px;border-radius:var(--r-xs);display:grid;place-items:center;
  background:var(--surface-2);color:var(--text-2);font-size:8.5px;font-weight:600}
.event-mark.generator{background:var(--role-g-bg);color:var(--role-g)}
.event-mark.auditor{background:var(--role-a-bg);color:var(--role-a)}
.event-mark.compute{background:var(--escalated-bg);color:var(--escalated)}
.event-mark.tool,.event-mark.done{background:var(--pass-bg);color:var(--pass)}
.event-main{min-width:0}
.event-line{font-size:var(--fs-label);line-height:1.35}
.event-line b{font-weight:600;margin-right:6px}
.event-detail{color:var(--text-3);font-size:var(--fs-caption);line-height:1.4;margin-top:2px;
  white-space:pre-wrap;overflow-wrap:anywhere}
.event-time{color:var(--text-3);font-size:var(--fs-caption);font-family:var(--font-label);padding-top:2px}
.activity-empty{padding:6px 4px;color:var(--text-3);font-size:var(--fs-label);line-height:1.45}
.audit-evidence-head{display:flex;align-items:baseline;gap:8px;margin:var(--sp-6) 0 var(--sp-3);padding-top:1px}
.audit-evidence-head h3{margin:0;font-size:var(--fs-body);font-weight:600}
.audit-evidence-head span{color:var(--text-3);font-size:var(--fs-caption)}

/* Composer: the one write path, floating Nav glass over the thread. */
.composer-wrap{position:absolute;left:var(--sidebar);right:var(--inspector);bottom:0;
  padding:var(--sp-7) var(--sp-5) var(--sp-4);pointer-events:none;z-index:var(--z-composer)}
.composer-wrap.view-hidden{display:none}
.composer{width:min(var(--thread-max),100%);margin:0 auto;pointer-events:auto;
  border:1px solid var(--glass-border);border-radius:var(--r-xl);background:var(--glass-nav-bg);
  box-shadow:var(--edge-highlight),var(--shadow-3);padding:var(--sp-2);
  -webkit-backdrop-filter:blur(20px) saturate(150%);backdrop-filter:blur(20px) saturate(150%);
  transition:border-color var(--dur-fast) ease,box-shadow var(--dur-fast) ease}
.composer:focus-within{border-color:color-mix(in srgb,var(--accent) 42%,var(--glass-border))}
.composer.drag{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg),var(--shadow-3)}
.contract-preview{display:none;margin:1px 3px 7px;padding:7px 9px;border-radius:var(--r-sm);
  background:var(--accent-bg);color:var(--text-2);font-size:var(--fs-caption);line-height:1.4}
.contract-preview.on{display:block}
.contract-preview b{color:var(--accent)}
.attachments{display:none;gap:6px;padding:3px 3px 8px;max-height:172px;overflow:auto}
.attachments.on{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr))}
.attachment{position:relative;display:grid;grid-template-columns:28px minmax(0,1fr) 20px;align-items:center;
  gap:7px;background:var(--surface-2);border:1px solid var(--line);border-radius:var(--r-md);
  padding:7px;min-width:0;overflow:hidden}
.attachment-type{width:28px;height:28px;border-radius:var(--r-xs);background:var(--surface);
  border:1px solid var(--line);display:grid;place-items:center;color:var(--text-2);font-size:8px;
  font-weight:600;font-family:var(--font-mono)}
.attachment-copy{min-width:0}
.attachment-name{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  font-size:var(--fs-caption);font-weight:500}
.attachment-state{display:block;color:var(--text-3);font-size:var(--fs-caption);margin-top:1px}
.attachment button{border:0;background:none;color:var(--text-3);padding:0;width:20px;height:20px;
  border-radius:5px}
.attachment button:hover{background:var(--hover);color:var(--text)}
.attachment-progress{position:absolute;left:0;right:0;bottom:0;height:2px;background:transparent}
.attachment-progress i{display:block;height:100%;background:var(--accent);
  transition:width var(--dur-fast) linear}
.attachment.failed{border-color:var(--blocked)}
.attachment.failed .attachment-state{color:var(--blocked)}
.attachment-note{grid-column:1/-1;color:var(--text-2);font-size:var(--fs-caption);padding:1px 2px;
  display:flex;gap:7px;align-items:center}
.attachment-note b{color:var(--text);font-weight:500}
.attachment-more{color:var(--accent)}
.audience-bar{display:flex;align-items:center;gap:5px;padding:1px 3px 5px}
.audience-label{font-size:var(--fs-caption);color:var(--text-3);margin-right:2px}
.audience-chip{height:24px;border:1px solid transparent;border-radius:var(--r-xs);background:transparent;
  color:var(--text-2);padding:0 8px;font-size:var(--fs-caption)}
.audience-chip:hover{background:var(--hover)}
.audience-chip.active{background:var(--surface-2);color:var(--text);border-color:var(--line-strong);font-weight:500}
.audience-chip[data-audience="generator"].active{background:var(--role-g-bg);color:var(--role-g);border-color:transparent}
.audience-chip[data-audience="auditor"].active{background:var(--role-a-bg);color:var(--role-a);border-color:transparent}
.compose-row{display:flex;align-items:flex-end;gap:7px}
.compose-well{flex:1;min-width:0;display:flex;background:var(--surface-2);border-radius:var(--r-md)}
textarea{border:0;outline:0;resize:none;min-height:44px;max-height:160px;flex:1;
  padding:12px 10px 10px;background:transparent;line-height:1.5;font-size:var(--fs-prose)}
textarea::placeholder{color:var(--text-3)}
.compose-button{border:0;background:transparent;width:34px;height:34px;border-radius:var(--r-sm);
  display:grid;place-items:center;color:var(--text-2);flex:none;margin-bottom:5px;
  transition:background var(--dur-fast) ease,color var(--dur-fast) ease}
.compose-button:hover{background:var(--hover);color:var(--text)}
.compose-button:active{transform:scale(.97)}
.send{background:var(--accent);color:var(--inverse-text)}
.send:hover{background:var(--send-hover);color:var(--inverse-text)}
.send:disabled{opacity:.35;cursor:default}
.stop{background:var(--blocked);color:var(--inverse-text)}
.stop:hover{background:color-mix(in srgb,var(--blocked) 86%,#fff);color:var(--inverse-text)}
.stop:disabled{opacity:.62;cursor:wait}
.composer-meta{display:flex;align-items:center;gap:var(--sp-2);padding:5px 5px 1px;
  color:var(--text-3);font-size:var(--fs-caption)}
#model-summary{border:0;background:transparent;padding:0;color:var(--text-2);
  font-family:var(--font-label);font-size:var(--fs-caption);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;max-width:220px;cursor:pointer}
#model-summary:hover{color:var(--text)}
.autonomy-summary{display:inline-flex;align-items:center;gap:4px;border-left:1px solid var(--line);
  padding-left:8px;color:var(--text-2)}
.autonomy-summary:hover{color:var(--text)}
.route{display:none;margin:7px 3px 0;padding:7px 9px;border-radius:var(--r-sm);background:var(--surface-2);
  color:var(--text-2);font-size:var(--fs-label);white-space:pre-wrap;word-break:break-word}
.route.on{display:block}
.route.setup{background:var(--escalated-bg,var(--surface-2))}
.setup-card{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px}
.setup-card b{flex:1 1 100%}
.setup-card span{flex:1 1 auto;color:var(--text-2)}
.setup-card-action{flex:0 0 auto}
.route b{color:var(--text)}
.route .ask{color:var(--escalated)}
.drop-overlay{position:fixed;inset:0;z-index:var(--z-overlay);display:none;place-items:center;padding:26px;
  pointer-events:none;background:var(--scrim-bg);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px)}
.drop-overlay.on{display:grid}
.drop-target{width:min(560px,calc(100vw - 52px));min-height:240px;border:2px dashed var(--accent);
  border-radius:var(--r-xl);background:var(--glass-palette-bg);
  box-shadow:var(--edge-highlight),var(--shadow-4);display:flex;flex-direction:column;
  align-items:center;justify-content:center;text-align:center;padding:36px;
  -webkit-backdrop-filter:blur(34px) saturate(170%);backdrop-filter:blur(34px) saturate(170%)}
.drop-icon{width:48px;height:48px;border-radius:var(--r-lg);background:var(--accent-bg);color:var(--accent);
  display:grid;place-items:center;font-size:24px;margin-bottom:14px}
.drop-target b{font-size:var(--fs-h2)}
.drop-target span{color:var(--text-2);font-size:var(--fs-label);margin-top:6px;max-width:380px}

/* Right context panel: five tabs, on demand, never squeezing the centre. */
.inspector{position:fixed;right:8px;top:calc(var(--topbar-h) + 14px);bottom:8px;width:var(--ctx-w);
  z-index:var(--z-sheet);border:1px solid var(--line);border-radius:var(--r-xl);
  background:var(--surface);box-shadow:var(--shadow-2);
  transform:translateX(calc(100% + 16px));visibility:hidden;
  transition:transform var(--dur-slow) var(--spring),visibility 0s var(--dur-slow)}
.inspector.open{transform:translateX(0);visibility:visible;transition:transform var(--dur-slow) var(--spring)}
.inspect-head{display:flex;align-items:center;min-height:48px;padding:0 var(--sp-3) 0 var(--sp-4);flex:none}
.inspect-head h2{font-size:var(--fs-body);margin:0;font-weight:600}
.panel-tabs{display:flex;flex-wrap:wrap;gap:2px;padding:0 var(--sp-2) var(--sp-2);flex:none}
/* flex-basis:auto, not 0: a tab is never narrower than its own label. Eight
   tabs at a 318px panel width give 36px each, and "Governed" needs 52 — with
   an equal-share basis the labels bled into each other rather than wrapping.
   They now take a second row instead of being clipped. The rows start at the
   same edge: centred, the second row floated in the middle aligned to nothing
   above it, which reads as leftovers rather than as a grid.
   English is two rows at EVERY desktop width, not only narrow ones — the strip
   never exceeds 398px — so this is the permanent English layout, not an edge
   case. Chinese is one row everywhere. The inspector getting NARROWER as the
   screen gets wider (398px at 1280, 318px at 1440-1920) is what makes one row
   impossible in English; that inversion belongs to whoever owns the inspector. */
.panel-tabs .nav-item{flex:0 1 auto;min-width:0;height:40px;padding:0 7px;border:0;border-radius:var(--r-sm);
  background:transparent;display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:2px;color:var(--text-2);font-size:var(--fs-caption);text-align:center}
.panel-tabs .nav-item:hover{background:var(--hover);color:var(--text)}
.panel-tabs .nav-item.active{background:var(--surface-2);color:var(--text);font-weight:500}
.panel-tabs .nav-icon{width:15px;height:15px;color:currentColor}
.panel-tabs .nav-icon:before{width:15px;height:15px}
.panel-body{flex:1;min-height:0;overflow:auto;padding:0 var(--sp-4) var(--sp-4)}
.panel-pane{min-width:0}
.inspect-section{border-top:1px solid var(--line);padding:var(--sp-4) 1px}
.inspect-section:first-of-type{border-top:0;padding-top:var(--sp-2)}
.inspect-title{font-size:var(--fs-caption);color:var(--text-3);font-weight:600;margin-bottom:9px}
.kv{display:flex;gap:10px;padding:4px 0;font-size:var(--fs-label)}
.kv span:first-child{color:var(--text-2)}
.kv span:last-child{margin-left:auto;text-align:right;min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;max-width:175px;font-family:var(--font-mono);font-size:var(--fs-caption);
  font-variant-numeric:tabular-nums}
.model{padding:9px 10px;border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  margin-bottom:6px;display:flex;align-items:center;gap:10px}
.model .role-mark{width:22px;height:22px}
.model-copy{min-width:0;flex:1}
.model-role{font-size:var(--fs-caption);color:var(--text-3)}
.model-name{font-size:var(--fs-caption);font-family:var(--font-label);margin-top:2px;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.model-actions-row{display:flex;gap:6px;margin-top:var(--sp-2)}
.model-actions-row .secondary{flex:1;height:30px;font-size:var(--fs-caption)}
.contract{font-family:var(--font-mono);font-size:var(--fs-caption);padding:4px 0;color:var(--text-2);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* SPEC-2. One verification vocabulary, four states, used by every surface that
   shows a check result. The glyph carries the state so the row survives
   greyscale, colour-blindness and a screenshot pasted into a bug report; the
   colour is a second channel, never the only one. Only .passed may be green.
   Failed is the only state that takes a background, so a panel of passing rows
   does not become a wall of colour and one failure stands out.
   Not-run is --text-2, deliberately NOT --text-3: --text-3 measures 3.06:1
   light / 3.77:1 dark and would make the honest state the unreadable one. */
.check-summary{margin:0 0 8px;font-size:var(--fs-caption);color:var(--text-2);line-height:1.5}
.check-row{display:flex;align-items:baseline;gap:7px;padding:4px 0;
  font-family:var(--font-mono);font-size:var(--fs-caption);color:var(--text-2);font-weight:400}
.check-glyph{width:11px;flex:none;text-align:center;font-family:var(--font-label)}
.check-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.check-row.passed{color:var(--pass);font-weight:500}
.check-row.failed{color:var(--blocked);font-weight:600;background:var(--blocked-bg);
  border-radius:var(--r-xs);padding-left:5px;margin:0 -5px}
/* Measured, not assumed: --blocked on its own 10% wash composites to 4.50:1 in
   light at 1440 and 4.31:1 at 390, where the panel sits on a different ground.
   The failed row is the one state that must never be the hard one to read. */
:root[data-theme="light"] .check-row.failed{color:#A82F26}
.mini-metrics{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.mini-metric{border:1px solid var(--line);background:var(--surface);border-radius:var(--r-sm);padding:8px}
.mini-value{font-size:var(--fs-h2);font-weight:600;letter-spacing:-.02em;font-family:var(--font-mono);
  font-variant-numeric:tabular-nums}
.mini-label{font-size:var(--fs-caption);color:var(--text-3)}
.escalation{padding:9px 10px;background:var(--state-decide-bg);border-radius:var(--r-sm);margin-bottom:6px}
.escalation b{font-size:var(--fs-label);color:var(--state-decide)}
.escalation p{font-size:var(--fs-caption);color:var(--text-2);margin:3px 0 0}
.escalation small{color:var(--text-3);font-size:var(--fs-caption)}
.escalation-actions{display:flex;gap:5px;margin-top:8px}
.escalation-actions button{height:26px;font-size:var(--fs-caption);padding:0 8px}
.empty{color:var(--text-3);font-size:var(--fs-label);padding:var(--sp-5) var(--sp-4);
  border:1px dashed var(--line-strong);border-radius:var(--r-md);text-align:center}
.files{white-space:pre-wrap;word-break:break-word}
.mobile-sidebar{display:none}
.scrim{display:none;position:fixed;inset:0;z-index:calc(var(--z-sheet) - 1);border:0;
  background:var(--scrim-bg);padding:0}
.scrim.on{display:block}

/* Command palette: navigation and common actions on Cmd+K. */
.palette-shell{align-items:flex-start!important;padding-top:16vh!important}
.palette{width:min(560px,calc(100vw - 32px));max-height:min(430px,60vh);display:flex;flex-direction:column;
  border:1px solid var(--glass-border);border-radius:var(--r-xl);background:var(--glass-palette-bg);
  box-shadow:var(--edge-highlight),var(--shadow-4);overflow:hidden;
  -webkit-backdrop-filter:blur(34px) saturate(170%);backdrop-filter:blur(34px) saturate(170%)}
.palette-input{height:48px;border:0;outline:0;background:transparent;padding:0 var(--sp-4);
  font-size:var(--fs-title);color:var(--text);border-bottom:1px solid var(--line);flex:none;
  border-radius:0}
.palette-input::placeholder{color:var(--text-3)}
.palette-list{flex:1;min-height:0;overflow:auto;padding:var(--sp-2)}
.palette-section{font-size:var(--fs-caption);font-weight:600;color:var(--text-3);
  padding:var(--sp-2) var(--sp-2) var(--sp-1)}
.palette-row{display:flex;align-items:center;gap:10px;width:100%;min-height:40px;border:0;
  border-radius:var(--r-md);background:transparent;padding:0 var(--sp-3);color:var(--text);
  text-align:left;font-size:var(--fs-body);position:relative}
.palette-row .palette-context{margin-left:auto;color:var(--text-3);font-size:var(--fs-caption);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:40%}
.palette-row kbd{color:var(--text-3);font:var(--fs-caption) var(--font-mono);margin-left:8px}
.palette-row.selected{background:var(--hover)}
.palette-row.selected:before{content:"";position:absolute;left:0;top:8px;bottom:8px;width:2px;
  border-radius:2px;background:var(--accent)}
.palette-empty{padding:var(--sp-5);text-align:center;color:var(--text-3);font-size:var(--fs-body)}

/* Human decision screen: what was wanted, tried, blocked, and suggested. */
.decision{display:none;position:fixed;left:var(--sidebar);right:0;top:calc(var(--topbar-h) + 14px);
  bottom:0;background:var(--surface);overflow:auto;
  /* The inspector shares --z-sheet and comes later in the DOM, so it won the
     tie and covered this surface: the close button rendered, looked live and
     did nothing. A modal that announces itself and cannot be dismissed is
     worse than one that does neither, so the decision sits one level above. */
  z-index:calc(var(--z-sheet) + 1);
  margin:0 8px 8px;border:1px solid var(--line);border-radius:var(--r-xl)}
.decision.on{display:block}
body.deciding .composer-wrap{display:none}
.decision-body{width:min(640px,calc(100% - 40px));margin:0 auto;padding:var(--sp-7) 0 var(--sp-9)}
.decision-head{display:flex;align-items:flex-start;gap:var(--sp-3);margin-bottom:var(--sp-6)}
.decision-glyph{width:36px;height:36px;border-radius:var(--r-md);background:var(--state-decide-bg);
  color:var(--state-decide);display:grid;place-items:center;flex:none}
.decision-glyph:before{width:20px;height:20px}
.decision-head h1{font-size:var(--fs-h1);line-height:1.2;margin:0;letter-spacing:-.02em;font-weight:600}
.decision-head p{margin:6px 0 0;color:var(--text-2);font-size:var(--fs-prose);line-height:1.6}
.decision-flag{display:inline-flex;align-items:center;gap:6px;color:var(--state-decide);
  font-size:var(--fs-caption);font-weight:600;margin-bottom:6px}
.decision-block{margin-bottom:var(--sp-6)}
.decision-label{font-size:var(--fs-caption);text-transform:uppercase;letter-spacing:.06em;
  color:var(--text-3);font-weight:600;margin-bottom:var(--sp-2)}
.decision-goal{margin:0;font-size:var(--fs-prose);line-height:1.6;overflow-wrap:anywhere}
.decision-limit{display:flex;gap:12px;align-items:flex-start;padding:var(--sp-3) var(--sp-4);
  border:1px solid var(--line);background:var(--surface-2);border-radius:var(--r-md)}
.decision-limit-mark{display:grid;place-items:center;flex:none;width:28px;height:28px;
  border-radius:var(--r-sm);background:var(--state-decide-bg);color:var(--state-decide);font-weight:600}
.decision-limit b{display:block;font-size:var(--fs-body)}
.decision-limit p{margin:3px 0 0;color:var(--text-2);font-size:var(--fs-label);line-height:1.45}
.decision-attempts{margin-top:var(--sp-2);display:grid;gap:2px}
.decision-attempt{display:flex;align-items:baseline;gap:10px;padding:5px 2px;font-size:var(--fs-body)}
.decision-attempt .round-n{font-family:var(--font-label);font-size:var(--fs-caption);color:var(--text-3);flex:none}
.decision-attempt .verdict-word{margin-left:auto;font-weight:600;font-size:var(--fs-caption)}
.decision-attempt .verdict-word.passed{color:var(--pass)}
.decision-attempt .verdict-word.blocked{color:var(--blocked)}
.decision-title-row{display:flex;align-items:center;gap:8px;font-size:var(--fs-body);font-weight:600;
  margin-bottom:9px}
.decision-count{border-radius:var(--r-pill);background:var(--blocked-bg);color:var(--blocked);
  padding:2px 7px;font-size:var(--fs-caption);font-family:var(--font-mono)}
.decision-issues{display:grid;gap:7px}
.decision-issue{border:1px solid var(--line);border-radius:var(--r-md);padding:10px 12px;
  background:var(--surface)}
.decision-issue-head{display:flex;gap:7px;align-items:center;font-size:var(--fs-caption);color:var(--text-3)}
.decision-issue-head span:first-child{color:var(--blocked);font-weight:600}
.decision-issue-head b{color:var(--text);font-size:var(--fs-caption)}
.decision-issue p{margin:5px 0 0;font-size:var(--fs-body);line-height:1.5;color:var(--text)}
.decision-issue small{display:block;margin-top:5px;color:var(--text-3);font-size:var(--fs-caption);
  font-family:var(--font-mono);overflow-wrap:anywhere}
.decision-empty{border:1px solid var(--line);border-radius:var(--r-md);padding:11px;color:var(--text-2);
  font-size:var(--fs-label);line-height:1.5;background:var(--surface-2)}
.decision-request{color:var(--text-2);font-size:var(--fs-body);line-height:1.5;margin:0 0 10px}
.decision-secondary{display:flex;gap:7px;margin-bottom:10px;flex-wrap:wrap}
.decision-options{display:grid;grid-template-columns:1fr;gap:9px}
.decision-option{position:relative;display:flex;gap:10px;padding:var(--sp-3) var(--sp-4);
  border:1px solid var(--line-strong);border-radius:var(--r-md);background:var(--surface);cursor:pointer}
.decision-option:hover{background:var(--hover)}
.decision-option:has(input:checked){border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg)}
.decision-option input{margin-top:2px;accent-color:var(--accent)}
.decision-option b{display:block;font-size:var(--fs-body);font-weight:600}
.decision-option small{display:block;margin-top:3px;color:var(--text-2);font-size:var(--fs-label);line-height:1.45}
.suggested-tag{display:inline-block;margin-left:8px;padding:2px 6px;border-radius:var(--r-xs);
  background:var(--state-decide-bg);color:var(--state-decide);font-size:var(--fs-caption);font-weight:600}
.decision-guidance{margin-top:var(--sp-3)}
.decision-guidance textarea{min-height:86px}
.decision-ledger-note{display:flex;gap:6px;align-items:center;color:var(--text-2);
  font-size:var(--fs-caption);margin-top:8px}
.decision-ledger-note b{color:var(--text)}
.decision-actions{display:flex;align-items:center;gap:9px;margin-top:var(--sp-5)}
.decision-actions .stop-task{border:0;background:transparent;color:var(--blocked);font-size:var(--fs-label);
  padding:0}
.decision-actions .primary{margin-left:auto}
/* Panel views: files, audit, usage, compute, tools. Compact and opaque. */
.view-heading{padding:var(--sp-2) 0 var(--sp-4)}
.view-heading h2{font-size:var(--fs-body);margin:0;font-weight:600;letter-spacing:-.01em}
.view-heading p{margin:4px 0 0;color:var(--text-3);font-size:var(--fs-caption);line-height:1.5}
.artifact-grid{display:grid;grid-template-columns:1fr;gap:8px}
.artifact-grid .output-file{margin:0;min-width:0}
.finding,.output-file,.usage-card,.usage-role,.usage-bars{border-color:var(--line)}
.usage-note{display:flex;align-items:flex-start;gap:9px;margin:0 0 var(--sp-4);padding:10px 11px;
  border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface-2);
  color:var(--text-2);font-size:var(--fs-caption);line-height:1.5}
.usage-note b{color:var(--text);font-weight:600}
.usage-note span:first-child{color:var(--accent)}
.usage-cards{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:var(--sp-5)}
.usage-card{border:1px solid var(--line);border-radius:var(--r-md);padding:var(--sp-3);
  background:var(--surface);min-width:0}
.usage-card-label{font-size:var(--fs-caption);color:var(--text-3);font-weight:600}
.usage-card-value{font-size:var(--fs-h2);font-weight:600;letter-spacing:-.02em;margin-top:6px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:var(--font-mono);
  font-variant-numeric:tabular-nums}
.usage-card-detail{font-size:var(--fs-caption);color:var(--text-2);margin-top:3px}
.usage-section{margin:0 0 var(--sp-5)}
.usage-section-head{display:flex;align-items:baseline;gap:8px;margin-bottom:10px}
.usage-section-head h3{font-size:var(--fs-label);margin:0;font-weight:600}
.usage-section-head span{color:var(--text-3);font-size:var(--fs-caption)}
.usage-bars{height:110px;display:grid;grid-template-columns:repeat(7,1fr);gap:5px;align-items:end;
  padding:12px 10px 8px;border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface)}
.usage-day{height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;
  gap:5px;min-width:0}
.usage-day-value{font-size:var(--fs-caption);color:var(--text-3);white-space:nowrap;display:none}
.usage-bar-track{height:62px;width:100%;max-width:24px;display:flex;align-items:flex-end;
  border-radius:5px;background:var(--surface-2);overflow:hidden}
.usage-bar{width:100%;min-height:2px;border-radius:5px;background:var(--accent)}
.usage-day-label{font-size:var(--fs-caption);color:var(--text-3)}
.usage-roles{display:grid;grid-template-columns:1fr;gap:8px}
.usage-role{border:1px solid var(--line);border-radius:var(--r-md);padding:11px 12px;background:var(--surface)}
.usage-role-top{display:flex;align-items:center;gap:7px}
.usage-role-top b{font-size:var(--fs-label);text-transform:capitalize;font-weight:600}
.usage-role-top span{margin-left:auto;color:var(--text-2);font-size:var(--fs-caption);
  font-family:var(--font-mono)}
.usage-role-meter{height:4px;background:var(--surface-2);border-radius:var(--r-pill);overflow:hidden;
  margin:9px 0 5px}
.usage-role-meter i{height:100%;display:block;background:var(--role-g);border-radius:inherit}
.usage-role.auditor i{background:var(--role-a)}
.usage-role small{color:var(--text-3);font-size:var(--fs-caption)}
.usage-table{border:1px solid var(--line);border-radius:var(--r-md);overflow:hidden;background:var(--surface)}
.usage-row{display:grid;grid-template-columns:minmax(90px,1fr) 64px 64px;gap:8px;align-items:center;
  padding:9px 10px;border-bottom:1px solid var(--line);font-size:var(--fs-caption);
  font-variant-numeric:tabular-nums}
.usage-row>*:nth-child(3),.usage-row>*:nth-child(5){display:none}
.usage-row:last-child{border-bottom:0}
.usage-row.head{background:var(--surface-2);color:var(--text-3);font-weight:600}
.usage-model{min-width:0}
.usage-model b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  font-family:var(--font-ui);font-size:var(--fs-caption);font-weight:500}
.usage-model small{color:var(--text-3);text-transform:capitalize}
.usage-quality{display:inline-flex;width:max-content;padding:3px 5px;border-radius:var(--r-xs);
  background:var(--pass-bg);color:var(--pass);font-size:var(--fs-caption);font-weight:600}
.usage-quality.estimated{background:var(--escalated-bg);color:var(--escalated)}
.usage-quality.unpriced{background:var(--surface-2);color:var(--text-2)}
.usage-recent{display:grid;gap:3px}
.usage-call{display:grid;grid-template-columns:24px minmax(0,1fr) auto;gap:9px;align-items:center;
  padding:8px;border-radius:var(--r-sm)}
.usage-call:hover{background:var(--hover)}
.usage-call-mark{width:22px;height:22px;border-radius:var(--r-xs);display:grid;place-items:center;
  background:var(--role-g-bg);color:var(--role-g);font-size:8px;font-weight:600}
.usage-call-mark.auditor{background:var(--role-a-bg);color:var(--role-a)}
.usage-call-main{min-width:0}
.usage-call-main b{display:block;font-size:var(--fs-caption);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;font-family:var(--font-ui);font-weight:500}
.usage-call-main span{font-size:var(--fs-caption);color:var(--text-3)}
.usage-call-value{text-align:right;font-variant-numeric:tabular-nums}
.usage-call-value b{display:block;font-size:var(--fs-caption);font-family:var(--font-mono)}
.usage-call-value span{display:block;color:var(--text-3);font-size:var(--fs-caption)}
.compute-toolbar{display:flex;align-items:center;gap:8px;margin-bottom:var(--sp-4);flex-wrap:wrap}
.compute-toolbar .spacer{flex:1}
.compute-note{display:flex;gap:9px;padding:11px 12px;border:1px solid var(--line);
  border-radius:var(--r-md);background:var(--surface-2);color:var(--text-2);
  font-size:var(--fs-caption);line-height:1.5;margin-bottom:var(--sp-4)}
.compute-note b{color:var(--text)}
.compute-message{display:none;margin:-8px 0 var(--sp-4);padding:9px 11px;border-radius:var(--r-sm);
  background:var(--blocked-bg);color:var(--blocked);font-size:var(--fs-caption)}
.compute-message.on{display:block}
.compute-grid{display:grid;grid-template-columns:1fr;gap:14px;align-items:start}
.compute-section{border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  overflow:hidden}
.compute-section-head{display:flex;align-items:center;gap:8px;padding:11px 12px;
  border-bottom:1px solid var(--line)}
.compute-section-head b{font-size:var(--fs-label);font-weight:600}
.compute-section-head span{margin-left:auto;color:var(--text-3);font-size:var(--fs-caption)}
.compute-empty{padding:24px 14px;text-align:center;color:var(--text-3);font-size:var(--fs-label)}
.host-row{padding:11px 12px;border-bottom:1px solid var(--line)}
.host-row:last-child{border-bottom:0}
.host-top{display:flex;align-items:center;gap:7px}
.host-top b{font-size:var(--fs-label);font-weight:600}
.host-kind{margin-left:auto;color:var(--text-2);background:var(--surface-2);padding:3px 6px;
  border-radius:var(--r-xs);font-size:var(--fs-caption)}
.host-detail{margin-top:5px;color:var(--text-2);font-size:var(--fs-caption);line-height:1.45;
  overflow-wrap:anywhere}
.host-resources{display:flex;flex-wrap:wrap;gap:4px;margin-top:7px}
.host-resource{border:1px solid var(--line);border-radius:var(--r-xs);padding:2px 5px;
  color:var(--text-3);font-size:var(--fs-caption)}
.host-actions{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}
.host-actions button{height:26px;font-size:var(--fs-caption);padding:0 8px}
.hpc-job{padding:12px;border-bottom:1px solid var(--line)}
.hpc-job:last-child{border-bottom:0}
.hpc-job-top{display:flex;align-items:center;gap:8px}
.hpc-job-top b{font-size:var(--fs-label);min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;font-weight:600}
.hpc-job-top .status{margin-left:auto}
.hpc-job-meta{display:flex;flex-wrap:wrap;gap:9px;color:var(--text-3);font-size:var(--fs-caption);
  margin-top:5px;font-family:var(--font-mono)}
.hpc-job-detail{color:var(--text-2);font-size:var(--fs-caption);margin-top:6px}
.hpc-connection-error{color:var(--escalated);font-size:var(--fs-caption);margin-top:5px}
.hpc-job-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
.hpc-job-actions button,.hpc-job-actions a{height:26px;font-size:var(--fs-caption);padding:0 8px}
.hpc-console{display:none;margin-top:9px;border:1px solid var(--line);border-radius:var(--r-sm);
  overflow:hidden}
.hpc-console.on{display:block}
.hpc-console-tabs{display:flex;align-items:center;gap:4px;padding:6px 7px;background:var(--surface-2);
  border-bottom:1px solid var(--line);font-size:var(--fs-caption);color:var(--text-3)}
.hpc-console-tabs .bad{color:var(--blocked)}
.hpc-console pre{margin:0;padding:9px;max-height:240px;overflow:auto;background:var(--surface-2);
  color:var(--text);font:var(--fs-caption)/1.5 var(--font-mono);white-space:pre-wrap}
.hpc-output-list{display:grid;gap:5px;padding:8px}
.hpc-output{display:flex;align-items:center;gap:8px;border:1px solid var(--line);
  border-radius:var(--r-sm);padding:7px 8px;color:var(--text);text-decoration:none;
  font-size:var(--fs-caption)}
.hpc-output:hover{background:var(--hover)}
.hpc-output span:last-child{margin-left:auto;color:var(--text-3)}
.mcp-tool-list{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}
.mcp-tool{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--line);
  border-radius:var(--r-xs);padding:4px 6px;font-size:var(--fs-caption);color:var(--text-2)}
.mcp-tool.approved{border-color:color-mix(in srgb,var(--pass) 45%,var(--line));color:var(--pass)}
.mcp-tool .mcp-risk{margin-left:2px;padding:1px 6px;font-size:10px}
.mcp-call{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 10px;padding:10px 12px;
  border-bottom:1px solid var(--line)}
.mcp-call:last-child{border-bottom:0}
.mcp-call b{font-size:var(--fs-caption);font-weight:600}
.mcp-call small{color:var(--text-3);font-size:var(--fs-caption)}
.tools-grid .compute-section:last-child{grid-column:auto}

/* Project hub: the quiet control plane. */
.project-hub{display:none;height:100vh;overflow:auto;background:transparent}
body.hub-mode .app{display:none}
body.hub-mode .project-hub{display:block}
.hub-main{width:min(1100px,calc(100% - 48px));margin:0 auto;padding:44px 0 var(--sp-10)}
.hub-heading{display:flex;gap:18px;align-items:flex-end;margin-bottom:var(--sp-6)}
.hub-heading h1{margin:0;font-size:var(--fs-display);letter-spacing:-.025em;font-weight:600}
.hub-heading p{margin:5px 0 0;color:var(--text-2)}
.hub-summary{margin-left:auto;color:var(--text-2);font-size:var(--fs-label)}
.hub-note{margin-bottom:14px;padding:11px 14px;border:1px solid var(--line);border-radius:var(--r-md);
  background:var(--surface);color:var(--text-2);font-size:var(--fs-label);line-height:1.5}
.hub-tools{display:flex;gap:9px;margin-bottom:14px}
.hub-search{height:38px;min-width:280px;border:1px solid var(--line);border-radius:var(--r-md);
  background:var(--surface);padding:0 12px;outline:0;color:var(--text)}
.hub-search:focus{border-color:var(--accent)}
.primary{height:34px;border:0;border-radius:var(--r-sm);padding:0 13px;background:var(--accent);
  color:var(--inverse-text);font-weight:500;transition:filter var(--dur-instant) ease}
.primary:hover{filter:brightness(1.06)}
.primary:active{transform:scale(.97)}
.primary:disabled{opacity:.45;cursor:not-allowed}
.secondary{height:34px;border:1px solid var(--line-strong);border-radius:var(--r-sm);padding:0 12px;
  background:var(--surface);display:inline-flex;align-items:center;justify-content:center;
  text-decoration:none;color:var(--text)}
.secondary:hover{background:var(--hover)}
.project-table{border:1px solid var(--line);border-radius:var(--r-lg);background:var(--surface);
  overflow:hidden;box-shadow:var(--shadow-2)}
.project-row{width:100%;border:0;border-bottom:1px solid var(--line);background:transparent;
  display:grid;grid-template-columns:minmax(220px,1.6fr) minmax(200px,1fr) 96px 104px 116px 26px 26px 18px;
  align-items:center;gap:16px;padding:17px 20px;text-align:left;cursor:pointer;color:inherit;
  border-radius:var(--r-md);transition:background .12s}
.project-row:last-child{border-bottom:0}
.project-row:hover{background:var(--hover)}
/* Calm resting state: row actions appear on hover/focus (a pinned star stays),
   so the list reads by name + quiet metadata, not a wall of controls. */
@media (hover:hover){
  .project-pin,.project-delete,.project-arrow{opacity:0;transition:opacity .12s}
  .project-row:hover .project-pin,.project-row:hover .project-delete,.project-row:hover .project-arrow,
  .project-row:focus-within .project-pin,.project-row:focus-within .project-delete,
  .project-row:focus-within .project-arrow,.project-pin.pinned{opacity:1}
}
.project-pin{width:28px;height:28px;border:0;border-radius:var(--r-xs);background:transparent;
  color:var(--text-3);display:grid;place-items:center}
.project-pin:hover{background:var(--hover);color:var(--text)}
.project-delete{width:28px;height:28px;border:0;border-radius:var(--r-xs);background:transparent;
  color:var(--text-3);display:grid;place-items:center}
.project-delete:hover{background:var(--blocked-bg);color:var(--blocked)}
.project-name{display:block;font-weight:600;font-size:var(--fs-body)}
.project-path{display:block;font-size:var(--fs-caption);color:var(--text-3);margin-top:2px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:var(--font-ui)}
.project-models{font-size:var(--fs-caption);color:var(--text-2);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;font-family:var(--font-ui)}
.project-stat{font-size:var(--fs-caption);color:var(--text-2)}
.project-arrow{color:var(--text-3)}
.paired-mark{font-size:var(--fs-caption);color:var(--text-2);background:var(--surface-2);
  border-radius:var(--r-xs);padding:4px 6px;width:max-content}
.project-live{display:flex;align-items:center;gap:7px;margin-top:7px;min-width:0;color:var(--accent);
  font-size:var(--fs-caption)}
.project-progress{position:relative;display:block;width:8px;height:8px;flex:none;border-radius:50%;
  background:var(--accent)}
.project-progress i{display:block;width:100%;height:100%;border-radius:inherit;background:inherit;
  animation:breathe 2.4s ease-in-out infinite}
.project-live-copy{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.project-live-time{color:var(--text-3);flex:none;font-family:var(--font-label)}
.project-recovery{display:flex;align-items:center;gap:7px;margin-top:7px;color:var(--blocked);
  font-size:var(--fs-caption)}
.retry-setup{border:1px solid var(--blocked);border-radius:var(--r-xs);background:var(--surface);
  color:var(--blocked);padding:3px 7px;font-size:var(--fs-caption);font-weight:600}
.retry-setup:hover{background:var(--blocked-bg)}
.project-interrupted{display:block;margin-top:7px;color:var(--escalated);font-size:var(--fs-caption)}
.hub-empty{padding:50px 20px;text-align:center;color:var(--text-2)}
.job-panel{display:none;margin:0 0 var(--sp-4);border:1px solid color-mix(in srgb,var(--accent) 40%,var(--line));
  border-radius:var(--r-md);background:var(--accent-bg);padding:14px 16px}
.job-panel.on{display:flex;gap:13px;align-items:flex-start}
.job-spinner{width:12px;height:12px;border-radius:50%;background:var(--accent);margin-top:4px;flex:none;
  animation:breathe 2.4s ease-in-out infinite;display:grid;place-items:center}
.job-panel.failed{border-color:color-mix(in srgb,var(--blocked) 40%,var(--line));background:var(--blocked-bg)}
.job-panel.complete{border-color:color-mix(in srgb,var(--pass) 40%,var(--line));background:var(--pass-bg)}
.job-panel.failed .job-spinner,.job-panel.complete .job-spinner{animation:none;background:transparent;
  width:16px;height:16px}
.job-panel.failed .job-spinner:after{content:'×';color:var(--blocked);font-weight:600;font-size:14px}
.job-panel.complete .job-spinner:after{content:'✓';color:var(--pass);font-weight:600;font-size:13px}
.job-copy{min-width:0;flex:1}
.job-copy b{display:block}
.job-copy span{font-size:var(--fs-label);color:var(--text-2)}
.job-steps{margin:8px 0 0;padding:0;list-style:none;display:grid;gap:3px}
.job-steps li{font-size:var(--fs-caption);color:var(--text-2)}
.job-steps li:before{content:'✓';color:var(--pass);margin-right:6px}
/* Modal flows: guided setup on Palette-tier glass; forms stay opaque wells. */
.project-modal{display:none;position:fixed;inset:0;z-index:var(--z-overlay);background:var(--scrim-bg);
  -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);
  padding:28px;align-items:center;justify-content:center}
.project-modal.on{display:flex}
.wizard{width:min(720px,100%);max-height:calc(100vh - 40px);overflow:auto;
  background:var(--glass-palette-bg);border:1px solid var(--glass-border);border-radius:var(--r-xl);
  box-shadow:var(--edge-highlight),var(--shadow-4);
  -webkit-backdrop-filter:blur(34px) saturate(170%);backdrop-filter:blur(34px) saturate(170%)}
.project-modal.on .wizard{transform-origin:50% 14%;animation:materialize var(--dur-base) var(--spring) both}
@keyframes materialize{from{opacity:0;transform:translateY(10px) scale(.975)}to{opacity:1;transform:none}}
.wizard-head{padding:21px 24px 17px;display:flex;gap:12px;align-items:flex-start;
  border-bottom:1px solid var(--line)}
.wizard-head h2{font-size:var(--fs-h2);margin:0;letter-spacing:-.015em;font-weight:600}
.wizard-head p{margin:4px 0 0;color:var(--text-2);font-size:var(--fs-label);line-height:1.5}
.wizard-body{padding:22px 24px}
.wizard-foot{padding:15px 24px;border-top:1px solid var(--line);display:flex;align-items:center;gap:9px}
.wizard-foot span{font-size:var(--fs-caption);color:var(--text-2);margin-right:auto;max-width:390px}
.form-section{margin-bottom:25px}
.form-section:last-child{margin:0}
.form-title{font-size:var(--fs-label);font-weight:600;margin-bottom:11px;color:var(--text-2)}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px}
.field{display:block}
.field.full{grid-column:1/-1}
.field span{display:block;font-size:var(--fs-label);color:var(--text-2);margin-bottom:6px}
.field input,.field select,.field textarea,.fallback-row select,.fallback-row input{
  width:100%;min-height:38px;border:1px solid var(--line-strong);border-radius:var(--r-md);
  background:var(--surface);padding:9px 10px;outline:0;color:var(--text)}
.field textarea{resize:vertical;min-height:74px}
.field input:focus,.field select:focus,.field textarea:focus{border-color:var(--accent);
  box-shadow:0 0 0 3px var(--accent-bg)}
.path-picker{display:flex;gap:8px;align-items:center}
.path-picker input{min-width:0;flex:1;font-family:var(--font-mono);font-size:var(--fs-caption)}
.path-picker button{white-space:nowrap}
.path-preview{display:block;margin-top:6px;color:var(--text-3);font-size:var(--fs-caption);
  overflow-wrap:anywhere}
.role-card{border:1px solid var(--line);border-radius:var(--r-lg);padding:13px;background:var(--surface)}
.role-card b{display:block;margin-bottom:9px}
.role-card .field+.field{margin-top:10px}
.runtime-role-head{display:flex;align-items:flex-start;gap:9px;margin-bottom:11px}
.runtime-role-head b{margin:0}
.runtime-role-head span{margin-left:auto;color:var(--text-3);font-size:var(--fs-caption)}
.runtime-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.runtime-note{margin-top:12px;padding:10px 11px;border:1px solid var(--line);border-radius:var(--r-md);
  background:var(--surface-2);color:var(--text-2);font-size:var(--fs-caption);line-height:1.5}
.runtime-note b{color:var(--text)}
.effort-help{display:block;color:var(--text-3);font-size:var(--fs-caption);margin-top:6px;line-height:1.4}
.runtime-saved{color:var(--pass)}
.model-actions{display:flex;justify-content:flex-end;margin-top:6px}
.model-actions button{height:27px;font-size:var(--fs-caption)}
.fallback-list{display:grid;gap:8px}
.fallback-row{display:grid;grid-template-columns:130px minmax(0,1fr) 92px 28px;gap:7px;align-items:center}
.fallback-row select,.fallback-row input{min-height:34px;padding:6px 8px;font-size:var(--fs-caption)}
.fallback-remove{height:30px;border:1px solid var(--line);border-radius:var(--r-xs);
  background:var(--surface);color:var(--text-2);cursor:pointer}
.fallback-empty{color:var(--text-3);font-size:var(--fs-caption);padding:8px 0}
.guardrail-state{font-size:var(--fs-caption);color:var(--text-2);margin-top:8px}
.custom-model.off{display:none}
.conditional-field.off{display:none}
.delete-summary{border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface-2);
  padding:12px 13px;display:grid;gap:5px;font-size:var(--fs-label)}
.delete-summary b{font-size:var(--fs-body)}
.delete-summary code{font-family:var(--font-mono);color:var(--text-2);overflow-wrap:anywhere}
.delete-warning{border:1px solid color-mix(in srgb,var(--blocked) 32%,var(--line));
  background:var(--blocked-bg);color:var(--blocked);border-radius:var(--r-md);padding:11px 12px;
  font-size:var(--fs-label);line-height:1.5}
.delete-detail{color:var(--text-2);font-size:var(--fs-caption);line-height:1.5}
.danger-button{height:34px;border:0;border-radius:var(--r-sm);padding:0 13px;background:var(--blocked);
  color:var(--inverse-text);font-weight:600}
.danger-button:hover{filter:brightness(.94)}
.danger-button:disabled{opacity:.4;cursor:not-allowed}
.runtime-wizard{width:min(980px,100%);height:min(740px,calc(100vh - 40px));display:flex;
  flex-direction:column;overflow:hidden}
.runtime-wizard>.wizard-head,.runtime-wizard>.wizard-foot{flex:none}
.runtime-shell{min-height:0;flex:1;padding:0;display:grid;grid-template-columns:200px minmax(0,1fr);
  overflow:hidden}
.runtime-nav{display:flex;flex-direction:column;gap:5px;padding:13px;border-right:1px solid var(--line)}
.runtime-nav-button{width:100%;min-height:48px;padding:8px 10px;border:0;border-radius:var(--r-md);
  background:transparent;color:var(--text-2);text-align:left;
  transition:background var(--dur-instant) ease}
.runtime-nav-button:hover{background:var(--hover);color:var(--text)}
.runtime-nav-button:active{transform:scale(.98)}
.runtime-nav-button.active{background:var(--surface-2);color:var(--text);box-shadow:var(--shadow-1)}
.runtime-nav-button b{display:block;font-size:var(--fs-label);font-weight:600}
.runtime-nav-button small{display:block;margin-top:2px;color:var(--text-3);font-size:var(--fs-caption)}
.runtime-content{min-width:0;overflow:auto;padding:24px 25px}
.runtime-pane[hidden]{display:none}
.runtime-pane-heading{margin:0 0 17px}
.runtime-pane-heading h3{margin:0;font-size:var(--fs-title);letter-spacing:-.01em;font-weight:600}
.runtime-pane-heading p{margin:4px 0 0;color:var(--text-2);font-size:var(--fs-caption);line-height:1.5}
.runtime-advanced{margin-top:14px;border:1px solid var(--line);border-radius:var(--r-md);
  background:var(--surface);overflow:hidden}
.runtime-advanced>summary{min-height:46px;padding:0 13px;display:flex;align-items:center;gap:8px;
  cursor:pointer;list-style:none;color:var(--text);font-size:var(--fs-label);font-weight:500}
.runtime-advanced>summary::-webkit-details-marker{display:none}
.runtime-advanced>summary:after{content:"";width:14px;height:14px;margin-left:auto;background:var(--text-3);
  transition:transform var(--dur-fast) var(--spring);
  -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat}
.runtime-advanced[open]>summary:after{transform:rotate(180deg)}
.runtime-advanced-body{border-top:1px solid var(--line);padding:13px}
.runtime-content>.wizard-error{margin-top:12px}
.github-box{border:1px solid var(--line);border-radius:var(--r-md);padding:14px;background:var(--surface)}
.toggle-line{display:flex;align-items:flex-start;gap:10px}
.toggle-line input{margin-top:3px;accent-color:var(--accent)}
.toggle-line b{display:block}
.toggle-line small{display:block;color:var(--text-2);margin-top:2px}
.github-fields{margin-top:14px}
.github-fields.off{display:none}
.connection{font-size:var(--fs-label);margin:10px 0 0;color:var(--text-2)}
.connection.ok{color:var(--pass)}
.connection.bad{color:var(--blocked)}
.github-connect{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.github-connect .secondary{height:30px}
.github-device{margin-top:9px;padding:10px;border:1px solid var(--line);border-radius:var(--r-sm);
  background:var(--surface);color:var(--text)}
.github-device b{font-size:var(--fs-body)}
.device-code{font-family:var(--font-mono);letter-spacing:.12em;padding:4px 7px;
  border-radius:var(--r-xs);background:var(--surface-2);user-select:all}
.github-device-actions{display:flex;gap:7px;margin-top:8px;align-items:center}
.github-device a{color:var(--accent);font-weight:500;text-decoration:none}
.github-device small{display:block;color:var(--text-2);margin-top:5px}
.repo-actions{display:flex;align-items:center;gap:8px;margin-top:11px}
.repo-actions .secondary{height:29px}
.repo-check{font-size:var(--fs-caption);color:var(--text-2)}
.repo-check.ok{color:var(--pass)}
.repo-check.warn{color:var(--escalated)}
.job-guidance{display:none;margin-top:10px;padding:10px;
  border:1px solid color-mix(in srgb,var(--blocked) 30%,var(--line));border-radius:var(--r-sm);
  background:var(--surface)}
.job-guidance.on{display:block}
.job-guidance b{font-size:var(--fs-label)}
.job-guidance p{margin:4px 0 8px;color:var(--text-2);font-size:var(--fs-caption)}
.guidance-actions{display:flex;gap:7px;flex-wrap:wrap}
.guidance-actions a,.guidance-actions button{height:28px;font-size:var(--fs-caption)}
.recovery-note{padding:11px;border:1px solid color-mix(in srgb,var(--escalated) 42%,var(--line));
  background:var(--escalated-bg);border-radius:var(--r-md);color:var(--text);
  font-size:var(--fs-label);line-height:1.5;margin-bottom:14px}
.recovery-note b{display:block;margin-bottom:3px}
.wizard-error{display:none;color:var(--blocked);background:var(--blocked-bg);border-radius:var(--r-sm);
  padding:9px 11px;margin-top:14px;font-size:var(--fs-label)}
.wizard-error.on{display:block}
.wizard-error a{color:inherit;font-weight:600;margin-left:7px}
.credential-card{border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  padding:0;overflow:hidden}
.credential-head{display:flex;align-items:center;gap:8px}
.credential-head b{font-size:var(--fs-body)}
.credential-state{margin-left:auto;font-size:var(--fs-caption);color:var(--text-3)}
.credential-state.ok{color:var(--pass)}
details.credential-card>.credential-head{min-height:52px;margin:0;padding:10px 13px;cursor:pointer;
  list-style:none}
details.credential-card>.credential-head::-webkit-details-marker{display:none}
details.credential-card>.credential-head:after{content:"";width:14px;height:14px;margin-left:3px;
  background:var(--text-3);transition:transform var(--dur-fast) var(--spring);
  -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat}
details.credential-card[open]>.credential-head:after{transform:rotate(180deg)}
.credential-body{padding:0 13px 14px;border-top:1px solid var(--line)}
.credential-body>.connection-method,.credential-body>.provider-note{margin-top:12px}
.secret-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px;align-items:end}
.secret-row .toggle-line{padding-bottom:9px}
.connection-method{display:flex;align-items:center;gap:12px;padding:11px;border:1px solid var(--line);
  border-radius:var(--r-md);background:var(--surface-2);margin-bottom:11px}
.connection-method-copy{min-width:0;flex:1}
.connection-method-copy b{display:block;font-size:var(--fs-label)}
.connection-method-copy small{display:block;color:var(--text-2);margin-top:3px;line-height:1.4}
.connection-method .secondary{flex:none}
.provider-note{padding:9px 10px;border-radius:var(--r-sm);background:var(--escalated-bg);
  color:var(--text-2);font-size:var(--fs-caption);line-height:1.45;margin-bottom:11px}
.provider-note b{color:var(--escalated)}
.login-link{color:var(--accent);font-weight:500;text-decoration:none}
.field-help{display:block!important;margin-top:5px;color:var(--text-3);font-size:var(--fs-caption);
  line-height:1.4}
.settings-readiness{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.readiness-item{border:1px solid var(--line);border-radius:var(--r-sm);padding:10px;
  background:var(--surface);font-size:var(--fs-label)}
.readiness-item span{float:right;color:var(--pass)}
.readiness-item span.bad{color:var(--blocked)}
.doctor-panel{margin-top:12px;border:1px solid var(--line);border-radius:var(--r-md);
  background:var(--surface);overflow:hidden}
.doctor-head{display:flex;align-items:center;gap:10px;padding:12px 13px;border-bottom:1px solid var(--line)}
.doctor-head-copy{min-width:0;flex:1}
.doctor-head-copy b{display:block;font-size:var(--fs-body)}
.doctor-head-copy small{display:block;margin-top:2px;color:var(--text-2);font-size:var(--fs-caption)}
.doctor-state{width:8px;height:8px;border-radius:50%;background:var(--text-3);flex:none}
.doctor-state.ready{background:var(--pass)}
.doctor-state.blocked,.doctor-state.failed{background:var(--blocked)}
.doctor-state.attention{background:var(--escalated)}
.doctor-state.running{background:var(--accent);animation:breathe 2.4s ease-in-out infinite}
.doctor-head .secondary{height:29px;flex:none}
.doctor-list{display:grid}
.doctor-empty{padding:18px;color:var(--text-2);font-size:var(--fs-label);text-align:center}
.doctor-check{display:grid;grid-template-columns:18px minmax(0,1fr) auto;gap:9px;padding:11px 13px;
  border-bottom:1px solid var(--line);align-items:start}
.doctor-check:last-child{border-bottom:0}
.doctor-mark{width:17px;height:17px;border-radius:50%;display:grid;place-items:center;font-size:9px;
  font-weight:600;background:var(--pass-bg);color:var(--pass);margin-top:1px}
.doctor-check.missing .doctor-mark,.doctor-check.outdated .doctor-mark{background:var(--blocked-bg);
  color:var(--blocked)}
.doctor-check.warning .doctor-mark,.doctor-check.unknown .doctor-mark,.doctor-check.waiting .doctor-mark{
  background:var(--escalated-bg);color:var(--escalated)}
.doctor-copy{min-width:0}
.doctor-copy b{display:block;font-size:var(--fs-label)}
.doctor-copy small{display:block;color:var(--text-2);font-size:var(--fs-caption);line-height:1.4;
  margin-top:2px;overflow-wrap:anywhere}
.doctor-copy small.doctor-why{color:var(--text-3);margin-top:4px}
.doctor-version{color:var(--text-3);font-family:var(--font-mono);font-size:var(--fs-caption);
  margin-top:2px;white-space:nowrap}
.doctor-action{grid-column:2/4;display:flex;gap:7px;align-items:center;flex-wrap:wrap}
.doctor-action .secondary{height:27px;font-size:var(--fs-caption);text-decoration:none}
.doctor-identity{display:grid;grid-template-columns:1fr 1fr auto;gap:7px;width:100%}
.doctor-identity input{min-width:0;border:1px solid var(--line-strong);border-radius:var(--r-xs);
  background:var(--surface);padding:7px 8px;font-size:var(--fs-caption)}
.doctor-message{display:none;margin:0 13px 12px;padding:9px 10px;border-radius:var(--r-sm);
  background:var(--accent-bg);color:var(--accent);font-size:var(--fs-caption)}
.doctor-message.on{display:block}
.doctor-message.bad{background:var(--blocked-bg);color:var(--blocked)}
.doctor-panel:not(.expanded) .doctor-list{display:none}
.doctor-details-toggle{min-width:86px}
#provider-credentials{display:grid;grid-template-columns:1fr;gap:10px;margin-top:10px}
#provider-credentials .credential-card{margin:0;min-width:0}
#provider-credentials .provider-note{min-height:58px}

/* Project creation: a short guided flow, not a wall of configuration. */
.project-wizard{width:min(800px,100%);height:min(760px,calc(100vh - 40px));display:flex;
  flex-direction:column;overflow:hidden}
.project-wizard .wizard-head{flex:none}
.wizard-progress{position:relative;flex:none;display:grid;grid-template-columns:repeat(3,1fr);gap:0;
  margin:0;padding:15px 25px 14px;list-style:none;border-bottom:1px solid var(--line)}
.wizard-progress li{position:relative;z-index:1;display:grid;grid-template-columns:28px minmax(0,1fr);
  grid-template-rows:auto auto;column-gap:9px;color:var(--text-3)}
.wizard-progress li:not(:last-child):after{content:"";position:absolute;z-index:-1;top:13px;left:28px;
  right:8px;height:1px;background:var(--line-strong)}
.wizard-progress li>span{grid-row:1/3;width:28px;height:28px;border:1px solid var(--line-strong);
  border-radius:50%;display:grid;place-items:center;background:var(--surface);font-size:var(--fs-caption);
  font-weight:600;font-family:var(--font-mono)}
.wizard-progress li>b{align-self:end;font-size:var(--fs-label);color:var(--text-2);font-weight:500}
.wizard-progress li>small{align-self:start;font-size:var(--fs-caption);white-space:nowrap}
.wizard-progress li.active>span,.wizard-progress li.complete>span{border-color:var(--accent);
  background:var(--accent);color:var(--inverse-text)}
.wizard-progress li.active>b{color:var(--text)}
.wizard-progress li.complete:not(:last-child):after{background:var(--accent)}
.project-wizard-body{min-height:0;flex:1;overflow:auto}
.project-step{margin:0}
.project-step[hidden]{display:none}
.project-step:not([hidden]){animation:step-arrive var(--dur-base) var(--spring) both}
@keyframes step-arrive{from{opacity:0;transform:translateX(8px)}to{opacity:1;transform:none}}
.step-heading{margin-bottom:21px}
.step-heading>span{display:block;margin-bottom:5px;color:var(--accent);font-size:var(--fs-caption);
  font-weight:600}
.step-heading h3{margin:0;font-size:var(--fs-h2);line-height:1.2;letter-spacing:-.015em;font-weight:600}
.step-heading p{max-width:610px;margin:6px 0 0;color:var(--text-2);font-size:var(--fs-label);line-height:1.55}
.advanced-options{border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface-2);
  overflow:hidden}
.advanced-options summary{height:42px;display:flex;align-items:center;padding:0 13px;cursor:pointer;
  color:var(--text-2);font-size:var(--fs-label);font-weight:500;list-style:none}
.advanced-options summary::-webkit-details-marker{display:none}
.advanced-options summary:after{content:"+";margin-left:auto;color:var(--text-3);font-size:17px;font-weight:400}
.advanced-options[open] summary:after{content:"−"}
.advanced-options-body{padding:2px 13px 14px;border-top:1px solid var(--line)}
.advanced-options-body>.field{margin-top:12px}
.role-choice-grid{align-items:start}
.role-card-head{display:flex;align-items:center;gap:10px;margin-bottom:13px}
.role-card-head b{margin:0}
.role-card-head small{display:block;margin-top:2px;color:var(--text-2);font-size:var(--fs-caption)}
.role-index{width:28px;height:28px;border-radius:var(--r-sm);display:grid;place-items:center;
  background:var(--role-g-bg);color:var(--role-g);font-size:var(--fs-caption);font-weight:600}
.role-index.auditor{background:var(--role-a-bg);color:var(--role-a)}
.role-details{margin-top:11px;border-top:1px solid var(--line);padding-top:9px}
.role-details>summary{min-height:28px;display:flex;align-items:center;gap:7px;color:var(--text-2);
  cursor:pointer;list-style:none;font-size:var(--fs-caption);font-weight:500}
.role-details>summary::-webkit-details-marker{display:none}
.role-details>summary:after{content:"";width:12px;height:12px;margin-left:auto;background:var(--text-3);
  transition:transform var(--dur-fast) var(--spring);
  -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat}
.role-details[open]>summary:after{transform:rotate(180deg)}
.role-details-body{padding-top:5px}
.role-details-body>.field+.field{margin-top:10px}
.project-review{margin-top:14px;border:1px solid var(--line);border-radius:var(--r-lg);
  background:var(--surface);padding:13px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.project-review-item{min-width:0}
.project-review-item span{display:block;color:var(--text-3);font-size:var(--fs-caption)}
.project-review-item b{display:block;margin-top:3px;font-size:var(--fs-label);font-weight:500;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.project-wizard-foot{flex:none}

/* Settings: macOS preference-window pattern, category rail + one pane. */
.settings-wizard{width:min(980px,100%);height:min(740px,calc(100vh - 40px));display:flex;
  flex-direction:column;overflow:hidden}
.settings-wizard>.wizard-head,.settings-wizard>.wizard-foot{flex:none}
.settings-shell{min-height:0;flex:1;padding:0;display:grid;grid-template-columns:210px minmax(0,1fr);
  overflow:hidden}
.settings-nav{display:flex;flex-direction:column;gap:3px;padding:13px;border-right:1px solid var(--line)}
/* Claude-Code-style scope headers grouping the sections. */
.settings-nav-group{margin:14px 8px 4px;font-size:var(--fs-caption);font-weight:600;
  letter-spacing:.045em;text-transform:uppercase;color:var(--text-3)}
.settings-nav-group:first-child{margin-top:2px}
/* Single-line nav items (icon + title): cleaner, Claude-Code-like; the pane's
   own heading carries the description the subtitle used to. */
.settings-nav-button{position:relative;width:100%;min-height:38px;padding:7px 9px;border:0;
  border-radius:var(--r-md);display:grid;grid-template-columns:28px minmax(0,1fr) auto;
  align-items:center;gap:9px;background:transparent;color:var(--text-2);text-align:left;
  transition:background var(--dur-instant) ease}
.settings-nav-button:hover{background:var(--hover);color:var(--text)}
.settings-nav-button:active{transform:scale(.98)}
.settings-nav-button.active{background:var(--surface-2);color:var(--text);box-shadow:var(--shadow-1)}
.settings-nav-button b{display:block;font-size:var(--fs-label);font-weight:500}
.settings-nav-button small{display:none}
.settings-nav-button i{min-width:20px;padding:2px 5px;border-radius:var(--r-pill);
  background:var(--surface-2);color:var(--text-2);font-size:var(--fs-caption);font-style:normal;
  text-align:center;font-family:var(--font-mono)}
.settings-nav-button i.ok{background:var(--pass-bg);color:var(--pass)}
.settings-nav-button i.bad{background:var(--blocked-bg);color:var(--blocked)}
.settings-nav-button i.attention{background:var(--escalated-bg);color:var(--escalated)}
.settings-nav-icon{width:28px;height:28px;border-radius:var(--r-sm);display:grid;place-items:center;
  background:var(--surface-2);color:var(--text-2)}
.settings-nav-icon:before{content:"";width:15px;height:15px;background:currentColor;
  -webkit-mask:var(--settings-icon) center/contain no-repeat;mask:var(--settings-icon) center/contain no-repeat}
.settings-nav-icon.general{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M4 6h10M18 6h2M4 12h2M10 12h10M4 18h7M15 18h5'/%3E%3Ccircle cx='16' cy='6' r='2'/%3E%3Ccircle cx='8' cy='12' r='2'/%3E%3Ccircle cx='13' cy='18' r='2'/%3E%3C/svg%3E")}
.settings-nav-icon.providers{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='3' width='16' height='7' rx='2'/%3E%3Crect x='4' y='14' width='16' height='7' rx='2'/%3E%3Cpath d='M8 6.5h.01M8 17.5h.01M12 6.5h4M12 17.5h4'/%3E%3C/svg%3E")}
.settings-nav-icon.agent{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='5' y='8' width='14' height='11' rx='2'/%3E%3Cpath d='M12 4v4'/%3E%3Ccircle cx='12' cy='3.5' r='1'/%3E%3Cpath d='M9 13h.01M15 13h.01'/%3E%3C/svg%3E")}
.settings-nav-icon.audit{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V6z'/%3E%3Cpath d='M9 12l2 2 4-4'/%3E%3C/svg%3E")}
.settings-nav-icon.files{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'/%3E%3C/svg%3E")}
.settings-nav-icon.github{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='6' cy='6' r='2'/%3E%3Ccircle cx='6' cy='18' r='2'/%3E%3Ccircle cx='18' cy='9' r='2'/%3E%3Cpath d='M6 8v8M18 11c0 4-6 1-6 5'/%3E%3C/svg%3E")}
.settings-nav-icon.compute{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='5' width='16' height='6' rx='1.5'/%3E%3Crect x='4' y='13' width='16' height='6' rx='1.5'/%3E%3Cpath d='M8 8h.01M8 16h.01'/%3E%3C/svg%3E")}
.settings-nav-icon.integrations{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='7' y='7' width='10' height='10' rx='2'/%3E%3Cpath d='M9 3v4M15 3v4M9 21v-4M15 21v-4M3 9h4M3 15h4M21 9h-4M21 15h-4'/%3E%3C/svg%3E")}
.settings-nav-icon.usage{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 19V11M9 19V5M14 19v-6M19 19V8M3 20h18'/%3E%3C/svg%3E")}
.settings-nav-icon.security{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='5' y='11' width='14' height='9' rx='2'/%3E%3Cpath d='M8 11V8a4 4 0 0 1 8 0v3'/%3E%3C/svg%3E")}
.settings-nav-icon.diagnostics{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 12h4l2-6 4 12 2-6h6'/%3E%3C/svg%3E")}
.settings-nav-icon.advanced{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='4' width='18' height='16' rx='2'/%3E%3Cpath d='M7 9l3 3-3 3M13 15h4'/%3E%3C/svg%3E")}
.settings-nav-button.dim{opacity:.4}
.settings-result.active{background:var(--surface-2);outline:1px solid var(--accent);outline-offset:-1px}
.settings-content{min-width:0;overflow:auto;padding:24px 25px}
.settings-pane{margin:0}
.settings-pane[hidden]{display:none}
.settings-heading{margin-bottom:20px}
.settings-nav{overflow-y:auto}
.settings-search-bar{margin-bottom:18px}
.settings-search-bar input{width:100%;height:36px;padding:0 12px;border:1px solid var(--line);
  border-radius:var(--r-md);background:var(--surface-2);color:var(--text);font-size:var(--fs-label)}
.settings-search-bar input:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.settings-search-results{display:flex;flex-direction:column;gap:2px}
.settings-search-results[hidden]{display:none}
.settings-result{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
  width:100%;padding:9px 11px;border:0;border-radius:var(--r-sm);background:transparent;
  color:var(--text);text-align:left;cursor:pointer}
.settings-result:hover{background:var(--hover)}
.settings-result:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.settings-result-label{font-size:var(--fs-label);font-weight:500}
.settings-result-group{color:var(--text-3);font-size:var(--fs-caption);white-space:nowrap}
.settings-result-empty{padding:9px 11px;color:var(--text-3);font-size:var(--fs-label)}
.settings-empty{margin:14px 0 0;color:var(--text-3);font-size:var(--fs-caption);line-height:1.55}
.settings-hint{margin:12px 0 0;color:var(--text-2);font-size:var(--fs-caption);line-height:1.55}
.settings-jump{display:flex;align-items:center;flex-wrap:wrap;gap:9px;margin-top:14px}
.settings-jump .settings-empty,.settings-jump .settings-scope{margin:0}

/* Remote compute host wizard and job submission. */
.hpc-host-wizard{width:min(820px,100%);overflow:hidden;display:flex;flex-direction:column}
.hpc-host-wizard .wizard-body{overflow:auto}
.hpc-host-intro{display:flex;align-items:flex-start;gap:10px;padding:11px 12px;margin-bottom:14px;
  border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  color:var(--text-2);font-size:var(--fs-caption);line-height:1.55}
.hpc-host-intro b{display:block;color:var(--text);font-size:var(--fs-label);margin-bottom:2px}
.hpc-host-intro-icon{width:28px;height:28px;flex:none;border-radius:var(--r-sm);
  background:var(--accent-bg);color:var(--accent);display:grid;place-items:center}
.hpc-setup-section{border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  padding:15px;margin-bottom:12px}
.hpc-setup-section:last-child{margin-bottom:0}
.hpc-section-head{display:grid;grid-template-columns:25px minmax(0,1fr);gap:9px;align-items:start;
  margin-bottom:13px}
.hpc-section-index{width:24px;height:24px;border-radius:var(--r-xs);background:var(--surface-2);
  color:var(--text-2);display:grid;place-items:center;font-size:var(--fs-caption);font-weight:600;
  font-family:var(--font-mono)}
.hpc-section-head b{display:block;font-size:var(--fs-body)}
.hpc-section-head p{margin:2px 0 0;color:var(--text-2);font-size:var(--fs-caption);line-height:1.5;
  max-width:620px}
.hpc-connection-grid{display:grid;grid-template-columns:1fr 1.4fr 110px;gap:11px}
.hpc-connection-grid .field.full{grid-column:1/-1}
.hpc-permission{display:flex;align-items:flex-start;gap:10px;padding:11px 12px;
  border:1px solid var(--line-strong);border-radius:var(--r-md);background:var(--surface);cursor:pointer}
.hpc-permission:has(input:checked){border-color:var(--accent);background:var(--accent-bg)}
.hpc-permission input{margin-top:2px;accent-color:var(--accent)}
.hpc-permission b{display:block;font-size:var(--fs-label);color:var(--text)}
.hpc-permission small{display:block;margin-top:3px;color:var(--text-2);font-size:var(--fs-caption);
  line-height:1.45}
.hpc-policy{margin-top:13px;padding-top:13px;border-top:1px solid var(--line)}
.hpc-policy.off{display:none}
.hpc-policy-title{display:flex;align-items:baseline;gap:7px;margin-bottom:9px;
  font-size:var(--fs-label);font-weight:600}
.hpc-policy-title span{color:var(--text-3);font-size:var(--fs-caption);font-weight:400}
.hpc-limit-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
.hpc-advanced{margin-top:10px;border-top:1px solid var(--line);padding-top:10px}
.hpc-advanced summary{cursor:pointer;color:var(--text-2);font-size:var(--fs-caption);user-select:none}
.hpc-advanced .hpc-limit-grid{margin-top:10px}
.hpc-host-key{display:flex;align-items:flex-start;gap:9px;font-size:var(--fs-caption);color:var(--text-2)}
.hpc-host-key input{margin-top:2px;accent-color:var(--accent)}
.hpc-host-key b{display:block;color:var(--text);font-size:var(--fs-label)}
.hpc-host-key small{display:block;margin-top:2px;line-height:1.45}
.hpc-host-wizard .wizard-foot{flex:none}
.hpc-input-list{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}
.hpc-input{display:inline-flex;align-items:center;gap:5px;max-width:100%;border:1px solid var(--line);
  border-radius:var(--r-xs);padding:4px 6px;color:var(--text-2);font-size:var(--fs-caption)}
.hpc-input b{max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text)}
.hpc-input button{border:0;background:transparent;color:var(--text-3);cursor:pointer;padding:0 2px;
  font-size:12px}
.hpc-script{min-height:180px!important;font:var(--fs-caption)/1.5 var(--font-mono)!important}
.hpc-confirm{display:flex;align-items:flex-start;gap:9px;padding:10px;
  border:1px solid color-mix(in srgb,var(--escalated) 50%,var(--line));border-radius:var(--r-sm);
  background:var(--escalated-bg);font-size:var(--fs-caption);color:var(--text-2)}
/* the label also carries .field, which makes inputs full-width; the checkbox
   must NOT stretch, or it eats the row and the text collapses to one glyph wide */
.hpc-confirm input{margin-top:2px;accent-color:var(--accent);flex:none;width:auto}
.hpc-confirm>span{flex:1;min-width:0}
.hpc-confirm b{display:block;color:var(--escalated)}
.mcp-transport-fields.off{display:none}
/* Add-MCP-server dialog: a two-step wizard that mirrors the real lifecycle
   the server enforces (connect -> discover -> approve -> enable), with the
   footer pinned so the primary action is never below the fold. */
.mcp-wizard{display:flex;flex-direction:column;overflow:hidden}
.mcp-wizard>.wizard-head,.mcp-wizard>.mcp-steps,.mcp-wizard>.wizard-foot{flex:none}
/* Chinese has no word boundaries, so a squeezed button breaks inside a word
   (\53d6/\6d88). The label is never the thing that should shrink. */
.mcp-wizard>.wizard-foot>button{white-space:nowrap;flex:none}
.mcp-wizard-body{flex:1;min-height:0;overflow:auto}
.mcp-steps{display:flex;gap:8px;margin:0;padding:11px 24px;list-style:none;
  border-bottom:1px solid var(--line);background:var(--surface-2)}
.mcp-steps li{display:flex;align-items:center;gap:9px;padding:5px 11px 5px 5px;
  border-radius:var(--r-pill);color:var(--text-3)}
.mcp-steps li.active{background:var(--surface);color:var(--text);box-shadow:var(--shadow-1)}
.mcp-steps li>span{width:22px;height:22px;flex:none;display:grid;place-items:center;
  border:1px solid var(--line-strong);border-radius:50%;font-size:var(--fs-caption);font-weight:600}
.mcp-steps li.active>span{border-color:var(--accent);background:var(--accent);color:var(--on-accent,#fff)}
.mcp-steps li.complete>span{border-color:var(--pass);color:var(--pass);font-size:0}
.mcp-steps li.complete>span:after{content:"\2713";font-size:var(--fs-caption)}
.mcp-steps li b{display:block;font-size:var(--fs-label);font-weight:600}
.mcp-steps li small{display:block;font-size:var(--fs-caption);color:var(--text-3)}
.mcp-advanced{margin-top:14px;border:1px solid var(--line);border-radius:var(--r-md);padding:0}
.mcp-advanced>summary{padding:10px 13px;cursor:pointer;font-size:var(--fs-label);font-weight:500}
.mcp-advanced[open]>summary{border-bottom:1px solid var(--line)}
.mcp-advanced>.form-grid{padding:13px}
.mcp-step-note{margin:14px 0 0;font-size:var(--fs-caption);color:var(--text-2);line-height:1.55}
.mcp-connected{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:15px;
  padding:11px 13px;border:1px solid color-mix(in srgb,var(--pass) 32%,var(--line));
  border-radius:var(--r-md);background:var(--pass-bg)}
.mcp-connected b{font-size:var(--fs-label);font-weight:600;color:var(--pass)}
.mcp-connected small{font-size:var(--fs-caption);color:var(--text-2)}
.mcp-connected .mcp-draft-note{flex-basis:100%;margin-top:1px}
.field input[aria-invalid="true"],.field textarea[aria-invalid="true"]{border-color:var(--blocked)}
.mcp-approve-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:9px;margin-bottom:8px}
.mcp-approve-head>span{font-size:var(--fs-label);font-weight:600}
.mcp-approve-head>small{font-size:var(--fs-caption);color:var(--text-3);margin-right:auto}
.mcp-approve{border:1px solid var(--line);border-radius:var(--r-md);overflow:hidden}
.mcp-approve-row{display:flex;align-items:flex-start;gap:10px;padding:11px 13px;cursor:pointer;
  border-bottom:1px solid var(--line)}
.mcp-approve-row:last-child{border-bottom:0}
.mcp-approve-row:hover{background:var(--hover)}
.mcp-approve-row input{margin-top:2px;flex:none;width:auto;accent-color:var(--accent)}
.mcp-approve-row>span{flex:1;min-width:0}
.mcp-approve-row b{display:block;font-size:var(--fs-label);font-weight:600;overflow-wrap:anywhere}
.mcp-approve-row small{display:block;font-size:var(--fs-caption);color:var(--text-2);
  margin-top:2px;line-height:1.5;overflow-wrap:anywhere}
.mcp-risk{flex:none;font-style:normal;font-size:var(--fs-caption);padding:2px 8px;
  border-radius:var(--r-pill);border:1px solid var(--line);color:var(--text-3)}
.mcp-risk.destructive{border-color:color-mix(in srgb,var(--blocked) 45%,var(--line));
  color:var(--blocked);background:var(--blocked-bg)}
.mcp-risk.readonly{border-color:color-mix(in srgb,var(--pass) 40%,var(--line));color:var(--pass)}
.mcp-risk.unlabelled{border-style:dashed;border-color:var(--line-strong);color:var(--text-2);background:none}
.mcp-caveat{margin:0 0 9px}
/* The field help under Server name states the rule a person has to satisfy
   BEFORE typing, and the one under Arguments states how the textarea is
   read. .field-help's --text-3 measures 2.72:1 light / 3.59:1 dark, so as
   written neither was legible. Raised to the same tone the step notes use
   (5.31 / 7.05) inside this dialog. The same shortfall exists wherever else
   .field-help is used; that is a wider change than this slice and is
   reported rather than made here. */
.mcp-wizard .field-help{color:var(--text-2)}
/* Light-theme AA. Each of these sits on a 10%-tinted wash of its own token,
   which pulls the token under 4.5:1 against the composited background:
   "May change data" measured 4.03, the consent heading 3.96 and the Connected
   heading 4.16 at 11-12px. Darkened here, in light only — dark measured 5.18 /
   6.76 / 6.38 and is deliberately untouched. Re-measure, do not assume: the
   backgrounds are alpha-composited down the whole ancestor chain. */
:root[data-theme="light"] .mcp-risk.destructive{color:#A82F26}
:root[data-theme="light"] .hpc-confirm b{color:#7F540A}
:root[data-theme="light"] .mcp-connected b,
:root[data-theme="light"] .mcp-approved b{color:#14684A}
/* D7: a consent the person cannot give yet should not be the loudest thing on
   the step. Until something is approved the box steps back to a plain surface
   instead of wearing the same alert wash as the live one. */
.hpc-confirm.awaiting{background:var(--surface-2);
  border-color:var(--line);color:var(--text-3)}
:root .hpc-confirm.awaiting b,:root[data-theme="light"] .hpc-confirm.awaiting b{color:var(--text-2)}
.mcp-empty{margin:0;padding:15px 13px;font-size:var(--fs-label);color:var(--text-2)}
.mcp-approved{padding:11px 13px;border-radius:var(--r-md);
  border:1px solid color-mix(in srgb,var(--pass) 32%,var(--line));background:var(--pass-bg)}
.mcp-approved b{display:block;font-size:var(--fs-label);font-weight:600;color:var(--pass)}
.mcp-approved small{display:block;margin-top:3px;font-size:var(--fs-caption);
  color:var(--text-2);line-height:1.5}
.mcp-link{border:0;background:none;padding:0;font:inherit;font-size:var(--fs-caption);
  color:var(--accent);cursor:pointer;text-decoration:underline;text-underline-offset:2px}
.mcp-link:disabled{color:var(--text-3);cursor:default;text-decoration:none}
@media(max-width:760px){
  .mcp-steps{padding:9px 14px}
  .mcp-steps li small{display:none}
}

/* File preview: rendered locally, audited from the final binary. */
:root,:root[data-theme="dark"]{--tok-key:#6CA8F8;--tok-str:#7DD3A8;--tok-num:#E0A66B;
  --tok-com:#6E7684;--tok-lit:#C58AF0;--tok-tag:#6CA8F8;--tok-attr:#E0A66B;
  --preview-mark:rgba(224,166,107,.32);--preview-mark-on:#E0A66B;
  --checker:rgba(228,237,248,.06)}
:root[data-theme="light"]{--tok-key:#2266D4;--tok-str:#0F7B52;--tok-num:#9A5518;
  --tok-com:#8C94A2;--tok-lit:#7A34B0;--tok-tag:#2266D4;--tok-attr:#9A5518;
  --preview-mark:rgba(154,85,24,.22);--preview-mark-on:#9A5518;
  --checker:rgba(52,64,84,.08)}
.preview-wizard{width:min(1120px,calc(100% - 32px));height:min(860px,calc(100vh - 40px));
  display:flex;flex-direction:column;overflow:hidden}
.preview-wizard .wizard-head{flex:none}
.preview-toolbar{flex:none;display:flex;align-items:center;gap:8px;padding:7px 14px;
  border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:var(--surface)}
.preview-toolbar[hidden]{display:none}
.preview-tool{height:28px;min-width:28px;padding:0 9px;border:1px solid var(--line-strong);
  border-radius:var(--r-sm);background:var(--surface-2);color:var(--text-2);cursor:pointer;
  font-size:var(--fs-caption);line-height:1;display:inline-flex;align-items:center;justify-content:center}
.preview-tool:hover{background:var(--hover);color:var(--text)}
.preview-tool[aria-pressed="true"]{color:var(--accent);border-color:var(--accent);background:var(--accent-bg)}
.preview-tool:disabled{opacity:.4;cursor:not-allowed}
.preview-find{display:flex;align-items:center;gap:6px}
.preview-find[hidden],.preview-zoom[hidden]{display:none}
.preview-search-input{height:28px;width:min(240px,40vw);padding:0 9px;border:1px solid var(--line-strong);
  border-radius:var(--r-sm);background:var(--surface-2);color:var(--text);font-size:var(--fs-caption)}
.preview-find-count{min-width:52px;color:var(--text-3);font-size:var(--fs-caption);
  font-variant-numeric:tabular-nums}
.preview-zoom{display:flex;align-items:center;gap:6px}
.preview-zoom-level{min-width:44px;text-align:center;color:var(--text-2);font-size:var(--fs-caption);
  font-variant-numeric:tabular-nums}
.preview-shell{flex:1;min-height:0;display:flex}
.preview-outline{flex:none;width:236px;overflow:auto;padding:12px 6px 12px 14px;
  border-right:1px solid var(--line);background:var(--surface);font-size:var(--fs-caption)}
.preview-outline[hidden]{display:none}
.preview-outline button{display:block;width:100%;text-align:left;border:0;background:transparent;
  color:var(--text-2);cursor:pointer;padding:4px 8px;border-radius:var(--r-xs);line-height:1.35;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.preview-outline button:hover{background:var(--hover);color:var(--text)}
.preview-outline .lvl0{font-weight:600;color:var(--text)}
.preview-outline .lvl2{padding-left:18px}.preview-outline .lvl3{padding-left:30px}
.preview-outline .lvl4,.preview-outline .lvl5,.preview-outline .lvl6{padding-left:42px}
.preview-body{min-height:0;flex:1;overflow:auto;background:var(--surface-2);padding:18px;
  display:grid;place-items:center}
.preview-body.fill{place-items:stretch;padding:0}
.preview-loading,.preview-unavailable{color:var(--text-2);font-size:var(--fs-label);text-align:center;
  max-width:560px;line-height:1.6;padding:24px}
.preview-frame{width:100%;height:100%;min-height:520px;border:1px solid var(--line);
  border-radius:var(--r-md);background:var(--surface)}
.preview-stage{position:relative;width:100%;height:100%;overflow:auto;
  display:grid;place-items:center;
  background-color:var(--surface-2);
  background-image:conic-gradient(var(--checker) 25%,transparent 0 50%,var(--checker) 0 75%,transparent 0);
  background-size:22px 22px;background-position:0 0}
.preview-stage.grabbing{cursor:grabbing}
.preview-image{display:block;max-width:100%;max-height:100%;object-fit:contain;
  transform-origin:center center;box-shadow:var(--shadow-2);
  transition:transform .12s ease}
.preview-image.zoomed{max-width:none;max-height:none;cursor:grab}
.preview-code{width:100%;min-height:100%;margin:0;background:var(--surface);color:var(--text);
  font:var(--fs-label)/1.62 var(--font-mono);display:flex;flex-direction:column}
.preview-code-scroll{position:relative;overflow:auto;flex:1;min-height:0}
.preview-code-lines{position:relative;min-width:100%;width:max-content}
.preview-row{display:flex;align-items:flex-start}
.preview-gutter{flex:none;width:calc(var(--gutter-w,4)*1ch + 20px);padding:0 10px 0 8px;text-align:right;
  color:var(--text-3);background:var(--surface);position:sticky;left:0;line-height:20px;
  user-select:none;border-right:1px solid var(--line)}
.preview-line{flex:1;padding:0 16px 0 12px;white-space:pre;line-height:20px}
.preview-code.wrap .preview-line{white-space:pre-wrap;word-break:break-word}
.preview-rawsrc{width:min(820px,100%);margin:0;padding:24px 28px;border:1px solid var(--line);
  border-radius:var(--r-md);background:var(--surface);color:var(--text);box-shadow:var(--shadow-1);
  white-space:pre-wrap;word-break:break-word;font:var(--fs-label)/1.6 var(--font-mono)}
.preview-hex-cap{margin:2px 0 8px;color:var(--text-3);font-size:var(--fs-caption)}
.tok-key{color:var(--tok-key)}.tok-str{color:var(--tok-str)}.tok-num{color:var(--tok-num)}
.tok-com{color:var(--tok-com);font-style:italic}.tok-lit{color:var(--tok-lit)}
.tok-tag{color:var(--tok-tag)}.tok-attr{color:var(--tok-attr)}
mark.preview-hit{background:var(--preview-mark);color:inherit;border-radius:2px}
mark.preview-hit.on{background:var(--preview-mark-on);color:var(--inverse-text)}
.preview-document,.preview-markdown{width:min(820px,100%);min-height:100%;margin:0;
  padding:28px 32px;border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  color:var(--text);box-shadow:var(--shadow-1)}
.preview-document{white-space:pre-wrap;word-break:break-word;font:var(--fs-prose)/1.7 ui-serif,Georgia,serif}
.preview-markdown{font-size:var(--fs-prose);line-height:1.65}
.preview-markdown h1,.preview-markdown h2,.preview-markdown h3{line-height:1.25;scroll-margin-top:12px}
.preview-markdown pre{overflow:auto;padding:12px;border-radius:var(--r-sm);background:var(--surface-2)}
.preview-markdown code{font-family:var(--font-mono)}
.preview-markdown table{border-collapse:collapse;width:100%}
.preview-markdown th,.preview-markdown td{border:1px solid var(--line);padding:6px 8px;text-align:left}
.preview-markdown blockquote{margin-left:0;padding-left:12px;border-left:3px solid var(--line-strong);
  color:var(--text-2)}
.preview-table-wrap{width:100%;height:100%;overflow:auto;background:var(--surface)}
.preview-table{border-collapse:separate;border-spacing:0;font:var(--fs-caption)/1.5 var(--font-mono);
  color:var(--text)}
.preview-table th,.preview-table td{border-right:1px solid var(--line);border-bottom:1px solid var(--line);
  padding:5px 10px;white-space:pre;max-width:420px;overflow:hidden;text-overflow:ellipsis;vertical-align:top}
.preview-table td.num{text-align:right;font-variant-numeric:tabular-nums}
.preview-table thead th{position:sticky;top:0;z-index:2;background:var(--surface-3);color:var(--text);
  text-align:left;font-weight:600}
.preview-table tbody th{position:sticky;left:0;z-index:1;background:var(--surface);color:var(--text-3);
  text-align:right;font-weight:400;font-variant-numeric:tabular-nums}
.preview-table thead th:first-child{left:0;z-index:3}
.preview-hex{width:min(820px,100%);margin:0;padding:22px 26px;border:1px solid var(--line);
  border-radius:var(--r-md);background:var(--surface);color:var(--text);box-shadow:var(--shadow-1)}
.preview-meta-grid{display:grid;grid-template-columns:auto 1fr;gap:6px 16px;margin-bottom:18px;
  font-size:var(--fs-caption)}
.preview-meta-grid dt{color:var(--text-3)}
.preview-meta-grid dd{margin:0;color:var(--text);font-family:var(--font-mono);word-break:break-all}
.preview-hex pre{margin:0;overflow:auto;font:var(--fs-caption)/1.5 var(--font-mono);color:var(--text-2);
  background:var(--surface-2);padding:12px;border-radius:var(--r-sm)}
.preview-note{min-height:34px;padding:9px 18px;border-top:1px solid var(--line);color:var(--text-2);
  font-size:var(--fs-caption)}
@media (prefers-reduced-motion: reduce){.preview-image{transition:none}}
/* Responsive layout: the centre column always wins. */
@media(max-width:1280px){
  .inspector{width:min(400px,calc(100vw - 16px));background:var(--glass-sheet-bg);
    border-color:var(--glass-border);box-shadow:var(--edge-highlight),var(--shadow-3);
    -webkit-backdrop-filter:blur(28px) saturate(160%);backdrop-filter:blur(28px) saturate(160%)}
}
@media(min-width:1281px){
  .scrim.inspector-open:not(.sidebar-open){display:none}
}
@media(max-width:840px){
  .hpc-connection-grid{grid-template-columns:1fr 1fr}
  .hpc-connection-grid .field:nth-child(2){grid-column:1/-1}
  .hpc-limit-grid{grid-template-columns:1fr 1fr}
}
@media(max-width:760px){
  .hub-bar{padding:0 14px}
  .hub-main{width:calc(100% - 24px);padding-top:26px}
  .hub-heading{align-items:flex-start;flex-direction:column}
  .hub-summary{margin-left:0}
  .project-row{grid-template-columns:minmax(0,1fr) 58px 62px 28px 28px 16px;gap:8px}
  .project-models,.project-tier{display:none}
  .form-grid{grid-template-columns:1fr}
  .field.full{grid-column:auto}
  .project-modal{padding:8px}
  .wizard{max-height:calc(100vh - 16px)}
  #provider-credentials{grid-template-columns:1fr}
  .doctor-check{grid-template-columns:18px minmax(0,1fr)}
  .doctor-version{grid-column:2}
  .doctor-action{grid-column:2}
  .doctor-identity{grid-template-columns:1fr}
  .doctor-head{align-items:flex-start}
  .runtime-grid{grid-template-columns:1fr}
  .fallback-row{grid-template-columns:minmax(0,1fr) 92px 28px}
  .fallback-row [data-fallback-model]{grid-column:1/-1;grid-row:2}
  .path-picker{align-items:stretch;flex-direction:column}
  .path-picker button{width:100%}
  .repo-actions{align-items:flex-start;flex-direction:column}
  .hub-tools,.hub-search{width:100%;min-width:0}
}
@media(max-width:720px){
  .icon-button,.compose-button{min-width:44px;min-height:44px}
  .nav-item,.new-task,.primary,.secondary,.runtime-button,.palette-row{min-height:44px}
  .brand-button{min-width:44px;min-height:44px}
  .panel-tabs .nav-item{min-height:48px}
  :root{--sidebar:0px}
  .app{grid-template-columns:1fr}
  .topbar{height:48px;margin:6px 6px 0}
  .decision-banner{margin:6px 6px 0}
  .sidebar{position:fixed;left:0;top:calc(var(--topbar-h) + 10px);bottom:6px;
    width:min(280px,calc(100vw - 44px));margin:0 0 0 6px;z-index:var(--z-sheet);
    transform:translateX(calc(-100% - 12px));visibility:hidden;
    transition:transform var(--dur-slow) var(--spring),visibility 0s var(--dur-slow)}
  .sidebar.open{transform:translateX(0);visibility:visible;
    transition:transform var(--dur-slow) var(--spring)}
  .mobile-sidebar{display:grid}
  .workspace{margin:6px 6px 6px}
  .thread-head{padding:0 var(--sp-4)}
  .thread-inner{width:calc(100% - 28px)}
  .composer-wrap{left:0;padding:24px 12px 10px}
  .decision{left:0;margin:0 6px 6px}
  .loop-detail{display:none}
  .hub-main{width:calc(100% - 24px);padding-top:30px}
  .settings-shell{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr)}
  .settings-nav{flex-direction:row;padding:8px;border-right:0;border-bottom:1px solid var(--line);
    overflow-x:auto}
  .settings-nav-button{min-width:160px;flex:1}
  .settings-content{padding:19px 17px}
  .runtime-wizard{height:min(760px,calc(100vh - 16px))}
  .runtime-shell{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr)}
  .runtime-nav{flex-direction:row;padding:8px;border-right:0;border-bottom:1px solid var(--line);
    overflow-x:auto}
  .runtime-nav-button{min-width:136px;flex:1}
  .runtime-content{padding:19px 17px}
  .project-wizard{height:min(760px,calc(100vh - 16px))}
  .wizard-progress{padding:12px 17px}
  #branch-label{display:none}
  .top-project{max-width:180px}
}
@media(max-width:560px){
  .topbar{padding:0 8px;gap:4px}
  .brand-button{padding-right:3px;font-size:0;gap:0}
  .top-project,#current-project-pin,.live-pill,.version{display:none}
  .thread-head{min-height:52px}
  .thread-inner{padding-top:20px}
  .composer{border-radius:var(--r-xl)}
  .composer-meta #model-summary{display:none}
  .turn-meta{flex-wrap:wrap}
  .finding-head{flex-wrap:wrap}
  .finding-head .spacer{display:none}
  .finding-head span:last-child{width:100%;overflow-wrap:anywhere}
  .run-overview{padding:13px 12px}
  .run-task{font-size:var(--fs-body)}
  .run-meta{flex-wrap:wrap}
  .loop{grid-template-columns:1fr;gap:0;padding:14px 12px 7px}
  .loop-step{display:grid;grid-template-columns:31px minmax(0,1fr) auto;grid-template-rows:auto auto;
    padding:0 0 11px;align-items:start}
  .loop-track{grid-row:1/3;height:auto;align-self:stretch}
  .loop-step:not(:last-child) .loop-track:after{top:25px;bottom:-8px;left:11px;right:auto;
    width:1px;height:auto}
  .loop-name{grid-column:2;grid-row:1;margin:3px 0 0}
  .loop-state{grid-column:3;grid-row:1;margin:4px 0 0 8px}
  .loop-detail{display:block;grid-column:2/4;grid-row:2;margin:3px 0 0;min-height:0;-webkit-line-clamp:3}
  .loop-focus{margin:0 12px 12px;grid-template-columns:1fr;gap:3px}
  .activity{padding:11px 12px 13px}
  .audit-event{grid-template-columns:24px minmax(0,1fr)}
  .event-time{grid-column:2;margin-top:-2px}
  .inspector{top:auto;right:6px;left:6px;bottom:6px;width:auto;max-height:min(560px,78vh);
    transform:translateY(calc(100% + 12px))}
  .inspector.open{transform:translateY(0)}
  .palette-shell{padding-top:8vh!important;padding-left:8px!important;padding-right:8px!important}
  .palette{width:100%}
  .decision-body{width:calc(100% - 32px)}
  .project-modal{padding:0}
  .wizard{max-height:100vh;height:100vh;border-radius:0;border-left:0;border-right:0}
  .wizard-head{padding:18px 17px 15px}
  .wizard-body{padding:18px 17px}
  .wizard-foot{padding:13px 17px;padding-bottom:max(13px,env(safe-area-inset-bottom))}
  /* the footer note was taking ~60% of a 390px row; give it its own row and let
     the buttons keep their natural width */
  .mcp-wizard>.wizard-foot{flex-wrap:wrap}
  .mcp-wizard>.wizard-foot>span{flex-basis:100%;max-width:none;margin:0 0 9px}
  .mcp-wizard>.wizard-foot>button:nth-of-type(1){margin-left:auto}
  .project-wizard,.settings-wizard{height:100dvh;max-height:100dvh}
  .project-wizard-body{padding:18px 17px}
  .wizard-progress li{grid-template-columns:26px minmax(0,1fr);column-gap:7px}
  .wizard-progress li>span{width:26px;height:26px}
  .wizard-progress li>small{display:none}
  .wizard-progress li:not(:last-child):after{top:12px;left:26px}
  .settings-shell{padding:0}
  .settings-nav{padding:7px}
  .settings-nav-button{min-width:0;min-height:48px;grid-template-columns:26px minmax(0,1fr);padding:7px}
  .settings-nav-button i,.settings-nav-button small{display:none}
  .settings-nav-icon{width:26px;height:26px}
  .settings-content{padding:18px 17px}
  .doctor-head{flex-wrap:wrap}
  .doctor-head .doctor-details-toggle{margin-left:27px}
  .role-choice-grid{grid-template-columns:1fr}
  .project-review{grid-template-columns:1fr}
  .project-wizard-foot>span{display:none}
  .project-row{grid-template-columns:minmax(0,1fr) auto 44px 44px;gap:8px;padding:14px}
  .project-row>span:first-child{grid-column:1/-1}
  .project-row>.project-stat:not(.project-tier){grid-column:1}
  .project-row>.status{grid-column:2}
  .project-row>.project-pin{grid-column:3}
  .project-row>.project-delete{grid-column:4}
  .project-pin,.project-delete,.artifact-action{width:44px;height:44px}
  .project-arrow{display:none}
  .preview-wizard{width:100%;height:100vh;max-height:none;border-radius:0}
  .preview-body{padding:8px}
  .preview-code,.preview-document,.preview-markdown{padding:18px 16px;border-radius:var(--r-sm)}
  .preview-frame{min-height:420px}
  .hpc-connection-grid,.hpc-limit-grid{grid-template-columns:1fr}
  .hpc-connection-grid .field:nth-child(2){grid-column:auto}
  .hpc-setup-section{padding:12px}
  .hpc-host-wizard .wizard-head p{max-width:280px}
  .runtime-grid,.runtime-content .form-grid{grid-template-columns:1fr}
  .runtime-wizard>.wizard-head p{display:none}
}
@media(max-width:380px){
  .composer-wrap{padding-left:8px;padding-right:8px}
  .thread-inner{width:calc(100% - 20px)}
  .thread-head{padding:0 10px}
  .state-pill .pill-detail{display:none}
}

/* ============ First-launch flow (North Star §4): "A base + graft B/C" ============ */
#first-run{display:none}
body.first-run .app,body.first-run .project-hub{display:none}
body.first-run #first-run{display:flex;flex-direction:column;min-height:100vh;height:100vh;overflow:hidden;
  background:radial-gradient(72% 62% at 88% -8%,var(--tint-a),transparent 66%),radial-gradient(55% 54% at -8% 96%,var(--tint-b),transparent 70%),var(--bg)}
.fr-chrome{position:relative;z-index:2;display:flex;align-items:center;gap:var(--sp-4);
  height:var(--topbar-h);padding:0 clamp(var(--sp-5),4vw,var(--sp-8));
  background:var(--glass-nav-bg);-webkit-backdrop-filter:blur(20px) saturate(1.3);backdrop-filter:blur(20px) saturate(1.3);
  border-bottom:1px solid var(--glass-border)}
.fr-brand{display:flex;align-items:center;gap:var(--sp-2);font-size:var(--fs-title);font-weight:600;letter-spacing:-.01em}
.fr-mark{color:var(--role-g)}
.fr-steps{display:flex;align-items:center;gap:var(--sp-4);margin-left:var(--sp-5)}
.fr-step{display:flex;align-items:baseline;gap:6px;color:var(--text-3);position:relative;padding-bottom:2px;
  transition:color var(--dur-base) var(--ease-out)}
.fr-step .fr-k{font-family:var(--font-mono);font-size:var(--fs-caption);letter-spacing:.1em}
.fr-step .fr-l{font-size:var(--fs-caption);letter-spacing:.16em;text-transform:uppercase}
.fr-step.complete{color:var(--text-2)}
.fr-step.complete .fr-k{color:var(--pass)}
.fr-step.active{color:var(--text)}
.fr-step.active:after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;border-radius:2px;background:var(--accent)}
.fr-skip{margin-left:auto;color:var(--text-3);font-size:var(--fs-label);background:none;border:0;padding:6px 8px;border-radius:var(--r-sm)}
.fr-skip:hover{color:var(--text-2);background:var(--hover)}
.fr-stage{position:relative;flex:1;min-height:0;overflow:auto;display:flex;align-items:safe center;
  padding:clamp(var(--sp-7),6vh,var(--sp-10)) clamp(var(--sp-5),5vw,var(--sp-9))}
.fr-stage:focus{outline:none}
.fr-col{position:relative;z-index:2;width:100%;max-width:960px;margin:0 auto}
.fr-ghost{position:absolute;z-index:1;top:50%;right:clamp(-40px,-2vw,0px);transform:translateY(-52%);
  font-family:var(--font-mono);font-weight:700;font-size:clamp(180px,26vw,340px);line-height:.8;
  color:var(--surface-3);pointer-events:none;user-select:none;letter-spacing:-.04em}
.fr-display{margin:0;font-weight:600;letter-spacing:-.03em;line-height:1.02;
  font-size:clamp(2.2rem,5.4vw,3.9rem);display:flex;flex-direction:column}
.fr-display .l2{margin-left:clamp(24px,10vw,180px)}
.fr-display .g{color:var(--role-g)}
.fr-display .a{color:var(--role-a)}
.fr-lede{margin:clamp(20px,4vh,34px) 0 clamp(26px,5vh,42px);max-width:54ch;color:var(--text-2);
  font-size:var(--fs-prose);line-height:1.65}
.fr-choices{display:flex;flex-direction:column;gap:var(--sp-5);max-width:520px}
.fr-arw{transition:transform var(--dur-base) var(--spring)}
.fr-primary{display:inline-flex;align-items:center;gap:9px;width:fit-content;white-space:nowrap;
  font-size:var(--fs-title);font-weight:600;border:1px solid transparent;border-radius:var(--r-md);
  padding:12px 22px;background:var(--accent);color:var(--inverse-text);box-shadow:var(--shadow-2),var(--edge-highlight);
  transition:transform var(--dur-fast) var(--ease-out),filter var(--dur-fast) var(--ease-out)}
.fr-primary:hover{filter:brightness(1.06);transform:translateY(-1px)}
.fr-primary:hover .fr-arw{transform:translateX(3px)}
.fr-primary:active{transform:translateY(0)}
.fr-primary:disabled{opacity:.6;cursor:default;filter:none;transform:none}
.fr-choices-alt{display:flex;flex-direction:column}
.fr-choice{display:flex;align-items:center;gap:12px;width:100%;padding:14px 12px 14px 4px;
  color:var(--text-2);font-size:var(--fs-prose);background:none;border:0;border-top:1px solid var(--line);
  transition:color var(--dur-fast) var(--ease-out),padding-left var(--dur-base) var(--spring),background-color var(--dur-fast) var(--ease-out)}
.fr-choices-alt .fr-choice:last-child{border-bottom:1px solid var(--line)}
.fr-choice em{font-style:normal;color:var(--text-3)}
.fr-choice .fr-arw{margin-left:auto;color:var(--text-3);opacity:0;transform:translateX(-4px);
  transition:opacity var(--dur-base) var(--ease-out),transform var(--dur-base) var(--spring)}
.fr-choice:hover{color:var(--text);padding-left:14px;background:linear-gradient(90deg,var(--hover),transparent 60%)}
.fr-choice:hover .fr-arw{opacity:1;transform:translateX(0)}
.fr-head{display:flex;align-items:flex-end;justify-content:space-between;gap:var(--sp-6);flex-wrap:wrap}
.fr-nameplate{display:block;font-family:var(--font-mono);font-size:var(--fs-caption);letter-spacing:.2em;
  text-transform:uppercase;color:var(--text-3);margin-bottom:10px}
.fr-rollup{margin:0;font-size:clamp(1.4rem,2.6vw,1.95rem);font-weight:600;letter-spacing:-.02em;line-height:1.18;color:var(--text)}
.fr-rollup b{color:var(--escalated);font-weight:600}
.fr-rollup .done{color:var(--pass)}
.fr-recheck{display:inline-flex;align-items:center;gap:7px;color:var(--text-2);font-size:var(--fs-label);
  height:32px;padding:0 12px;border-radius:var(--r-sm);border:1px solid var(--line);background:transparent}
.fr-recheck:hover{background:var(--hover);color:var(--text);border-color:var(--line-strong)}
.fr-recheck:disabled{opacity:.6;cursor:default}
.fr-groups{margin-top:clamp(18px,4vh,34px);display:flex;flex-direction:column;gap:var(--sp-7)}
.fr-group>.fr-nameplate{margin-bottom:4px}
.fr-ready-group>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:var(--sp-2);padding:4px 0;border-radius:var(--r-sm)}
.fr-ready-group>summary::-webkit-details-marker{display:none}
.fr-ready-group>summary .fr-nameplate{display:inline;margin:0}
.fr-ready-n{color:var(--text-3);font-size:var(--fs-label)}
.fr-ready-chev{color:var(--text-3);transition:transform var(--dur-fast) var(--ease-out);display:inline-block;line-height:1}
.fr-ready-group[open]>summary .fr-ready-chev{transform:rotate(90deg)}
.fr-ready-group>summary:hover .fr-ready-n,.fr-ready-group>summary:hover .fr-ready-chev{color:var(--text-2)}
.fr-ready-group>.fr-rows{margin-top:var(--sp-3)}
.fr-ready-group:not([open])>.fr-rows{display:none}
.fr-scanning,.fr-offline{padding:18px 0;color:var(--text-3);font-size:var(--fs-body);
  border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.fr-rows{display:flex;flex-direction:column}
.fr-row{display:grid;grid-template-columns:auto 1fr auto;align-items:start;gap:var(--sp-4);
  padding:15px 0;border-top:1px solid var(--line)}
.fr-rows .fr-row:last-child{border-bottom:1px solid var(--line)}
.fr-row.soft{opacity:.92}
.fr-dot{width:8px;height:8px;margin-top:7px;border-radius:50%;background:currentColor;flex:none;
  box-shadow:0 0 0 4px color-mix(in srgb,currentColor 14%,transparent)}
.fr-d-ready{color:var(--pass)}.fr-d-warn{color:var(--escalated)}.fr-d-opt{color:var(--text-3)}
.fr-row-main{min-width:0}
.fr-row-name{display:flex;align-items:baseline;gap:11px;flex-wrap:wrap}
.fr-name{font-size:var(--fs-title);color:var(--text);font-weight:500}
.fr-stat{font-size:var(--fs-caption);font-weight:600;letter-spacing:.06em;padding:3px 9px;border-radius:var(--r-pill)}
.fr-s-ready{color:var(--pass);background:var(--pass-bg)}
.fr-s-warn{color:var(--escalated);background:var(--escalated-bg)}
.fr-s-opt{color:var(--text-3);background:var(--surface-2)}
.fr-s-pending{color:var(--text-2);background:var(--surface-2);border:1px solid var(--line)}
.fr-why{margin:5px 0 0;color:var(--text-2);font-size:var(--fs-body);max-width:64ch}
.fr-row-act{display:flex;align-items:center;gap:12px;justify-self:end}
.fr-fix{display:inline-flex;align-items:center;gap:7px;font-size:var(--fs-body);font-weight:600;
  color:var(--inverse-text);background:var(--accent);border:1px solid transparent;
  padding:8px 15px;border-radius:var(--r-sm);box-shadow:var(--edge-highlight);
  transition:filter var(--dur-fast) var(--ease-out)}
.fr-fix:hover{filter:brightness(1.06)}
.fr-fix:disabled{opacity:.6;cursor:default;filter:none}
.fr-learn{font-size:var(--fs-body);color:var(--accent);white-space:nowrap;background:none;border:0;padding:0}
.fr-learn:hover{text-decoration:underline}
.fr-tech{margin-top:9px}
.fr-tech>summary{list-style:none;cursor:pointer;display:inline-flex;align-items:center;gap:6px;
  font-family:var(--font-mono);font-size:var(--fs-caption);letter-spacing:.08em;text-transform:uppercase;color:var(--text-3)}
.fr-tech>summary::-webkit-details-marker{display:none}
.fr-tech>summary:before{content:"+";font-family:var(--font-mono);color:var(--text-3)}
.fr-tech[open]>summary:before{content:"–"}
.fr-tech:hover>summary{color:var(--text-2)}
.fr-tech-body{margin-top:8px;padding:11px 13px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--r-sm);font-family:var(--font-mono);font-size:var(--fs-caption);color:var(--text-2);line-height:1.7;white-space:pre-wrap}
.fr-footbar{position:relative;z-index:2;border-top:1px solid var(--line);background:var(--surface)}
.fr-foot-wrap{width:100%;max-width:960px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;
  gap:var(--sp-4);padding:16px clamp(var(--sp-5),5vw,var(--sp-9))}
.fr-hint{color:var(--text-3);font-size:var(--fs-caption)}
.fr-foot-right{display:flex;align-items:center;gap:20px}
.fr-back{color:var(--text-3);font-size:var(--fs-body);background:none;border:0;padding:6px 8px;border-radius:var(--r-sm);
  white-space:nowrap}
.fr-back:hover{color:var(--text-2);background:var(--hover)}
.fr-rail{position:relative;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:var(--sp-4);
  height:34px;padding:0 clamp(var(--sp-5),4vw,var(--sp-8));border-top:1px solid var(--line);
  font-family:var(--font-mono);font-size:var(--fs-caption);letter-spacing:.08em;color:var(--text-3)}
.fr-rail-grp{display:flex;align-items:center;gap:var(--sp-2);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fr-rail .fr-dot{width:6px;height:6px;margin-top:0;box-shadow:none}
.fr-live{background:var(--accent);box-shadow:0 0 0 3px var(--accent-bg);animation:frpulse 2.4s var(--ease-out) infinite}
.fr-rail-ok{background:var(--pass)}
.fr-rail-warn{background:var(--escalated)}
@keyframes frpulse{0%,100%{opacity:.4}50%{opacity:1}}
@keyframes fr-stage-in{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
body.first-run [data-fr-step]:not([hidden]){animation:fr-stage-in var(--dur-slow) var(--ease-out)}
@keyframes fr-choice-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
body.first-run [data-fr-step="1"]:not([hidden]) .fr-primary,
body.first-run [data-fr-step="1"]:not([hidden]) .fr-choice{animation:fr-choice-in var(--dur-base) var(--ease-out) both}
body.first-run [data-fr-step="1"]:not([hidden]) .fr-primary{animation-delay:80ms}
body.first-run [data-fr-step="1"]:not([hidden]) .fr-choice:nth-of-type(1){animation-delay:130ms}
body.first-run [data-fr-step="1"]:not([hidden]) .fr-choice:nth-of-type(2){animation-delay:175ms}
body.first-run [data-fr-step="1"]:not([hidden]) .fr-choice:nth-of-type(3){animation-delay:220ms}
/* ── Step 3 · Providers ─────────────────────────────────────────────────── */
.fr-keychain{display:inline-flex;align-items:center;gap:8px;margin:14px 0 0;color:var(--text-2);font-size:var(--fs-body)}
.fr-keychain svg{color:var(--text-3);flex:none}
.fr-lede-3{margin:10px 0 0;max-width:56ch;color:var(--text-2);font-size:var(--fs-prose);line-height:1.5}
.fr-provs{margin-top:clamp(18px,3.5vh,30px);display:flex;flex-direction:column}
.fr-prov{padding:18px 0;border-top:1px solid var(--line)}
.fr-provs .fr-prov:last-child{border-bottom:1px solid var(--line)}
.fr-prov-id{display:flex;align-items:center;gap:14px}
.fr-prov-mark{width:32px;height:32px;flex:none;display:grid;place-items:center;border-radius:var(--r-sm);
  background:var(--surface-2);border:1px solid var(--line);color:var(--text-2);font-weight:600;font-size:var(--fs-prose)}
.fr-prov-name{font-size:var(--fs-title);color:var(--text);font-weight:500}
.fr-prov-sub{font-family:var(--font-mono);font-size:var(--fs-caption);color:var(--text-3);letter-spacing:.02em}
.fr-prov-id .fr-stat{margin-left:auto}
.fr-s-invalid{color:var(--blocked);background:color-mix(in srgb,var(--blocked) 14%,transparent)}
.fr-s-info{color:var(--accent);background:var(--accent-bg)}
.fr-prov-body{margin-top:13px;padding-left:46px;display:flex;flex-direction:column;gap:10px}
@media(max-width:560px){.fr-prov-body{padding-left:0}}
.fr-configured{display:flex;align-items:center;gap:12px;color:var(--text-2);font-size:var(--fs-body)}
.fr-configured .fr-mask{font-family:var(--font-mono);letter-spacing:.18em;color:var(--text-3)}
.fr-keyfield{display:flex;align-items:center;gap:6px;flex-wrap:wrap;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--r-md);padding:6px 8px 6px 13px;transition:border-color var(--dur-fast) var(--ease-out),box-shadow var(--dur-fast) var(--ease-out)}
.fr-keyfield:focus-within{border-color:var(--line-strong);box-shadow:0 0 0 3px var(--accent-bg)}
.fr-key{flex:1;min-width:120px;background:none;border:0;outline:0;font-family:var(--font-mono);
  font-size:var(--fs-body);letter-spacing:.02em;color:var(--text)}
.fr-key::placeholder{color:var(--text-3);font-family:var(--font-ui);letter-spacing:0}
.fr-tool{display:inline-flex;align-items:center;gap:6px;flex:none;color:var(--text-2);font-size:var(--fs-label);
  padding:7px 10px;border-radius:var(--r-xs);background:none;border:0;cursor:pointer;
  transition:background-color var(--dur-fast) var(--ease-out),color var(--dur-fast) var(--ease-out)}
.fr-tool:hover{background:var(--hover);color:var(--text)}
.fr-tool:disabled{opacity:.4;cursor:default;background:none}
.fr-tool-cta{border:1px solid var(--line-strong);color:var(--text)}
.fr-tool[aria-pressed="true"]{color:var(--accent);background:var(--accent-bg)}
.fr-divider{display:flex;align-items:center;gap:12px;margin:2px 0;color:var(--text-3);font-size:var(--fs-label)}
.fr-divider:before,.fr-divider:after{content:"";height:1px;flex:1;background:var(--line)}
.fr-chatgpt{display:inline-flex;align-items:center;gap:9px;width:fit-content;padding:9px 15px;border-radius:var(--r-md);
  color:var(--text);font-size:var(--fs-body);font-weight:500;background:var(--surface);border:1px solid var(--line-strong)}
.fr-chatgpt:hover{background:var(--hover)}
.fr-chatgpt:disabled{opacity:.6;cursor:default}
.fr-honesty{margin:0;color:var(--text-3);font-size:var(--fs-caption);max-width:60ch}
.fr-keymsg{margin:0;font-size:var(--fs-caption)}
.fr-keymsg.bad{color:var(--blocked)}
.fr-keymsg.ok{color:var(--pass)}
.fr-keymsg.info{color:var(--text-2)}

/* ── Step 4 · Generator / Auditor ───────────────────────────────────────── */
.fr-pair{margin-top:clamp(22px,4vh,38px);display:grid;grid-template-columns:1fr auto 1fr;align-items:start;gap:clamp(16px,3vw,40px)}
.fr-role{position:relative;padding-left:20px}
.fr-role:before{content:"";position:absolute;left:0;top:4px;bottom:4px;width:2px;border-radius:2px}
.fr-role-g:before{background:var(--role-g)}
.fr-role-a{margin-top:clamp(28px,5vw,60px)}
.fr-role-a:before{background:var(--role-a)}
.fr-role-kicker{font-family:var(--font-mono);font-size:var(--fs-caption);letter-spacing:.22em;text-transform:uppercase}
.fr-role-g .fr-role-kicker{color:var(--role-g)}
.fr-role-a .fr-role-kicker{color:var(--role-a)}
.fr-role-does{margin:8px 0 14px;font-size:var(--fs-prose);color:var(--text-2);max-width:36ch;line-height:1.5}
.fr-role-pickers{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.fr-select{appearance:none;-webkit-appearance:none;background:var(--surface);border:1px solid var(--line);color:var(--text);
  font-size:var(--fs-label);font-family:var(--font-ui);padding:7px 26px 7px 11px;border-radius:var(--r-sm);cursor:pointer;
  background-image:linear-gradient(45deg,transparent 50%,var(--text-3) 50%),linear-gradient(135deg,var(--text-3) 50%,transparent 50%);
  background-position:calc(100% - 14px) 52%,calc(100% - 9px) 52%;background-size:5px 5px,5px 5px;background-repeat:no-repeat}
.fr-select:focus-visible{outline:none;border-color:var(--line-strong);box-shadow:0 0 0 3px var(--accent-bg)}
.fr-role-model{font-size:var(--fs-h2);font-weight:600;letter-spacing:-.01em;color:var(--text)}
.fr-role-mid{font-family:var(--font-mono);font-size:var(--fs-caption);color:var(--text-3);margin-top:3px}
.fr-chips{margin-top:15px;display:flex;flex-wrap:wrap;gap:8px}
.fr-chip{display:inline-flex;align-items:center;gap:6px;padding:5px 11px;border-radius:var(--r-pill);
  border:1px solid var(--line);color:var(--text-2);font-size:var(--fs-caption)}
.fr-chip .n{font-family:var(--font-mono);color:var(--text)}
.fr-chip-auth{color:var(--pass);border-color:color-mix(in srgb,var(--pass) 30%,transparent)}
.fr-chip-price{font-family:var(--font-mono);color:var(--text)}
.fr-chip-muted{color:var(--text-3)}
.fr-handoff{align-self:center;display:grid;place-items:center;padding-top:clamp(14px,2.5vw,30px)}
.fr-handoff svg{width:clamp(40px,7vw,82px);height:auto}
.fr-handoff .ho0{stop-color:var(--role-g)}
.fr-handoff .ho1{stop-color:var(--role-a)}
.fr-handoff .ho-line{stroke:url(#fr-ho)}
.fr-handoff .ho-head{stroke:var(--role-a)}
.fr-independent{margin-top:clamp(22px,4vh,36px);display:inline-flex;align-items:center;gap:10px;padding:11px 16px;
  border-radius:var(--r-md);background:var(--pass-bg);color:var(--pass);font-size:var(--fs-body);font-weight:500}
.fr-independent svg{flex:none}
.fr-independent.bad{background:color-mix(in srgb,var(--blocked) 14%,transparent);color:var(--blocked)}
.fr-role-msg{margin:14px 0 0;font-size:var(--fs-body);color:var(--blocked)}
.fr-role-msg:empty{display:none}
.fr-rollup .fr-g{color:var(--role-g)}
.fr-rollup .fr-a{color:var(--role-a)}

@media(max-width:820px){.fr-steps .fr-l{display:none}.fr-steps{gap:var(--sp-3);margin-left:var(--sp-3)}}
@media(max-width:720px){
  .fr-display .l2{margin-left:clamp(14px,7vw,56px)}
  .fr-row{grid-template-columns:auto 1fr;gap:12px}
  .fr-row-act{grid-column:2;justify-self:start;margin-top:8px}
  .fr-pair{grid-template-columns:1fr;gap:8px}
  .fr-role-a{margin-top:6px}
  .fr-handoff{justify-self:start;padding:6px 0 6px 20px}
  .fr-handoff svg{transform:rotate(90deg);width:34px}
}

/* Degradation matrix: every row is a testable contract. */
@media(prefers-contrast:more){
  :root,:root[data-theme="dark"]{--line:rgba(228,237,248,.28);--line-strong:rgba(228,237,248,.36);
    --text-3:#A6AEBB;--glass-border:rgba(255,255,255,.32)}
  :root[data-theme="light"]{--line:rgba(52,64,84,.34);--line-strong:rgba(52,64,84,.44);
    --text-3:#5C6472;--glass-border:rgba(31,38,50,.26)}
  .topbar,.hub-bar,.sidebar,.workspace,.inspector,.composer,.wizard,.palette,.project-table{border-width:2px}
  .state-pill{border:1px solid currentColor}
}
@media(prefers-reduced-motion:reduce){
  *,*:before,*:after{scroll-behavior:auto!important;animation-duration:.001ms!important;
    animation-iteration-count:1!important;transition-duration:.001ms!important}
  .state-pill.pill-live .pill-glyph{animation:none;opacity:1}
  .job-spinner,.project-progress i,.doctor-state.running,.fr-live{animation:none}
}
@media(prefers-reduced-transparency:reduce){
  .topbar,.hub-bar,.sidebar,.inspector,.composer,.wizard,.palette,.project-table,.drop-target{
    -webkit-backdrop-filter:none!important;backdrop-filter:none!important;
    background:var(--surface)!important}
  .project-modal,.drop-overlay{-webkit-backdrop-filter:none;backdrop-filter:none;
    background:rgba(6,9,14,.62)}
  body{background:var(--bg)}
}
@supports not ((-webkit-backdrop-filter:blur(1px)) or (backdrop-filter:blur(1px))){
  .topbar,.hub-bar,.sidebar,.inspector,.composer,.wizard,.palette,.project-table,.drop-target{
    background:var(--surface)}
}
@media(forced-colors:active){
  .topbar,.hub-bar,.sidebar,.inspector,.composer,.wizard,.palette,.project-table,.run-card,
  .review-card,.decision-banner{border:1px solid CanvasText}
  .primary,.compose-button.send{forced-color-adjust:none;background:Highlight;color:HighlightText}
}
</style></head>
<body>
<p id="announcer" role="status" aria-live="polite" class="sr-only"></p>
<section class="project-hub" id="project-hub" aria-label="Projects">
  <header class="hub-bar"><button class="brand-button" id="hub-brand"><span class="brand-mark" aria-hidden="true">◇</span>
    CrossAudit <span class="version" id="hub-version">V4.16.0</span></button><span class="spacer"></span>
    <button class="icon-button" id="hub-locale" aria-label="Switch to Chinese" title="Switch language">中文</button>
    <button class="icon-button" id="hub-settings" aria-label="Settings" title="Settings">⚙</button>
    <button class="icon-button" id="hub-theme" aria-label="Switch theme">◐</button>
    <button class="primary" id="create-project">＋ New project</button></header>
  <main class="hub-main"><div class="hub-heading"><div><h1>Projects</h1>
    <p>Local project folders, each with its own files and individual chats.</p></div><div class="hub-summary" id="workspace-label">Discovering workspace…</div></div>
    <div class="job-panel" id="project-job"><span class="job-spinner"></span><div class="job-copy">
      <b id="job-title">Creating project</b><span id="job-detail">Validating settings…</span>
      <ul class="job-steps" id="job-steps"></ul><div class="job-guidance" id="job-guidance"></div></div>
      <button class="secondary" id="open-created" hidden>Open project</button></div>
    <div class="hub-note" id="hub-note" hidden></div>
    <div class="hub-tools"><input class="hub-search" id="project-search" aria-label="Search projects" placeholder="Search projects…"></div>
    <div class="project-table" id="project-list"><div class="hub-empty">Loading projects…</div></div>
  </main>
</section>

<section class="first-run" id="first-run" aria-label="First launch setup">
  <header class="fr-chrome">
    <div class="fr-brand"><span class="fr-mark" aria-hidden="true">◇</span>CrossAudit</div>
    <nav class="fr-steps" id="fr-steps" aria-label="Setup steps">
      <span class="fr-step active" data-fr-indicator="1" aria-current="step"><span class="fr-k">01</span><span class="fr-l">Welcome</span></span>
      <span class="fr-step" data-fr-indicator="2"><span class="fr-k">02</span><span class="fr-l">Readiness</span></span>
      <span class="fr-step" data-fr-indicator="3"><span class="fr-k">03</span><span class="fr-l">Providers</span></span>
      <span class="fr-step" data-fr-indicator="4"><span class="fr-k">04</span><span class="fr-l">Roles</span></span>
    </nav>
    <button type="button" class="fr-skip" id="fr-skip">Skip for now</button>
  </header>

  <div class="fr-stage" data-fr-step="1" tabindex="-1">
    <div class="fr-ghost" aria-hidden="true">01</div>
    <div class="fr-col">
      <h1 class="fr-display"><span class="l1">Build with <span class="g">one agent.</span></span><span class="l2">Verify with <span class="a">another.</span></span></h1>
      <p class="fr-lede">One model does the work. A different model checks it, independently. Everything stays on your Mac — nothing is sent anywhere you didn't choose.</p>
      <div class="fr-choices">
        <button type="button" class="fr-primary" id="fr-create">Create your first project <span class="fr-arw" aria-hidden="true">→</span></button>
        <div class="fr-choices-alt">
          <button type="button" class="fr-choice" id="fr-open">Open an existing project <span class="fr-arw" aria-hidden="true">→</span></button>
          <button type="button" class="fr-choice" id="fr-import">Import a folder <span class="fr-arw" aria-hidden="true">→</span></button>
          <button type="button" class="fr-choice" id="fr-demo">Explore a local demo <em>— no credentials needed</em> <span class="fr-arw" aria-hidden="true">→</span></button>
        </div>
      </div>
    </div>
  </div>

  <div class="fr-stage" data-fr-step="2" tabindex="-1" hidden>
    <div class="fr-ghost" aria-hidden="true">02</div>
    <div class="fr-col">
      <div class="fr-head">
        <div>
          <span class="fr-nameplate">System readiness</span>
          <h2 class="fr-rollup" id="fr-rollup">Checking your Mac…</h2>
        </div>
        <button type="button" class="fr-recheck" id="fr-recheck" aria-label="Re-check the system">
          <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M16.5 6.5A6.75 6.75 0 1 0 17 11"/><path d="M16.8 3.5v3.4h-3.4"/></svg>
          <span class="fr-recheck-label">Re-check</span>
        </button>
      </div>
      <div class="fr-groups" id="fr-groups"><div class="fr-scanning">Checking required software…</div></div>
    </div>
  </div>

  <div class="fr-stage" data-fr-step="3" tabindex="-1" hidden>
    <div class="fr-ghost" aria-hidden="true">03</div>
    <div class="fr-col">
      <span class="fr-nameplate">Provider setup</span>
      <h2 class="fr-rollup">Connect the providers you'll build and verify with.</h2>
      <p class="fr-lede-3">You need at least two different providers — one to do the work, a different one to check it.</p>
      <span class="fr-keychain">
        <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="4.5" y="8.6" width="11" height="7.4" rx="2"/><path d="M7 8.6V6.6a3 3 0 0 1 6 0v2"/></svg>
        Keys are stored in your macOS Keychain and never shown again.
      </span>
      <div class="fr-provs" id="fr-provs"><div class="fr-scanning">Loading providers…</div></div>
    </div>
  </div>

  <div class="fr-stage" data-fr-step="4" tabindex="-1" hidden>
    <div class="fr-ghost" aria-hidden="true">04</div>
    <div class="fr-col">
      <span class="fr-nameplate">Generator / Auditor</span>
      <h2 class="fr-rollup"><span class="fr-g">One builds.</span> <span class="fr-a">Another checks.</span></h2>
      <p class="fr-lede-3">We picked a recommended pair on two different providers. You can change either one.</p>
      <div class="fr-pair" id="fr-pair">
        <div class="fr-role fr-role-g">
          <span class="fr-role-kicker">Generator</span>
          <p class="fr-role-does">Does the work.</p>
          <div class="fr-role-pickers">
            <select class="fr-select" id="fr-gen-vendor" aria-label="Generator provider"></select>
            <select class="fr-select" id="fr-gen-model" aria-label="Generator model"></select>
          </div>
          <div class="fr-role-model" id="fr-gen-name">—</div>
          <div class="fr-role-mid" id="fr-gen-mid"></div>
          <div class="fr-chips" id="fr-gen-chips"></div>
        </div>
        <div class="fr-handoff" aria-hidden="true">
          <svg viewBox="0 0 90 40" fill="none"><defs><linearGradient id="fr-ho" x1="0" y1="0" x2="1" y2="0"><stop class="ho0" offset="0"/><stop class="ho1" offset="1"/></linearGradient></defs><path class="ho-line" d="M2 20h78" stroke-width="2"/><path class="ho-head" d="M72 12l14 8-14 8" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" fill="none"/></svg>
        </div>
        <div class="fr-role fr-role-a">
          <span class="fr-role-kicker">Auditor</span>
          <p class="fr-role-does">Independently checks the work — must run on a different provider.</p>
          <div class="fr-role-pickers">
            <select class="fr-select" id="fr-aud-vendor" aria-label="Auditor provider"></select>
            <select class="fr-select" id="fr-aud-model" aria-label="Auditor model"></select>
          </div>
          <div class="fr-role-model" id="fr-aud-name">—</div>
          <div class="fr-role-mid" id="fr-aud-mid"></div>
          <div class="fr-chips" id="fr-aud-chips"></div>
        </div>
      </div>
      <div class="fr-independent" id="fr-independent">
        <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 10.5 8.2 14.5 16 6"/></svg>
        <span id="fr-independent-text">Independent — your auditor runs on a different provider than your generator.</span>
      </div>
      <p class="fr-role-msg" id="fr-role-msg" role="alert"></p>
    </div>
  </div>

  <div class="fr-footbar" id="fr-footbar" hidden>
    <div class="fr-foot-wrap">
      <span class="fr-hint" id="fr-hint">You can re-run these checks any time from Settings.</span>
      <div class="fr-foot-right">
        <button type="button" class="fr-back" id="fr-back">Back</button>
        <button type="button" class="fr-primary" id="fr-continue"><span class="fr-continue-label">Continue</span> <span class="fr-arw" aria-hidden="true">→</span></button>
      </div>
    </div>
  </div>

  <footer class="fr-rail" id="fr-rail">
    <span class="fr-rail-grp"><span class="fr-dot fr-live" id="fr-rail-dot" aria-hidden="true"></span><span id="fr-rail-status">Preflight — probing environment</span></span>
    <span class="fr-rail-grp" id="fr-rail-queue">3 checks queued</span>
  </footer>
</section>

<div class="project-modal" id="project-modal" role="dialog" aria-modal="true" aria-labelledby="wizard-title">
  <form class="wizard project-wizard" id="project-form"><div class="wizard-head"><div><h2 id="wizard-title">Create a supervised project</h2>
    <p>Set up the workspace first, then choose the independent model team and GitHub delivery.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-project-modal" aria-label="Close">×</button></div>
    <ol class="wizard-progress" id="project-progress" aria-label="Project setup progress">
      <li class="active" data-project-indicator="1" aria-current="step"><span>1</span><b>Project</b><small>Name and workspace</small></li>
      <li data-project-indicator="2"><span>2</span><b>Model team</b><small>Generator and auditor</small></li>
      <li data-project-indicator="3"><span>3</span><b>GitHub</b><small>Delivery and review</small></li>
    </ol>
    <div class="wizard-body project-wizard-body"><section class="form-section project-step" data-project-step="1" tabindex="-1"><div class="step-heading"><span>Step 1 of 3</span><h3>Start with the project</h3><p>Choose where the work lives and describe the result you expect.</p></div><div class="form-grid">
      <label class="field"><span>Project name</span><input name="name" id="project-name" maxlength="80" required placeholder="chem-agent"></label>
      <label class="field full"><span>Local project folder</span><div class="path-picker"><input id="project-workspace" readonly required aria-label="Selected local project folder"><button type="button" class="secondary" id="choose-project-workspace">Choose folder…</button></div><small class="path-preview" id="project-path-preview">Choose the exact folder CrossAudit should use. The project name will not create another subfolder.</small></label>
      <label class="field full"><span>Project type</span><select name="project_type" id="project-type">
        <option value="general" selected>General work - documents, reviews, code</option>
        <option value="science">Scientific / data workflow - structured experiment outputs</option></select></label>
      <label class="field full"><span>What are you building, and what would count as a mistake?</span>
        <textarea name="description" maxlength="4000" required placeholder="A user-facing review that must be accurate, balanced, and delivered as one clear document."></textarea></label>
      <div class="field full"><span id="project-contract-hint">General projects use format, reference, link, and completeness checks. They do not require scientific metadata sidecars.</span></div>
      <details class="advanced-options field full"><summary>Advanced audit settings</summary><div class="advanced-options-body">
        <label class="field"><span>Automatic revision limit</span><select name="max_rounds" id="max-rounds-choice"><option value="1">1 - quick stop</option><option value="3" selected>3 - recommended</option><option value="5">5 - persistent</option><option value="10">10 - maximum</option></select><small class="field-help" id="round-limit-help">Up to 3 generator → auditor rounds, then the task pauses for you. It never auto-passes.</small></label>
      </div></details>
    </div></section>
    <section class="form-section project-step" data-project-step="2" tabindex="-1" hidden><div class="step-heading"><span>Step 2 of 3</span><h3>Choose the independent model team</h3><p>The generator creates the work. A different provider audits it before delivery.</p></div><div class="form-grid role-choice-grid">
      <div class="role-card"><div class="role-card-head"><span class="role-index">G</span><div><b>Generator</b><small>Creates and revises the work</small></div></div><label class="field"><span>Provider</span><select name="generator_vendor" id="generator-vendor"></select></label>
        <label class="field"><span>Connection</span><select name="generator_connection" id="generator-connection" required></select></label>
        <label class="field"><span>Model</span><select name="generator_model_choice" id="generator-model"></select></label>
        <details class="role-details" id="generator-details"><summary>Connection details</summary><div class="role-details-body">
          <label class="field"><span>API region</span><select name="generator_endpoint" id="generator-endpoint"></select><small class="field-help">The region must match the API key.</small></label>
          <label class="field custom-model off" id="generator-custom-wrap"><span>Custom model ID</span><input id="generator-custom" maxlength="120" placeholder="Model available to your account"></label>
          <div class="model-actions"><button type="button" class="secondary" data-refresh-models="generator">Refresh from provider</button></div>
        </div></details></div>
      <div class="role-card"><div class="role-card-head"><span class="role-index auditor">A</span><div><b>Independent auditor</b><small>Checks the result and cannot generate it</small></div></div><label class="field"><span>Provider</span><select name="auditor_vendor" id="auditor-vendor"></select></label>
        <label class="field"><span>Connection</span><select name="auditor_connection" id="auditor-connection" required></select></label>
        <label class="field"><span>Model</span><select name="auditor_model_choice" id="auditor-model"></select></label>
        <details class="role-details" id="auditor-details"><summary>Connection details</summary><div class="role-details-body">
          <label class="field"><span>API region</span><select name="auditor_endpoint" id="auditor-endpoint"></select><small class="field-help">The region must match the API key.</small></label>
          <label class="field custom-model off" id="auditor-custom-wrap"><span>Custom model ID</span><input id="auditor-custom" maxlength="120" placeholder="Model available to your account"></label>
          <div class="model-actions"><button type="button" class="secondary" data-refresh-models="auditor">Refresh from provider</button></div>
        </div></details></div>
    </div></section>
    <section class="form-section project-step" data-project-step="3" tabindex="-1" hidden><div class="step-heading"><span>Step 3 of 3</span><h3>Choose delivery and review</h3><p>GitHub pairing is optional. Review the local and model setup before creating anything.</p></div><div class="github-box">
      <label class="toggle-line"><input type="checkbox" name="github" id="github-toggle"><span><b>Create and connect two repositories</b>
        <small>Recommended for shared or reviewed work; a single local project is fine to start.</small></span></label>
      <div class="connection" id="github-connection">Checking GitHub connection…</div>
      <div class="github-fields" id="github-fields"><div class="form-grid">
        <label class="field"><span>Work repository name</span><input name="science_repo" id="science-repo" maxlength="161" placeholder="owner/project"></label>
        <label class="field"><span>Audit repository name</span><input name="audit_repo" id="audit-repo" maxlength="161" placeholder="owner/project-audit"></label>
        <label class="toggle-line full"><input type="checkbox" name="adopt_existing" id="adopt-existing"><span><b>Use accessible repositories if these names already exist</b><small>Off by default. Leave it off when you want two new repositories.</small></span></label>
        <label class="toggle-line full"><input type="checkbox" name="public"><span><b>Public repositories</b><small>Off by default. Private is safer for a new project.</small></span></label>
      </div><div class="repo-actions"><button type="button" class="secondary" id="check-repositories">Check names</button><span class="repo-check" id="repo-check">Names will be checked again before anything is created.</span></div></div></div>
      <div class="project-review" id="project-review" aria-live="polite"></div></section><div class="wizard-error" id="wizard-error" role="alert"></div></div>
    <div class="wizard-foot project-wizard-foot"><span id="project-foot-note">Nothing is created until the final step.</span>
      <button type="button" class="secondary" id="cancel-project">Cancel</button><button type="button" class="secondary" id="project-back" hidden>Back</button>
      <button type="button" class="primary" id="project-next">Continue</button><button class="primary" id="submit-project" hidden>Create project</button></div>
  </form>
</div>

<div class="project-modal" id="recovery-modal" role="dialog" aria-modal="true" aria-labelledby="recovery-title">
  <form class="wizard" id="recovery-form"><div class="wizard-head"><div><h2 id="recovery-title">Finish GitHub setup</h2>
    <p>Correct the repository settings and continue from the last durable step.</p></div><span class="spacer"></span>
    <button type="button" class="icon-button" id="close-recovery" aria-label="Close">×</button></div>
    <div class="wizard-body"><div class="recovery-note" id="recovery-note"></div><input type="hidden" id="recovery-root">
      <div class="form-grid"><label class="field"><span>Work repository</span><input id="recovery-science" maxlength="161" required></label>
        <label class="field"><span>Audit repository</span><input id="recovery-audit" maxlength="161" required></label></div>
      <div class="connection" id="recovery-connection"></div>
      <div class="repo-actions"><button type="button" class="secondary" id="recovery-connect-github">Connect GitHub</button>
        <a class="secondary" id="recovery-help" target="_blank" rel="noopener" hidden>Open GitHub help ↗</a></div>
      <div class="wizard-error" id="recovery-error"></div></div>
    <div class="wizard-foot"><span>Retry is idempotent: repositories created before the interruption are reused, not duplicated.</span>
      <button type="button" class="secondary" id="cancel-recovery">Cancel</button><button class="primary" id="retry-recovery">Retry setup</button></div>
  </form>
</div>

<div class="project-modal" id="delete-project-modal" role="dialog" aria-modal="true" aria-labelledby="delete-project-title">
  <form class="wizard" id="delete-project-form"><div class="wizard-head"><div><h2 id="delete-project-title">Delete project</h2>
    <p>Review the local and GitHub impact before anything is changed.</p></div><span class="spacer"></span>
    <button type="button" class="icon-button" id="close-delete-project" aria-label="Close">×</button></div>
    <div class="wizard-body"><input type="hidden" id="delete-project-root">
      <div class="delete-summary"><b id="delete-project-name">Project</b><code id="delete-project-path"></code>
        <span id="delete-project-impact" class="delete-detail">Checking project state…</span></div>
      <div class="delete-warning" style="margin-top:12px">The local folder will move to CrossAudit Trash and can be recovered. GitHub repositories remain untouched unless you explicitly select permanent deletion below.</div>
      <label class="field" style="margin-top:14px"><span>Type the project name to confirm</span>
        <input id="delete-project-confirmation" autocomplete="off" required></label>
      <label class="toggle-line" style="margin-top:14px"><input type="checkbox" id="delete-working-repository"><span><b>Permanently delete working repository</b>
        <small id="delete-working-repository-name">No working repository detected.</small></span></label>
      <label class="toggle-line" style="margin-top:10px"><input type="checkbox" id="delete-audit-repository"><span><b>Permanently delete audit repository</b>
        <small id="delete-audit-repository-name">No audit repository detected.</small></span></label>
      <label class="field conditional-field off" id="delete-github-confirm-wrap" style="margin-top:12px"><span>Type DELETE GITHUB</span>
        <input id="delete-github-confirmation" autocomplete="off" placeholder="DELETE GITHUB"></label>
      <div class="connection" id="delete-github-authorization"></div>
      <button type="button" class="secondary" id="authorize-delete-repositories" hidden>Authorize GitHub deletion</button>
      <div class="wizard-error" id="delete-project-error"></div></div>
    <div class="wizard-foot"><span>Running tasks and remote compute block deletion.</span>
      <button type="button" class="secondary" id="cancel-delete-project">Cancel</button>
      <button class="danger-button" id="confirm-delete-project" disabled>Move project to Trash</button></div>
  </form>
</div>

<div class="project-modal" id="delete-chat-modal" role="dialog" aria-modal="true" aria-labelledby="delete-chat-title">
  <form class="wizard" id="delete-chat-form"><div class="wizard-head"><div><h2 id="delete-chat-title">Delete chat?</h2>
    <p id="delete-chat-name">This chat will disappear from the project sidebar.</p></div><span class="spacer"></span>
    <button type="button" class="icon-button" id="close-delete-chat" aria-label="Close">×</button></div>
    <div class="wizard-body"><input type="hidden" id="delete-chat-id">
      <div class="delete-warning">Audit reports, receipts, commits and delivered files are preserved in the project ledger. Deleting a chat never rewrites evidence that may already have admitted a result.</div>
      <p class="delete-detail" id="delete-chat-impact" style="margin:12px 0 0"></p>
      <div class="wizard-error" id="delete-chat-error"></div></div>
    <div class="wizard-foot"><span>This only removes the individual chat from navigation.</span>
      <button type="button" class="secondary" id="cancel-delete-chat">Cancel</button>
      <button class="danger-button" id="confirm-delete-chat">Delete chat</button></div>
  </form>
</div>
<div class="project-modal" id="rename-chat-modal" role="dialog" aria-modal="true" aria-labelledby="rename-chat-title">
  <form class="wizard" id="rename-chat-form"><div class="wizard-head"><div><h2 id="rename-chat-title">Rename chat</h2>
    <p>Give this chat a title that is independent of its first message.</p></div><span class="spacer"></span>
    <button type="button" class="icon-button" id="close-rename-chat" aria-label="Close">×</button></div>
    <div class="wizard-body"><input type="hidden" id="rename-chat-id">
      <label class="field full"><span>Chat title</span><input id="rename-chat-input" maxlength="120" required placeholder="Quarterly analysis"></label>
      <div class="wizard-error" id="rename-chat-error"></div></div>
    <div class="wizard-foot"><span>The title is navigation only; audit evidence is unchanged.</span>
      <button type="button" class="secondary" id="cancel-rename-chat">Cancel</button>
      <button class="primary" id="confirm-rename-chat">Save name</button></div>
  </form>
</div>
<div class="chat-menu" id="chat-menu" role="menu" aria-label="Chat actions" hidden>
  <button type="button" role="menuitem" data-chat-menu="rename">Rename chat</button>
  <button type="button" role="menuitem" data-chat-menu="duplicate">Duplicate chat</button>
  <button type="button" role="menuitem" data-chat-menu="pin" id="chat-menu-pin">Pin chat</button>
  <button type="button" role="menuitem" data-chat-menu="archive">Archive chat</button>
  <div class="chat-menu-sep" role="separator"></div>
  <button type="button" role="menuitem" class="danger" data-chat-menu="delete">Delete chat</button>
</div>

<div class="project-modal" id="file-preview-modal" role="dialog" aria-modal="true" aria-labelledby="file-preview-title">
  <section class="wizard preview-wizard"><div class="wizard-head"><div><h2 id="file-preview-title">File preview</h2>
    <p id="file-preview-meta">Preparing preview…</p></div><span class="spacer"></span>
    <a class="secondary" id="file-preview-download" download>Download</a>
    <button type="button" class="icon-button" id="close-file-preview" aria-label="Close preview">×</button></div>
    <div class="preview-toolbar" id="file-preview-toolbar" hidden>
      <div class="preview-find" id="file-preview-find" hidden>
        <input type="search" id="file-preview-search" class="preview-search-input" placeholder="Search preview" aria-label="Search in preview" autocomplete="off" spellcheck="false">
        <span class="preview-find-count" id="file-preview-find-count" aria-live="polite"></span>
        <button type="button" class="preview-tool" id="file-preview-find-prev" aria-label="Previous match" title="Previous match">↑</button>
        <button type="button" class="preview-tool" id="file-preview-find-next" aria-label="Next match" title="Next match">↓</button>
      </div>
      <span class="spacer"></span>
      <div class="preview-zoom" id="file-preview-zoom" hidden>
        <button type="button" class="preview-tool" id="file-preview-zoom-out" aria-label="Zoom out" title="Zoom out">−</button>
        <span class="preview-zoom-level" id="file-preview-zoom-level">100%</span>
        <button type="button" class="preview-tool" id="file-preview-zoom-in" aria-label="Zoom in" title="Zoom in">+</button>
        <button type="button" class="preview-tool" id="file-preview-zoom-reset" aria-label="Reset view" title="Reset view">Reset</button>
      </div>
      <button type="button" class="preview-tool" id="file-preview-outline-toggle" hidden aria-pressed="false" aria-controls="file-preview-outline">Outline</button>
      <button type="button" class="preview-tool" id="file-preview-source" hidden aria-pressed="false">Raw</button>
      <button type="button" class="preview-tool" id="file-preview-wrap" hidden aria-pressed="false">Wrap</button>
      <button type="button" class="preview-tool" id="file-preview-copy" hidden>Copy</button>
    </div>
    <div class="preview-shell">
      <nav class="preview-outline" id="file-preview-outline" hidden aria-label="Document outline"></nav>
      <div class="preview-body" id="file-preview-body"><div class="preview-loading">Loading audited deliverable…</div></div>
    </div>
    <div class="preview-note" id="file-preview-note">The complete file remains available to download.</div>
  </section>
</div>

<div class="project-modal" id="runtime-modal" role="dialog" aria-modal="true" aria-labelledby="runtime-title">
  <form class="wizard runtime-wizard" id="runtime-form"><div class="wizard-head"><div><h2 id="runtime-title">Project controls</h2>
    <p>Choose how this project works. Changes apply to the next provider call.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-runtime" aria-label="Close">×</button></div>
    <div class="wizard-body runtime-shell"><nav class="runtime-nav" aria-label="Project control categories">
      <button type="button" class="runtime-nav-button active" data-runtime-panel="models" aria-pressed="true"><b>Models</b><small>Team & reasoning</small></button>
      <button type="button" class="runtime-nav-button" data-runtime-panel="automation" aria-pressed="false"><b>Automation</b><small>Audit & recovery</small></button>
      <button type="button" class="runtime-nav-button" data-runtime-panel="budgets" aria-pressed="false"><b>Budgets</b><small>Limits & warnings</small></button>
      <button type="button" class="runtime-nav-button" data-runtime-panel="instructions" aria-pressed="false"><b>Instructions</b><small>Project guidance</small></button>
    </nav><div class="runtime-content">
      <section class="runtime-pane" data-runtime-pane="models" tabindex="-1"><div class="runtime-pane-heading"><h3>Models, reasoning & audit loop</h3><p>Choose one model to do the work and a different provider to review it independently.</p></div>
        <div class="runtime-grid"><section class="role-card" id="runtime-generator-card"><div class="runtime-role-head"><b>Generator</b><span id="runtime-generator-vendor">…</span></div>
          <label class="field"><span>Model</span><select id="runtime-generator-model"></select></label>
          <label class="field custom-model off" id="runtime-generator-custom-wrap"><span>Custom model ID</span><input id="runtime-generator-custom" maxlength="120" placeholder="Exact provider model ID"></label>
          <label class="field"><span>Reasoning effort</span><select id="runtime-generator-effort"></select><small class="effort-help" id="runtime-generator-effort-help"></small></label>
          <div class="model-actions"><button type="button" class="secondary" data-runtime-refresh="generator">Refresh models</button></div>
        </section><section class="role-card" id="runtime-auditor-card"><div class="runtime-role-head"><b>Independent auditor</b><span id="runtime-auditor-vendor">…</span></div>
          <label class="field"><span>Model</span><select id="runtime-auditor-model"></select></label>
          <label class="field custom-model off" id="runtime-auditor-custom-wrap"><span>Custom model ID</span><input id="runtime-auditor-custom" maxlength="120" placeholder="Exact provider model ID"></label>
          <label class="field"><span>Reasoning effort</span><select id="runtime-auditor-effort"></select><small class="effort-help" id="runtime-auditor-effort-help"></small></label>
          <div class="model-actions"><button type="button" class="secondary" data-runtime-refresh="auditor">Refresh models</button></div>
        </section></div><div class="runtime-note" id="runtime-note"><b>Safe handoff.</b> A running audit keeps the models and controls it started with. These changes apply to the next call.</div>
      </section>
      <section class="runtime-pane" data-runtime-pane="automation" tabindex="-1" hidden><div class="runtime-pane-heading"><h3>Audit automation</h3><p>CrossAudit revises automatically, then pauses for you instead of silently accepting an unresolved result.</p></div>
        <section class="form-section"><div class="form-title">Audit loop</div><label class="field"><span>Automatic revision limit</span><select id="runtime-max-rounds"><option value="1">1 - quick stop</option><option value="3">3 - recommended</option><option value="5">5 - persistent</option><option value="10">10 - maximum</option></select><small class="field-help">After this many generator → auditor rounds, the task pauses and explains what needs your decision. It never auto-passes.</small></label></section>
        <details class="runtime-advanced"><summary>Advanced provider recovery</summary><div class="runtime-advanced-body"><div class="form-title">Automatic provider recovery</div>
          <div class="runtime-grid"><div class="role-card"><div class="runtime-role-head"><b>Generator fallback chain</b><span>in order</span></div><div class="fallback-list" id="runtime-generator-fallbacks"></div><div class="model-actions"><button type="button" class="secondary" data-add-fallback="generator">＋ Add fallback</button></div></div>
          <div class="role-card"><div class="runtime-role-head"><b>Auditor fallback chain</b><span>in order</span></div><div class="fallback-list" id="runtime-auditor-fallbacks"></div><div class="model-actions"><button type="button" class="secondary" data-add-fallback="auditor">＋ Add fallback</button></div></div></div>
          <div class="form-grid" style="margin-top:13px"><label class="field"><span>Attempts per route</span><input id="runtime-max-attempts" type="number" min="1" max="10"></label>
            <label class="field"><span>Initial retry delay (seconds)</span><input id="runtime-initial-backoff" type="number" min="0" max="60" step="0.1"></label>
            <label class="field"><span>Maximum retry delay (seconds)</span><input id="runtime-max-backoff" type="number" min="0" max="300" step="0.1"></label>
            <label class="field"><span>Honor Retry-After up to (seconds)</span><input id="runtime-retry-after-cap" type="number" min="0" max="900" step="1"></label>
            <label class="field"><span>Open circuit after failures</span><input id="runtime-circuit-failures" type="number" min="1" max="20"></label>
            <label class="field"><span>Circuit cooldown (seconds)</span><input id="runtime-circuit-cooldown" type="number" min="1" max="3600" step="1"></label></div>
          <small class="field-help">Retries stay inside one provider call and do not consume Generator → Auditor revision rounds. Fallback routes run only after the route before them fails.</small>
        </div></details>
      </section>
      <section class="runtime-pane" data-runtime-pane="budgets" tabindex="-1" hidden><div class="runtime-pane-heading"><h3>Usage guardrails</h3><p>Optional local warnings and stops. Your provider remains the authority for billing.</p></div>
        <div class="form-grid"><label class="field"><span>Daily token warning</span><input id="runtime-daily-token-warning" type="number" min="1" placeholder="No warning"></label>
          <label class="field"><span>Daily token hard limit</span><input id="runtime-daily-token-limit" type="number" min="1" placeholder="No limit"></label>
          <label class="field"><span>Monthly API-value warning (USD)</span><input id="runtime-monthly-cost-warning" type="number" min="0.01" step="0.01" placeholder="No warning"></label>
          <label class="field"><span>Monthly API-value hard limit (USD)</span><input id="runtime-monthly-cost-limit" type="number" min="0.01" step="0.01" placeholder="No limit"></label></div>
        <div class="guardrail-state" id="runtime-guardrail-state">Limits are local safeguards; provider billing remains authoritative.</div>
        <div class="unpriced-note" id="runtime-unpriced" hidden><span aria-hidden="true">!</span><div id="runtime-unpriced-text"></div></div>
        <div class="form-title" style="margin-top:16px">Model prices</div>
        <small class="field-help">USD per 1M tokens for models the price snapshot does not carry. Used for this project's estimates only.</small>
        <div class="price-head" aria-hidden="true"><span>Model</span><span>Input</span><span>Output</span><span>Cache write</span><span>Cache read</span><span></span></div>
        <div class="price-rows" id="runtime-prices"></div>
        <div class="model-actions"><button type="button" class="secondary" data-add-price>＋ Add price</button></div>
      </section>
      <section class="runtime-pane" data-runtime-pane="instructions" tabindex="-1" hidden><div class="runtime-pane-heading"><h3>Generator guidance</h3><p>Reusable project instructions shape the work without weakening the independent audit rules.</p></div>
        <div class="form-grid"><label class="field"><span>Edit guidance</span><select id="runtime-skill-select"><option value="__new__">Create new guidance…</option></select></label>
          <label class="field"><span>Name</span><input id="runtime-skill-name" maxlength="60" placeholder="house-style"></label>
          <label class="field full"><span>Applies to paths (optional)</span><input id="runtime-skill-scope" maxlength="500" placeholder="work/reports, work/data"><small class="field-help">Comma-separated project-relative prefixes. Leave blank to apply on every task.</small></label>
          <label class="field full"><span>Instructions for the generator</span><textarea id="runtime-skill-body" maxlength="60000" placeholder="Describe the tone, output shape, conventions or checklist this project should follow."></textarea><small class="field-help">Guidance changes how the generator works. It never changes the Constitution or what the independent auditor enforces.</small></label></div>
        <div class="model-actions"><button type="button" class="secondary" id="save-runtime-skill">Save guidance</button><span class="repo-check" id="runtime-skill-status"></span></div>
      </section>
      <div class="wizard-error" id="runtime-error"></div>
    </div></div>
    <div class="wizard-foot"><span id="runtime-foot">Automatic means the provider chooses its documented default.</span>
      <button type="button" class="secondary" id="cancel-runtime">Cancel</button><button class="primary" id="save-runtime">Save for next call</button></div>
  </form>
</div>

<div class="decision" id="resolution-modal" role="dialog" aria-modal="true"
  aria-labelledby="resolution-flag resolution-title" aria-describedby="resolution-summary">
  <form class="decision-body" id="resolution-form"><header class="decision-head">
    <span class="decision-glyph" aria-hidden="true"></span><div>
    <div class="decision-flag" id="resolution-flag">Automatic loop paused</div>
    <h1 id="resolution-title">The audit needs your decision</h1>
    <p id="resolution-summary">CrossAudit stopped safely. Nothing will continue or be admitted until you decide.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="decision-locale" aria-label="Switch to Chinese" title="Switch language">中文</button><button type="button" class="icon-button" id="close-resolution" aria-label="Review later" title="Review later">×</button></header>
    <input type="hidden" id="resolution-cycle"><input type="hidden" id="resolution-action">
    <section class="decision-block"><div class="decision-label">Goal</div>
      <p class="decision-goal" id="resolution-goal">The task this conversation asked for.</p></section>
    <section class="decision-block"><div class="decision-label">Attempted</div>
      <div class="decision-limit"><span class="decision-limit-mark" aria-hidden="true">!</span><div><b id="resolution-limit-title">Automatic audit limit reached</b>
        <p id="resolution-limit-copy">The configured rounds were used without a passing result.</p></div></div>
      <div class="decision-attempts" id="resolution-attempts"></div></section>
    <section class="decision-block"><div class="decision-label">Blocked on</div>
      <div class="decision-title-row">What is still blocking the result <span class="decision-count" id="resolution-issue-count">0</span></div>
      <div class="decision-issues" id="resolution-issues"></div></section>
    <section class="decision-block"><div class="decision-label">Recommendation</div>
      <p class="decision-request" id="resolution-request">Choose whether to provide concrete correction guidance for one more round or stop this task.</p>
      <div class="decision-secondary"><button type="button" class="secondary" id="resolution-open-settings" hidden>Review provider connection</button>
      <button type="button" class="secondary" id="resolution-open-runtime" hidden>Change model or fallback</button></div>
      <div class="decision-options">
        <label class="decision-option"><input type="radio" name="resolution-choice" value="reopen" required><span><b id="resolution-reopen-title">Revise and continue</b><i class="suggested-tag">Suggested</i><small id="resolution-reopen-copy">Give the generator specific correction guidance and unlock one additional audited round.</small></span></label>
        <label class="decision-option"><input type="radio" name="resolution-choice" value="close" required><span><b>Stop this task</b><small>Keep the current output unadmitted and close the audit cycle with your reason.</small></span></label>
      </div>
      <label class="field decision-guidance"><span id="resolution-reason-label">Your guidance or reason</span><textarea id="resolution-reason" maxlength="400" required placeholder="Select an action, then explain what CrossAudit should do."></textarea></label>
      <div class="decision-ledger-note"><b>Human decision required.</b> Your action and explanation become part of the durable audit ledger.</div>
      <div class="decision-ledger-note">The models cannot approve their own result or bypass this pause.</div>
      <div class="wizard-error" id="resolution-error"></div>
      <div class="decision-actions"><button type="button" class="secondary" id="cancel-resolution">Review later</button>
        <span class="spacer"></span><button class="primary" id="submit-resolution">Record human decision</button></div>
    </section>
  </form>
</div>

<div class="project-modal" id="settings-modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
  <form class="wizard settings-wizard" id="settings-form"><div class="wizard-head"><div><h2 id="settings-title">CrossAudit settings</h2>
    <p>Manage this Mac and model connections without using Terminal.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-settings" aria-label="Close settings">×</button></div>
    <div class="wizard-body settings-shell"><nav class="settings-nav" aria-label="Settings sections">
      <div class="settings-nav-group">General</div>
      <button type="button" class="settings-nav-button active" data-settings-panel="general" aria-pressed="true"><span class="settings-nav-icon general" aria-hidden="true"></span><span><b>General</b><small>Language and appearance</small></span></button>
      <button type="button" class="settings-nav-button" data-settings-panel="providers" aria-pressed="false"><span class="settings-nav-icon providers" aria-hidden="true"></span><span><b>Providers</b><small>Accounts and credentials</small></span><i id="settings-provider-count">0</i></button>
      <div class="settings-nav-group">Audit &amp; agent</div>
      <button type="button" class="settings-nav-button" data-settings-panel="agent" aria-pressed="false"><span class="settings-nav-icon agent" aria-hidden="true"></span><span><b>Agent behavior</b><small>Permissions and defaults</small></span></button>
      <button type="button" class="settings-nav-button" data-settings-panel="audit" aria-pressed="false"><span class="settings-nav-icon audit" aria-hidden="true"></span><span><b>Audit</b><small>Constitution and rules</small></span></button>
      <div class="settings-nav-group">Workspace</div>
      <button type="button" class="settings-nav-button" data-settings-panel="files" aria-pressed="false"><span class="settings-nav-icon files" aria-hidden="true"></span><span><b>Files</b><small>Storage on this Mac</small></span></button>
      <button type="button" class="settings-nav-button" data-settings-panel="github" aria-pressed="false"><span class="settings-nav-icon github" aria-hidden="true"></span><span><b>GitHub</b><small>Delivery connection</small></span></button>
      <button type="button" class="settings-nav-button" data-settings-panel="compute" aria-pressed="false"><span class="settings-nav-icon compute" aria-hidden="true"></span><span><b>Compute</b><small>Remote hosts</small></span></button>
      <div class="settings-nav-group">Capabilities</div>
      <button type="button" class="settings-nav-button" data-settings-panel="integrations" aria-pressed="false"><span class="settings-nav-icon integrations" aria-hidden="true"></span><span><b>Integrations</b><small>MCP, skills, tools</small></span></button>
      <button type="button" class="settings-nav-button" data-settings-panel="usage" aria-pressed="false"><span class="settings-nav-icon usage" aria-hidden="true"></span><span><b>Usage</b><small>Budgets and estimates</small></span></button>
      <div class="settings-nav-group">System</div>
      <button type="button" class="settings-nav-button" data-settings-panel="security" aria-pressed="false"><span class="settings-nav-icon security" aria-hidden="true"></span><span><b>Security &amp; privacy</b><small>Keychain and data</small></span></button>
      <button type="button" class="settings-nav-button" data-settings-panel="diagnostics" aria-pressed="false"><span class="settings-nav-icon diagnostics" aria-hidden="true"></span><span><b>Diagnostics</b><small>Doctor and versions</small></span><i id="settings-diagnostics-state">…</i></button>
      <button type="button" class="settings-nav-button" data-settings-panel="advanced" aria-pressed="false"><span class="settings-nav-icon advanced" aria-hidden="true"></span><span><b>Advanced</b><small>Developer options</small></span></button>
    </nav><div class="settings-content" id="settings-content">
    <div class="settings-search-bar"><input type="search" id="settings-search" role="searchbox" aria-label="Search settings" placeholder="Search settings…" autocomplete="off" aria-controls="settings-search-results"></div>
    <div class="settings-search-results" id="settings-search-results" role="listbox" aria-label="Search results" hidden></div>
    <section class="form-section settings-pane" data-settings-pane="general" tabindex="-1"><div class="step-heading settings-heading"><span>General</span><h3>Language and appearance</h3><p>Choose how CrossAudit looks and reads on this Mac.</p></div>
      <label class="field"><span>Appearance</span><select id="settings-appearance"><option value="light">Light</option><option value="dark">Dark</option></select></label>
      <div class="settings-jump"><button type="button" class="secondary" id="settings-appearance-system">Match system</button><small class="settings-hint">Follow this Mac's light or dark setting.</small></div>
      <label class="field" style="margin-top:14px"><span>Language</span><select id="settings-language"><option value="en">English</option><option value="zh">中文</option></select></label>
      <p class="settings-empty">Startup, updates, and notifications follow the macOS app and aren't configurable here yet.</p>
    </section><section class="form-section settings-pane" data-settings-pane="providers" tabindex="-1" hidden><div class="step-heading settings-heading"><span>Providers</span><h3>Connect the services you use</h3><p>Open only the provider you want to configure. Existing secrets are never displayed again.</p></div>
      <div class="provider-note"><b>Developer access and consumer subscriptions are different products.</b> CrossAudit only offers web sign-in where the provider publishes a supported third-party inference flow. It never imports browser cookies or CLI session files.</div>
      <div id="provider-credentials"></div>
      <p class="settings-empty">Which models each role uses, and fallback routes, are chosen per project.</p>
    </section><section class="form-section settings-pane" data-settings-pane="agent" tabindex="-1" hidden><div class="step-heading settings-heading"><span>Agent behavior</span><h3>Permissions and per-project defaults</h3><p>How the generator and independent auditor are set up, and how many rounds run before CrossAudit pauses.</p></div>
      <div class="step-heading settings-heading" id="settings-permissions"><span>Permissions</span><h3>What the agent may do in this project</h3><p>File edits and command runs are off by default. Every grant is recorded in the audit ledger, edits are recoverable, and commands still need your per-call approval.</p></div>
      <label class="toggle-line" style="margin-bottom:12px"><input type="checkbox" id="workspace-writes-toggle"><span><b>Allow the agent to edit files in this project</b><small>The agent may create and modify files in this project's directories. Every change takes a recovery point, is recorded in the audit ledger, and is reviewed by the independent auditor. Off by default.</small></span></label>
      <label class="field" style="margin-bottom:12px"><span>Commands the agent may run</span><input id="allowed-commands-input" maxlength="500" placeholder="e.g. pytest, npm, make"><small class="field-help">Comma-separated executables the agent is allowed to run (tests, build, format). Each run needs your per-call approval and runs as an argv list — never a shell — in this project only. Empty = the agent cannot run any command.</small></label>
      <p class="settings-empty">Roles, reasoning effort, and the revision limit are set per project, not as global defaults yet.</p>
      <div class="settings-jump"><button type="button" class="secondary" id="settings-open-runtime" data-settings-open="runtime">Open project controls</button><small class="settings-empty" data-scope-note hidden></small></div>
    </section><section class="form-section settings-pane" data-settings-pane="audit" tabindex="-1" hidden><div class="step-heading settings-heading"><span>Audit</span><h3>Constitution and audit rules</h3><p>The rules that govern every audit, and the guarantees CrossAudit always enforces.</p></div>
      <p class="settings-hint">Admission and source independence are always-on guarantees, not adjustable settings.</p>
      <p class="settings-empty">The constitution is edited inside each project. Evidence retention isn't configurable here yet.</p>
    </section><section class="form-section settings-pane" data-settings-pane="files" tabindex="-1" hidden><div class="step-heading settings-heading"><span>Files</span><h3>Local storage</h3><p>Where CrossAudit keeps projects on this Mac.</p></div>
      <label class="field"><span>Project workspace</span><div class="path-picker"><input id="settings-workspace" readonly><button type="button" class="secondary" id="choose-settings-workspace">Choose folder…</button></div></label>
      <p class="settings-empty">Indexing, preview, temporary files, and large-file handling use built-in defaults and aren't configurable here yet.</p>
    </section><section class="form-section settings-pane" data-settings-pane="github" tabindex="-1" hidden><div class="step-heading settings-heading"><span>GitHub</span><h3>GitHub delivery</h3><p>The GitHub connection used to deliver and audit work.</p></div>
      <div class="settings-readiness"><div class="readiness-item">GitHub connection tool<span id="settings-github-status">…</span></div></div>
      <p class="settings-empty">Repository owner and defaults are chosen per project, when you create it.</p>
    </section><section class="form-section settings-pane" data-settings-pane="compute" tabindex="-1" hidden><div class="step-heading settings-heading"><span>Compute</span><h3>Remote compute</h3><p>SSH hosts and the limits on how the generator may use them.</p></div>
      <p class="settings-empty">SSH hosts and scheduler limits are configured inside the active project. Transfer limits use built-in defaults.</p>
      <div class="settings-jump"><button type="button" class="secondary" data-settings-open="compute">Open remote compute</button><small class="settings-empty" data-scope-note hidden></small></div>
    </section><section class="form-section settings-pane" data-settings-pane="integrations" tabindex="-1" hidden><div class="step-heading settings-heading"><span>Integrations</span><h3>MCP, skills, and tools</h3><p>Capabilities the generator can call while it works.</p></div>
      <p class="settings-empty">MCP servers and generator skills are configured inside the active project.</p>
      <div class="settings-jump"><button type="button" class="secondary" data-settings-open="tools">Open tools &amp; skills</button><button type="button" class="secondary" id="settings-open-skills" data-settings-open="skills">Manage Skills</button><small class="settings-empty" data-scope-note hidden></small></div>
    </section><section class="form-section settings-pane" data-settings-pane="usage" tabindex="-1" hidden><div class="step-heading settings-heading"><span>Usage</span><h3>Usage and budgets</h3><p>Token and cost estimates, and the limits that pause a run.</p></div>
      <p class="settings-hint">Usage and budgets are tracked per project, from each project's own local ledger. Nothing is sent anywhere.</p>
      <div class="settings-jump"><label class="field"><span>Export period</span><select id="settings-usage-period"><option value="day">Today</option><option value="month" selected>This month</option><option value="all">Everything</option></select></label>
        <button type="button" class="secondary" data-usage-export="csv">Export CSV</button><button type="button" class="secondary" data-usage-export="json">Export JSON</button><small class="settings-empty" data-scope-note hidden></small></div>
      <div class="settings-usage-rollup" id="settings-usage-rollup"><p class="settings-empty">Open a project to see usage across projects.</p></div>
      <div class="settings-jump"><button type="button" class="secondary" data-settings-open="usage">Open usage</button><button type="button" class="secondary" data-settings-open="runtime-budgets">Set budgets</button><small class="settings-empty" data-scope-note hidden></small></div>
    </section><section class="form-section settings-pane" data-settings-pane="security" tabindex="-1" hidden><div class="step-heading settings-heading"><span>Security &amp; privacy</span><h3>Security and privacy</h3><p>How credentials are stored and where your data goes.</p></div>
      <p class="settings-hint">API keys are stored as write-only macOS Keychain items and are never shown again.</p>
      <div class="form-title">Where CrossAudit keeps data</div>
      <p class="settings-hint">Everything CrossAudit stores lives in three places; removing them removes every trace.</p>
      <ul class="settings-hint" id="data-locations"><li><b>App and workspace</b> — <code>~/Library/Application Support/CrossAudit</code></li><li><b>Project state</b> — <code>.crossaudit/</code> inside each project folder (the audit ledger in <code>cycles/</code> is part of the repository)</li><li><b>API keys</b> — macOS Keychain items named <code>io.crossaudit.app.provider.&lt;vendor&gt;</code>; remove them under Providers</li></ul>
      <p class="settings-empty">Provider routing is set per project. Retention, redaction, and log controls aren't configurable here yet.</p>
    </section><section class="form-section settings-pane" data-settings-pane="diagnostics" tabindex="-1" hidden><div class="step-heading settings-heading"><span>Diagnostics</span><h3>Diagnostics</h3><p>Check this Mac's setup and versions, and repair problems.</p></div>
      <div class="settings-readiness"><div class="readiness-item">Git<span id="git-state">…</span></div>
        <div class="readiness-item">GitHub connection tool<span id="ghcli-state">…</span></div>
        <div class="readiness-item">Application build<span id="runtime-state">…</span></div>
        <div class="readiness-item">Code identity<span id="digest-state">…</span></div></div>
      <div class="doctor-panel"><div class="doctor-head"><span class="doctor-state" id="doctor-state"></span>
        <div class="doctor-head-copy"><b>Environment Doctor</b><small id="doctor-summary">Preparing checks…</small></div>
        <button type="button" class="secondary doctor-details-toggle" id="toggle-doctor-details" aria-expanded="false">Show details</button>
        <button type="button" class="secondary" id="run-doctor">Run check</button></div>
        <div class="doctor-list" id="doctor-checks"><div class="doctor-empty">Checking required software…</div></div>
        <div class="doctor-message" id="doctor-message"></div></div>
      <p class="settings-empty">Logs, support bundles, and per-subsystem reset aren't available here yet.</p>
    </section><section class="form-section settings-pane" data-settings-pane="advanced" tabindex="-1" hidden><div class="step-heading settings-heading"><span>Advanced</span><h3>Advanced</h3><p>Developer and experimental options.</p></div>
      <p class="settings-empty">No developer settings, experiments, local endpoints, or debug logging are configurable here yet.</p>
    </section><div class="wizard-error" id="settings-error" role="alert"></div></div></div>
    <div class="wizard-foot"><span id="settings-foot-note">API keys are write-only macOS Keychain items. Subscription credentials stay with the official provider runtime.</span>
      <button type="button" class="secondary" id="cancel-settings">Cancel</button><button class="primary" id="save-settings">Save settings</button></div>
  </form>
</div>

<div class="project-modal" id="compute-host-modal" role="dialog" aria-modal="true" aria-labelledby="compute-host-title">
  <form class="wizard hpc-host-wizard" id="compute-host-form"><div class="wizard-head"><div><h2 id="compute-host-title">Add SSH compute host</h2>
    <p>Connect a workstation or Slurm cluster through your existing SSH setup.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-compute-host" aria-label="Close">×</button></div>
    <div class="wizard-body"><div class="hpc-host-intro"><span class="hpc-host-intro-icon">⌘</span><div><b>CrossAudit does not install anything on the cluster.</b>It uses OpenSSH config, keys, ssh-agent and ProxyJump already configured on this Mac, then runs a read-only capability check.</div></div>
      <section class="hpc-setup-section"><div class="hpc-section-head"><span class="hpc-section-index">1</span><div><b>Connection</b><p>Name the SSH target and choose a shared work directory for durable remote jobs.</p></div></div>
        <div class="hpc-connection-grid">
          <label class="field"><span>SSH alias</span><input name="alias" id="compute-alias" list="compute-aliases" maxlength="128" required placeholder="hpc-login"><datalist id="compute-aliases"></datalist><small class="field-help">Alias from ~/.ssh/config or a reachable hostname.</small></label>
          <label class="field"><span>Shared scratch directory</span><input name="scratch" maxlength="500" required placeholder="/scratch/your-user/crossaudit"><small class="field-help">For Slurm, login and compute nodes must both see this path.</small></label>
          <label class="field"><span>Parallel jobs</span><input name="concurrency" type="number" min="1" max="100" value="4" required><small class="field-help">Project limit</small></label>
          <label class="field full"><span>Cluster notes <small>optional</small></span><textarea name="details" maxlength="4000" placeholder="Approved partitions, module loads, environment activation, or account policy."></textarea></label>
        </div></section>
      <section class="hpc-setup-section"><div class="hpc-section-head"><span class="hpc-section-index">2</span><div><b>Generator access</b><p>Manual job submission is always available. Automatic access is optional and constrained by hard ceilings.</p></div></div>
        <label class="hpc-permission"><input name="agent_enabled" id="hpc-agent-enabled" type="checkbox"><span><b>Allow Generator to use this host automatically</b><small>The Generator can submit calculation scripts without per-job confirmation. Use a dedicated least-privilege SSH account.</small></span></label>
        <div class="hpc-policy off" id="hpc-agent-policy"><div class="hpc-policy-title">Generator compute policy <span>hard maximums per task</span></div>
          <div class="hpc-limit-grid">
            <label class="field"><span>Jobs per task</span><input name="agent_max_jobs" type="number" min="1" max="10" value="2" required></label>
            <label class="field"><span>Maximum nodes</span><input name="agent_max_nodes" type="number" min="1" max="64" value="1" required></label>
            <label class="field"><span>Maximum CPUs</span><input name="agent_max_cpus" type="number" min="1" max="4096" value="8" required></label>
            <label class="field"><span>Maximum GPUs</span><input name="agent_max_gpus" type="number" min="0" max="64" value="0" required></label>
            <label class="field"><span>Maximum memory</span><input name="agent_max_memory" value="16G" required></label>
            <label class="field"><span>Maximum wall time</span><input name="agent_max_walltime" value="01:00:00" required></label>
          </div><details class="hpc-advanced"><summary>Scheduler restrictions (optional)</summary><div class="hpc-limit-grid">
            <label class="field"><span>Fixed partition</span><input name="agent_partition" maxlength="128" placeholder="cpu"></label>
            <label class="field"><span>Fixed account</span><input name="agent_account" maxlength="128" placeholder="lab-account"></label>
            <label class="field"><span>Fixed QoS</span><input name="agent_qos" maxlength="128"></label>
          </div></details></div></section>
      <section class="hpc-setup-section"><div class="hpc-section-head"><span class="hpc-section-index">3</span><div><b>Host identity</b><p>Known host keys are required. A changed key always stops the connection.</p></div></div>
        <label class="hpc-host-key"><input name="trust_first_key" type="checkbox"><span><b>Trust a new host key once</b><small>Only select this after verifying the hostname with your cluster administrator. Existing or changed keys are never replaced.</small></span></label>
      </section><div class="wizard-error" id="compute-host-error"></div></div>
    <div class="wizard-foot"><span>Next: read-only connection and capability check.</span>
      <button type="button" class="secondary" id="cancel-compute-host">Cancel</button><button class="primary" id="save-compute-host">Probe & add</button></div>
  </form>
</div>

<div class="project-modal" id="compute-job-modal" role="dialog" aria-modal="true" aria-labelledby="compute-job-title">
  <form class="wizard" id="compute-job-form"><div class="wizard-head"><div><h2 id="compute-job-title">Submit remote job</h2>
    <p>Review the exact script and requested resources. The job runs as your SSH user outside the local sandbox.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-compute-job" aria-label="Close">×</button></div>
    <div class="wizard-body"><div class="form-grid">
      <label class="field"><span>Compute host</span><select name="host_id" id="compute-job-host" required></select></label>
      <label class="field"><span>Job name</span><input name="name" maxlength="80" value="CrossAudit job" required></label>
      <label class="field"><span>Partition</span><input name="partition" maxlength="128" placeholder="gpu"></label>
      <label class="field"><span>Account</span><input name="account" maxlength="128" placeholder="lab-account"></label>
      <label class="field"><span>Wall time</span><input name="walltime" value="00:30:00" required></label>
      <label class="field"><span>Memory</span><input name="memory" placeholder="16G"></label>
      <label class="field"><span>Nodes</span><input name="nodes" type="number" min="1" max="1024" value="1" required></label>
      <label class="field"><span>CPUs per task</span><input name="cpus" type="number" min="1" max="4096" value="1" required></label>
      <label class="field"><span>GPUs</span><input name="gpus" type="number" min="0" max="1024" value="0" required></label>
      <label class="field"><span>QoS</span><input name="qos" maxlength="128"></label>
      <label class="field full"><span>Job script</span><textarea class="hpc-script" name="script" required spellcheck="false" placeholder="module load python\npython analysis.py"></textarea></label>
      <div class="field full"><span>Input files</span><input id="compute-input-files" type="file" multiple hidden>
        <button type="button" class="secondary" id="add-compute-inputs">＋ Add files</button>
        <div class="field-help" id="compute-input-summary">Optional. Files are streamed to inputs/ on the remote host with no CrossAudit size or count quota.</div>
        <div class="hpc-input-list" id="compute-input-list"></div></div>
      <label class="hpc-confirm field full"><input name="approved" type="checkbox" required><span><b>I approve this remote execution</b>The script can access anything my account can read or write on this host. Closing CrossAudit will not stop it.</span></label>
    </div><div class="wizard-error" id="compute-job-error"></div></div>
    <div class="wizard-foot"><span>Slurm jobs use sbatch; workstations use a detached nohup process. Both survive connection loss.</span>
      <button type="button" class="secondary" id="cancel-compute-job">Cancel</button><button class="primary" id="submit-compute-job">Submit job</button></div>
  </form>
</div>

<div class="project-modal" id="mcp-modal" role="dialog" aria-modal="true" aria-labelledby="mcp-title">
  <form class="wizard mcp-wizard" id="mcp-form"><div class="wizard-head"><div><h2 id="mcp-title">Add MCP server</h2>
    <p>Connect the server first, then choose which of its tools this project may use.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-mcp" aria-label="Close">×</button></div>
    <ol class="mcp-steps" id="mcp-steps">
      <li class="active" data-mcp-marker="connect" aria-current="step"><span>1</span><div><b>Connect</b><small>Reach the server</small></div></li>
      <li data-mcp-marker="tools"><span>2</span><div><b>Approve tools</b><small>Choose what it may do</small></div></li>
    </ol>
    <div class="wizard-body mcp-wizard-body">
      <input type="hidden" name="server_id" id="mcp-server-id">
      <input type="hidden" name="allowed_tools_text" id="mcp-allowed-tools">
      <section class="mcp-step" data-mcp-step="connect" tabindex="-1"><div class="form-grid">
        <label class="field"><span>Server name</span><input name="name" id="mcp-name" maxlength="80" required placeholder="Research tools" aria-describedby="mcp-name-help"><small class="field-help" id="mcp-name-help">A label for this project. ASCII letters, digits, spaces and . _ - only, and it must start with a letter or digit.</small></label>
        <label class="field"><span>Transport</span><select name="transport" id="mcp-transport"><option value="stdio">Local stdio</option><option value="http">Streamable HTTP</option></select></label>
        <div class="field full mcp-transport-fields" id="mcp-stdio-fields"><div class="form-grid">
          <label class="field"><span>Executable</span><input name="command" id="mcp-command" maxlength="1000" placeholder="npx" autocomplete="off"></label>
          <label class="field"><span>Arguments</span><textarea name="args_text" id="mcp-args" maxlength="32000" placeholder="-y&#10;@example/mcp-server"></textarea><small class="field-help">One argument per line. CrossAudit never invokes a shell.</small></label>
          <label class="hpc-confirm field full" id="mcp-approve-box"><input name="approve_local_code" type="checkbox"><span><b>I approve this exact local command</b>A local MCP server runs with this app's user permissions and may access files or the network. Verify its publisher and arguments.</span></label>
          <p class="mcp-step-note field full" id="mcp-approve-required" hidden>Connect runs this command on your Mac, so the approval above is required before it can run.</p>
          <div class="field full mcp-approved" id="mcp-approved-note" hidden><b>This exact command is already approved</b><small>You approved this executable and these arguments when you connected the server. Editing either one asks you to approve the new command.</small></div>
        </div></div>
        <div class="field full mcp-transport-fields off" id="mcp-http-fields"><div class="form-grid">
          <label class="field full"><span>MCP endpoint</span><input name="url" id="mcp-url" maxlength="2000" placeholder="Secure MCP endpoint URL"></label>
          <label class="field"><span>Bearer token (optional)</span><input name="bearer_token" id="mcp-token" type="password" maxlength="16384" autocomplete="off" placeholder="Leave blank to keep saved token"></label>
          <label class="hpc-confirm field full"><input name="allow_private_network" type="checkbox"><span><b>Allow a verified private-network server</b>Use only for an enterprise hostname you control. Public remote servers must use HTTPS.</span></label>
        </div></div>
      </div>
        <details class="mcp-advanced"><summary>Call limits</summary><div class="form-grid">
          <label class="field"><span>Request timeout</span><input name="timeout" type="number" min="1" max="300" value="30" required><small class="field-help">Seconds to wait for one response.</small></label>
          <label class="field"><span>Calls per task</span><input name="max_calls_per_task" type="number" min="1" max="20" value="5" required><small class="field-help">How many times a single task may call this server.</small></label>
        </div></details>
        <p class="mcp-step-note">Connecting only reads the server's tool list. Nothing can be called until you approve it in the next step.</p>
      </section>
      <section class="mcp-step" data-mcp-step="tools" tabindex="-1" hidden>
        <div class="mcp-connected" id="mcp-connected" role="status" aria-live="polite"></div>
        <p class="mcp-step-note mcp-caveat">Tool names, descriptions and risk labels are reported by the server itself and are not verified by CrossAudit. Approve only what you recognise.</p>
        <div class="mcp-approve-head"><span>Tools this project may use</span><small id="mcp-approve-count" aria-live="polite"></small><button type="button" class="mcp-link" id="mcp-select-all">Select all except destructive</button></div>
        <div class="mcp-approve" id="mcp-tool-approve" role="group" aria-label="Advertised tools"></div>
        <label class="hpc-confirm field full" style="margin-top:15px"><input name="enabled" type="checkbox" id="mcp-enabled" aria-describedby="mcp-enable-note"><span><b>Allow Generator to call the approved tools automatically</b>Calls appear live in the task loop. Tool output is treated as untrusted external data and never becomes an audit rule.</span></label>
        <p class="mcp-step-note" id="mcp-enable-note">Leave this off to keep the server manual-only. You can turn it on later.</p>
      </section>
      <div class="wizard-error" id="mcp-error" role="alert" tabindex="-1"></div></div>
    <div class="wizard-foot"><span id="mcp-foot-note">Bearer tokens are write-only Keychain items. Local commands are stored without secrets.</span>
      <button type="button" class="secondary" id="cancel-mcp">Cancel</button>
      <button type="button" class="secondary" id="mcp-back" hidden>Back</button>
      <button class="primary" id="save-mcp" aria-describedby="mcp-approve-required">Connect</button></div>
  </form>
</div>

<div class="drop-overlay" id="drop-overlay" aria-hidden="true"><div class="drop-target">
  <div class="drop-icon">＋</div><b>Drop files to add them</b>
  <span>No CrossAudit file-count or file-size quota. Available storage, filesystem limits and provider context still apply.</span>
</div></div>

<div class="project-modal palette-shell" id="palette" role="dialog" aria-modal="true" aria-labelledby="palette-title">
  <div class="palette"><h2 class="sr-only" id="palette-title">Command palette</h2>
    <input class="palette-input" id="palette-input" placeholder="Type a command or search…" autocomplete="off" aria-label="Command palette">
    <div class="palette-list" id="palette-list"></div></div>
</div>

<div class="app">
  <header class="topbar">
    <button class="icon-button mobile-sidebar" id="sidebar-toggle" aria-label="Open navigation"
      aria-controls="sidebar-panel" aria-expanded="false">☰</button>
    <button class="icon-button" id="back-projects" aria-label="Back to projects" title="Back to projects">←</button>
    <button class="brand-button" id="projects-home"><span class="brand-mark" aria-hidden="true">◇</span>CrossAudit
      <span class="version" id="version-badge">V4.16.0</span></button>
    <button class="top-project" id="project-switcher"><b id="proj">…</b> <span id="branch-label">/ project folder</span></button>
    <button class="icon-button" id="current-project-pin" aria-label="Pin project" title="Pin project">☆</button>
    <span class="spacer"></span>
    <button type="button" class="usage-pill" id="usage-pill" aria-label="Open usage" title="Open usage" hidden></button>
    <div class="live-pill"><span class="live-dot" id="livedot"></span><span id="conn-text">connecting</span></div>
    <button class="icon-button" id="palette-open" aria-label="Command palette" title="Command palette · ⌘K">⌘</button>
    <button class="icon-button" id="locale-toggle" aria-label="Switch to Chinese" title="Switch language">中文</button>
    <button class="icon-button" id="settings-open" aria-label="Settings" title="Settings">⚙</button>
    <button class="icon-button" id="theme-toggle" aria-label="Switch to dark theme" title="Toggle theme">◐</button>
    <button class="icon-button" id="inspect-toggle" aria-label="Toggle context panel"
      aria-controls="inspector" aria-expanded="false">☷</button>
  </header>

  <div class="sample-banner" id="sample-banner" role="note" aria-label="Sample demonstration notice" hidden>
    <span class="sample-badge" aria-hidden="true">SAMPLE</span>
    <b>Sample demonstration — not a real audit.</b>
    <span class="sample-detail">No models were run and no API keys were used; this content is illustrative.</span></div>

  <div class="decision-banner" id="decision-banner" hidden><span class="banner-glyph" aria-hidden="true"></span>
    <b id="decision-banner-text">1 task needs your decision</b>
    <button type="button" class="secondary" id="decision-banner-review">Review</button></div>

  <div class="usage-banner" id="usage-banner" role="status" hidden><span class="banner-glyph" aria-hidden="true"></span>
    <b id="usage-banner-text"></b><span id="usage-banner-reset"></span>
    <button type="button" class="secondary" id="usage-banner-dismiss">Dismiss</button></div>

  <button class="scrim" id="scrim" aria-label="Close open panel"></button>

  <aside class="sidebar" id="sidebar-panel" aria-label="Chats">
    <div class="rail-search"><span class="rail-search-icon" aria-hidden="true"></span>
      <input id="rail-search" placeholder="Search chats" aria-label="Search chats"></div>
    <button class="new-task" id="new-task"><span aria-hidden="true">＋</span>New chat<span>⌘N</span></button>
    <div class="task-list" id="task-list"></div>
    <div class="sidebar-foot"><b id="side-project">…</b><span id="tier-label">local controller</span></div>
  </aside>

  <main class="workspace">
    <div class="thread-head"><div class="thread-title"><h1 id="thread-title">New task</h1></div><span class="spacer"></span>
      <span class="state-pill" id="thread-status"><span class="pill-glyph" aria-hidden="true"></span><span class="pill-label">ready</span><span class="pill-detail" hidden></span></span>
      <button type="button" class="runtime-button" id="runtime-open" title="Switch models, reasoning effort and audit loop settings">Project controls</button></div>
    <div class="thread" id="thread"><div class="thread-inner">
      <div class="interrupted" id="interrupted"></div><div id="conversation"></div>
    </div></div>
  </main>

  <div class="composer-wrap"><form class="composer" id="f" autocomplete="off">
    <input id="file-input" type="file" multiple hidden>
    <div class="contract-preview" id="contract-preview"></div>
    <div class="attachments" id="attachments"></div>
    <div class="audience-bar" aria-label="Message recipient"><span class="audience-label">To</span>
      <button type="button" class="audience-chip active" data-audience="auto">Auto</button>
      <button type="button" class="audience-chip" data-audience="generator">@ Generator</button>
      <button type="button" class="audience-chip" data-audience="auditor">@ Auditor</button></div>
    <div class="compose-row"><button type="button" class="compose-button" id="attach" aria-label="Add files" title="Add files"><span class="attach-glyph" aria-hidden="true"></span></button>
      <div class="compose-well"><textarea id="say" rows="1" aria-label="Your task or message" placeholder="Message the group, or @ someone…"></textarea></div>
      <button type="button" id="stop-run" class="compose-button stop" aria-label="Cancel running task" title="Cancel running task" hidden><span class="stop-glyph" aria-hidden="true"></span></button>
      <button id="send" class="compose-button send" aria-label="Run task"><span class="send-glyph" aria-hidden="true"></span></button></div>
    <div class="composer-meta"><button type="button" id="model-summary">Generator → Auditor</button>
      <span class="autonomy-summary" title="Generator infers focus, format, tone, and structure unless you specify them.">Auto-planning</span><span class="spacer"></span>
      <span>Enter to send · Shift+Enter for new line</span></div><div class="route" id="route"></div>
  </form></div>

  <aside class="inspector" id="inspector" aria-label="Context panel">
    <div class="inspect-head"><h2 id="panel-title">Files</h2><span class="spacer"></span>
      <button class="icon-button" id="inspect-close" aria-label="Close context panel">×</button></div>
    <nav class="panel-tabs" id="workspace-tools" aria-label="Context tabs">
      <button type="button" class="nav-item" data-view="artifacts" aria-pressed="false"><span class="nav-icon" aria-hidden="true"></span>Files</button>
      <button type="button" class="nav-item" data-view="audits" aria-pressed="false" aria-label="Audit context"><span class="nav-icon" aria-hidden="true"></span>Audit</button>
      <button type="button" class="nav-item" data-view="models" aria-pressed="false"><span class="nav-icon" aria-hidden="true"></span>Models</button>
      <button type="button" class="nav-item" data-view="usage" aria-pressed="false"><span class="nav-icon" aria-hidden="true"></span>Usage</button>
      <button type="button" class="nav-item" data-view="compute" aria-pressed="false"><span class="nav-icon" aria-hidden="true"></span>Compute</button>
      <button type="button" class="nav-item" data-view="tools" aria-pressed="false" aria-label="Tools &amp; Skills"><span class="nav-icon" aria-hidden="true"></span>Tools</button>
      <button type="button" class="nav-item" data-view="evidence" aria-pressed="false" aria-label="Governed actions and evidence"><span class="nav-icon" aria-hidden="true"></span>Governed</button>
      <button type="button" class="nav-item" data-view="plan" aria-pressed="false" aria-label="Goal and plan"><span class="nav-icon" aria-hidden="true"></span>Plan</button></nav>
    <div class="panel-body">
      <div class="panel-pane" id="panel-models" hidden>
        <section class="inspect-section"><div class="inspect-title">Models</div>
          <div class="model"><span class="role-mark generator" aria-hidden="true">G</span><div class="model-copy"><div class="model-role">Generator</div><div class="model-name" id="runtime-generator">…</div></div></div>
          <div class="model"><span class="role-mark auditor" aria-hidden="true">A</span><div class="model-copy"><div class="model-role">Independent auditor</div><div class="model-name" id="runtime-auditor">…</div></div></div>
          <div class="model-actions-row"><button type="button" class="secondary" id="panel-open-runtime">Change models</button>
            <button type="button" class="secondary" data-view="tools">Tools &amp; Skills</button></div></section>
        <section class="inspect-section"><div class="inspect-title">Loop parameters</div>
          <div class="kv"><span>Maximum rounds</span><span id="max-rounds">…</span></div>
          <div class="kv"><span>Current round</span><span id="current-round">-</span></div>
          <div class="kv"><span>Constitution</span><span id="rules-count">…</span></div>
          <div class="kv"><span>Admission tier</span><span id="tier-value">…</span></div></section>
        <section class="inspect-section"><div class="inspect-title" id="runtime-checks-title">Automatic checks</div>
          <p class="check-summary" id="runtime-checks-state"></p>
          <div id="runtime-checks" role="list" aria-labelledby="runtime-checks-title" aria-describedby="runtime-checks-state"></div></section>
        <section class="inspect-section"><div class="inspect-title">Ledger</div>
          <div class="mini-metrics" id="mini-metrics"></div></section>
        <section class="inspect-section"><div class="inspect-title">Needs attention</div>
          <div id="escalations"></div></section>
      </div>
      <div class="panel-pane" id="panel-dynamic"></div>
    </div>
  </aside>
</div>

<script>
const T = new URLSearchParams(location.search).get('t') || '';
const LOCALE_KEY='crossaudit-locale';
const LOCALE_COOKIE='crossaudit_v4_locale';
const ZH={
  "Agent behavior":"智能体行为","Diagnostics":"诊断","Advanced":"高级","Security & privacy":"安全与隐私","Integrations":"集成",
  "Language and appearance":"语言与外观","Accounts and credentials":"账户与凭据","Roles and rounds":"角色与轮数",
  "Constitution and rules":"章程与规则","Storage on this Mac":"此 Mac 上的存储","Delivery connection":"交付连接",
  "Remote hosts":"远程主机","MCP, skills, tools":"MCP、技能、工具","Budgets and estimates":"预算与估算",
  "Keychain and data":"钥匙串与数据","Doctor and versions":"诊断与版本","Developer options":"开发者选项",
  "Default roles and revision rounds":"默认角色与修订轮数","Constitution and audit rules":"章程与审计规则",
  "Local storage":"本地存储","GitHub delivery":"GitHub 交付","Remote compute":"远程计算","MCP, skills, and tools":"MCP、技能与工具",
  "Usage and budgets":"用量与预算","Security and privacy":"安全与隐私",
  "Choose how CrossAudit looks and reads on this Mac.":"选择 CrossAudit 在此 Mac 上的外观与阅读方式。",
  "How the generator and independent auditor are set up, and how many rounds run before CrossAudit pauses.":"生成者与独立审计者的配置方式，以及在 CrossAudit 暂停前运行多少轮。",
  "The rules that govern every audit, and the guarantees CrossAudit always enforces.":"约束每一次审计的规则，以及 CrossAudit 始终强制执行的保证。",
  "Where CrossAudit keeps projects on this Mac.":"CrossAudit 在此 Mac 上保存项目的位置。",
  "The GitHub connection used to deliver and audit work.":"用于交付与审计工作的 GitHub 连接。",
  "SSH hosts and the limits on how the generator may use them.":"SSH 主机，以及生成者使用它们的限制。",
  "Capabilities the generator can call while it works.":"生成者在工作时可以调用的能力。",
  "Token and cost estimates, and the limits that pause a run.":"Token 与成本估算，以及会使运行暂停的上限。",
  "How credentials are stored and where your data goes.":"凭据的存储方式，以及你的数据流向何处。",
  "Check this Mac's setup and versions, and repair problems.":"检查此 Mac 的配置与版本，并修复问题。",
  "Developer and experimental options.":"开发者与实验性选项。",
  "Startup, updates, and notifications follow the macOS app and aren't configurable here yet.":"启动、更新与通知随 macOS 应用一同管理，此处暂不可配置。",
  "Which models each role uses, and fallback routes, are chosen per project.":"每个角色使用的模型以及备用路由按项目分别选择。",
  "Roles, reasoning effort, and the revision limit are set per project, not as global defaults yet.":"角色、推理强度与修订上限按项目设置，暂不作为全局默认值。",
  "Admission and source independence are always-on guarantees, not adjustable settings.":"准入与来源独立性是始终启用的保证，而非可调设置。",
  "The constitution is edited inside each project. Evidence retention isn't configurable here yet.":"章程在每个项目内部编辑。证据留存此处暂不可配置。",
  "Indexing, preview, temporary files, and large-file handling use built-in defaults and aren't configurable here yet.":"索引、预览、临时文件与大文件处理使用内置默认值，此处暂不可配置。",
  "Repository owner and defaults are chosen per project, when you create it.":"仓库所有者与默认值在创建项目时按项目选择。",
  "SSH hosts and scheduler limits are configured inside the active project. Transfer limits use built-in defaults.":"SSH 主机与调度器限制在当前项目内部配置。传输限制使用内置默认值。",
  "MCP servers and generator skills are configured inside the active project.":"MCP 服务器与生成者技能在当前项目内部配置。",
  "API keys are stored as write-only macOS Keychain items and are never shown again.":"API 密钥以只写方式存入 macOS 钥匙串，且不会再次显示。",
  "Where CrossAudit keeps data":"CrossAudit 的数据存放位置","Everything CrossAudit stores lives in three places; removing them removes every trace.":"CrossAudit 保存的所有内容只在三个位置；删除它们即可清除全部痕迹。","App and workspace":"应用与工作区","Project state":"项目状态","API keys":"API 密钥","inside each project folder (the audit ledger in":"位于每个项目文件夹内（","is part of the repository)":"中的审计账本属于仓库的一部分）","— macOS Keychain items named":"—— macOS 钥匙串条目，名为","; remove them under Providers":"；可在“供应商”中移除",
  "Provider routing is set per project. Retention, redaction, and log controls aren't configurable here yet.":"供应商路由按项目设置。留存、脱敏与日志控制此处暂不可配置。",
  "Logs, support bundles, and per-subsystem reset aren't available here yet.":"日志、支持包与按子系统重置此处暂不可用。",
  "No developer settings, experiments, local endpoints, or debug logging are configurable here yet.":"暂无可配置的开发者设置、实验、本地端点或调试日志。",
  "Follow this Mac's light or dark setting.":"跟随此 Mac 的浅色或深色设置。",
  "Appearance":"外观","Light":"浅色","Dark":"深色","Match system":"跟随系统","Language":"语言",
  "Open project controls":"打开项目控制","Open remote compute":"打开远程计算","Open tools & skills":"打开工具与技能",
  "Open usage":"打开用量","Set budgets":"设置预算",
  "Search settings…":"搜索设置…","Search settings":"搜索设置","No matching settings.":"没有匹配的设置。",
  "Credentials":"凭据","Revision rounds":"修订轮数","SSH hosts":"SSH 主机","Keychain":"钥匙串",
  "Projects":"项目","Local project folders, each with its own files and individual chats.":"本地项目文件夹，每个项目都有自己的文件和独立对话。",
  "Discovering workspace…":"正在发现工作区…","Creating project":"正在创建项目","Validating settings…":"正在验证设置…",
  "Open project":"打开项目","Search projects…":"搜索项目…","New project":"新建项目","＋ New project":"＋ 新建项目",
  "Create a supervised project":"创建受监督项目","Configure both roles and, if you choose, create the separated GitHub repositories.":"配置两个角色，并可选择创建相互隔离的 GitHub 仓库。",
  "Set up the workspace first, then choose the independent model team and GitHub delivery.":"先设置工作区，再选择相互独立的模型团队和 GitHub 交付方式。",
  "Project setup progress":"项目设置进度","Name and workspace":"名称和工作区","Model team":"模型团队","Generator and auditor":"生成者和审计者","Delivery and review":"交付与确认",
  "Step 1 of 3":"第 1 / 3 步","Step 2 of 3":"第 2 / 3 步","Step 3 of 3":"第 3 / 3 步",
  "Start with the project":"先定义项目","Choose where the work lives and describe the result you expect.":"选择工作所在位置，并描述你期望的结果。",
  "Advanced audit settings":"高级审计设置","Choose the independent model team":"选择相互独立的模型团队",
  "The generator creates the work. A different provider audits it before delivery.":"生成者负责完成工作，交付前由另一家供应商独立审计。",
  "Creates and revises the work":"创建并修订工作","Checks the result and cannot generate it":"检查结果，且不能参与生成",
  "Choose delivery and review":"选择交付方式并确认","GitHub pairing is optional. Review the local and model setup before creating anything.":"GitHub 配对是可选项。创建任何内容前，请确认本地与模型设置。",
  "Nothing is created until the final step.":"到最后一步前不会创建任何内容。","Back":"返回","Continue":"继续",
  "Project":"项目","Project name":"项目名称","Project type":"项目类型","General work - documents, reviews, code":"通用工作——文档、评审、代码",
  "Scientific / data workflow - structured experiment outputs":"科学 / 数据工作流——结构化实验输出",
  "General projects use format, reference, link, and completeness checks. They do not require scientific metadata sidecars.":"通用项目检查格式、引用、链接和完整性，不要求科学元数据附属文件。",
  "What are you building, and what would count as a mistake?":"你要构建什么？哪些情况应判定为错误？",
  "A user-facing review that must be accurate, balanced, and delivered as one clear document.":"一份面向用户、准确平衡且以单一清晰文档交付的评审。",
  "Automatic revision limit":"自动修订轮数上限","1 - quick stop":"1 - 快速停止","3 - recommended":"3 - 推荐",
  "5 - persistent":"5 - 持续修订","10 - maximum":"10 - 最大值",
  "Local workspace folder":"本地工作区文件夹","Local project folder":"本地项目文件夹","Choose folder…":"选择文件夹…","Selected local workspace":"已选择的本地工作区","Selected local project folder":"已选择的本地项目文件夹",
  "Choose where this project's local folder will be created.":"选择创建该项目本地文件夹的位置。","Choose the exact folder CrossAudit should use. The project name will not create another subfolder.":"请选择 CrossAudit 直接使用的文件夹；项目名称不会再创建子文件夹。",
  "Independent roles":"独立角色","Generator":"生成者","Independent auditor":"独立审计者","Provider":"供应商","Connection":"连接方式",
  "Connection details":"连接详情","API region":"API 区域","The region must match the API key.":"区域必须与 API key 匹配。","Model":"模型",
  "Model available to your account":"你的账户可用的模型","Custom model ID":"自定义模型 ID","Exact provider model ID":"准确的供应商模型 ID",
  "Refresh from provider":"从供应商刷新","GitHub":"GitHub","Create and connect two repositories":"创建并连接两个仓库",
  "Recommended for shared or reviewed work; a single local project is fine to start.":"适合共享或需要评审的工作；一开始只用一个本地项目也完全可以。",
  "Checking GitHub connection…":"正在检查 GitHub 连接…","Work repository name":"工作仓库名称","Audit repository name":"审计仓库名称",
  "Use accessible repositories if these names already exist":"若这些名称已存在，则使用可访问的仓库",
  "Off by default. Leave it off when you want two new repositories.":"默认关闭。需要创建两个新仓库时请保持关闭。",
  "Public repositories":"公开仓库","Off by default. Private is safer for a new project.":"默认关闭。新项目使用私有仓库更安全。",
  "Check names":"检查名称","Names will be checked again before anything is created.":"创建任何内容前都会再次检查名称。",
  "Creating may send the description to the auditor model and create repositories in your connected GitHub account.":"创建操作可能会把描述发送给审计模型，并在已连接的 GitHub 账户中创建仓库。",
  "Cancel":"取消","Create project":"创建项目","Finish GitHub setup":"完成 GitHub 设置",
  "Correct the repository settings and continue from the last durable step.":"修正仓库设置，并从最近的持久化步骤继续。",
  "Work repository":"工作仓库","Audit repository":"审计仓库","Connect GitHub":"连接 GitHub","Open GitHub help ↗":"打开 GitHub 帮助 ↗",
  "Retry setup":"重试设置","Retry is idempotent: repositories created before the interruption are reused, not duplicated.":"重试是幂等的：中断前已创建的仓库会被复用，不会重复创建。",
  "Project controls":"项目控制","Choose how this project works. Changes apply to the next provider call.":"选择此项目的工作方式；更改会从下一次供应商调用开始生效。",
  "Project control categories":"项目控制分类","Models":"模型","Team & reasoning":"团队与推理","Automation":"自动化","Audit & recovery":"审计与恢复",
  "Budgets":"预算","Limits & warnings":"上限与预警","Instructions":"指令","Project guidance":"项目指导",
  "Models, reasoning & audit loop":"模型、推理与审计循环","Choose one model to do the work and a different provider to review it independently.":"选择一个模型执行工作，并由另一家供应商的模型独立审查。",
  "Audit automation":"审计自动化","CrossAudit revises automatically, then pauses for you instead of silently accepting an unresolved result.":"CrossAudit 会自动修订；若问题仍未解决则暂停等待你决定，绝不会静默接受。",
  "Advanced provider recovery":"高级供应商恢复","Optional local warnings and stops. Your provider remains the authority for billing.":"可选的本地预警与停止线；最终计费仍以供应商为准。",
  "Reusable project instructions shape the work without weakening the independent audit rules.":"可复用的项目指令会规范工作方式，但不会削弱独立审计规则。",
  "Reasoning effort":"推理强度","Refresh models":"刷新模型","Audit loop":"审计循环",
  "Automatic provider recovery":"供应商自动恢复","Generator fallback chain":"生成者备用路由链","Auditor fallback chain":"审计者备用路由链","in order":"按顺序",
  "＋ Add fallback":"＋ 添加备用路由","Attempts per route":"每条路由尝试次数","Initial retry delay (seconds)":"首次重试延迟（秒）",
  "Maximum retry delay (seconds)":"最大重试延迟（秒）","Honor Retry-After up to (seconds)":"遵循 Retry-After 的最大秒数",
  "Open circuit after failures":"连续失败后打开熔断器","Circuit cooldown (seconds)":"熔断冷却时间（秒）",
  "Retries stay inside one provider call and do not consume Generator → Auditor revision rounds. Fallback routes run only after the route before them fails.":"重试发生在单次供应商调用内部，不消耗生成者 → 审计者修订轮次；只有前一条路由失败后才会使用备用路由。",
  "Usage guardrails":"用量保护线","Daily token warning":"每日 Token 预警","Daily token hard limit":"每日 Token 硬上限",
  "Monthly API-value warning (USD)":"每月 API 价值预警（美元）","Monthly API-value hard limit (USD)":"每月 API 价值硬上限（美元）",
  "No warning":"不预警","No limit":"不限制","Limits are local safeguards; provider billing remains authoritative.":"这些上限是本地保护措施，最终计费以供应商为准。",
  "No fallback. A provider failure pauses safely for you.":"未配置备用路由。供应商失败时会安全暂停并等待你处理。",
  "Project controls updated.":"项目控制已更新。","Recovery routes, usage guardrails, models and loop limits apply to the next provider call.":"恢复路由、用量保护线、模型和循环上限将在下一次供应商调用时生效。",
  "The selected effort is sent on the next provider request.":"所选推理强度会用于下一次供应商请求。",
  "After this many generator → auditor rounds, the task pauses and explains what needs your decision. It never auto-passes.":"达到该生成者 → 审计者轮数后，任务会暂停并说明需要你决定的事项，绝不会自动通过。",
  "Generator guidance":"生成者指导","Edit guidance":"编辑指导","Create new guidance…":"创建新指导…","Name":"名称",
  "Applies to paths (optional)":"适用路径（可选）","Comma-separated project-relative prefixes. Leave blank to apply on every task.":"以逗号分隔的项目相对路径前缀。留空则适用于所有任务。",
  "Instructions for the generator":"给生成者的说明","Describe the tone, output shape, conventions or checklist this project should follow.":"描述此项目应遵循的语气、输出形式、约定或检查清单。",
  "Guidance changes how the generator works. It never changes the Constitution or what the independent auditor enforces.":"指导只改变生成者的工作方式，不会修改审计章程或独立审计者执行的标准。",
  "Save guidance":"保存指导","Safe handoff.":"安全交接。",
  "A running audit keeps the models and controls it started with. These changes apply to the next call.":"运行中的审计会保持启动时的模型与控制设置；这些更改从下一次调用生效。",
  "Models and loop limits update crossaudit.yml; generator guidance is versioned in the project. A running audit keeps the controls it started with.":"模型和循环上限会更新 crossaudit.yml；生成者指导在项目中进行版本控制。运行中的审计保持启动时的控制设置。",
  "Automatic means the provider chooses its documented default.":"自动表示由供应商采用其文档规定的默认值。","Save for next call":"保存供下次调用使用",
  "Automatic loop paused":"自动循环已暂停","The audit needs your decision":"审计需要你作出决定",
  "CrossAudit stopped safely. Nothing will continue or be admitted until you decide.":"CrossAudit 已安全暂停。在你作出决定前，不会继续执行，也不会准入任何结果。",
  "Automatic audit limit reached":"已达自动审计轮数上限","The configured rounds were used without a passing result.":"已用完设定的轮数，但仍未获得通过结果。",
  "What is still blocking the result":"当前仍在阻止结果通过的问题","What CrossAudit needs from you":"CrossAudit 需要你处理什么",
  "Choose whether to provide concrete correction guidance for one more round or stop this task.":"请选择：提供具体修正指导并再进行一轮，或停止此任务。",
  "Revise and continue":"修订并继续","Give the generator specific correction guidance and unlock one additional audited round.":"向生成者提供具体修正指导，并解锁额外一轮受审计执行。",
  "Stop this task":"停止此任务","Keep the current output unadmitted and close the audit cycle with your reason.":"保持当前输出不准入，并附上原因关闭审计循环。",
  "Your guidance or reason":"你的指导或原因","Select an action, then explain what CrossAudit should do.":"先选择一项操作，再说明 CrossAudit 应该如何处理。",
  "Human decision required.":"需要人工决定。","Your action and explanation become part of the durable audit ledger.":"你的操作和说明会成为持久审计账本的一部分。",
  "The models cannot approve their own result or bypass this pause.":"模型无法自行批准结果，也无法绕过此暂停。","Review later":"稍后处理","Record human decision":"记录人工决定",
  "Correction guidance for the next round":"下一轮的修正指导","Describe exactly what should change before the next audit.":"具体说明下一次审计前应修改什么。",
  "Record guidance & unlock round":"记录指导并解锁一轮","Reason for stopping":"停止原因","Explain why this task should stop without admitting its current output.":"说明为什么应停止任务且不准入当前输出。",
  "Stop without admission":"停止且不准入","The automatic loop could not continue safely":"自动循环无法安全继续",
  "No structured findings were recorded. Review the stop reason above before continuing.":"未记录结构化问题。继续前请检查上方的停止原因。",
  "Choose whether to revise and continue, or stop this task.":"请选择修订并继续，或停止此任务。","Review issues & decide":"查看问题并决定",
  "Generator connection stopped":"生成者连接已停止","The task is waiting for a working Generator connection":"任务正在等待可用的生成者连接",
  "CrossAudit stopped before an audit began. No result was admitted and the original task is ready to retry.":"CrossAudit 在审计开始前已安全暂停。没有结果被准入，原任务可直接重试。",
  "No audit findings were created because the Generator stopped before producing a reviewable result.":"生成者在产出可审查结果前停止，因此没有生成审计问题。",
  "Retry the same task now, review the model connection first, or stop this task.":"立即重试同一任务、先检查模型连接，或停止此任务。",
  "Retry provider":"重试供应商","Use the current connection and rerun the original task.":"使用当前连接重新运行原任务。",
  "Review provider connection":"检查供应商连接","Change model or fallback":"更改模型或备用路由","Retry provider now":"立即重试供应商","Provider retry started.":"供应商重试已开始。",
  "Waiting for the provider":"等待供应商","waiting for provider":"等待供应商","stalled":"已停滞","just now":"刚刚",
  "Needs your decision · later round":"需要你决定 · 更晚的一轮",
  "no heartbeat was ever recorded for this run":"此任务从未记录过心跳",
  "The original task is running again; live progress will appear here.":"原任务已重新运行；实时进度会显示在这里。",
  "Retry note (optional)":"重试备注（可选）","Optional note for the audit ledger.":"可选：为审计账本添加备注。",
  "Usage limit reached":"已达用量上限","The task paused at a usage limit":"任务因达到用量上限而暂停",
  "Adjust usage limits":"调整用量上限","Continue later":"稍后继续","Raise the limit & retry":"提高上限并重试",
  "CrossAudit stopped before spending past your usage limit. No result was admitted and the original task is ready once you raise or clear the limit.":"CrossAudit 在超出用量上限前已停止。没有结果被准入；提高或清除上限后即可重新运行原任务。",
  "No audit findings were created because the task paused at a usage limit before producing a reviewable result.":"任务在产出可审查结果前因达到用量上限而暂停，因此没有生成审计问题。",
  "Raise or clear the usage limit and rerun the original task, or stop this task.":"提高或清除用量上限并重新运行原任务，或停止此任务。",
  "Adjust the usage limit in Project controls, then rerun the original task.":"在项目控制中调整用量上限，然后重新运行原任务。",
  "Open folder":"打开文件夹","Dismiss":"忽略","Project creation stopped":"项目创建已暂停",
  "Review local changes before setup":"设置前请检查本地改动","Checking the project again":"正在重新检查项目",
  "CrossAudit settings":"CrossAudit 设置","Check this Mac, repair setup issues, and connect model providers without using Terminal.":"检查此 Mac、修复设置问题并连接模型供应商，全程无需终端。",
  "Manage this Mac and model connections without using Terminal.":"管理此 Mac 与模型连接，全程无需终端。","Settings sections":"设置分类",
  "General":"通用","Workspace and this Mac":"工作区与此 Mac","Model providers":"模型供应商","Subscriptions and API keys":"订阅与 API key",
  "Workspace and application readiness":"工作区与应用就绪状态","CrossAudit checks required software and offers a direct recovery action when something needs attention.":"CrossAudit 会检查必需软件，并在发现问题时直接提供修复操作。",
  "Show details":"显示详情","Hide details":"隐藏详情","Connect the services you use":"连接你使用的服务",
  "Open only the provider you want to configure. Existing secrets are never displayed again.":"只展开需要配置的供应商；已保存的密钥永远不会再次显示。","Done":"完成",
  "Workspace changes apply immediately. Run Doctor after moving or updating this Mac.":"工作区修改会立即生效；迁移或更新此 Mac 后请再次运行环境诊断。",
  "Application readiness":"应用就绪状态","Git":"Git","GitHub connection tool":"GitHub 连接工具","Application build":"应用构建","Code identity":"代码身份",
  "Environment Doctor":"环境诊断","Preparing checks…":"正在准备检查…","Run check":"运行检查","Checking required software…":"正在检查所需软件…",
  "Project workspace":"项目工作区","Provider credentials":"供应商凭据",
  "Backup API key (optional)":"备用 API Key（可选）","Used only by an explicit fallback route":"仅由明确配置的备用路由使用",
  "Delete backup key":"删除备用 Key","Primary key":"主 Key","Backup key":"备用 Key",
  "Developer access and consumer subscriptions are different products.":"开发者 API 与消费者订阅是不同的产品。",
  "CrossAudit only offers web sign-in where the provider publishes a supported third-party inference flow. It never imports browser cookies or CLI session files.":"只有供应商公开支持第三方推理登录流程时，CrossAudit 才提供网页登录。它不会导入浏览器 Cookie 或 CLI 会话文件。",
  "API keys are write-only macOS Keychain items. Subscription credentials stay with the official provider runtime.":"API key 以只写方式存入 macOS 钥匙串；订阅凭据始终由官方供应商运行时持有。",
  "Save settings":"保存设置","Add SSH compute host":"添加 SSH 计算主机",
  "Connect a workstation or Slurm cluster through your existing SSH setup.":"通过现有 SSH 配置连接工作站或 Slurm 集群。",
  "CrossAudit does not install anything on the cluster.":"CrossAudit 不会在集群上安装任何内容。",
  "It uses OpenSSH config, keys, ssh-agent and ProxyJump already configured on this Mac, then runs a read-only capability check.":"它使用此 Mac 已配置的 OpenSSH、密钥、ssh-agent 和 ProxyJump，然后执行只读能力检查。",
  "Name the SSH target and choose a shared work directory for durable remote jobs.":"指定 SSH 目标，并为可持续运行的远程任务选择共享工作目录。",
  "Alias from ~/.ssh/config or a reachable hostname.":"~/.ssh/config 中的别名或可访问的主机名。","For Slurm, login and compute nodes must both see this path.":"使用 Slurm 时，登录节点和计算节点必须都能访问此路径。",
  "Parallel jobs":"并行任务数","Project limit":"项目上限","Cluster notes":"集群说明","optional":"可选","Approved partitions, module loads, environment activation, or account policy.":"获准分区、模块加载、环境激活或账户政策。",
  "Generator access":"生成者权限","Manual job submission is always available. Automatic access is optional and constrained by hard ceilings.":"始终可以手动提交任务；自动权限为可选项，并受硬性上限约束。",
  "The Generator can submit calculation scripts without per-job confirmation. Use a dedicated least-privilege SSH account.":"生成者可无需逐个确认即提交计算脚本。请使用专用的最小权限 SSH 账户。",
  "hard maximums per task":"每个任务的硬性上限","Scheduler restrictions (optional)":"调度器限制（可选）",
  "Host identity":"主机身份","Known host keys are required. A changed key always stops the connection.":"必须使用已知主机密钥；密钥一旦变化，连接必定停止。",
  "Only select this after verifying the hostname with your cluster administrator. Existing or changed keys are never replaced.":"仅在与集群管理员核实主机名后选择。已有或发生变化的密钥绝不会被替换。",
  "Next: read-only connection and capability check.":"下一步：执行只读连接和能力检查。",
  "CrossAudit uses your existing OpenSSH config, keys, ssh-agent and ProxyJump. Nothing is installed remotely.":"CrossAudit 使用你现有的 OpenSSH 配置、密钥、ssh-agent 和 ProxyJump，不会在远端安装任何内容。",
  "SSH alias":"SSH 别名","A Host alias from ~/.ssh/config, or a directly reachable hostname.":"~/.ssh/config 中的 Host 别名，或可直接访问的主机名。",
  "Shared scratch directory":"共享临时目录","For Slurm this must be visible from login and compute nodes.":"使用 Slurm 时，该目录必须同时对登录节点和计算节点可见。",
  "Concurrent job limit":"并发任务上限","Host instructions":"主机说明",
  "Account code, approved partitions, module loads, environment activation, and local cluster policy.":"账户代码、获准分区、模块加载、环境激活和本地集群政策。",
  "Allow Generator to use this host automatically":"允许生成者自动使用此主机","The Generator may author and submit scripts without per-job confirmation, but only inside the resource and file policy below. Use a dedicated least-privilege SSH account.":"生成者可无需逐个确认即编写并提交脚本，但必须遵守下方资源和文件政策。请使用专用的最小权限 SSH 账户。",
  "Generator compute policy":"生成者计算政策","These are hard ceilings. SSH identity, scheduler policy and filesystem permissions remain the final boundary.":"以下是不可突破的上限；SSH 身份、调度器政策和文件系统权限仍是最终边界。",
  "Jobs per task":"每个任务的作业数","Maximum nodes":"最大节点数","Maximum CPUs":"最大 CPU 数","Maximum GPUs":"最大 GPU 数","Maximum memory":"最大内存","Maximum wall time":"最长运行时间",
  "Fixed partition":"固定分区","Fixed account":"固定账户","Fixed QoS":"固定 QoS",
  "Trust a new host key once":"仅一次信任新主机密钥","Use only after verifying the hostname with your cluster administrator. Existing or changed keys are never replaced.":"仅在与集群管理员核实主机名后使用。已有或发生变化的密钥绝不会被替换。",
  "Registration runs a read-only probe for CPU, memory, GPU, Slurm, modules, conda and Apptainer.":"注册过程会对 CPU、内存、GPU、Slurm、模块、conda 和 Apptainer 进行只读探测。","Probe & add":"探测并添加",
  "Submit remote job":"提交远程任务","Review the exact script and requested resources. The job runs as your SSH user outside the local sandbox.":"检查准确脚本和资源请求。任务会以你的 SSH 用户身份在本地沙箱之外运行。",
  "Compute host":"计算主机","Job name":"任务名称","Partition":"分区","QoS":"服务质量","Account":"账户","Nodes":"节点","CPUs per task":"每任务 CPU 数","Memory":"内存","GPUs":"GPU 数","Wall time":"运行时限",
  "Input files":"输入文件","Optional. Files are streamed to inputs/ on the remote host with no CrossAudit size or count quota.":"可选。文件会流式传输到远端主机的 inputs/，CrossAudit 不限制数量或大小。",
  "Job script":"任务脚本","I approve this remote execution":"我批准此次远程执行",
  "The script can access anything my account can read or write on this host. Closing CrossAudit will not stop it.":"脚本可访问我的账户在该主机上有权读写的所有内容。关闭 CrossAudit 不会停止它。","Submit job":"提交任务",
  "Tasks":"任务","New chat":"新对话","＋ New chat":"＋ 新对话","Workspace views":"工作区视图","Chat":"对话","Files":"文件","More":"更多",
  "Audit history":"审计记录","Usage":"用量","Tools & Skills":"工具与技能","Tools":"工具",
  "Back to projects":"返回项目列表","Pin project":"置顶项目","Settings":"设置","Switch theme":"切换主题","Toggle audit context":"切换审计上下文","Open navigation":"打开导航","Close open panel":"关闭面板",
  "You":"你","Auditor":"审计者","New task":"新任务",
  "Message recipient":"消息接收方","To":"发送给","Auto":"自动","@ Generator":"@ 生成者","@ Auditor":"@ 审计者","Add files":"添加文件","＋ Add files":"＋ 添加文件",
  "Message the group, or @ someone…":"给群组发送消息，或 @ 某一方…","Run task":"运行任务","Generator → Auditor":"生成者 → 审计者","Auto-planning":"自动规划","Generator infers focus, format, tone, and structure unless you specify them.":"除非你明确指定，否则生成者会自动判断重点、格式、语气和结构。","Enter to send · Shift+Enter for new line":"Enter 发送 · Shift+Enter 换行",
  "What should CrossAudit work on?":"希望 CrossAudit 完成什么？","Describe what you need or add files. CrossAudit will do the work and independently check the result before showing it here.":"描述你的需求或添加文件。CrossAudit 会完成工作，并在结果显示到这里之前进行独立检查。",
  "Audit context":"审计上下文","Close audit context":"关闭审计上下文","Loop parameters":"循环参数","Maximum rounds":"最大轮数","Current round":"当前轮次","Constitution":"审计章程","Admission tier":"准入级别","Automatic checks":"自动检查","Ledger":"账本",
  "Drop files to add them":"拖放文件以添加","No CrossAudit file-count or file-size quota. Available storage, filesystem limits and provider context still apply.":"CrossAudit 不限制文件数量或大小，但仍受可用存储、文件系统和供应商上下文限制。",
  "Rendered locally and audited from the final binary":"在本地渲染，并从最终二进制文件回读审计","File preview":"文件预览","Preparing preview…":"正在准备预览…","Loading audited deliverable…":"正在加载已审计的交付文件…","Download":"下载","Close preview":"关闭预览","The complete file remains available to download.":"完整文件始终可供下载。","Preview unavailable for this file type. Download the complete file to open it in a compatible app.":"此文件类型无法安全预览。请下载完整文件并使用兼容应用打开。","The reading preview is shortened for responsiveness; the download is complete.":"为保证界面流畅，阅读预览已截短；下载文件是完整的。","Preview is reconstructed from the final audited DOCX binary.":"预览内容从最终通过审计的 DOCX 二进制文件中重建。","HTML preview is isolated from the app and cannot access the network.":"HTML 预览与应用隔离，且无法访问网络。",
  "Search preview":"搜索预览","Search in preview":"在预览中搜索","Previous match":"上一个匹配","Next match":"下一个匹配",
  "Zoom in":"放大","Zoom out":"缩小","Reset view":"重置视图","Reset":"重置","Outline":"大纲","Document outline":"文档大纲",
  "Raw":"源码","Wrap":"自动换行","Copy":"复制","Copied":"已复制","Type":"类型","Size":"大小","Byte sample":"字节样本",
  "Wrap is off for very long files":"超长文件已关闭自动换行",
  "Some rows or columns are hidden for responsiveness; the download is complete.":"为保证界面流畅，部分行或列已隐藏；下载文件是完整的。",
  "ready":"就绪","connecting":"正在连接","Connected":"已连接","Not connected":"未连接","Checking…":"正在检查…","Loading projects…":"正在加载项目…","Something went wrong":"发生了错误","Open help ↗":"打开帮助 ↗",
  "Close":"关闭","Close settings":"关闭设置","No matching projects.":"没有匹配的项目。","Switch to dark theme":"切换到深色主题","Switch to light theme":"切换到浅色主题",
  "Delete project":"删除项目","Review the local and GitHub impact before anything is changed.":"更改任何内容前，请检查本地与 GitHub 影响。",
  "Checking project state…":"正在检查项目状态…","The local folder will move to CrossAudit Trash and can be recovered. GitHub repositories remain untouched unless you explicitly select permanent deletion below.":"本地文件夹会移到 CrossAudit 废纸篓并可恢复。除非你在下方明确选择永久删除，否则 GitHub 仓库保持不变。",
  "Type the project name to confirm":"输入项目名称以确认","Permanently delete working repository":"永久删除工作仓库","Permanently delete audit repository":"永久删除审计仓库",
  "No working repository detected.":"未检测到工作仓库。","No audit repository detected.":"未检测到审计仓库。","Type DELETE GITHUB":"输入 DELETE GITHUB","Running tasks and remote compute block deletion.":"运行中的任务和远程计算会阻止删除。",
  "Authorize GitHub deletion":"授权 GitHub 删除仓库","GitHub requires the delete_repo permission before it can delete a repository.":"GitHub 需要 delete_repo 权限才能删除仓库。","GitHub deletion authorized. Submit again.":"GitHub 删除权限已授权，请再次提交。","GitHub deletion authorized. Submit again to delete the selected repositories.":"GitHub 删除权限已授权，请再次提交以删除所选仓库。",
  "Move project to Trash":"将项目移到废纸篓","Delete chat?":"删除对话？","This chat will disappear from the project sidebar.":"此对话将从项目侧栏消失。",
  "Audit reports, receipts, commits and delivered files are preserved in the project ledger. Deleting a chat never rewrites evidence that may already have admitted a result.":"审计报告、收据、提交和交付文件会保留在项目账本中。删除对话绝不会重写可能已经准入结果的证据。",
  "This only removes the individual chat from navigation.":"此操作只会从导航中移除该独立对话。","Delete chat":"删除对话","Delete chat from project":"从项目中删除对话","Delete project from CrossAudit":"从 CrossAudit 删除项目",
  "Rename chat":"重命名对话","Duplicate chat":"复制对话","Archive chat":"归档对话","Unarchive chat":"取消归档对话","Archived":"已归档",
  "More chat actions":"更多对话操作","Chat actions":"对话操作","Pin chat":"置顶对话","Unpin chat":"取消置顶对话",
  "Give this chat a title that is independent of its first message.":"为该对话设置一个独立于首条消息的标题。","Chat title":"对话标题","Quarterly analysis":"季度分析",
  "The title is navigation only; audit evidence is unchanged.":"标题仅用于导航；审计证据保持不变。","Save name":"保存名称",
  "Return to the main Projects window to delete this open project":"请返回主项目窗口后删除当前打开的项目","Move to Trash & delete selected GitHub repositories":"移到废纸篓并删除所选 GitHub 仓库","Deleting…":"正在删除…","Project moved to Trash":"项目已移到废纸篓",
  "ChatGPT subscription":"ChatGPT 订阅","Default":"默认","Enter a custom model ID…":"输入自定义模型 ID…",
  "highest capability":"最高能力","balanced · recommended":"均衡 · 推荐","fastest, lowest cost":"最快、成本最低",
  "API access.":"API 访问。","Use an official developer API key.":"请使用官方开发者 API key。",
  "This provider has no supported third-party subscription sign-in for model inference. Use an official developer API key.":"该供应商没有支持第三方模型推理的订阅登录流程，请使用官方开发者 API key。",
  "Anthropic does not permit Claude consumer subscriptions to be bound to third-party apps. Use an Anthropic API key or a separately implemented enterprise cloud route.":"Anthropic 不允许第三方应用绑定 Claude 消费者订阅。请使用 Anthropic API key 或单独实现的企业云连接。",
  "A Gemini consumer subscription is not an API credential. Google AI Studio API/auth keys are supported; Vertex AI IAM is a separate cloud connection.":"Gemini 消费者订阅不是 API 凭据。支持 Google AI Studio API/auth key；Vertex AI IAM 属于独立云连接。",
  "Qwen Code offers its own official Coding Plan login, but CrossAudit does not reuse CLI session files as general inference credentials. Use a Model Studio API key here.":"Qwen Code 提供官方 Coding Plan 登录，但 CrossAudit 不会把 CLI 会话文件复用为通用推理凭据。请在此使用 Model Studio API key。",
  "xAI's inference API supports API credentials (and documented OAuth tokens for approved integrations), but an X consumer subscription is not automatically an inference entitlement. API key is enabled here.":"xAI 推理 API 支持 API 凭据及获准集成的 OAuth token，但 X 消费者订阅不会自动获得推理权限。请在此使用 API key。",
  "New API key ·":"新 API key ·","Get key ↗":"获取 key ↗","API docs ↗":"API 文档 ↗","Leave blank to keep the saved key":"留空以保留已保存的 key",
  "Remove":"移除","Delete saved key":"删除已保存的 key","Official Codex sign-in.":"官方 Codex 登录。","Connect":"连接","Try again":"重试","Waiting…":"等待中…","Starting…":"正在启动…",
  "Environment has not been checked":"尚未检查环境","Checking this Mac…":"正在检查此 Mac…","Ready":"就绪","Missing":"缺失","Outdated":"版本过旧",
  "Embedded Python":"内置 Python","Remote compute client":"远程计算客户端","ChatGPT connection runtime":"ChatGPT 连接运行时",
  "Secure network certificates":"安全网络证书","Project Git ledger":"项目 Git 账本","Git author identity":"Git 作者身份","The `crossaudit` command":"`crossaudit` 命令",
  "Add a name and email before creating commits.":"创建提交前请添加姓名和邮箱。","Git author name":"Git 作者姓名","Git author email":"Git 作者邮箱",
  "Save for this project":"保存到此项目","Project configuration":"项目配置","Audit rules":"审计规则","CrossAudit application":"CrossAudit 应用",
  "source":"源码构建","Unknown":"未知","Warning":"警告","Waiting":"等待中",
  "Install Git tools":"安装 Git 工具","Update Git tools":"更新 Git 工具","Open SSH setup guide":"打开 SSH 设置指南",
  "Reinstall CrossAudit":"重新安装 CrossAudit","Download latest":"下载最新版","Download update":"下载更新","Open Software Update":"打开软件更新",
  "Choose another folder":"选择其他文件夹","Initialize safely":"安全初始化","Run again":"重新运行",
  "Automatic · provider default":"自动 · 供应商默认","Not applicable":"不适用","Human-written changes":"人工编写的修改","Create reusable project guidance":"创建可复用的项目指导",
  "Editing committed guidance":"正在编辑已提交的指导","Saved and committed":"已保存并提交","Already up to date":"已是最新状态",
  "Allow another round":"再给一轮","Stop task":"停止任务","Review decision":"审查决定","Admit result":"准入结果","Nothing needs attention.":"没有需要处理的事项。"
  ,"Another audited attempt is unlocked.":"已解锁另一次受审计尝试。","Your guidance is in the composer. Review it, then press Run task.":"你的指导已放入输入框。检查后按“运行任务”。",
  "Task stopped.":"任务已停止。","The current output remains unadmitted and your reason was recorded.":"当前输出仍未准入，你的原因已记录。",
  "Add concrete guidance or a reason so the decision is auditable.":"请添加具体指导或原因，以便对该决定进行审计。",
  "The automatic audit loop stopped.":"自动审计循环已停止。","Review why the loop stopped, then decide whether to revise or stop.":"检查循环停止原因，再决定修订或停止。",
  "The audit controller paused this task.":"审计控制器已暂停此任务。","No explanation was recorded.":"未记录说明。","A human decision is required.":"需要人工决定。",
  "Tell the generator how to correct the remaining blockers, or stop the task without admitting its output.":"请告诉生成者如何修复剩余阻断问题，或停止任务且不准入其输出。",
  "Automatic repair refused":"自动修复被拒绝","The revision reached outside the audited files":"修订改动了已审计文件之外的内容",
  "The generator\u2019s revision was refused: it changed files outside the audited directories, or wrote a binary file that cannot be reviewed line by line. The refused attempt was rolled back, so the audited files are unchanged and nothing was admitted.":"生成者的修订被拒绝：它改动了已审计目录之外的文件，或写入了无法逐行审查的二进制文件。被拒绝的尝试已回滚，因此已审计的文件未被改动，也没有任何结果被准入。",
  "Why the last revision was refused":"上一次修订被拒绝的原因",
  "Tell the generator to keep the fix inside the audited files, or stop the task without admitting its output.":"请告诉生成者把修复限制在已审计文件之内，或停止任务且不准入其输出。",
  "Name the file inside the audited directories that should change, then unlock one additional audited round.":"指出已审计目录内应当修改的文件，然后解锁额外一轮受审计执行。",
  "the revision changed nothing that could be reviewed":"该修订没有做出任何可供审查的改动",
  "the revision was refused before the audit":"修订在审计前被拒绝","asking for a repair that stays within the audited files":"正在要求生成者做出不超出已审计文件范围的修复",
  "the revision has edits the auditor should weigh":"本次修订包含需要审计者权衡的改动",
  "The auditor raised a concern":"审计者提出了一项疑虑",
  "The auditor blocked this round on its own reading; no deterministic check reproduces the concern. CrossAudit does not let a model-only claim drive automatic rewrites, so it stopped and left the files unchanged.":"审计者依据自身判读阻断了本轮；没有任何确定性检查能复现这项疑虑。CrossAudit 不允许仅凭模型的说法驱动自动改写，因此已停止并保持文件不变。",
  "the auditor raised a concern that no deterministic check reproduces; it needs your judgment":"审计者提出了一项没有任何确定性检查能复现的疑虑；需要你来判断",
  "Review the auditor's concern and its evidence. If it is a misreading, say so in your reason and continue; if it is right, tell the generator how to address it; or stop without admitting the work.":"请审查审计者的疑虑及其证据。若属误读，请在理由中说明后继续；若疑虑成立，请告诉生成者如何处理；也可停止任务且不准入其输出。",
  "If the concern is right, tell the generator how to address it. If it is a misreading, say so here; your reason is recorded.":"如果疑虑成立，请告诉生成者如何处理；如果属于误读，请在此说明，你的理由会被记录。",
  "Verified by a deterministic check":"已由确定性检查验证","Raised by the auditor, not yet reproduced":"由审计者提出，尚未被复现","Raised by the auditor and verified":"由审计者提出，并已验证",
  "Your task or message":"你的任务或消息","Search projects":"搜索项目",
  "Fix the provider, model, or credential setting before allowing another round, or stop the task.":"再给一轮前，请先修复供应商、模型或凭据设置；否则停止任务。",
  "Review why the loop stopped, then either give concrete guidance for one more round or stop the task.":"检查循环停止原因，然后提供具体指导再进行一轮，或停止任务。",
  "no model audit ran, so the result cannot pass":"没有运行模型审计，因此结果无法通过","the automatic audit loop stopped":"自动审计循环已停止"
  ,"/ project folder":"/ 项目文件夹","local controller":"本地控制器","No chats yet":"尚无对话",
  "Describe a task in plain language. A generator will make the change, deterministic checks will run, and an independent model will audit every round before admission.":"用自然语言描述任务。生成者完成修改，系统运行确定性检查，并由独立模型在准入前审计每一轮。",
  "Working":"处理中","The result will appear here when it is ready.":"结果就绪后会显示在这里。",
  "The delivered files passed the independent review.":"交付文件已通过独立审查。","Needs revision":"需要修订",
  "The result did not pass review yet.":"结果尚未通过审查。","Needs your input":"需要你决定",
  "Ready for your correction":"已准备接收你的修正","Send the approved guidance to start the human-authorized audited attempt.":"发送已确认的指导，以启动由你授权的受审计尝试。",
  "CrossAudit needs a decision before it can continue.":"CrossAudit 需要你作出决定才能继续。","Stopped":"已停止",
  "The task did not complete.":"任务未完成。","View audit details":"查看审计详情",
  "conversational reply · not audited":"对话回复 · 未经审计",
  "Queued.":"已排队。","Will be read at the next generator round":"将在下一轮生成时读取",
  "Queued — read at next round":"已排队 · 下一轮读取",
  "Send guidance to the running task":"向运行中的任务发送补充信息",
  "owner guidance queued":"已排队所有者补充信息",
  "Generator reply format problem":"生成者回复格式异常","Generator request refused":"生成者请求被拒",
  "CrossAudit answered":"CrossAudit 已回应","CrossAudit answered, but made no audited deliverable":"CrossAudit 已回应,但没有产出受审计的交付物","CrossAudit reply":"CrossAudit 的回应","This request could not become an audited deliverable — often because it refers to something that is not in the project. CrossAudit reply is shown below. Refine the task and run again, or stop it.":"这个请求无法变成受审计的交付物——通常是因为它指向了项目里不存在的东西。CrossAudit 的回应见下方。请把任务写得更具体后重跑,或直接停止。",
  "The generator could not produce auditable work":"生成者未能产出可审计的工作",
  "Nothing new to audit":"没有新内容可审计",
  "The generator repeated the existing work":"生成者重复了已有的工作",
  "The generator was asked twice and both replies matched the already-committed work byte for byte, so there was nothing new to audit. The existing files are untouched. Make the task more specific about what should change, or stop the task if the current work already satisfies it.":"生成者被要求了两次，但两次回复都与已提交的工作逐字节相同，因此没有新内容可审计。现有文件未被改动。请把任务写得更具体、说明希望改动什么；如果现有内容已满足要求，可直接停止此任务。",
  "One corrective retry was already made automatically. Technical detail: ":"系统已自动进行过一次纠正性重试。技术细节：",
  "the round changed nothing; asking for a real revision":"本轮没有产生任何改动；正在要求一次真正的修订",
  "The generator was asked twice and still replied outside the required file format, so there was nothing to audit. No result was admitted.":"系统已让生成者重试一次，但两次回复都不符合要求的文件格式，因此没有可审计的内容。未准入任何结果。",
  "What happened":"发生了什么",
  "The reply was corrected once automatically and still failed to parse. Technical detail: ":"系统已自动纠正重试一次，回复仍无法解析。技术细节：",
  "No audit ran because the generator never produced readable work. What usually helps: rewrite the task as one concrete instruction, or switch the generator model in Settings, then run one more round.":"由于生成者始终没有产出可读的工作内容，审计未能进行。通常有效的做法：把任务改写成一条具体的工作指令，或在设置中更换生成者模型，然后再试一轮。",
  "Rewrite the task as one concrete instruction and run one more round, switch the generator model, or stop this task.":"把任务改写成一条具体指令再试一轮，或更换生成者模型，或停止此任务。",
  "correcting a malformed reply":"正在纠正格式错误的回复",
  "Permissions":"权限","What the agent may do in this project":"智能体在此项目中可以做什么",
  "File edits and command runs are off by default. Every grant is recorded in the audit ledger, edits are recoverable, and commands still need your per-call approval.":"文件编辑与命令运行默认关闭。每次授权都会记入审计账本，编辑可恢复，命令仍需你逐次批准。",
  "Allow the agent to edit files in this project":"允许智能体编辑此项目中的文件",
  "The agent may create and modify files in this project's directories. Every change takes a recovery point, is recorded in the audit ledger, and is reviewed by the independent auditor. Off by default.":"智能体可以在此项目目录内创建和修改文件。每次改动都会先建立恢复点、记入审计账本，并由独立审计者审查。默认关闭。",
  "Commands the agent may run":"智能体可运行的命令",
  "Comma-separated executables the agent is allowed to run (tests, build, format). Each run needs your per-call approval and runs as an argv list — never a shell — in this project only. Empty = the agent cannot run any command.":"以逗号分隔的可执行程序清单（测试、构建、格式化）。每次运行都需你逐次批准，并以参数列表方式执行——绝不经过 shell——仅限本项目。留空 = 智能体不能运行任何命令。",
  "e.g. pytest, npm, make":"例如 pytest、npm、make",
  "Goal & plan":"目标与计划","Goal":"目标","Desired outputs":"预期产出","Constraints":"约束",
  "Success criteria":"成功标准","Plan v1 · the audited loop":"计划 v1 · 受审计的循环","Rounds":"轮次",
  "The stated goal and the audited plan for the current task.":"当前任务的既定目标与受审计的执行计划。",
  "No plan yet — the plan appears when a task starts.":"还没有计划——任务开始后计划会显示在这里。",
  "Derived from the supervised loop this run actually executes — generator-authored step plans arrive in a later slice.":"由本次运行真实执行的受监督循环推导——生成者自行编写的分步计划将在后续版本提供。",
  "The structured goal record is not available for this run.":"本次运行没有可用的结构化目标记录。",
  "authorized (recoverable)":"已授权（可恢复）","read-only":"只读","allowlisted":"已列入允许清单",
  "not authorized":"未授权","configured":"已配置","not configured":"未配置",
  "direct reply · no project files shared":"直接回复 · 未共享项目文件",
  "Answered.":"已回答。","Admitted.":"已准入。","Not admitted.":"未获准入。",
  "No work was lost — the report, receipt and ledger are unchanged, and nothing was consumed.":"没有丢失任何工作——报告、收据与账本均未改动，也未消费任何结果。",
  "What would make it admissible":"怎样才能获得准入",
  "connect a real auditor provider and run the task again — a replayed audit can never admit":"连接真实的审计者供应商并重新运行任务——回放的审计永远无法准入",
  "give the two roles distinct first-party vendors so independence is attestable":"为两个角色配置不同的第一方厂商，使独立性可被证明",
  "only a PASS can be admitted":"只有 PASS 结果才能准入",
  "run the task again so a fresh receipt is recorded for this cycle":"重新运行任务，让本周期记录一份新的收据",
  "run a real audited task; its receipt is minted automatically":"运行一次真实的受审计任务，收据会自动生成",
  "run a task and let the audit finish with a PASS first":"先运行一个任务并让审计以 PASS 结束",
  "Delivered files":"交付文件","Only final files that passed independent review.":"仅显示已通过独立审查的最终文件。",
  "No audited deliverables yet.":"尚无经审计的交付物。","Independent verdicts and findings reconstructed from the ledger.":"从账本重建的独立判定与发现。",
  "Audit evidence":"审计证据","No audit evidence yet.":"尚无审计证据。","Token usage":"Token 用量",
  "Project-level model consumption, updated with every completion.":"项目级模型用量，每次完成调用时更新。",
  "Today":"今日","This month":"本月","Model calls":"模型调用","Cached tokens":"缓存 Token","Last 7 days":"最近 7 天","Audits run":"已跑审计",
  "all roles":"全部角色","By role":"按角色","this month":"本月","Tokens":"Token","Cached":"已缓存","Source":"来源",
  "Recent calls":"最近调用","counts only · no prompt content":"仅统计数量 · 不包含提示词内容","No model calls this month.":"本月尚无模型调用。",
  "Usage will appear after the first model completion.":"第一次模型调用完成后会显示用量。","No calls recorded yet.":"尚无调用记录。",
  "Reported":"已报告","Estimated":"估算","Unpriced":"未计价",
  // Billing slice: header pill, threshold banner, cost lines, prices, export.
  "Open usage":"打开用量","Display mode":"显示模式","≈ value":"≈ 价值","Monthly report":"月度报告","Top models":"主要模型",
  "Generator share":"生成者占比","Auditor share":"审计者占比","Passed audits":"通过的审计","Unpriced calls":"未计价调用","Calls":"调用次数",
  "Model prices":"模型价格","＋ Add price":"＋ 添加价格","Input":"输入","Output":"输出","Cache write":"缓存写入","Cache read":"缓存读取","Model ID":"模型 ID",
  "USD per 1M tokens for models the price snapshot does not carry. Used for this project's estimates only.":"价格快照未收录的模型按每 100 万 token 的美元价格计费。仅用于本项目的估算。",
  "No overrides. Models missing from the price snapshot stay unpriced.":"没有覆盖价格。价格快照中缺失的模型保持未计价。",
  "Usage and budgets are tracked per project, from each project's own local ledger. Nothing is sent anywhere.":"用量与预算按项目跟踪，来自每个项目自己的本地账本。不会发送到任何地方。",
  "Export period":"导出范围","Export CSV":"导出 CSV","Export JSON":"导出 JSON","Everything":"全部",
  "Open a project to see usage across projects.":"打开一个项目后即可查看各项目的用量。","This month across projects":"本月全部项目合计",
  "Usage across projects":"各项目用量","Budget":"预算","Within budget":"预算内","Budget warning":"预算预警","Paused at limit":"已达上限暂停","No budget":"未设预算",
  "Resets at midnight":"明天 0:00 重置","Usage warning":"用量预警",
  "SSH workstations and Slurm clusters, detached from this Mac.":"与此 Mac 解耦运行的 SSH 工作站和 Slurm 集群。","SSH workstations and Slurm clusters for manual jobs or Generator calculations.":"用于手动作业或生成者计算的 SSH 工作站和 Slurm 集群。",
  "Remote-owned execution.":"远程主机负责执行。","＋ Add SSH host":"＋ 添加 SSH 主机","Refresh now":"立即刷新",
  "CrossAudit stores only host aliases and job identifiers. Keys remain with OpenSSH; remote work continues if the app closes, the Mac sleeps, or the network drops. A host marked as a Generator tool can receive model-authored jobs automatically within its saved policy.":"CrossAudit 只保存主机别名和任务标识；密钥始终由 OpenSSH 管理。即使应用关闭、Mac 休眠或网络中断，远程任务也会继续运行。标记为生成者工具的主机可在已保存政策范围内自动接收模型编写的任务。",
  "Generator tool":"生成者工具","Generator calculations":"生成者计算",
  "Compute hosts":"计算主机","Remote jobs":"远程任务","No SSH compute hosts yet.":"尚未添加 SSH 计算主机。",
  "No jobs submitted from this project.":"此项目尚未提交任务。","Probe":"探测","Run job":"运行任务","Live logs":"实时日志","Outputs":"输出",
  "Cancel job":"取消任务","Remote outputs":"远程输出","Updating…":"正在更新…","No remote output files found.":"未找到远程输出文件。",
  "Add MCP server":"添加 MCP 服务器","Configure MCP server":"配置 MCP 服务器",
  "Server name":"服务器名称","Transport":"传输方式","Local stdio":"本地 stdio","Streamable HTTP":"Streamable HTTP","Executable":"可执行文件","Arguments":"参数",
  "One argument per line. CrossAudit never invokes a shell.":"每行一个参数。CrossAudit 绝不会调用 shell。","I approve this exact local command":"我批准此准确的本地命令","A local MCP server runs with this app's user permissions and may access files or the network. Verify its publisher and arguments.":"本地 MCP 服务器使用本应用的用户权限运行，可能访问文件或网络。请核实发布者和参数。",
  "MCP endpoint":"MCP 端点","Secure MCP endpoint URL":"安全的 MCP 端点 URL","Bearer token (optional)":"Bearer token（可选）","Leave blank to keep saved token":"留空以保留已保存的 token","Allow a verified private-network server":"允许已核实的专用网络服务器","Use only for an enterprise hostname you control. Public remote servers must use HTTPS.":"仅用于你所控制的企业主机名。公共远程服务器必须使用 HTTPS。",
  "Request timeout":"请求超时","Calls per task":"每个任务的调用次数","Tools this project may use":"本项目可以使用的工具","Allow Generator to call the approved tools automatically":"允许生成者自动调用已批准的工具","Calls appear live in the task loop. Tool output is treated as untrusted external data and never becomes an audit rule.":"调用会实时显示在任务循环中。工具输出被视为不可信外部数据，绝不会成为审计规则。",
  "Advertised tools":"公布的工具","Bearer tokens are write-only Keychain items. Local commands are stored without secrets.":"Bearer token 以只写方式存入钥匙串；本地命令不含秘密信息。",
  "Project-scoped MCP capabilities and committed Generator guidance.":"项目级 MCP 能力与已提交的生成者指导。","Explicit capability boundaries.":"明确的能力边界。","MCP servers and Skills are invisible until you configure them. Approved MCP output remains untrusted data; Skills guide only the Generator and never change the Constitution.":"MCP 服务器和技能在你配置前不可见。已批准的 MCP 输出仍是不可信数据；技能只指导生成者，绝不会修改审计章程。",
  "＋ Add MCP server":"＋ 添加 MCP 服务器","Manage Skills":"管理技能","MCP servers":"MCP 服务器","Recent tool calls":"最近工具调用","Skills":"技能","No MCP servers connected to this project.":"此项目尚未连接 MCP 服务器。","No MCP tools called in this project.":"此项目尚未调用 MCP 工具。","No project Skills yet.":"此项目尚无技能。",
  // Add-MCP-server dialog (two-step connect -> approve).
  "Connect the server first, then choose which of its tools this project may use.":"先连接服务器，再选择本项目可以使用它的哪些工具。",
  "Reach the server":"连接到服务器","Approve tools":"批准工具","Choose what it may do":"选择它可以做什么",
  "Call limits":"调用限制","Seconds to wait for one response.":"等待单次响应的秒数。",
  "How many times a single task may call this server.":"单个任务可以调用此服务器的次数。",
  "Connecting only reads the server's tool list. Nothing can be called until you approve it in the next step.":"连接只会读取服务器的工具列表。在你于下一步批准之前，任何工具都不会被调用。",
  "This exact command is already approved":"此命令已获批准",
  "You approved this executable and these arguments when you connected the server. Editing either one asks you to approve the new command.":"你在连接此服务器时已批准该可执行文件与这些参数。修改其中任何一项都会要求你重新批准新的命令。",
  "Save":"保存","Saving…":"正在保存…","Select all except destructive":"全选（破坏性除外）","Clear all":"全部清除",
  "Read-only":"只读","May change data":"可能修改数据","Not labelled by the server":"服务器未标注","No description provided.":"未提供说明。",
  "This server advertised no tools, so there is nothing to approve.":"此服务器未公布任何工具，因此没有可批准的内容。",
  "Tool names, descriptions and risk labels are reported by the server itself and are not verified by CrossAudit. Approve only what you recognise.":"工具名称、说明与风险标签均由服务器自行提供，CrossAudit 不对其进行核实。请只批准你认得的内容。",
  "Approve at least one tool before the Generator can call this server.":"先批准至少一个工具，生成者才能调用此服务器。",
  "Leave this off to keep the server manual-only. You can turn it on later.":"保持关闭即为仅手动使用。你可以稍后再开启。",
  "Re-connecting cleared this server's approvals. Nothing can be called until you save.":"重新连接已清除此服务器的批准。在你保存之前，任何工具都不会被调用。",
  "Only the tools you tick are approved. Tools the server adds later stay blocked until you review them.":"只有你勾选的工具会被批准。服务器之后新增的工具在你复核前始终处于阻止状态。",
  // A2: page-side labels for a runtime context-condensation notice. The
  // notice TEXT itself arrives pre-localised on the wire (text_i18n /
  // detail_i18n / summary_i18n), so it is deliberately NOT duplicated here —
  // the old ZH_PATTERNS/dictionary handoff for these strings is superseded.
  "Context reduced":"上下文已精简","round":"轮次",
  "A label for this project. ASCII letters, digits, spaces and . _ - only, and it must start with a letter or digit.":"本项目中的标识名称。仅限 ASCII 字母、数字、空格和 . _ -，且必须以字母或数字开头。",
  "Connect runs this command on your Mac, so the approval above is required before it can run.":"连接会在你的 Mac 上运行此命令，因此必须先勾选上方的批准。",
  "Server names use ASCII letters, digits, spaces and . _ - only, and must start with a letter or digit. Rename this server to continue.":"服务器名称仅支持 ASCII 字母、数字、空格和 . _ -，且必须以字母或数字开头。请修改名称后继续。",
  "This project already has an MCP server with that name. Choose a different name, or configure the existing one.":"此项目已存在同名的 MCP 服务器。请换一个名称，或直接配置已有的服务器。",
  "This project already has an MCP server running that exact command. Configure the existing one instead.":"此项目已存在运行该命令的 MCP 服务器。请直接配置已有的服务器。",
  "Not saved yet — Cancel removes this connection.":"尚未保存 —— 取消将移除此连接。",
  // Denials /api/mcp can return into this dialog. The backend wording is the
  // contract; these are its Chinese parity, so a refusal is never English-only.
  "MCP server settings must be an object":"MCP 服务器设置必须是一个对象",
  "MCP server name uses unsupported characters":"MCP 服务器名称包含不支持的字符",
  "MCP transport must be stdio or Streamable HTTP":"MCP 传输方式必须是 stdio 或 Streamable HTTP",
  "invalid MCP server identifier":"无效的 MCP 服务器标识符",
  "that MCP server is not registered in this project":"该 MCP 服务器未注册在此项目中",
  "MCP timeout must be a whole number":"MCP 超时必须是整数",
  "MCP timeout must be between 1 and 300 seconds":"MCP 超时必须在 1 到 300 秒之间",
  "MCP calls per task must be a whole number":"MCP 每任务调用次数必须是整数",
  "approve the exact local MCP command before it runs":"请先批准将要运行的这条本地 MCP 命令",
  "MCP executable is required":"必须填写 MCP 可执行文件",
  "MCP arguments must be a list":"MCP 参数必须是一个列表",
  "an MCP argument is invalid or too long":"某个 MCP 参数无效或过长",
  "MCP arguments are unexpectedly large":"MCP 参数过大",
  "allowed MCP tools must be a list":"允许的 MCP 工具必须是一个列表",
  "an allowed MCP tool is not advertised by this server":"某个已允许的 MCP 工具并未由此服务器公布",
  "select at least one MCP tool before enabling Generator access":"启用生成者访问前，请至少选择一个 MCP 工具",
  "connect the MCP server without Generator access first, review the advertised tool list, then configure and enable it":"请先在不开放生成者访问的情况下连接 MCP 服务器，复核其公布的工具列表，然后再配置并启用它",
  "MCP URL must be a plain HTTP(S) endpoint without credentials, query or fragment":"MCP URL 必须是不含凭据、查询串或片段的纯 HTTP(S) 端点",
  "remote MCP servers require HTTPS; HTTP is allowed only on loopback":"远程 MCP 服务器必须使用 HTTPS；仅回环地址允许使用 HTTP",
  "the MCP hostname could not be resolved":"无法解析该 MCP 主机名",
  "the MCP hostname resolves to a private or reserved address; enable private-network access only for a verified enterprise server":"该 MCP 主机名解析到专用或保留地址；请仅对已核实的企业服务器启用专用网络访问",
  "MCP endpoint redirects are refused; register the final HTTPS URL":"MCP 端点重定向会被拒绝；请直接登记最终的 HTTPS 地址",
  "MCP server requires authorization. Add a valid bearer token; interactive MCP OAuth is not configured for this server.":"MCP 服务器需要授权。请添加有效的 bearer token；此服务器未配置交互式 MCP OAuth。",
  "MCP request timed out":"MCP 请求超时",
  "MCP server wrote non-JSON data to stdout":"MCP 服务器向标准输出写入了非 JSON 数据",
  "MCP server returned invalid JSON":"MCP 服务器返回了无效的 JSON",
  "MCP server returned a non-object JSON-RPC message":"MCP 服务器返回了非对象的 JSON-RPC 消息",
  "MCP server response exceeded the safety limit":"MCP 服务器响应超出安全上限",
  "MCP event stream ended without the requested response":"MCP 事件流在返回所请求的响应前已结束",
  "MCP tools/list returned an invalid tool list":"MCP tools/list 返回了无效的工具列表",
  "MCP server advertised an invalid tool":"MCP 服务器公布了无效的工具",
  "MCP server advertised more than 1000 tools":"MCP 服务器公布了超过 1000 个工具",
  "MCP server returned an invalid pagination cursor":"MCP 服务器返回了无效的分页游标",
  "MCP bearer token is empty or unexpectedly large":"MCP bearer token 为空或过大",
  "MCP bearer token contains control characters":"MCP bearer token 含有控制字符",
  "macOS Keychain is unavailable for the MCP credential":"无法使用 macOS 钥匙串保存 MCP 凭据",
  "Generator MCP request must be an object":"生成者的 MCP 请求必须是一个对象",
  "this MCP server is not enabled for the Generator":"此 MCP 服务器未对生成者启用",
  "this MCP tool is not approved for automatic use":"此 MCP 工具未被批准自动使用",
  "the Generator reached this MCP server's calls-per-task limit":"生成者已达到此 MCP 服务器的每任务调用上限",
  "MCP tool arguments must be an object":"MCP 工具参数必须是一个对象",
  "Generator enabled":"已为生成者启用","Manual only":"仅手动","Configure":"配置","Refresh tools":"刷新工具","No tools advertised.":"未公布工具。","Applies to every task":"适用于每个任务","MCP tool":"MCP 工具","calling MCP tool":"正在调用 MCP 工具","policy":"政策",
  "Last 64 KB · stdout + stderr":"最近 64 KB · 标准输出 + 标准错误","Remote process finished":"远程进程已完成","Submitted to Slurm":"已提交至 Slurm","Detached on host":"已在远程主机后台启动","Preparing remote job":"正在准备远程任务",
  "Passed":"已通过","Blocked":"已阻止","Waiting on you":"等待你决定","Admitted":"已准入","Complete":"已完成","Active":"正在进行","Pending":"等待中"
  ,"live":"实时","complete":"完成","completed":"已完成","failed":"失败","cancelled":"已取消","timeout":"超时","out_of_memory":"内存不足","queued":"排队中","running":"运行中","submitting":"提交中","unknown":"未知","declared":"已声明","internal":"内部","parseable":"可解析",
  "Use light theme":"使用亮色主题","Use dark theme":"使用暗色主题",
  "Switch models, reasoning effort and audit loop settings":"切换模型、推理强度和审计循环设置",
  "Understanding":"正在理解","Checking":"正在检查","Revising":"正在修订","Completed":"已完成",
  "Needs your decision":"需要你决定","Stopping":"正在停止",
  "Audit":"审计","Compute":"计算","Context tabs":"上下文标签","Context panel":"上下文面板",
  "Close context panel":"关闭上下文面板","Change models":"更换模型","Search chats":"搜索对话",
  "Command palette":"命令面板","Command palette · ⌘K":"命令面板 · ⌘K","Type a command or search…":"输入命令或搜索…","Actions":"操作",
  "Chats":"对话","No matching results.":"没有匹配的结果。","All projects":"全部项目",
  "Open settings":"打开设置","Run Doctor":"运行环境诊断","Switch language":"切换语言",
  "Stop current task":"停止当前任务","Review":"查看","Attempted":"已尝试",
  "Blocked on":"阻塞在","Recommendation":"建议","Suggested":"建议选项",
  "The task this conversation asked for.":"此对话所要求完成的任务。",
  "Independent review":"独立审查","Independent auditor approved the result":"独立审计者已批准该结果",
  "No blocking findings":"没有阻断性问题","Recorded in the audit ledger":"已记录到审计账本",
  // SPEC-9 slice 1 — spoken, not seen. A screen reader hears these; nothing renders them.
  "A task is waiting for your decision.":"有一个任务正在等待你的决定。",
  "CrossAudit replied.":"CrossAudit 已回复。",
  // SPEC-2 verification states. The section line is the only thing a person
  // who does not know what a deterministic check is has to read.
  "Not run yet — these run automatically on your first task.":"尚未运行——它们会在你的第一个任务中自动运行。",
  "These run with every task; no result has been reported for the latest round.":"它们会随每个任务运行；最近一轮尚未报告结果。",
  "No checks configured":"未配置任何检查",
  "Findings":"发现的问题","Record":"记录","Commit":"提交","Cycle":"审计循环",
  "Open Files panel":"打开文件面板","now":"刚刚","Human decision":"人工决定",
  "First launch setup":"首次启动设置","Setup steps":"设置步骤","Welcome":"欢迎","Readiness":"就绪检查","Providers":"供应商","Roles":"角色",
  "Skip for now":"暂时跳过","Build with":"用","one agent.":"一个智能体来构建。","Verify with":"用","another.":"另一个来验证。",
  "One model does the work. A different model checks it, independently. Everything stays on your Mac — nothing is sent anywhere you didn't choose.":"一个模型完成工作，另一个模型独立检查它。一切都保留在你的 Mac 上——绝不会发送到任何你未选择的地方。",
  "Create your first project":"创建你的第一个项目","Open an existing project":"打开已有项目","Import a folder":"导入文件夹",
  "Explore a local demo":"体验本地演示","— no credentials needed":"— 无需凭据",
  "Cancel running task":"取消正在运行的任务","Generated files":"生成的文件",
  "Project history":"项目历史","Recovered chat":"已恢复的对话",
  "Files produced":"生成的文件","Applies to":"适用于","Dismiss notice":"关闭提示",
  "Notice dismissed.":"提示已关闭。","Retry task":"重试任务",
  "Stop requested.":"已请求停止。","Task interrupted safely":"任务已安全中断",
  "Task restarted.":"任务已重新启动。",
  "Deleted chat":"已删除的对话","rounds the ledger holds":"账本中保存的轮次",
  "cleared both layers":"两层检查均已通过","a concern was raised":"提出了一处疑虑",
  "escalated; the loop cannot settle these":"已升级；循环无法自行了结这些",
  "receipts consumed, once each":"已消费的回执，每份一次",
  "Creating the local project":"正在创建本地项目",
  "No API key is stored for this provider yet.":"尚未为此提供方保存 API 密钥。",
  "The key authenticated but exposes no compatible models.":"密钥通过了验证，但没有可用的兼容模型。",
  "A human generator has no model settings.":"人工生成者没有模型设置。",
  "Sample role — no model runs in the local demo.":"示例角色——本地演示不会运行任何模型。",
  "current project model":"当前项目模型",
  "GitHub authorization timed out":"GitHub 授权超时",
  "GitHub authorization was not completed":"GitHub 授权未完成",
  "Retry after reviewing the provider connection.":"请检查提供方连接后重试。",
  "no provider route is available":"没有可用的提供方路由",
  "the run stopped for a person before its decision record was written":"该运行在写入决定记录之前就为等待人工而停止",
  "Illustrative CrossAudit demo project. No models were run, no provider was contacted, and no audit occurred.":"用于演示的 CrossAudit 示例项目。没有运行任何模型，没有联系任何提供方，也没有进行任何审计。",
  "Toggle context panel":"切换上下文面板","Tools & Skills":"工具与技能",
  "System readiness":"系统就绪检查","Re-check the system":"重新检查系统","Re-check":"重新检查",
  "Checking your Mac…":"正在检查你的 Mac…",
  "Everything required is ready":"所有必需项都已就绪","Environment ready":"环境已就绪","Environment status unavailable":"无法获取环境状态",
  "Environment status is unavailable — the check could not run. You can continue and re-check later.":"无法获取环境状态——检查未能运行。你可以继续，稍后再重新检查。",
  "Doctor unavailable":"诊断不可用","No checks to show yet. Re-check to inspect this Mac.":"暂无可显示的检查项。重新检查以检测此 Mac。",
  "Needs attention":"需要处理","Optional enhancement":"可选增强","Optional":"可选",
  "Fix automatically":"自动修复","Learn how →":"了解方法 →","Technical detail":"技术细节","Working…":"处理中…",
  "Preflight — probing environment":"预检——正在探测环境","You can re-run these checks any time from Settings.":"你可以随时在设置中重新运行这些检查。",
  "SAMPLE":"示例","Sample demonstration — not a real audit.":"示例演示——并非真实审计。",
  "No models were run and no API keys were used; this content is illustrative.":"未运行任何模型，也未使用任何 API 密钥；此内容仅供演示说明。",
  "Provider setup":"供应商设置","Connect the providers you'll build and verify with.":"连接你将用来构建和验证的供应商。",
  "You need at least two different providers — one to do the work, a different one to check it.":"你至少需要两家不同的供应商——一家负责完成工作，另一家负责检查。",
  "Keys are stored in your macOS Keychain and never shown again.":"密钥仅存入你的 macOS 钥匙串，之后不再显示。","Loading providers…":"正在加载供应商…",
  "New API key":"新的 API key","Paste":"粘贴","Clear":"清除","Validate":"验证","Replace":"替换",
  "Reveal the key you just typed":"显示你刚输入的密钥","Stored in your macOS Keychain.":"已存入你的 macOS 钥匙串。",
  "or":"或","Sign in with ChatGPT (official)":"使用 ChatGPT 登录（官方）",
  "Invalid":"无效","No access":"无访问权限","Unavailable":"不可用","Configured":"已配置",
  "Connection verified.":"连接已验证。","This key was rejected. Check it and try again.":"该密钥被拒绝。请检查后重试。",
  "The key works, but no models are available to it.":"该密钥有效，但没有可用的模型。",
  "Could not reach the provider. Check your connection and try again.":"无法连接到供应商。请检查网络后重试。",
  "Two different providers is enough to begin — one to build, one to check.":"两家不同的供应商即可开始——一家构建，一家检查。",
  "Generator / Auditor":"生成者 / 审计者","One builds.":"一个负责构建。","Another checks.":"另一个负责检查。",
  "We picked a recommended pair on two different providers. You can change either one.":"我们在两家不同的供应商上挑选了推荐搭配。你可以随时更换其中任意一个。",
  "Does the work.":"负责完成工作。","Independently checks the work — must run on a different provider.":"独立检查工作——必须运行在不同的供应商上。",
  "Generator provider":"生成者供应商","Generator model":"生成者模型","Auditor provider":"审计者供应商","Auditor model":"审计者模型",
  "context":"上下文","Vision":"视觉","Structured output":"结构化输出","Reasoning":"推理","/ Mtok":"/ 百万 Token","Price not published":"暂无公开价格","Keychain key":"钥匙串密钥",
  "Independent — your auditor runs on a different provider than your generator.":"相互独立——你的审计者运行在与生成者不同的供应商上。",
  "Connect at least two different providers on the previous step to form an independent Generator / Auditor pair.":"请在上一步至少连接两家不同的供应商，以组成独立的生成者 / 审计者搭配。",
  "Generator and auditor must run on different providers. Independent review is the core of the protocol and cannot be turned off.":"生成者和审计者必须运行在不同的供应商上。独立审查是本协议的核心，无法关闭。",
  "You can swap either model later without losing history.":"你之后可以更换任一模型而不丢失历史记录。",
  "The copy of this report on disk differs from the audited one shown here. Run crossaudit verify to check the record.":"磁盘上的这份报告与此处显示的已审计版本不同。请运行 crossaudit verify 核对记录。",
  "Generator live draft · not yet audited":"生成者实时草稿 · 尚未审计",
  "No receipt names the commit this report was audited at, so CrossAudit cannot confirm the version shown here is the one that was audited. Run crossaudit verify to check the record.":"没有收据记录这份报告在哪个提交上接受了审计，因此 CrossAudit 无法确认此处显示的版本就是当时被审计的版本。请运行 crossaudit verify 核对记录。",
  "This report is not committed yet, so it cannot be verified yet.":"这份报告尚未提交，因此暂时无法核验。",
  "Start using CrossAudit":"开始使用 CrossAudit","Paste your API key":"粘贴你的 API key",
  "API key":"API 密钥","Saving your provider setup…":"正在保存你的供应商设置……",
  "Paste a new key to replace the saved one":"粘贴新密钥以替换已保存的密钥",
  "Same provider — independent review is not possible.":"同一家供应商——无法进行独立审查。",
  "Your provider setup is saved. Create your first project to put the recommended pair to work.":"你的供应商设置已保存。创建你的第一个项目，即可让推荐搭配开始工作。"
  ,"Governed":"治理","Governed actions and evidence":"受治理操作与证据","Plan":"计划","Goal and plan":"目标与计划","Governed actions":"受治理操作"
  ,"Every built-in action the agent proposed, the policy decision, your approval, and the content hashes recorded to the append-only evidence ledger.":"智能体提议的每个内置操作、策略决定、你的批准，以及写入只增证据账本的内容哈希。"
  ,"This is the audit trail.":"这里是审计轨迹。"
  ,"The broker writes each proposal, decision, approval and result to a hash-chained ledger the independent auditor reviews and the receipt binds — no raw output is shown or stored, only hashes and decisions. Hashes are truncated for display.":"代理会把每个提议、决定、批准和结果写入哈希链账本，由独立审计者审查并由收据绑定——不显示或存储任何原始输出，只保留哈希与决定。哈希已截断显示。"
  ,"No governed actions yet. When the agent uses a built-in tool — read, write, run a command, commit, or submit compute — each proposal, decision, approval and result appears here.":"尚无受治理操作。当智能体使用内置工具——读取、写入、运行命令、提交或提交计算任务——每个提议、决定、批准和结果都会显示在这里。"
  ,"succeeded":"成功","refused":"已拒绝","needs_approval":"待批准","recorded":"已记录"
  ,"Usage is below the configured thresholds.":"用量低于已配置的阈值。","API-value estimate":"API 价值估算","read + write this month":"本月读取 + 写入","≈ value":"≈ 价值","Audits":"审计","warning":"预警","current":"当前"
  ,"Scope":"范围","project":"项目","Writes":"写入","Commands":"命令","No gates to show.":"暂无可显示的关卡。","No checks configured":"未配置检查项","workstation":"工作站"
  ,"Current gate":"当前关卡","Stopped at":"停止于","Next gate":"下一关卡","Completed gate":"已完成关卡","Live activity":"实时活动","Run activity":"运行活动"
  ,"Live generator and auditor events appear here while a task runs. The gate states above are reconstructed from the Git ledger.":"任务运行时，生成者与审计者的实时事件会显示在这里。上方关卡状态由 Git 账本重建。"
  ,"Stop":"停止","Stopping…":"正在停止…","Ledger snapshot":"账本快照","Ledger-backed state":"账本支撑的状态","Controller":"控制器","Result":"结果","Round":"第","Audit gates reached":"已到达的审计关卡"
  ,"Working":"进行中","Passed review":"通过复核","Needs changes":"需要修改","Admitted":"已准入","Needs your input":"需要你处理","Current step":"当前步骤","Next step":"下一步","Completed step":"已完成步骤","Compute":"算力","Tool":"工具","Process":"流程","Done":"完成","Active":"进行中","Waiting":"等待","Stopped":"已停止","Audit steps done":"已完成的审计步骤","The generator and auditor show what they are doing here while a task runs.":"任务运行时，生成者和审计者会在这里显示各自正在做什么。"
  ,"passed":"已通过","blocked":"已阻止","escalated":"已升级","consumed":"已准入","interrupted":"已中断","setting_up":"正在设置","setup_failed":"设置失败"
  ,"PASS":"通过","PASSED":"已通过","BLOCKED":"已阻止","ESCALATED":"已升级","CONSUMED":"已准入","DCL_ONLY":"仅确定性检查"
  ,"NOTHING_TO_AUDIT":"暂无可审计内容"
  ,"Nothing to check yet — this command reviews work you have added, and there is none here so far.":"暂无可检查的内容——此命令用于审查你已添加的工作，目前这里还没有。"
  ,"To Auditor":"发给审计者","To Generator":"发给生成者","@ auditor":"@ 审计者","@ generator":"@ 生成者"
  ,"No findings. The audited increment passed.":"未发现问题。该受审增量已通过。","No structured findings were recorded.":"未记录结构化问题。"
  ,"Allow once":"仅允许一次","Allow this run":"允许本次运行","Allow this project":"允许此项目","Deny":"拒绝","Approval needed":"需要你批准","Paths":"路径","Host":"主机","Est. cost":"预计成本"
  ,"no change — reads only":"无更改——仅读取","reversible — a recovery point is saved before the edit":"可恢复——编辑前会先保存恢复点","runs a local command; effects are not automatically undone":"运行本地命令；效果不会自动撤销"
  ,"reaches the network; may have off-machine effects":"会访问网络；可能产生机外影响","high-impact — not easily reversible":"高影响——不易恢复","destructive / forbidden":"破坏性 / 禁止"
  ,"Admission result":"准入结果","Admission explanation":"准入说明","local":"本地","remote":"远程","paired":"配对","enforced":"强制"
  ,"self-review; the history is yours to rewrite":"自我审查；历史可由你随意改写","history out of unilateral control":"历史不受单方控制","privilege separation between the two agents":"两个智能体之间的权限隔离"
  ,"the verdict is published and checkable, but nothing is refused":"判定已发布且可核查，但不会拒绝任何内容","a failed audit refuses the merge":"审计未通过将拒绝合并"
  ,"Checks":"检查","Verdict":"判定","Admission":"准入","generator":"生成者","auditor":"审计者"
  ,"the generator writes and commits":"生成者编写并提交","deterministic layer, no model involved":"确定性检查层，不涉及模型","a different vendor reads the commit":"由另一家供应商读取该提交"
  ,"code decides; the checks dominate":"由代码判定；检查结果优先","a receipt is consumed, once":"收据只消费一次","clean":"无问题","hard failure — final, no model may waive it":"硬性失败——最终结论，任何模型都不能豁免"
  ,"no model ran — cannot be PASS":"未运行模型——不能判为 PASS","receipt consumed":"收据已消费","waiting: verify the receipt to admit":"等待中：验证收据后即可准入","not reached":"未到达"
  ,"signed · verifiable offline":"已签名 · 可离线验证"
  ,"writing":"正在撰写","reviewing the commit":"正在审查提交","findings returned to the generator":"问题已返回给生成者","cancelling":"正在取消","dismissed":"已忽略","running built-in tool":"正在运行内置工具"
  ,"resuming with tool result":"携工具结果继续","resuming with compute result":"携计算结果继续","requesting remote calculation":"正在请求远程计算","note":"备注","document export refused":"文档导出被拒绝"
  ,"the round could not be committed":"该轮次无法提交","rendering final document locally":"正在本地渲染最终文档","the round reproduced the previous one; nothing new to audit":"本轮与上一轮结果相同；没有新的内容可审计"
  ,"the loop cannot settle this itself":"循环无法自行解决此问题","this stop is waiting for a human":"此次停止正在等待人工处理"
  ,"Thinking":"思考中","Generator live reply · not audited":"生成者实时回复 · 未经审计","Auditor live reply · direct reply":"审计者实时回复 · 直接回复"
  ,"Connect a provider first":"请先连接供应商","The generator has no credential yet.":"生成者尚未连接凭据。","The auditor has no credential yet.":"审计者尚未连接凭据。"
  ,"Neither the generator nor the auditor has a credential yet.":"生成者与审计者都尚未连接凭据。","Open Settings → Providers":"打开设置 → 供应商"
  ,"Task started.":"任务已开始。","The result will appear in this conversation.":"结果会显示在此对话中。","Needs clarification.":"需要澄清。","Refused.":"已拒绝。","Message delivered.":"消息已送达。","Sending your files…":"正在发送文件…"
  ,"Pinned":"已置顶","Recent":"最近","Upload failed":"上传失败","Uploaded":"已上传"
  ,"Stored in chunks without an app quota. Model inspection depends on file support and context.":"分块存储，应用不设配额。模型能否读取取决于文件支持与上下文。"
  ,"polling":"轮询中","offline":"离线","reconnecting":"正在重连"
  ,"Interrupted · open to review and run again":"已中断 · 打开以检查并重新运行","Fix & retry":"修复并重试","GitHub setup stopped":"GitHub 设置已中断","GitHub paired":"已配对 GitHub","Local":"本地"
  ,"Project ready":"项目已就绪","Setup needs attention":"设置需要处理","Review the settings and retry.":"请检查设置后重试。","Edit repository names":"编辑仓库名称"
  ,"Could not pin project.":"无法置顶项目。","Could not create chat.":"无法创建对话。","Unpin project":"取消置顶项目","Live project activity":"项目实时活动","Sample demonstration notice":"示例演示提示"
  ,"Both names are available · one click will create both repositories":"两个名称均可用 · 一键即可创建两个仓库","Checking GitHub…":"正在检查 GitHub…"
  ,"Scientific projects require the visible metadata.yml/results.json, units, convergence, and provenance contract.":"科学项目要求可见的 metadata.yml/results.json、单位、收敛性与来源追溯契约。"
  ,"A loop is running. These controls unlock when its current model calls finish.":"循环正在运行。当前模型调用结束后，这些控制才会解锁。"
  ,"Applies to the next provider request.":"将用于下一次供应商请求。","This model uses its provider-controlled default.":"该模型使用由供应商控制的默认值。","Checking this model…":"正在检查该模型…"
  ,"Models updated":"模型已更新","Refreshing…":"正在刷新…","Refresh failed":"刷新失败","Connecting…":"正在连接…"
  ,"Slurm jobs use sbatch; workstations use a detached nohup process. Both survive connection loss.":"Slurm 任务使用 sbatch；工作站使用分离的 nohup 进程。两者都不受连接中断影响。"
  ,"Submitting…":"正在提交…","Uploading inputs…":"正在上传输入文件…"
  ,"GitHub connected":"GitHub 已连接","GitHub is not connected":"GitHub 未连接","Copy code":"复制代码","Open GitHub ↗":"打开 GitHub ↗"
  ,"Sign in, enter the code, and approve GitHub CLI. This page updates automatically.":"登录并输入代码，然后批准 GitHub CLI。此页面会自动更新。","Install GitHub tool ↗":"安装 GitHub 工具 ↗"
  ,"Enter the code in GitHub. This dialog updates automatically after approval.":"在 GitHub 中输入代码。批准后此对话框会自动更新。","Authorize CrossAudit in GitHub":"在 GitHub 中授权 CrossAudit"
  ,"Review the repository settings and retry.":"请检查仓库设置后重试。","Authorize permanent repository deletion":"授权永久删除仓库"
  ,"Exact model ID":"准确的模型 ID","Credential":"凭据","Could not resume setup":"无法恢复设置","Resuming GitHub setup":"正在恢复 GitHub 设置","visible to this account":"此账户可见"
  ,"Open help":"打开帮助","Fix":"修复","Git installation guide":"Git 安装指南"
  ,"Use the official Codex login and an eligible ChatGPT plan. CrossAudit never receives the OAuth token.":"使用官方 Codex 登录及符合条件的 ChatGPT 套餐。CrossAudit 绝不会接收 OAuth token。"
  ,"Official ChatGPT subscription sign-in is available through the bundled Codex runtime; CrossAudit never receives its OAuth token.":"可通过内置 Codex 运行时使用官方 ChatGPT 订阅登录；CrossAudit 绝不会接收其 OAuth token。"
  ,"Run the check to inspect this Mac.":"运行检查以检测此 Mac。"
  ,"Complete sign-in in your browser":"请在浏览器中完成登录","Complete sign in in your browser":"请在浏览器中完成登录","Open ChatGPT ↗":"打开 ChatGPT ↗"
  ,"Connected. Usage follows this ChatGPT workspace and plan.":"已连接。用量遵循该 ChatGPT 工作区和套餐。"
  ,"Use the CrossAudit macOS app to choose a local folder. The browser console cannot read arbitrary folder paths.":"请使用 CrossAudit macOS 应用选择本地文件夹。浏览器控制台无法读取任意文件夹路径。"
  ,"Search results":"搜索结果","frozen-app":"应用安装包","wheel":"wheel 包","editable":"可编辑安装","unavailable":"不可用"
  ,"Permissions and per-project defaults":"权限与按项目默认值","Permissions and defaults":"权限与默认值"
  ,"Apple Command Line Tools are not installed.":"未安装 Apple 命令行工具。","This application bundle must be replaced.":"必须更换此应用安装包。","CrossAudit requires macOS 13 or later.":"CrossAudit 需要 macOS 13 或更高版本。"
  ,"No trusted certificates are available for provider HTTPS calls.":"没有可用于供应商 HTTPS 调用的受信任证书。","Initialize this folder after Git is ready.":"Git 就绪后再初始化此文件夹。","This project is not initialized as a Git repository.":"此项目尚未初始化为 Git 仓库。"
  ,"CrossAudit runs on this bundled Python; an older build cannot execute the app reliably.":"CrossAudit 依赖此内置 Python 运行；旧版本无法可靠地运行本应用。"
  ,"Older macOS releases miss security fixes CrossAudit relies on for the Keychain and network trust.":"较旧的 macOS 缺少 CrossAudit 在钥匙串与网络信任方面依赖的安全修复。"
  ,"Git records every audit decision as a commit; without it CrossAudit cannot create or audit a project.":"Git 会把每个审计决定记录为提交；没有它，CrossAudit 无法创建或审计项目。"
  ,"Remote compute runs Generator jobs on a cluster over SSH; needed only if you use one.":"远程计算通过 SSH 在集群上运行生成者任务；仅在你使用集群时需要。"
  ,"This tool creates and syncs the work and audit repositories; not needed for local-only projects.":"此工具用于创建并同步工作仓库和审计仓库；纯本地项目不需要它。"
  ,"This runtime powers the official ChatGPT sign-in; needed only if you connect a ChatGPT subscription.":"此运行时支持官方 ChatGPT 登录；仅在你连接 ChatGPT 订阅时需要。"
  ,"Every provider call is HTTPS; without trusted certificates CrossAudit cannot reach any model safely.":"所有供应商调用都通过 HTTPS；没有受信任的证书，CrossAudit 无法安全连接任何模型。"
  ,"Projects and their files live in this folder; CrossAudit needs to read and write inside it.":"项目及其文件保存在此文件夹中；CrossAudit 需要在其中读写。"
  ,"The audit reads commits from this repository; it must be initialized before a run can be recorded.":"审计会读取此仓库中的提交；必须先初始化，才能记录运行。"
  ,"Every commit needs an author; without a name and email CrossAudit cannot record audit history.":"每个提交都需要作者；没有姓名和邮箱，CrossAudit 无法记录审计历史。","Another CrossAudit is earlier on your PATH, so typing `crossaudit` in a terminal runs that one instead of this app.":"你的 PATH 中有另一个更靠前的 CrossAudit，因此在终端里输入 `crossaudit` 运行的是那一个，而不是这个应用。"
  ,"This file defines the project's roles, routes, and rules; the project cannot run without it.":"此文件定义项目的角色、路由和规则；缺少它项目无法运行。"
  ,"These are the rules the auditor judges against; an audit cannot run without them.":"这些是审计者据以判定的规则；缺少它们无法进行审计。"
  // R1–R5 (results & decisions). Plain verdict words, finding details, the
  // Details record, the forecast line and one copy set per ESCALATE cause.
  ,"Needs you":"需要你","Checks only":"仅自动检查"
  ,"must fix":"必须修改","suggestion":"建议"
  ,"verified by a check":"已由检查验证","raised by the auditor, not yet reproduced":"由审计者提出，尚未复现","raised by the auditor, verified":"由审计者提出，已验证"
  ,"Details":"详情","Human":"人工"
  ,"First run here — no estimate yet":"首次运行，暂无预估","Usually under a minute":"通常不到 1 分钟","Rules":"规则"
  ,"Nothing to review yet":"尚无可审内容","The task produced no work in the audited folder":"任务未在受审文件夹中产生任何工作"
  ,"There is nothing to review yet: the generator produced no files inside the folder the auditor checks, so no audit could run and nothing was admitted.":"目前没有可审查的内容：生成者没有在审计者检查的文件夹中产生任何文件，因此无法进行审计，也没有准入任何结果。"
  ,"Tell the generator what to create inside the audited folder and run one more round, or stop this task.":"告诉生成者应在受审文件夹中创建什么，然后再运行一轮；或停止此任务。"
  ,"Say which files should be created inside the audited folder, then unlock one additional audited round.":"说明应在受审文件夹中创建哪些文件，然后解锁额外一轮受审计执行。"
  ,"Create the deliverable inside the audited folder; nothing was produced there.":"请在受审文件夹中创建交付物；此前那里没有产生任何内容。"
  ,"No audit findings were created because there was no work in the audited folder to review.":"由于受审文件夹中没有可审查的工作，未产生任何审计发现。"
  ,"The generator finished without writing any file under the audited folder, so the auditor had no files to check; the folder is unchanged.":"生成者完成时没有在受审文件夹下写入任何文件，审计者因此没有可检查的文件；该文件夹未改动。"
  ,"Auditor reply unreadable":"审计者回复无法读取","The auditor’s reply could not be read":"审计者的回复无法读取"
  ,"The auditor answered, but its reply was not in the required form, so no verdict could be recorded. The files are unchanged and nothing was admitted.":"审计者作出了回复，但其格式不符合要求，因此无法记录裁定。文件未改动，也没有准入任何结果。"
  ,"Run the audit again on the same work, switch the auditor model, or stop this task.":"对同一份工作再次运行审计、更换审计者模型，或停止此任务。"
  ,"Run the audit again":"再次运行审计","Unlock one more round with the work unchanged so the auditor can answer again.":"在工作不变的情况下解锁一轮，让审计者再次作答。"
  ,"Run the audit again on the same work; the previous auditor reply could not be read.":"请对同一份工作再次运行审计；上一次审计者的回复无法读取。"
  ,"No audit findings were recorded because the auditor’s reply could not be read.":"由于审计者的回复无法读取，未记录任何审计发现。"
  ,"The reply was checked against the required format and rejected; CrossAudit never guesses a verdict from a reply it cannot parse, so the round was handed to you.":"该回复经过格式校验后被拒绝；CrossAudit 不会从无法解析的回复中猜测裁定，因此本轮交由你处理。"
  ,"Task too large for one audit":"任务过大，无法一次审计","The task is too large for one audit":"该任务过大，无法在一次审计中完成"
  ,"The work exceeds what one audit can read at once, so the auditor stopped rather than judge part of it. Nothing was admitted.":"工作量超出了一次审计能够读取的范围，审计者因此停止，而不是只评判其中一部分。没有准入任何结果。"
  ,"Narrow the scope or split the task into smaller pieces and run one more round, or stop this task.":"缩小范围或将任务拆分为更小的部分，然后再运行一轮；或停止此任务。"
  ,"Name the smaller piece the next round should cover, then unlock one additional audited round.":"指明下一轮应覆盖的较小部分，然后解锁额外一轮受审计执行。"
  ,"No audit findings were recorded because the work was too large to audit in one pass.":"由于工作量过大，无法一次审计完成，未记录任何审计发现。"
  ,"The audited files exceed what one audit prompt can hold; the auditor was not shown a partial set, and nothing was judged.":"受审文件超出了单次审计提示能容纳的范围；审计者没有被展示部分文件，也没有作出任何判断。"
  ,"The auditor asked for you":"审计者请你介入","The auditor asked for your judgment":"审计者请你作出判断"
  ,"The auditor could not settle this round on its own and handed it to you. Its stated reason is below. Nothing was admitted.":"审计者无法独自裁定本轮，已交由你处理。其陈述的原因见下方。没有准入任何结果。"
  ,"What the auditor said":"审计者的说明"
  ,"Read the auditor’s reason, then tell the generator how to address it or stop this task.":"阅读审计者的原因，然后告诉生成者如何处理；或停止此任务。"
  ,"Tell the generator how to address the auditor’s reason, then unlock one additional audited round.":"告诉生成者如何处理审计者的原因，然后解锁额外一轮受审计执行。"
  ,"The auditor recorded no structured findings. Its stated reason is above.":"审计者未记录结构化问题。其陈述的原因见上方。"
  ,"The auditor returned no findings and no reason; only its request for a human decision was recorded.":"审计者没有返回任何发现或原因；仅记录了其请人工决定的请求。"
  ,"Read the auditor's reason, then tell the generator how to address it or stop this task.":"阅读审计者的原因，然后告诉生成者如何处理；或停止此任务。"
  ,"Waiting on an earlier decision":"等待更早的决定","This task is already waiting for your earlier decision":"此任务仍在等待你更早的决定"
  ,"An earlier round of this task is still waiting for you. No new round can run until that decision is made.":"此任务更早的一轮仍在等待你。在作出该决定前，无法运行新的一轮。"
  ,"Open the earlier decision and settle it; this task continues from there.":"打开更早的决定并作出处理；此任务将从那里继续。"
  ,"Settle the earlier decision":"先处理更早的决定","Open the earlier decision first. Guidance recorded here applies once it is settled.":"请先打开更早的决定。此处记录的指引将在其处理完毕后生效。"
  ,"No new findings were recorded because the earlier decision is still open.":"由于更早的决定仍未处理，未记录新的发现。"
  ,"Open the earlier decision":"打开更早的决定"
  ,"A newer commit was made while an earlier round was still waiting for you; the new commit was not audited, so the pending decision cannot be overtaken.":"在更早的一轮仍在等待你时，产生了新的提交；新提交未被审计，因此待定的决定不会被绕过。"
};
const ZH_PATTERNS=[
  // Billing slice: threshold alarms carry their percentage and the monthly
  // reset its date, so both are patterns (a fixed entry would fall back to
  // English the moment the number changed).
  [/^Today.s token budget is (\d+)% used$/, m=>'今日 token 预算已用 '+m[1]+'%'],
  [/^This month.s cost budget is (\d+)% used$/, m=>'本月费用预算已用 '+m[1]+'%'],
  [/^Resets on (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d+)$/,
   m=>(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].indexOf(m[1])+1)+' 月 '+m[2]+' 日重置'],
  // D148 repair guard. Every reason is COMPOSED from a path, a count or a
  // construct name, so each is a pattern; the path is never translated. The
  // event detail joins several with "; " and the stop reason wraps the first
  // in a round number, so those two shapes delegate to the per-reason rows.
  // Gate: tests/test_repair_guard_console_zh.py drives every sentence the
  // guard and build.py can emit (enumerated from their source) through zhValue.
  [/^the automatic repair was refused in round (\d+) because (.+)$/,
   m=>'第 '+m[1]+' 轮的自动修复被拒绝，原因：'+zhValue(m[2])],
  // The pattern IS the boundary between two guard sentences, so a string
  // matches only when it really joins two (no recursion on one sentence), and
  // the semicolon inside the scope sentence (if the fix needs ...) is not one.
  [/; (?=\S+ (?:is outside the audited|is a binary file|adds |removes |changes |renames )|the code change touches|\d+ staged file|the revision changed nothing)/,
   m=>m.input.split(/; (?=\S+ (?:is outside the audited|is a binary file|adds |removes |changes |renames )|the code change touches|\d+ staged file|the revision changed nothing)/).map(part=>zhValue(part)).join('；')],
  [/^(.+) is outside the audited directories \((.*)\)\. Only files inside them may change; if the fix needs another file, say so in `notes`\.$/,
   m=>m[1]+' 不在已审计目录（'+m[2]+'）内。只有这些目录内的文件可以修改；如果修复确实需要其他文件，请在 `notes` 中说明。'],
  [/^(.+) is a binary file written directly by the generator, which cannot be reviewed line by line$/,
   m=>m[1]+' 是生成者直接写入的二进制文件，无法逐行审查'],
  [/^the code change touches (\d+) lines, more than the (\d+)-line limit for an automatic repair$/,
   m=>'代码改动涉及 '+m[1]+' 行，超过了自动修复的 '+m[2]+' 行上限'],
  [/^(\d+) staged file\(s\) were larger than the review can read and were not screened: (.+)$/,
   m=>'有 '+m[1]+' 个已暂存文件超出审查可读取的大小而未被筛查：'+m[2]],
  // "<path> adds|removes|changes|renames <construct>": the constructs are
  // repair_guard's ADDED/MARKER/REMOVED tables and its re-raise sentence.
  [/^(\S+) (adds|removes|changes|renames) (.+)$/,m=>{const zh={
    'adds a catch-all `except` that swallows every error':'新增了会吞掉所有错误的 catch-all `except`',
    'adds a catch-all `except` (its handler re-raises)':'新增了 catch-all `except`（其处理程序会重新抛出）',
    'adds a `suppress(...)` block that hides errors':'新增了会隐藏错误的 `suppress(...)` 块',
    'adds an error handler that does nothing':'新增了一个什么也不做的错误处理',
    'adds an assertion that can no longer fail':'新增了一个不再可能失败的断言',
    'adds a skipped or expected-to-fail test':'新增了被跳过或预期失败的测试',
    'adds code under a branch that never runs (`if TYPE_CHECKING:` / `if False:`)':'在永远不会执行的分支下新增了代码（`if TYPE_CHECKING:` / `if False:`）',
    'adds a shell or make step that ignores its own failure':'新增了会忽略自身失败的 shell 或 make 步骤',
    'adds a marker that silences a checker (`noqa`, `type: ignore`, `pragma: no cover`, ...)':'新增了会让检查器静默的标记（`noqa`、`type: ignore`、`pragma: no cover` 等）',
    'adds a warnings filter set to ignore':'新增了设为忽略的警告过滤器',
    'removes an `assert` or `raise` without replacing it':'删除了一个 `assert` 或 `raise` 而没有替代',
    'changes an `assert` or `raise`':'改动了一个 `assert` 或 `raise`',
    'removes a test':'删除了一个测试','renames a test':'重命名了一个测试'}[m[2]+' '+m[3]];
    return zh?m[1]+' '+zh:m[0];}],
  [/^provider failure left this task waiting for a person: ?(.*)$/,
   m=>'提供方失败，该任务正在等待人工处理：'+m[1]],
  [/^the selected PASS is not ready for admission: ?(.*)$/,
   m=>'所选的 PASS 尚未达到准入条件：'+m[1]],
  // The fail-closed denial from the audit core: a corrupt evidence ledger
  // refuses to produce a receipt. It carries the reason from the verifier after
  // the colon, so it is a PATTERN — an exact entry would never match what a
  // person sees. This is the sentence standing between somebody and a forged
  // receipt, and it was the last string in the product anyone thought to
  // translate.
  [/^evidence ledger cannot be shown to the Auditor: ?(.*)$/,
   m=>'证据账本无法出示给审计者：'+m[1]],
  [/^Typing `crossaudit` runs (.+) \(version (.+)\)\. This app is (.+) at (.+)\.$/,
   m=>'在终端里输入 `crossaudit` 运行的是 '+m[1]+'（版本 '+m[2]+'）。本应用是 '+m[3]+'，位于 '+m[4]+'。'],
  [/^Typing `crossaudit` runs (.+)\. Its version could not be determined without running it, which CrossAudit does not do\. This app is (.+) at (.+)\.$/,
   m=>'在终端里输入 `crossaudit` 运行的是 '+m[1]+'。在不运行它的前提下无法确定其版本，而 CrossAudit 不会运行它。本应用是 '+m[2]+'，位于 '+m[3]+'。'],
  // ORDER MATTERS: ZH_PATTERNS is first-match-wins, and these sit at the front
  // deliberately. An existing /^Remove (.+)$/ was swallowing
  // "Remove OpenAI API key" into "移除 OpenAI API key" — translated verb,
  // untranslated noun, which reads as done and is not. A composed name must be
  // matched by the most specific pattern, so the most specific goes first.
  // SPEC-13 §3.1 and §3.4. Every one of these is COMPOSED from a provider name,
  // so each must be a pattern. A fixed entry would translate only the providers
  // whose names happen to be in the dictionary and hand every other Chinese
  // reader an English control name — the i18n form of the silent gap. The
  // provider name itself is never translated: it is the vendor identifier.
  [/^(Paste|Clear|Validate|Reveal|Replace|Remove) (.+) API key$/,m=>
    ({Paste:'粘贴',Clear:'清除',Validate:'验证',Reveal:'显示',Replace:'更换',Remove:'移除'})[m[1]]
    +' '+m[2]+' API 密钥']
  ,[/^Get key — (.+)$/,m=>'获取 key —— '+m[1]]
  ,[/^API docs — (.+)$/,m=>'API 文档 —— '+m[1]]
  ,[/^Checking (.+) key…$/,m=>'正在检查 '+m[1]+' 密钥……']
  ,[/^(.+) key verified\.$/,m=>m[1]+' 密钥已验证。']
  ,[/^(.+) key rejected\. Check it and try again\.$/,m=>m[1]+' 密钥被拒绝。请检查后重试。']
  ,[/^(.+) key works, but no models are available to it\.$/,m=>m[1]+' 密钥可用，但没有可用的模型。']
  ,[/^Could not reach (.+)\. Check your connection and try again\.$/,m=>'无法连接 '+m[1]+'。请检查网络后重试。']
  ,[/^reading (\d+) owner message\(s\)$/,m=>'正在读取 '+m[1]+' 条所有者补充信息'],
  [/^Draft: (\d+) words so far$/,m=>'草稿：已写 '+m[1]+' 字'],
  [/^Still (routing|preparing|generating|auditing|replying|reviewing) · (\d+) s$/,m=>
    ({routing:'仍在判断由谁处理',preparing:'仍在准备',generating:'仍在生成',auditing:'仍在审计',replying:'仍在回复',reviewing:'仍在审阅'})[m[1]]+' · '+m[2]+' 秒'],
  [/^queued as owner guidance for the running build \(#(\d+)\); it will be read at the next round$/,m=>'已作为所有者补充信息排队（第 '+m[1]+' 位），将在下一轮读取'],
  [/^(\d+) queued$/,m=>m[1]+' 条排队中'],
  [/^generator provider failure in round (\d+): (.+)$/,m=>'生成者在第 '+m[1]+' 轮失败：'+m[2]],
  [/^the generator returned malformed file blocks: (.+)$/,m=>'生成者返回了格式错误的文件块：'+m[1]],
  [/^the selected PASS is not ready for admission: (.+)$/,m=>'所选 PASS 尚不满足准入条件：'+m[1]],
  [/^the selected PASS receipt is missing — (.+)$/,m=>'所选 PASS 的收据缺失——'+m[1]],
  [/^there is no unconsumed passing result to admit$/,()=>'没有未消费的 PASS 结果可供准入'],
  [/^Admission tier ([\w-]+)( · .+)?$/,m=>'准入级别 '+zhValue(m[1])+(m[2]?' · '+zhValue(m[2].slice(3)):'')],
  [/^receipt ([0-9a-f]+)$/,m=>'收据 '+m[1]],[/^tier ([\w-]+)$/,m=>'级别 '+zhValue(m[1])],
  [/^reproducible · (\d+) locks?$/,m=>'可复现 · '+m[1]+' 个依赖锁'],
  [/^(\d+) cycles?$/,m=>m[1]+' 个审计循环'],[/^(\d+) chats?$/,m=>m[1]+' 个对话'],
  [/^(\d+) required items? needs? fixing$/i,m=>m[1]+' 个必需项需要修复'],
  [/^(\d+) optional items? needs? attention$/i,m=>m[1]+' 个可选项需要处理'],
  [/^(\d+) required items? needs? attention$/i,m=>m[1]+' 个必需项需要处理'],
  [/^(\d+) checks? queued$/i,m=>m[1]+' 项检查排队中'],
  [/^(\d+) checks?$/i,m=>m[1]+' 项检查'],
  [/^(\d+) checks? passed$/i,m=>m[1]+' 项检查通过'],
  [/^(\d+) trusted certificate authorities$/i,m=>m[1]+' 个受信任的证书颁发机构'],
  [/^round (\d+) of (\d+)$/i,m=>'第 '+m[1]+' / '+m[2]+' 轮'],[/^round (\d+)$/i,m=>'第 '+m[1]+' 轮'],
  [/^Updated (.+)$/i,m=>'更新于 '+m[1]],[/^Version (.+) is current\.$/i,m=>'版本 '+m[1]+' 已是最新版。'],
  [/^Version (.+) is available; this app is (.+)\.$/i,m=>'可用版本为 '+m[1]+'；当前应用为 '+m[2]+'。'],
  [/^Version (.+); the update server could not be reached\.$/i,m=>'版本 '+m[1]+'；无法连接更新服务器。'],
  [/^Version (.+) is installed; CrossAudit requires (.+) or later\.$/i,m=>'已安装版本 '+m[1]+'；CrossAudit 需要 '+m[2]+' 或更高版本。'],
  [/^Version (.+)$/i,m=>'版本 '+m[1]],
  [/^Connected as (.+) · (.+)\. Usage follows this ChatGPT workspace and plan\.$/i,m=>'已连接为 '+m[1]+' · '+m[2]+'。用量遵循该 ChatGPT 工作区和套餐。'],
  [/^Connected as (.+)\. Usage follows this ChatGPT workspace and plan\.$/i,m=>'已连接为 '+m[1]+'。用量遵循该 ChatGPT 工作区和套餐。'],
  [/^Connected · (.+)\. Usage follows this ChatGPT workspace and plan\.$/i,m=>'已连接 · '+m[1]+'。用量遵循该 ChatGPT 工作区和套餐。'],
  [/^Connected as (.+)$/i,m=>'已连接为 '+m[1]],[/^Local project: (.+)$/i,m=>'本地项目：'+m[1]],
  [/^(\d+) attachment\(s\) received$/i,m=>'已收到 '+m[1]+' 个附件'],
  [/^(\d+) rules?$/i,m=>m[1]+' 条规则'],
  [/^(\d+) reports?$/i,m=>m[1]+' 份报告'],[/^(\d+) connected$/i,m=>'已连接 '+m[1]+' 个'],[/^(\d+) active$/i,m=>m[1]+' 个正在运行'],
  [/^(.+) · local controller$/i,m=>m[1]+' · 本地控制器'],
  [/^(.+) · updated (.+)$/i,m=>m[1]+' · 更新于 '+m[2]],
  [/^(\d+) projects?, (\d+)\/(\d+) active · (.+)$/i,m=>m[1]+' 个项目，'+m[2]+'/'+m[3]+' 活跃 · '+m[4]],
  [/^(.+) API key - connect in Settings$/i,m=>m[1]+' API key - 请先在设置中连接'],
  [/^Connect (.+) in Settings first$/i,m=>'请先在设置中连接 '+m[1]],
  [/^(.+) - highest capability$/i,m=>m[1]+' - 最高能力'],
  [/^(.+) - balanced · recommended$/i,m=>m[1]+' - 均衡 · 推荐'],
  [/^(.+) - fastest, lowest cost$/i,m=>m[1]+' - 最快、成本最低'],
  [/^CrossAudit used all (\d+) of (\d+) automatic rounds without a passing result\. Nothing will continue or be admitted until you decide\.$/i,m=>'CrossAudit 已用完 '+m[1]+' / '+m[2]+' 轮自动审计，但仍未通过。在你决定前，不会继续执行或准入任何结果。'],
  [/^Automatic rounds used: (\d+) \/ (\d+)$/i,m=>'已用自动轮数：'+m[1]+' / '+m[2]],
  [/^Round history: (.+)$/i,m=>'轮次记录：'+m[1].replace(/Round (\d+):/gi,'第 $1 轮：').replace(/BLOCKED/gi,'未通过').replace(/PASS/gi,'通过').replace(/(\d+) issues?/gi,'$1 个问题')],[/^Affects (.+)$/i,m=>'影响 '+m[1]],
  [/^(\d+) remaining issues?$/i,m=>'剩余 '+m[1]+' 个问题'],
  [/^Automatic limit reached · (\d+) \/ (\d+) rounds$/i,m=>'已达自动上限 · '+m[1]+' / '+m[2]+' 轮'],
  [/^(·\s*)?CrossAudit paused after (\d+) of (\d+) rounds with (\d+) issues? remaining\.$/i,m=>(m[1]?'· ':'')+'CrossAudit 在第 '+m[2]+' / '+m[3]+' 轮后暂停，仍有 '+m[4]+' 个问题。']
  ,[/^(\d+) remote jobs active$/i,m=>m[1]+' 个远程任务正在运行']
  ,[/^Generator tool · (\d+) jobs\/task · (\d+) CPU · (\d+) GPU$/i,m=>'生成者工具 · 每任务 '+m[1]+' 个作业 · '+m[2]+' CPU · '+m[3]+' GPU']
  ,[/^Offline view · (.+) · the remote job continues independently$/i,m=>'离线视图 · '+m[1]+' · 远程任务仍在独立运行']
  ,[/^(\d+) MCP servers · (\d+) Skills$/i,m=>m[1]+' 个 MCP 服务器 · '+m[2]+' 个技能']
  ,[/^(\d+) of (\d+) approved$/i,m=>'已批准 '+m[1]+' / '+m[2]]
  ,[/^(.+) · MCP (.*) · (\d+) tools advertised$/i,m=>m[1]+' · MCP '+m[2]+' · 公布了 '+m[3]+' 个工具']
  ,[/^(\d+) calls\/task$/i,m=>'每任务 '+m[1]+' 次调用']
  ,[/^(\d+) recorded$/i,m=>'已记录 '+m[1]+' 次']
  ,[/^(\d+) committed$/i,m=>'已提交 '+m[1]+' 个']
  ,[/^Applies to (.+)$/i,m=>'适用于 '+m[1]]
  ,[/^(.+) · server annotations are untrusted$/i,m=>m[1]+' · 服务器标注不可信']
  ,[/^(\d+) tasks? needs? your decision$/i,m=>m[1]+' 个任务需要你决定']
  ,[/^round (\d+)\/(\d+)$/i,m=>'第 '+m[1]+'/'+m[2]+' 轮']
  ,[/^(\d+) findings?$/i,m=>m[1]+' 项发现']
  ,[/^(\d+) issues?$/i,m=>m[1]+' 个问题']
  ,[/^Usually (\d+)–(\d+) min( · about \$[\d.]+)?$/,m=>'通常 '+m[1]+'–'+m[2]+' 分钟'+(m[3]?' · 约 '+m[3].slice(9):'')]
  ,[/^Usually about (\d+) min( · about \$[\d.]+)?$/,m=>'通常约 '+m[1]+' 分钟'+(m[2]?' · 约 '+m[2].slice(9):'')]
  ,[/^Usually under a minute( · about \$[\d.]+)?$/,m=>'通常不到 1 分钟'+(m[1]?' · 约 '+m[1].slice(9):'')]
  ,[/^Rule id: (.+)$/,m=>'规则编号：'+m[1]]
  ,[/^(\d+) deterministic checks? passed$/i,m=>m[1]+' 项确定性检查已通过']
  ,[/^(\d+) files$/i,m=>m[1]+' 个文件']
  ,[/^Waiting for the provider · heartbeat (.+)$/,m=>'等待供应商 · 心跳 '+zhValue(m[1])]
  ,[/^last heartbeat (.+)$/,m=>'最后心跳 '+zhValue(m[1])]
  ,[/^no heartbeat for (.+)$/,m=>'已 '+zhValue(m[1])+'无心跳']
  ,[/^(\d+) min ago$/,m=>m[1]+' 分钟前'],[/^(\d+) h ago$/,m=>m[1]+' 小时前'],[/^(\d+) days? ago$/,m=>m[1]+' 天前']
  ,[/^(\d+) s$/,m=>m[1]+' 秒'],[/^(\d+) min$/,m=>m[1]+' 分钟'],[/^(\d+) h$/,m=>m[1]+' 小时']
  ,[/^(\d+)m (\d+)s elapsed$/,m=>'已运行 '+m[1]+' 分 '+m[2]+' 秒'],[/^(\d+)h (\d+)m elapsed$/,m=>'已运行 '+m[1]+' 小时 '+m[2]+' 分']
  ,[/^(.+) · round (\d+)$/,m=>zhValue(m[1])+' · 第 '+m[2]+' 轮']
  ,[/^(\d+)([mhd])$/,m=>m[1]+({m:' 分钟前',h:' 小时前',d:' 天前'})[m[2]]]
  ,[/^The local demo could not be prepared: (.+?)( — you can still create or import a project\.)?$/i,m=>'无法准备本地演示：'+m[1]+(m[2]?'——你仍可以创建或导入项目。':'')]
  ,[/^L(\d) (infer|read|write|command|network|high-impact|destructive)$/,m=>'L'+m[1]+' '+(({infer:'推断',read:'读取',write:'写入',command:'命令',network:'网络','high-impact':'高影响',destructive:'破坏性'})[m[2]]||m[2])]
  ,[/^⚠ flagged: (.+)$/,m=>'⚠ 已标记：'+m[1]]
  ,[/^decision (.+)$/,m=>'决定 '+m[1]]
  ,[/^approval (.+)$/,m=>'批准 '+m[1]]
  ,[/^path (.+)$/,m=>'路径 '+m[1]]
  ,[/^Token counts come from the provider runtime when available\. Costs use the (.+) public API price snapshot and are not a provider invoice or subscription charge\.$/,m=>'可用时，Token 数量来自供应商运行时。成本采用 '+zhValue(m[1])+' 公开 API 价格快照，并非供应商账单或订阅扣费。']
  ,[/^Local metering · (.+)$/,m=>'本地计量 · '+zhValue(m[1])]
  ,[/^Usage guardrail · (.+)$/,m=>'用量保护线 · '+zhValue(m[1])]
  ,[/^(\$[\d.,]+|-) API value$/,m=>m[1]+' API 价值']
  ,[/^(\d+) provider-reported$/,m=>m[1]+' 次由供应商报告']
  ,[/^([\d.,]+[KM]?) tokens$/,m=>m[1]+' Token']
  ,[/^(\d+) calls? · (.+) API value$/,m=>m[1]+' 次调用 · '+m[2]+' API 价值']
  ,[/^unpriced · (.+)$/,m=>'未计价 · '+m[1]]
  ,[/^(generator|auditor) · (.+), (.+) in \/ (.+) out$/,m=>zhValue(m[1])+' · '+m[2]+'，'+m[3]+' 输入 / '+m[4]+' 输出']
  ,[/^up to (\d+)$/,m=>'最多 '+m[1]+' 轮']
  ,[/^round (\d+) · (.+)$/i,m=>'第 '+m[1]+' 轮 · '+m[2]]
  ,[/^(\d+) \/ (\d+) rounds$/i,m=>m[1]+' / '+m[2]+' 轮']
  ,[/^(\d+) chats? · (\d+) cycles?$/i,m=>m[1]+' 个对话 · '+m[2]+' 个审计循环']
  ,[/^Uploading · (\d+)%$/,m=>'正在上传 · '+m[1]+'%']
  ,[/^(\d+) files? · (.+) · copied to remote inputs\/$/,m=>m[1]+' 个文件 · '+m[2]+' · 将复制到远端 inputs/']
  ,[/^(\d+) files? · (.+)$/,m=>m[1]+' 个文件 · '+m[2]]
  ,[/^\+(\d+) more selected$/,m=>'另有 '+m[1]+' 个已选择']
  ,[/^(.+) · current$/,m=>m[1]+' · 当前']
  ,[/^Creating (.+)$/,m=>'正在创建 '+m[1]]
  ,[/^Disconnected: (.+)$/,m=>'连接已断开：'+m[1]]
  ,[/^Up to (\d+) generator → auditor rounds?, then the task pauses for you\. It never auto-passes\.$/,m=>'最多进行 '+m[1]+' 轮生成者 → 审计者循环，随后暂停并等待你决定；绝不会自动通过。']
  ,[/^Already exists: (.+)$/,m=>'已存在：'+m[1]]
  ,[/^Ready to use: (.+)$/,m=>'可直接使用：'+m[1]]
  ,[/^(.+) · connected$/,m=>m[1]+' · 已连接']
  ,[/^(.+) · key needed$/,m=>m[1]+' · 需要 key']
  ,[/^(.+) - visible to this account$/,m=>m[1]+' - 此账户可见']
  ,[/^Remove (.+)$/,m=>'移除 '+m[1]]
  ,[/^(.+) was not found\.$/,m=>'未找到 '+m[1]+'。']
  ,[/^(.+) could not be started\.$/,m=>m[1]+' 无法启动。']
  ,[/^Doctor could not finish: (.+)$/,m=>'环境诊断未能完成：'+m[1]]
  ,[/^Level (\d+)$/,m=>'等级 '+m[1]]
  ,[/^of (\d+)$/,m=>'/ '+m[1]+' 轮']
  ,[/^of (\d+) gates reached$/,m=>'/ '+m[1]+' 个关卡已到达']
  ,[/^of (\d+) steps done$/,m=>'/ '+m[1]+' 步已完成']
  ,[/^(\d+) passed review$/,m=>m[1]+' 次通过复核']
  ,[/^(\d+)s elapsed$/,m=>'已运行 '+m[1]+' 秒']
  ,[/^(\d+) events?$/,m=>m[1]+' 个事件']
  ,[/^(.+): (Complete|Blocked|Active|Pending)$/,m=>zhValue(m[1])+'：'+zhValue(m[2])]
  ,[/^([0-9a-f]{7,40}) · round (\d+)$/i,m=>m[1]+' · 第 '+m[2]+' 轮']
  ,[/^(PASS|BLOCKED|ESCALATED|ESCALATE|DCL_ONLY|NOTHING_TO_AUDIT) · (\d+) finding\(s\)$/,m=>zhValue(m[1])+' · '+m[2]+' 项发现']
  ,[/^  Add a folder under (.+)\/ with your results, then run this again\.$/,
    m=>'  在 '+m[1]+'/ 下新建一个文件夹放入你的结果，然后再运行一次。']
  ,[/^cycle (\S+) is waiting for a human$/,m=>'循环 '+m[1]+' 正在等待人工处理']
  ,[/^(\d+) tasks are waiting for your decision\.$/,m=>'有 '+m[1]+' 个任务正在等待你的决定。']
  // Composed, so it MUST be a pattern: a fixed entry would translate only the
  // threads whose titles happen to be in the dictionary and leave every other
  // Chinese reader an English sentence. The title itself is not translated —
  // it is a name the person chose for their own thread.
  ,[/^CrossAudit replied in (.+)\.$/,m=>'CrossAudit 在「'+m[1]+'」中已回复。']
  ,[/^MCP executable (.+) was not found or is not executable$/,m=>'未找到 MCP 可执行文件 '+m[1]+'，或它不可执行']
  ,[/^MCP server could not start: (.+)$/,m=>'MCP 服务器无法启动：'+m[1]]
  ,[/^MCP server closed its input\.(.*)$/,m=>'MCP 服务器关闭了输入。'+m[1].trim()]
  ,[/^MCP server exited before replying\.(.*)$/,m=>'MCP 服务器在回复前已退出。'+m[1].trim()]
  ,[/^MCP server returned HTTP (\d+)$/,m=>'MCP 服务器返回 HTTP '+m[1]]
  ,[/^MCP server connection failed: (.+)$/,m=>'MCP 服务器连接失败：'+m[1]]
  ,[/^MCP server negotiated unsupported protocol (.+)$/,m=>'MCP 服务器协商了不受支持的协议 '+m[1]]
  ,[/^MCP (\S+) failed: (.+)$/,m=>'MCP '+m[1]+' 失败：'+m[2]]
  ,[/^MCP (\S+) returned an invalid result$/,m=>'MCP '+m[1]+' 返回了无效结果']
  ,[/^MCP calls per task must be between 1 and (\d+)$/,m=>'MCP 每任务调用次数必须在 1 到 '+m[1]+' 之间']
  ,[/^macOS Keychain refused the MCP credential: (.+)$/,m=>'macOS 钥匙串拒绝了 MCP 凭据：'+m[1]]
  ,[/^(.+) — the cancelled connection is still listed; remove it there\.$/,m=>zhValue(m[1])+' —— 已取消的连接仍在列表中，请在那里将其移除。']
  ,[/^All (\d+) checks? passed on the latest round\.$/,m=>'最近一轮的 '+m[1]+' 项检查全部通过。']
  ,[/^(\d+) of (\d+) checks? did not pass on the latest round\.$/,m=>'最近一轮中有 '+m[1]+' 项检查未通过。']
  ,[/^(\d+) of (\d+) checks? (?:has|have) not run on the latest round\.$/,m=>'最近一轮中有 '+m[1]+' 项检查尚未运行。']
  ,[/^(\d+) checks? passed, (\d+) had nothing to check\.$/,m=>m[1]+' 项检查通过，'+m[2]+' 项没有可检查的内容。']
  ,[/^(.+): (passed|did not pass|not run yet|nothing to check)$/,m=>m[1]+'：'
    +({passed:'已通过','did not pass':'未通过','not run yet':'尚未运行','nothing to check':'没有可检查的内容'})[m[2]]]
];
let currentLocale='en';
const textSources=new WeakMap(),attributeSources=new WeakMap();
function storedLocale(){try{const row=document.cookie.split(';').map(value=>value.trim())
    .find(value=>value.startsWith(LOCALE_COOKIE+'='));if(row)return decodeURIComponent(row.slice(LOCALE_COOKIE.length+1));}catch(e){}
  try{return localStorage.getItem(LOCALE_KEY);}catch(e){return null;}}
function zhValue(value){const exact=ZH[value];if(exact)return exact;for(const [pattern,replace] of ZH_PATTERNS){const match=value.match(pattern);if(match)return replace(match);}return value;}
function translatePreservingSpace(value){const match=String(value).match(/^(\s*)([\s\S]*?)(\s*)$/);return match[1]+zhValue(match[2])+match[3];}
function renderLocaleText(node){if(!node.parentElement||['SCRIPT','STYLE'].includes(node.parentElement.tagName))return;
  let source=textSources.get(node);const translated=source===undefined?'':translatePreservingSpace(source);
  if(source===undefined||(node.data!==source&&node.data!==translated)){source=node.data;textSources.set(node,source);}
  const wanted=currentLocale==='zh'?translatePreservingSpace(source):source;if(node.data!==wanted)node.data=wanted;}
function renderLocaleAttributes(element){const names=['placeholder','title','aria-label'];let sources=attributeSources.get(element)||{};
  for(const name of names){if(!element.hasAttribute(name))continue;const value=element.getAttribute(name);const old=sources[name];
    if(old===undefined||(value!==old&&value!==zhValue(old)))sources[name]=value;const wanted=currentLocale==='zh'?zhValue(sources[name]):sources[name];
    if(value!==wanted)element.setAttribute(name,wanted);}attributeSources.set(element,sources);}
function localizeTree(root){if(root.nodeType===Node.TEXT_NODE){renderLocaleText(root);return;}if(root.nodeType!==Node.ELEMENT_NODE&&root!==document.body)return;
  if(root.nodeType===Node.ELEMENT_NODE)renderLocaleAttributes(root);const walker=document.createTreeWalker(root,NodeFilter.SHOW_ELEMENT|NodeFilter.SHOW_TEXT);
  while(walker.nextNode()){const node=walker.currentNode;if(node.nodeType===Node.TEXT_NODE)renderLocaleText(node);else renderLocaleAttributes(node);}}
function applyLocale(locale,remember=true){currentLocale=locale==='zh'?'zh':'en';document.documentElement.lang=currentLocale==='zh'?'zh-CN':'en';
  // decision-locale: the Decision Center makes the shell inert (setDecidingInert),
  // so the top bar toggle is unreachable while a card is open; the card header
  // carries its own, the same control under a third id.
  for(const id of ['locale-toggle','hub-locale','decision-locale']){const button=document.getElementById(id);if(!button)continue;button.textContent=currentLocale==='zh'?'EN':'中文';
    button.setAttribute('aria-label',currentLocale==='zh'?'切换到英文':'Switch to Chinese');button.title=currentLocale==='zh'?'切换到英文':'Switch language';}
  localizeTree(document.body);if(remember){try{localStorage.setItem(LOCALE_KEY,currentLocale);}catch(e){}
    document.cookie=LOCALE_COOKIE+'='+encodeURIComponent(currentLocale)+'; Path=/; Max-Age=31536000; SameSite=Strict';}
  // Copy localised on the wire (event text_i18n / summary_i18n) is chosen when a
  // row is rendered, so the text-node translator cannot reach it by design.
  // Re-render so those rows follow the locale from every entry point. The guard
  // is a try/catch because this also runs during boot, before `lastState` is
  // initialised, where touching it would raise.
  try{if(lastState)render(lastState);}catch(e){}}
const localeObserver=new MutationObserver(records=>{for(const record of records){if(record.type==='characterData')renderLocaleText(record.target);
  else if(record.type==='attributes')renderLocaleAttributes(record.target);else for(const node of record.addedNodes)localizeTree(node);}});
localeObserver.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['placeholder','title','aria-label']});
document.getElementById('locale-toggle').onclick=()=>applyLocale(currentLocale==='zh'?'en':'zh');
document.getElementById('hub-locale').onclick=document.getElementById('locale-toggle').onclick;
document.getElementById('decision-locale').onclick=document.getElementById('locale-toggle').onclick;
applyLocale(storedLocale()==='zh'?'zh':'en',false);
// SPEC-9 §2.1 — one polite region for the whole console, written IN PLACE.
// Progress-class changes call this with a SENTENCE, never a value: a live
// region that reads a bare counter is a riddle; "Round 2 of 3 started" is not.
// Interrupt-class surfaces keep role="alert" on their own inserted node.
//
// Two things stop it becoming noise, and both are the point of this slice:
// re-announcing the SAME sentence is suppressed outright, because a render that
// re-states the state it already stated is not news; and a burst of stream
// events inside one frame is coalesced into the last sentence rather than
// spoken in sequence. The render loop polls every 2s and the stream can fire
// several times between frames, so without both a person hears the transcript
// on a loop.
let announcedText='';let announceTimer=null;
// SPEC-9, the locale-timing rule as a MECHANISM rather than a habit.
//
// Every live region has the same problem the announcer has, not just the
// announcer itself: it announces what IS there, not what is about to be.
// Writing an English source into one and letting the locale observer translate
// it a microtask later means a Chinese reader is SPOKEN the English while the
// screen shows Chinese.
//
// Measured, not reasoned about. Driving frUpdateIndependence — the function
// this page itself uses for the first-run provider step — in a Chinese page,
// and sampling the role=alert node #fr-role-msg at the write, at the next
// microtask and after a task, gave: English, then Chinese, then Chinese. The
// alert fires on the first of those. The sweep found nine live regions with
// this shape; two writes carried a string with a translation, both here.
//
// So: write, then translate in the SAME TASK. The English source is still what
// was written, so a later locale switch re-translates it the ordinary way —
// driven and confirmed, zh then en then zh, not assumed. One function rather
// than a rule each caller has to remember, because the defect this closes is
// precisely a canonicalisation applied at one point and not at the next.
//
// R2 CORRECTION, and it is the reason this comment is long. Write-then-
// translate-in-the-same-task was NOT the rule. It closed the microtask window
// and left the defect: the node still HELD the English source first, because
// the write and the translation are two separate mutations of the same node,
// and a live-region notification fires on the first one. The cross-vendor
// auditor drove it and recorded exactly that —
//   CrossAudit replied.  ->  CrossAudit 已回复。
// — while my guard, which inspected source ORDER, went green. Ordering is a
// claim about the code; the property is about the values the node held.
//
// So the rule is now: the live region is MUTATED ONCE, and the value it takes
// is already in the active locale. Build the content in a detached element —
// invisible to the locale observer and to assistive technology, so nothing
// there is announced — run localizeTree, the product own translator, over it
// there, and move the finished nodes in with a single replaceChildren.
//
// Translating in the holder rather than re-deriving the string is deliberate:
// the same text nodes are MOVED into the live region, carrying the `textSources`
// entries renderLocaleText recorded for them. That is what keeps the English
// source alive, so a later locale switch re-translates the ordinary way instead
// of freezing the region in whichever language it was born in. Driven zh -> en
// -> zh; the full English sentence returns.
function liveFragment(fill){
  const holder=document.createElement('div');
  fill(holder);
  if(typeof localizeTree==='function')localizeTree(holder);
  return holder;}
function liveText(node,value){
  if(!node)return;
  const holder=liveFragment(h=>{h.textContent=String(value==null?'':value);});
  node.replaceChildren(...holder.childNodes);}
function liveHTML(node,markup){
  if(!node)return;
  const holder=liveFragment(h=>{h.innerHTML=String(markup==null?'':markup);});
  node.replaceChildren(...holder.childNodes);}
// R2, and this is the SECOND cause of the silent-reply finding the auditor
// raised. The first was a lossy identity key; fixing it was not enough, and
// the browser drive is what showed that.
//
// Re-announcing the same sentence is suppressed outright: a correct rule
// about a STATE. `Round 2 of 3 started` restated is not news. But it is the
// wrong rule for an EVENT: `CrossAudit replied in Alpha analysis.` a second
// time means a SECOND reply, and that is exactly the news. Applied to an event,
// a state rule silences every arrival after the first — not only the ones whose
// keys collided, which is why the key fix alone left the region unmutated.
//
// So the caller says which it is. Default stays `state`, because the progress
// and panel announcements of slices 3-6 are states and must keep the
// suppression that stops a 2-second render loop becoming speech.
//
// Repeating an identical sentence has to be a REAL change to the region or a
// screen reader that compares content has nothing to notice, so an event clears
// first. An empty live region is not announced, and the empty string has no
// language, so this cannot reintroduce the wrong-locale value the other half of
// this rule exists to prevent. What a specific assistive technology vocalises is
// beyond what has been driven here; the DOM contract, one mutation per real
// arrival carrying the arrival sentence in the language being read, is what is
// established.
function announce(sentence,kind){
  const text=String(sentence==null?'':sentence).trim();
  if(!text)return false;
  const event=kind==='event';
  if(!event&&text===announcedText)return false;
  announcedText=text;
  if(announceTimer)clearTimeout(announceTimer);
  announceTimer=setTimeout(()=>{announceTimer=null;
    // Through the same helper as every other live region, so the rule has one
    // implementation and cannot hold true here while drifting elsewhere.
    const node=document.getElementById('announcer');
    if(event)liveText(node,'');
    liveText(node,text);},120);
  return true;}
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const at = t => t ? new Date(t*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '';
// Locale selection for wire-localised event copy. Agent B ships {en, zh} on the
// event itself precisely so the page never has to re-translate prose or match
// text nodes; this reads the active locale and falls back to the plain field.
const localeText = (bundle, base) => {
  const pair = bundle || {};
  return String(pair[currentLocale] || pair.en || base || '');
};
// Short UI words this consumer adds itself still go through the dictionary.
const t = value => currentLocale==='zh' ? zhValue(value) : value;
const MARK = {done:'✓',failed:'×',current:'·',pending:''};
let lastState = null;
let pendingContinuation={cycle:'',chat:''};
let pendingFiles = [];
let uploadProgress = new Map();
let transferBusy = false;
let activeView = 'artifacts';
let newTaskMode = false;
let activeChatId = '';
// The message the user just sent, shown optimistically (with a working
// indicator) the instant they press Enter — so the thread reacts immediately
// like Codex, while routing + the first model token are still in flight. It is
// cleared the moment the real state takes over (a live run, or the message
// echoed back in the stream) or the send is refused / needs clarification.
let optimisticSend = null;
// D150. The message the server accepted and is still handling (routing, then
// the lane) — its id, so a finished intake is applied exactly once — and the
// lane reply arriving live through named intake_chunk frames.
let pendingIntake=null;
let liveReply=null;
let archivedExpanded = false;
const expandedGroups = new Set();
const expandedReviews = new Set();
let lastPillKey = '';
let handoffDirection = '';
let handoffAt = 0;
// Relative time in words. Every relative age or duration a person reads goes
// through one of these three, in English; the catalogue turns each shape into
// Chinese by pattern. A raw seconds count ("205214s ago") is never rendered.
function relAge(seconds){const s=Math.max(0,Math.floor(Number(seconds)||0));
  if(s<60)return 'just now';if(s<3600)return Math.floor(s/60)+' min ago';
  if(s<86400)return Math.floor(s/3600)+' h ago';const d=Math.floor(s/86400);return d+(d===1?' day ago':' days ago');}
function durationText(seconds){const s=Math.max(0,Math.floor(Number(seconds)||0));
  if(s<60)return s+' s';if(s<3600)return Math.floor(s/60)+' min';return Math.floor(s/3600)+' h';}
function elapsedText(seconds){const s=Math.max(0,Math.floor(Number(seconds)||0));
  if(s<60)return s+'s elapsed';if(s<3600)return Math.floor(s/60)+'m '+(s%60)+'s elapsed';
  return Math.floor(s/3600)+'h '+Math.floor(s%3600/60)+'m elapsed';}
// The runtime writes "no heartbeat for 205214s" into an event detail; read it
// back in words before it reaches the screen.
function humaniseDetail(text){const m=/^no heartbeat for (\d+)s$/.exec(String(text||''));return m?'no heartbeat for '+durationText(m[1]):text;}
function ago(t){if(!t)return '';return relAge(Date.now()/1000-Number(t));}
const USER_STATES={DRAFT:'understand',QUEUED:'understand',GENERATING:'work',
  WAITING_FOR_PROVIDER:'work',WAITING_FOR_CAPABILITY:'work',AUDITING:'check',
  REVISING:'revise',PASSED:'done',WAITING_FOR_HUMAN:'decide',
  PROVIDER_UNAVAILABLE:'decide'};
const STATE_LABELS={understand:'Understanding',work:'Working',check:'Checking',
  revise:'Revising',done:'Completed',decide:'Needs your decision'};

const THEME_KEY = 'crossaudit-theme';
const themeButton = document.getElementById('theme-toggle');
const hubThemeButton = document.getElementById('hub-theme');
function storedTheme(){try{return localStorage.getItem(THEME_KEY);}catch(e){return null;}}
function applyTheme(theme, remember){
  const value = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme',value);
  themeButton.textContent = value === 'dark' ? '☀' : '◐';
  hubThemeButton.textContent = themeButton.textContent;
  themeButton.setAttribute('aria-label',value === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  themeButton.title = value === 'dark' ? 'Use light theme' : 'Use dark theme';
  if(remember){try{localStorage.setItem(THEME_KEY,value);}catch(e){}}
}
const savedTheme = storedTheme();
const systemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
applyTheme(savedTheme || (systemDark ? 'dark' : 'light'),false);
themeButton.onclick = () => applyTheme(
  document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark',true);
hubThemeButton.onclick = themeButton.onclick;

const composerWrap=document.querySelector('.composer-wrap');
const threadScroller=document.getElementById('thread');
function syncComposerClearance(){
  const nearBottom=threadScroller.scrollHeight-threadScroller.scrollTop-threadScroller.clientHeight<96;
  const clearance=composerWrap.classList.contains('view-hidden')?0:Math.ceil(composerWrap.getBoundingClientRect().height);
  document.documentElement.style.setProperty('--composer-clearance',clearance+'px');
  if(nearBottom)requestAnimationFrame(()=>{threadScroller.scrollTop=threadScroller.scrollHeight;});
}
new ResizeObserver(syncComposerClearance).observe(composerWrap);
window.addEventListener('resize',syncComposerClearance);
syncComposerClearance();

// The sentence of a refusal, in the language of the page. The server attaches
// `reason_zh` beside `reason`, looked up by the reason the Denial carries (never by
// its wording); a body without it renders the English, which the catalogue
// below then translates where it can — exactly what happened before.
function denialText(data){
  if(!data||typeof data!=='object')return '';
  return (currentLocale==='zh'&&data.reason_zh)||data.reason||'';}
async function api(path, body){
  const opt = body ? {method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify(body)} : {};
  const r = await fetch(path + '?t=' + encodeURIComponent(T), opt);
  const text=await r.text();let data=null;try{data=text?JSON.parse(text):{};}catch(e){}
  if(!r.ok){const error=new Error(denialText(data)||text||('Request failed ('+r.status+')'));
    if(data&&typeof data==='object')Object.assign(error,data);throw error;}
  return data||{};
}

let workspacePickerContext='project',selectedProjectFolder='';
function updateWorkspaceFields(path){
  const value=path||(currentLocale==='zh'?'未选择':'Not selected');
  document.getElementById('project-workspace').value=selectedProjectFolder;
  document.getElementById('settings-workspace').value=value;
  document.getElementById('project-path-preview').textContent=selectedProjectFolder
    ?'Local project: '+selectedProjectFolder
    :'Choose the exact folder CrossAudit should use. The project name will not create another subfolder.';
}
function workspaceError(message){
  const id=workspacePickerContext==='settings'?'settings-error':'wizard-error';
  const box=document.getElementById(id);box.textContent=message;box.className='wizard-error on';
}
function showInlineError(id,error){
  const box=document.getElementById(id),message=error&&error.message?error.message:String(error||'Something went wrong');
  box.innerHTML=esc(message)+(error&&error.url?' <a href="'+esc(error.url)+'" target="_blank" rel="noopener">Open help ↗</a>':'');
  box.className='wizard-error on';
}
function chooseWorkspace(context){
  workspacePickerContext=context;
  const current=(context==='project'?selectedProjectFolder:'')||
    (projectState&&projectState.workspace)||document.getElementById('settings-workspace').value||'';
  const bridge=window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.crossaudit;
  if(!bridge){workspaceError('Use the CrossAudit macOS app to choose a local folder. The browser console cannot read arbitrary folder paths.');return;}
  bridge.postMessage({action:'chooseWorkspace',current});
}
function revealProjectFolder(path){
  const bridge=window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.crossaudit;
  if(!bridge||!path)return false;
  bridge.postMessage({action:'revealInFinder',path});return true;
}
window.crossauditWorkspaceSelected=async choice=>{
  if(!choice||!choice.path)return;
  try{const result=await api('/api/workspace/select',{path:choice.path});
    if(workspacePickerContext==='project')selectedProjectFolder=result.workspace;
    if(projectState)projectState.workspace=result.workspace;updateWorkspaceFields(result.workspace);syncProjectReview();
    await refreshProjects();
  }catch(e){showInlineError(workspacePickerContext==='settings'?'settings-error':'wizard-error',e);}
};

const settingsModal=document.getElementById('settings-modal');
const settingsForm=document.getElementById('settings-form');
let settingsSource=null;let settingsState=null;
let activeSettingsPanel='general';
const SETTINGS_PANELS=['general','providers','agent','audit','files','github','compute','integrations','usage','security','diagnostics','advanced'];
const SETTINGS_INDEX=[
  {panel:'general',group:'General',label:'General',heading:'Language and appearance',purpose:'Choose how CrossAudit looks and reads on this Mac.'},
  {panel:'general',group:'General',label:'Appearance',anchor:'settings-appearance',keywords:'theme light dark'},
  {panel:'general',group:'General',label:'Language',anchor:'settings-language',keywords:'locale english chinese'},
  {panel:'providers',group:'Providers',label:'Providers',heading:'Connect the services you use',purpose:'Open only the provider you want to configure. Existing secrets are never displayed again.'},
  {panel:'providers',group:'Providers',label:'Credentials',anchor:'provider-credentials',keywords:'api key openai anthropic keychain validation fallbacks models'},
  {panel:'agent',group:'Agent behavior',label:'Agent behavior',heading:'Permissions and per-project defaults',purpose:'How the generator and independent auditor are set up, and how many rounds run before CrossAudit pauses.'},
  {panel:'agent',group:'Agent behavior',label:'Revision rounds',anchor:'settings-open-runtime',keywords:'reasoning effort roles max rounds clarification'},
  {panel:'agent',group:'Agent behavior',label:'Permissions',anchor:'settings-permissions',keywords:'permissions writes edit files commands allowlist authorization 权限 编辑 文件 命令 授权 写入'},
  {panel:'audit',group:'Audit',label:'Audit',heading:'Constitution and audit rules',purpose:'The rules that govern every audit, and the guarantees CrossAudit always enforces.'},
  {panel:'files',group:'Files',label:'Files',heading:'Local storage',purpose:'Where CrossAudit keeps projects on this Mac.'},
  {panel:'files',group:'Files',label:'Project workspace',anchor:'settings-workspace',keywords:'storage folder indexing preview temp large file'},
  {panel:'github',group:'GitHub',label:'GitHub',heading:'GitHub delivery',purpose:'The GitHub connection used to deliver and audit work.'},
  {panel:'compute',group:'Compute',label:'Compute',heading:'Remote compute',purpose:'SSH hosts and the limits on how the generator may use them.'},
  {panel:'compute',group:'Compute',label:'SSH hosts',keywords:'scheduler slurm transfer policy'},
  {panel:'integrations',group:'Integrations',label:'Integrations',heading:'MCP, skills, and tools',purpose:'Capabilities the generator can call while it works.'},
  {panel:'integrations',group:'Integrations',label:'MCP servers',keywords:'skills tools 技能 工具 服务器 连接器'},
  {panel:'integrations',group:'Integrations',label:'Skills',anchor:'settings-open-skills',keywords:'skills manage install guidance 技能 管理 安装 指导'},
  {panel:'usage',group:'Usage',label:'Usage',heading:'Usage and budgets',purpose:'Token and cost estimates, and the limits that pause a run.'},
  {panel:'usage',group:'Usage',label:'Budgets',keywords:'estimate cost tokens export'},
  {panel:'security',group:'Security & privacy',label:'Security & privacy',heading:'Security and privacy',purpose:'How credentials are stored and where your data goes.'},
  {panel:'security',group:'Security & privacy',label:'Keychain',keywords:'retention redaction logs provider routing privacy'},
  {panel:'diagnostics',group:'Diagnostics',label:'Diagnostics',heading:'Diagnostics',purpose:"Check this Mac's setup and versions, and repair problems."},
  {panel:'diagnostics',group:'Diagnostics',label:'Environment Doctor',anchor:'run-doctor',keywords:'versions repair support bundle reset logs'},
  {panel:'advanced',group:'Advanced',label:'Advanced',heading:'Advanced',purpose:'Developer and experimental options.'}
];
function settingsSearchMatch(entry,q){
  const n=String(q||'').trim().toLowerCase();if(!n)return true;
  // Match the English index AND its Chinese translations, so 中文搜索也能命中.
  const fields=[entry.group,entry.heading,entry.purpose,entry.label,entry.keywords];
  if(fields.some(v=>String(v||'').toLowerCase().indexOf(n)>=0))return true;
  const zh=typeof zhValue==='function'?zhValue:(v=>v);
  return fields.some(v=>String(zh(String(v||''))).toLowerCase().indexOf(n)>=0);
}
// Rank by how specifically the entry answers the query. Without this the
// group row (which repeats the group name in every field) always outranks the
// individual control, so searching "Appearance" opened General at the top of
// the pane instead of the Appearance control.
function settingsSearchScore(entry,q){
  const n=String(q||'').trim().toLowerCase();if(!n)return 0;
  const zh=typeof zhValue==='function'?zhValue:(v=>v);
  const forms=value=>{const raw=String(value||'').toLowerCase();
    return [raw,String(zh(String(value||''))).toLowerCase()];};
  const rank=(value,exact,prefix,partial)=>{let best=0;
    for(const form of forms(value)){if(!form)continue;
      if(form===n)best=Math.max(best,exact);
      else if(form.startsWith(n))best=Math.max(best,prefix);
      else if(form.indexOf(n)>=0)best=Math.max(best,partial);}
    return best;};
  let score=rank(entry.label,1000,700,400);
  score+=rank(entry.keywords,0,0,150);
  score+=rank(entry.heading,0,0,80);
  score+=rank(entry.purpose,0,0,40);
  score+=rank(entry.group,0,0,20);
  // A leaf control beats the group overview row on an equal textual hit.
  if(entry.anchor)score+=60;
  if(entry.heading)score-=30;
  return score;
}
function filterSettings(){
  const input=document.getElementById('settings-search');const q=input?input.value:'';
  const results=document.getElementById('settings-search-results');
  const content=document.getElementById('settings-content');
  const buttons=document.querySelectorAll('[data-settings-panel]');
  if(!String(q||'').trim()){
    results.hidden=true;results.innerHTML='';content.classList.remove('searching');
    buttons.forEach(b=>b.classList.remove('dim'));
    document.querySelectorAll('[data-settings-pane]').forEach(p=>p.hidden=p.dataset.settingsPane!==activeSettingsPanel);
    return;
  }
  content.classList.add('searching');
  document.querySelectorAll('[data-settings-pane]').forEach(p=>p.hidden=true);
  const matches=SETTINGS_INDEX.filter(e=>settingsSearchMatch(e,q))
    .map((entry,order)=>({entry,order,score:settingsSearchScore(entry,q)}))
    .sort((a,b)=>b.score-a.score||a.order-b.order).map(row=>row.entry);
  const groups=new Set(matches.map(e=>e.panel));
  buttons.forEach(b=>b.classList.toggle('dim',!groups.has(b.dataset.settingsPanel)));
  results.innerHTML=matches.length?matches.map((e,index)=>
    '<button type="button" role="option" id="settings-result-'+index+'" aria-selected="'+(index===0)+'"'
    +' class="settings-result'+(index===0?' active':'')+'" data-result-panel="'+esc(e.panel)+'" data-result-anchor="'+esc(e.anchor||'')+'">'
    +'<span class="settings-result-label">'+esc(e.label)+'</span>'
    +'<span class="settings-result-group">'+esc(e.group)+'</span></button>').join('')
    :'<div class="settings-result-empty">No matching settings.</div>';
  results.hidden=false;settingsResultIndex=matches.length?0:-1;syncSettingsActiveResult();
}
// The results container declares role="listbox", so it has to be operable from
// the keyboard: Down/Up move, Enter opens, Escape clears back to the pane.
let settingsResultIndex=-1;
function settingsResultRows(){return [...document.querySelectorAll('#settings-search-results [data-result-panel]')];}
function syncSettingsActiveResult(){const rows=settingsResultRows();const search=document.getElementById('settings-search');
  rows.forEach((row,index)=>{const active=index===settingsResultIndex;
    row.classList.toggle('active',active);row.setAttribute('aria-selected',String(active));
    if(active)row.scrollIntoView({block:'nearest'});});
  const current=rows[settingsResultIndex];
  if(search)search.setAttribute('aria-activedescendant',current?current.id:'');}
function openSettingsResult(row){if(!row)return;
  const panel=row.getAttribute('data-result-panel'),anchor=row.getAttribute('data-result-anchor');
  showSettingsPanel(panel,false);
  if(anchor){const el=document.getElementById(anchor);if(el){el.scrollIntoView({block:'center'});
    if(typeof el.focus==='function'){try{el.focus({preventScroll:true});}catch(e){el.focus();}}}}}
function showSettingsPanel(name,focus=true){
  const next=SETTINGS_PANELS.includes(name)?name:'general';activeSettingsPanel=next;
  const search=document.getElementById('settings-search');if(search)search.value='';
  const results=document.getElementById('settings-search-results');if(results){results.hidden=true;results.innerHTML='';}
  const content=document.getElementById('settings-content');if(content)content.classList.remove('searching');
  document.querySelectorAll('[data-settings-panel]').forEach(button=>{const active=button.dataset.settingsPanel===next;
    button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));button.classList.remove('dim');});
  document.querySelectorAll('[data-settings-pane]').forEach(pane=>pane.hidden=pane.dataset.settingsPane!==next);
  const save=document.getElementById('save-settings');save.hidden=next!=='providers';
  if(next==='usage')loadUsageRollup();
  document.getElementById('cancel-settings').textContent=currentLocale==='zh'?(next==='providers'?'取消':'完成'):(next==='providers'?'Cancel':'Done');
  document.getElementById('settings-foot-note').textContent=currentLocale==='zh'
    ?(next==='providers'?'API key 以只写方式存入 macOS 钥匙串；订阅凭据始终由官方供应商运行时持有。':'更改会立即生效；在“诊断”中可随时运行环境诊断。')
    :(next==='providers'?'API keys are write-only macOS Keychain items. Subscription credentials stay with the official provider runtime.':'Changes apply immediately. Run Doctor from Diagnostics after moving or updating this Mac.');
  if(focus)requestAnimationFrame(()=>document.querySelector('[data-settings-pane="'+next+'"]')?.focus());
}
document.querySelector('.settings-nav').onclick=ev=>{const button=ev.target.closest('[data-settings-panel]');
  if(button)showSettingsPanel(button.dataset.settingsPanel,false);};
document.getElementById('settings-search').addEventListener('input',filterSettings);
document.getElementById('settings-search-results').addEventListener('click',ev=>{
  const row=ev.target.closest('[data-result-panel]');if(!row)return;openSettingsResult(row);});
document.getElementById('settings-search').addEventListener('keydown',ev=>{
  const rows=settingsResultRows();
  if(ev.key==='Escape'){ev.preventDefault();ev.target.value='';filterSettings();return;}
  if(!rows.length)return;
  if(ev.key==='ArrowDown'){ev.preventDefault();settingsResultIndex=(settingsResultIndex+1)%rows.length;syncSettingsActiveResult();}
  else if(ev.key==='ArrowUp'){ev.preventDefault();settingsResultIndex=(settingsResultIndex-1+rows.length)%rows.length;syncSettingsActiveResult();}
  else if(ev.key==='Enter'){ev.preventDefault();openSettingsResult(rows[Math.max(settingsResultIndex,0)]);}});
const settingsAppearance=document.getElementById('settings-appearance');
const settingsLanguage=document.getElementById('settings-language');
function syncSettingsControls(){settingsAppearance.value=document.documentElement.getAttribute('data-theme')==='dark'?'dark':'light';
  settingsLanguage.value=currentLocale==='zh'?'zh':'en';}
settingsAppearance.onchange=()=>applyTheme(settingsAppearance.value==='dark'?'dark':'light',true);
settingsLanguage.onchange=()=>applyLocale(settingsLanguage.value==='zh'?'zh':'en');
document.getElementById('settings-appearance-system').onclick=()=>{try{localStorage.removeItem(THEME_KEY);}catch(e){}
  applyTheme((window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light',false);syncSettingsControls();};
document.getElementById('settings-content').addEventListener('click',ev=>{
  const b=ev.target.closest('[data-settings-open]');if(!b)return;
  const target=b.getAttribute('data-settings-open');
  if(!(lastState&&lastState.runtime_config)){
    const note=b.parentElement.querySelector('[data-scope-note]');
    if(note){note.textContent=currentLocale==='zh'?'请先打开一个项目再进行配置。':'Open a project to configure this.';note.hidden=false;}
    return;}
  closeSettings();
  if(target==='runtime')openRuntime();
  else if(target==='runtime-budgets'){openRuntime();showRuntimePanel('budgets',false);}
  else if(target==='skills')openSkillsEditor();
  else if(target==='compute')openPanelTab('compute');
  else if(target==='tools')openPanelTab('tools');
  else if(target==='usage')openPanelTab('usage');});
function renderProviderCards(d){
  const host=document.getElementById('provider-credentials');
  const vendors=Object.keys(d.providers||{}).sort((a,b)=>{const rank=vendor=>vendor==='openai'?0:(d.providers[vendor]||{}).configured?1:2;
    return rank(a)-rank(b)||String((d.providers[a]||{}).label||a).localeCompare(String((d.providers[b]||{}).label||b));});
  if(host.getAttribute('data-vendors')===vendors.join(','))return;
  host.setAttribute('data-vendors',vendors.join(','));
  host.innerHTML=vendors.map(vendor=>{const p=d.providers[vendor]||{};const label=p.label||vendor;
    const subscription=vendor==='openai'
      ?'<div class="connection-method"><div class="connection-method-copy"><b>ChatGPT subscription</b><small id="chatgpt-detail">'+esc((p.subscription||{}).detail||'Official Codex sign-in.')+'</small></div><button type="button" class="secondary" id="connect-chatgpt">Connect</button></div>'
      :'<div class="provider-note"><b>API access.</b> '+esc((p.subscription||{}).detail||'Use an official developer API key.')+'</div>';
    const links=(p.console_url?'<a class="login-link" href="'+esc(p.console_url)+'" target="_blank" rel="noopener">Get key ↗</a> ':'')
      +(p.docs_url?'<a class="login-link" href="'+esc(p.docs_url)+'" target="_blank" rel="noopener">API docs ↗</a>':'');
    return '<details class="credential-card"'+(vendor==='openai'?' open':'')+'><summary class="credential-head"><b>'+esc(label)+'</b><span class="credential-state" id="'+esc(vendor)+'-state">Checking…</span></summary><div class="credential-body">'
      +subscription+'<div class="secret-row"><label class="field"><span>New API key · '+links+'</span><input type="password" id="'+esc(vendor)+'-key" data-provider-key="'+esc(vendor)+'" autocomplete="new-password" placeholder="Leave blank to keep the saved key"></label>'
      +'<label class="toggle-line"><input type="checkbox" id="remove-'+esc(vendor)+'" data-provider-remove="'+esc(vendor)+'"><span><b>Remove</b><small>Delete saved key</small></span></label></div>'
      +'<div class="secret-row"><label class="field"><span>Backup API key (optional)</span><input type="password" id="'+esc(vendor)+'-backup-key" data-provider-key="'+esc(vendor)+'_backup" autocomplete="new-password" placeholder="Used only by an explicit fallback route"></label>'
      +'<label class="toggle-line"><input type="checkbox" id="remove-'+esc(vendor)+'-backup" data-provider-remove="'+esc(vendor)+'_backup"><span><b>Remove</b><small>Delete backup key</small></span></label></div></div></details>';
  }).join('');
}
function renderDoctor(doctor){
  const value=doctor||{};const status=value.status||'idle';
  const state=document.getElementById('doctor-state');state.className='doctor-state '+status;
  document.getElementById('doctor-summary').textContent=value.summary||'Environment has not been checked';
  const run=document.getElementById('run-doctor');run.disabled=status==='running';
  run.textContent=status==='running'?'Checking…':'Run check';
  const rows=Array.isArray(value.checks)?value.checks:[];
  const marks={ready:'✓',missing:'!',outdated:'↑',warning:'!',unknown:'?',waiting:'·'};
  document.getElementById('doctor-checks').innerHTML=rows.length?rows.map(row=>{
    const repair=row.repair||{};let action='';
    if(repair.inputs){
      action='<div class="doctor-action"><div class="doctor-identity"><input data-doctor-name maxlength="100" aria-label="Git author name" placeholder="Git author name"><input data-doctor-email type="email" maxlength="200" aria-label="Git author email" placeholder="Git author email"><button type="button" class="secondary" data-doctor-action="'+esc(repair.action)+'">'+esc(repair.label||'Save')+'</button></div></div>';
    }else if(repair.url){
      action='<div class="doctor-action"><a class="secondary" href="'+esc(repair.url)+'" target="_blank" rel="noopener">'+esc(repair.label||'Open help')+'<span aria-hidden="true"> ↗</span></a></div>';
    }else if(repair.action){
      action='<div class="doctor-action"><button type="button" class="secondary" data-doctor-action="'+esc(repair.action)+'">'+esc(repair.label||'Fix')+'</button></div>';
    }
    const version=row.version?'<span class="doctor-version">v'+esc(row.version)+'</span>':'';
    const why=row.why?'<small class="doctor-why">'+esc(row.why)+'</small>':'';
    return '<div class="doctor-check '+esc(row.status||'unknown')+'"><span class="doctor-mark">'+(marks[row.status]||'?')+'</span><div class="doctor-copy"><b>'+esc(row.label||row.id)+'</b><small>'+esc(row.detail||'')+'</small>'+why+'</div>'+version+action+'</div>';
  }).join(''):'<div class="doctor-empty">'+(status==='running'?'Checking required software…':'Run the check to inspect this Mac.')+'</div>';
  const panel=document.querySelector('.doctor-panel'),toggle=document.getElementById('toggle-doctor-details');
  if(['blocked','failed','attention'].includes(status))panel.classList.add('expanded');
  const expanded=panel.classList.contains('expanded');toggle.setAttribute('aria-expanded',String(expanded));
  toggle.textContent=currentLocale==='zh'?(expanded?'隐藏详情':'显示详情'):(expanded?'Hide details':'Show details');
}
function renderSettings(d){
  settingsState=d;
  const wwToggle=document.getElementById('workspace-writes-toggle');
  if(wwToggle){
    wwToggle.checked=!!(d.authorizations&&d.authorizations.workspace_writes);
    if(!wwToggle._wired){wwToggle._wired=true;wwToggle.onchange=async function(){
      const want=this.checked;
      try{const r=await api('/api/authorization',{enabled:want});this.checked=!!(r&&r.workspace_writes);}
      catch(e){this.checked=!want;}
    };}
  }
  const cmdInput=document.getElementById('allowed-commands-input');
  if(cmdInput){
    const current=(d.authorizations&&d.authorizations.allowed_commands)||[];
    if(document.activeElement!==cmdInput) cmdInput.value=current.join(', ');
    if(!cmdInput._wired){cmdInput._wired=true;cmdInput.onchange=async function(){
      const list=this.value.split(/[,\n]/).map(s=>s.trim()).filter(Boolean);
      try{const r=await api('/api/authorization',{allowed_commands:list});
        this.value=((r&&r.allowed_commands)||[]).join(', ');}
      catch(e){}
    };}
  }
  renderProviderCards(d);
  for(const vendor of Object.keys(d.providers||{})){
    const provider=d.providers&&d.providers[vendor]||{};
    const apiConfigured=Boolean(provider.api_key&&provider.api_key.configured);
    const configured=Boolean(provider.configured);
    const state=document.getElementById(vendor+'-state');state.textContent=configured?'Connected':'Not connected';
    state.className='credential-state'+(configured?' ok':'');
    document.getElementById('remove-'+vendor).disabled=!apiConfigured;
    document.getElementById('remove-'+vendor+'-backup').disabled=!Boolean(provider.backup_api_key&&provider.backup_api_key.configured);
  }
  const openai=d.providers&&d.providers.openai||{};const chatgpt=openai.chatgpt||{};
  const login=d.provider_login||{};const button=document.getElementById('connect-chatgpt');
  const detail=document.getElementById('chatgpt-detail');
  // The subscription block only renders when the provider payload offers it;
  // a missing element must degrade to "no block", never crash the whole pane.
  if(detail&&button)
  if(chatgpt.connected){
    detail.textContent='Connected'+(chatgpt.email?' as '+chatgpt.email:'')+(chatgpt.plan?' · '+chatgpt.plan:'')
      +'. Usage follows this ChatGPT workspace and plan.';button.textContent='Connected';button.disabled=true;
  }else if(login.status==='running'){
    detail.innerHTML=esc(login.detail||'Complete sign-in in your browser')
      +(login.url?' · <a class="login-link" href="'+esc(login.url)+'">Open ChatGPT ↗</a>':'');
    button.textContent='Waiting…';button.disabled=true;
  }else{
    detail.textContent=chatgpt.detail||'Use the official Codex login and an eligible ChatGPT plan. CrossAudit never receives the OAuth token.';
    button.textContent=login.status==='failed'?'Try again':'Connect';button.disabled=!chatgpt.available;
  }
  const deps=d.dependencies||{};const doctorRows=Object.fromEntries(((d.doctor&&d.doctor.checks)||[]).map(row=>[row.id,row]));
  for(const [id,key,value] of [['git-state','git',deps.git],['ghcli-state','github_cli',deps.github_cli],['settings-github-status','github_cli',deps.github_cli]]){
    const el=document.getElementById(id),row=doctorRows[key];const status=row&&row.status;
    el.textContent=status==='outdated'?'Outdated':status==='missing'?'Missing':status==='ready'?'Ready':value?'Ready':'Checking';
    el.className=status==='outdated'||status==='missing'||(!status&&!value)?'bad':'';
  }
  updateWorkspaceFields(d.workspace||'Not selected');
  const runtime=d.runtime||{};document.getElementById('runtime-state').textContent=runtime.install_mode||'unknown';
  document.getElementById('digest-state').textContent=runtime.code_digest||'unavailable';
  const providerRows=Object.values(d.providers||{}),connected=providerRows.filter(row=>row.configured).length;
  document.getElementById('settings-provider-count').textContent=connected+'/'+providerRows.length;
  const doctorStatus=d.doctor&&d.doctor.status||'idle';const diagnosticsState=document.getElementById('settings-diagnostics-state');
  diagnosticsState.textContent=['blocked','failed'].includes(doctorStatus)?'!':doctorStatus==='attention'?'1':doctorStatus==='ready'?'✓':'…';
  diagnosticsState.className=['blocked','failed'].includes(doctorStatus)?'bad':doctorStatus==='attention'?'attention':doctorStatus==='ready'?'ok':'';
  renderDoctor(d.doctor);
}
async function openSettings(panel){
  const requested=typeof panel==='string'?panel:'general';showSettingsPanel(requested,false);syncSettingsControls();
  settingsModal.className='project-modal on';document.getElementById('settings-error').className='wizard-error';
  try{renderSettings(await api('/api/settings'));if(!settingsSource){
    settingsSource=new EventSource('/api/settings/stream?t='+encodeURIComponent(T));
    settingsSource.onmessage=ev=>{try{renderSettings(JSON.parse(ev.data));}catch(e){}};
    settingsSource.onerror=()=>{};
  }}catch(e){const box=document.getElementById('settings-error');
    box.textContent=e.message;box.className='wizard-error on';}
}
function closeSettings(){settingsModal.className='project-modal';settingsForm.reset();}
document.getElementById('settings-open').onclick=openSettings;
document.getElementById('hub-settings').onclick=openSettings;
document.getElementById('close-settings').onclick=closeSettings;
document.getElementById('cancel-settings').onclick=closeSettings;
document.getElementById('choose-settings-workspace').onclick=()=>chooseWorkspace('settings');
document.getElementById('toggle-doctor-details').onclick=()=>{const panel=document.querySelector('.doctor-panel');
  panel.classList.toggle('expanded');const expanded=panel.classList.contains('expanded'),button=document.getElementById('toggle-doctor-details');
  button.setAttribute('aria-expanded',String(expanded));button.textContent=currentLocale==='zh'?(expanded?'隐藏详情':'显示详情'):(expanded?'Hide details':'Show details');};
function doctorMessage(text,bad=false){const box=document.getElementById('doctor-message');box.textContent=text||'';
  box.className='doctor-message'+(text?' on':'')+(bad?' bad':'');}
document.getElementById('run-doctor').onclick=async()=>{doctorMessage('');
  try{renderDoctor(await api('/api/doctor',{action:'scan'}));}
  catch(e){doctorMessage(e.message,true);}};
document.getElementById('doctor-checks').onclick=async ev=>{
  const button=ev.target.closest('[data-doctor-action]');if(!button)return;
  const action=button.getAttribute('data-doctor-action');
  if(action==='choose_workspace'){chooseWorkspace('settings');return;}
  const payload={action};const row=button.closest('.doctor-check');
  if(action==='set_git_identity'){
    payload.name=row.querySelector('[data-doctor-name]').value.trim();
    payload.email=row.querySelector('[data-doctor-email]').value.trim();
  }
  doctorMessage('');button.disabled=true;const before=button.textContent;button.textContent='Working…';
  try{const result=await api('/api/doctor',payload);doctorMessage(result.message||'Repair started. Doctor is checking again.');
    renderSettings(await api('/api/settings'));}
  catch(e){doctorMessage(e.message,true);button.disabled=false;button.textContent=before;}
};
settingsModal.addEventListener('click',ev=>{if(ev.target===settingsModal)closeSettings();});
document.getElementById('provider-credentials').onclick=async ev=>{if(!ev.target.closest('#connect-chatgpt'))return;
  const button=document.getElementById('connect-chatgpt');const error=document.getElementById('settings-error');
  button.disabled=true;button.textContent='Starting…';error.className='wizard-error';
  try{const result=await api('/api/providers/connect',{provider:'openai',method:'chatgpt'});
    if(result.url){const link=document.createElement('a');link.href=result.url;
      document.body.appendChild(link);link.click();link.remove();}
    renderSettings(await api('/api/settings'));
  }catch(e){error.textContent=e.message;error.className='wizard-error on';button.disabled=false;button.textContent='Connect';}
};
settingsForm.onsubmit=async ev=>{ev.preventDefault();const save=document.getElementById('save-settings');
  const error=document.getElementById('settings-error');error.className='wizard-error';save.disabled=true;
  const payload={};document.querySelectorAll('[data-provider-key]').forEach(el=>payload[el.getAttribute('data-provider-key')+'_key']=el.value);
  document.querySelectorAll('[data-provider-remove]').forEach(el=>payload['remove_'+el.getAttribute('data-provider-remove')]=el.checked);
  try{const state=await api('/api/settings',payload);settingsForm.reset();renderSettings(state);
    if(projectState)configureProjectForm();}
  catch(e){error.textContent=e.message;error.className='wizard-error on';}
  save.disabled=false;};

const runtimeModal=document.getElementById('runtime-modal');
const runtimeForm=document.getElementById('runtime-form');
let runtimeRoles={};let runtimeSkills=[];let runtimeFallbackCatalog=[];let runtimeCapabilityNonce={generator:0,auditor:0};
let activeRuntimePanel='models';
function showRuntimePanel(name,focus=true){
  const allowed=['models','automation','budgets','instructions'];const next=allowed.includes(name)?name:'models';
  activeRuntimePanel=next;document.querySelectorAll('[data-runtime-panel]').forEach(button=>{
    const active=button.dataset.runtimePanel===next;button.classList.toggle('active',active);
    button.setAttribute('aria-pressed',String(active));});
  document.querySelectorAll('[data-runtime-pane]').forEach(pane=>pane.hidden=pane.dataset.runtimePane!==next);
  if(focus)requestAnimationFrame(()=>document.querySelector('[data-runtime-pane="'+next+'"]')?.focus());
}
document.querySelector('.runtime-nav').onclick=ev=>{const button=ev.target.closest('[data-runtime-panel]');
  if(button)showRuntimePanel(button.dataset.runtimePanel,false);};
// "Manage Skills" and the Integrations jump both promise the skills editor.
// It lives inside the runtime "Generator guidance" pane, so land on the editor
// itself rather than the top of a pane with a different name.
function openSkillsEditor(){openRuntime();showRuntimePanel('instructions',false);
  setTimeout(()=>{const select=document.getElementById('runtime-skill-select');
    if(!select)return;select.scrollIntoView({block:'center'});
    try{select.focus({preventScroll:true});}catch(e){select.focus();}},0);}
function runtimeEl(role,name){return document.getElementById('runtime-'+role+'-'+name);}
function runtimeModel(role){const select=runtimeEl(role,'model');return select.value==='__custom__'
  ?runtimeEl(role,'custom').value.trim():select.value;}
function renderRuntimeEfforts(role,row){const target=runtimeEl(role,'effort');const previous=target.value;
  target.innerHTML='<option value="">Automatic · provider default</option>'+(row.efforts||[]).map(item=>
    '<option value="'+esc(item.id)+'">'+esc(item.id)+' - '+esc(item.hint||'')+'</option>').join('');
  const wanted=row.reasoning_effort!==undefined?row.reasoning_effort:previous;
  if([...target.options].some(option=>option.value===wanted))target.value=wanted;else target.value='';
  runtimeEl(role,'effort-help').textContent=row.detail||((row.efforts||[]).length
    ?'Applies to the next provider request.':'This model uses its provider-controlled default.');
  target.disabled=!(row.efforts||[]).length;}
function renderRuntimeRole(role,row){runtimeRoles[role]=row;const card=runtimeEl(role,'card');
  const human=row.vendor==='human';card.classList.toggle('human',human);runtimeEl(role,'vendor').textContent=row.label||row.vendor;
  const select=runtimeEl(role,'model');const rows=row.models||[];select.innerHTML=rows.map(item=>
    '<option value="'+esc(item.id)+'">'+esc(item.id)+' - '+esc(item.hint||'available')+'</option>').join('')
    +(human?'':'<option value="__custom__">Enter a custom model ID…</option>');
  if(human){select.innerHTML='<option value="">Human-written changes</option>';select.disabled=true;
    runtimeEl(role,'custom-wrap').className='field custom-model off';runtimeEl(role,'effort').innerHTML='<option>Not applicable</option>';
    runtimeEl(role,'effort').disabled=true;runtimeEl(role,'effort-help').textContent=row.detail||'';return;}
  select.disabled=false;if([...select.options].some(option=>option.value===row.model))select.value=row.model;
  else{select.value='__custom__';runtimeEl(role,'custom').value=row.model||'';}
  runtimeEl(role,'custom-wrap').className='field custom-model'+(select.value==='__custom__'?'':' off');
  renderRuntimeEfforts(role,row);}
function fallbackChoices(role){const opposite=role==='generator'?'auditor':'generator';const blocked=(runtimeRoles[opposite]||{}).vendor;
  return runtimeFallbackCatalog.filter(row=>row.vendor!==blocked);}
function renderFallbacks(role,rows){const host=document.getElementById('runtime-'+role+'-fallbacks');const choices=fallbackChoices(role);
  if(!(rows||[]).length){host.innerHTML='<div class="fallback-empty">No fallback. A provider failure pauses safely for you.</div>';return;}
  host.innerHTML=rows.map((row,index)=>{const listId='fallback-models-'+role+'-'+index;
    const options=choices.map(item=>'<option value="'+esc(item.vendor)+'"'+(item.vendor===row.vendor?' selected':'')+'>'+esc(item.label)+(item.connected?' · connected':' · key needed')+'</option>').join('');
    const selected=choices.find(item=>item.vendor===row.vendor)||choices[0]||{models:[]};
    return '<div class="fallback-row" data-fallback-role="'+role+'"><select data-fallback-vendor aria-label="Provider">'+options+'</select>'
      +'<input data-fallback-model list="'+listId+'" maxlength="120" value="'+esc(row.model||((selected.models||[])[0]||{}).id||'')+'" aria-label="Exact model ID" placeholder="Exact model ID"><datalist id="'+listId+'">'
      +(selected.models||[]).map(model=>'<option value="'+esc(model.id)+'">'+esc(model.hint||'')+'</option>').join('')+'</datalist>'
      +'<select data-fallback-credential title="Credential"><option value="primary"'+(row.credential==='backup'?'':' selected')+'>Primary key</option><option value="backup"'+(row.credential==='backup'?' selected':'')+'>Backup key</option></select>'
      +'<button type="button" class="fallback-remove" data-remove-fallback title="Remove">×</button></div>';}).join('');}
function fallbackRows(role){return [...document.querySelectorAll('[data-fallback-role="'+role+'"]')].map(row=>({
  vendor:row.querySelector('[data-fallback-vendor]').value,model:row.querySelector('[data-fallback-model]').value.trim(),
  credential:row.querySelector('[data-fallback-credential]').value}));}
function syncRuntimeBusy(d){const busy=Boolean(d&&d.progress&&!d.progress.finished);const save=document.getElementById('save-runtime');
  save.disabled=busy;document.getElementById('save-runtime-skill').disabled=busy;document.getElementById('runtime-foot').textContent=busy
    ?'A loop is running. These controls unlock when its current model calls finish.'
    :'Automatic means the provider chooses its documented default.';}
async function updateRuntimeCapabilities(role){const model=runtimeModel(role);if(!model)return;
  const nonce=++runtimeCapabilityNonce[role];runtimeEl(role,'effort').disabled=true;
  runtimeEl(role,'effort-help').textContent='Checking this model…';
  try{const row=await api('/api/runtime/options',{role,model});if(nonce!==runtimeCapabilityNonce[role])return;
    row.models=runtimeRoles[role].models;row.reasoning_effort='';runtimeRoles[role]={...runtimeRoles[role],...row};renderRuntimeEfforts(role,row);}
  catch(e){if(nonce!==runtimeCapabilityNonce[role])return;runtimeEl(role,'effort').innerHTML='<option value="">Automatic · provider default</option>';
    runtimeEl(role,'effort').disabled=true;runtimeEl(role,'effort-help').textContent=e.message;}}
function openRuntime(){const config=lastState&&lastState.runtime_config;if(!config)return;
  document.getElementById('runtime-error').className='wizard-error';
  runtimeFallbackCatalog=config.fallback_catalog||[];
  for(const role of ['generator','auditor'])renderRuntimeRole(role,config.roles[role]);
  for(const role of ['generator','auditor'])renderFallbacks(role,(config.roles[role]||{}).fallbacks||[]);
  document.getElementById('runtime-max-rounds').value=String(config.max_rounds||lastState.max_rounds||3);
  const resilience=config.resilience||{};document.getElementById('runtime-max-attempts').value=resilience.max_attempts||3;
  document.getElementById('runtime-initial-backoff').value=resilience.initial_backoff_seconds??1;
  document.getElementById('runtime-max-backoff').value=resilience.max_backoff_seconds??20;
  document.getElementById('runtime-retry-after-cap').value=resilience.retry_after_cap_seconds??120;
  document.getElementById('runtime-circuit-failures').value=resilience.circuit_breaker_failures||3;
  document.getElementById('runtime-circuit-cooldown').value=resilience.circuit_breaker_cooldown_seconds||60;
  const budgets=config.budgets||{};document.getElementById('runtime-daily-token-warning').value=budgets.daily_token_warning||'';
  document.getElementById('runtime-daily-token-limit').value=budgets.daily_token_limit||'';
  document.getElementById('runtime-monthly-cost-warning').value=budgets.monthly_cost_warning_usd||'';
  document.getElementById('runtime-monthly-cost-limit').value=budgets.monthly_cost_limit_usd||'';
  const guard=lastState&&lastState.usage&&lastState.usage.budget||{};document.getElementById('runtime-guardrail-state').textContent=
    guard.state==='blocked'?((guard.reasons||[]).join(' ')+' '+resetWords(guard)).trim():guard.state==='warning'?(guard.warnings||[]).join(' '):'Limits are local safeguards; provider billing remains authoritative.';
  renderRuntimeBudgetNotes(guard);renderPriceRows(config.prices||[]);
  renderRuntimeSkills(config.skills||[]);
  if(config.skills_error)document.getElementById('runtime-skill-status').textContent=config.skills_error;
  showRuntimePanel('models',false);syncRuntimeBusy(lastState);runtimeModal.className='project-modal on';}
function closeRuntime(){runtimeModal.className='project-modal';runtimeForm.reset();}
for(const role of ['generator','auditor']){
  runtimeEl(role,'model').onchange=()=>{runtimeEl(role,'custom-wrap').className='field custom-model'
      +(runtimeEl(role,'model').value==='__custom__'?'':' off');if(runtimeEl(role,'model').value!=='__custom__')updateRuntimeCapabilities(role);};
  runtimeEl(role,'custom').onchange=()=>updateRuntimeCapabilities(role);
}
document.querySelectorAll('[data-add-fallback]').forEach(button=>button.onclick=()=>{const role=button.getAttribute('data-add-fallback');
  const rows=fallbackRows(role),choices=fallbackChoices(role),choice=choices.find(item=>item.vendor!==(runtimeRoles[role]||{}).vendor)||choices[0];if(!choice)return;
  rows.push({vendor:choice.vendor,model:(choice.models[0]||{}).id||'',credential:'primary'});renderFallbacks(role,rows);});
runtimeModal.addEventListener('click',ev=>{const button=ev.target.closest('[data-remove-fallback]');if(!button)return;
  const row=button.closest('[data-fallback-role]'),role=row.getAttribute('data-fallback-role');row.remove();
  if(!fallbackRows(role).length)renderFallbacks(role,[]);});
runtimeModal.addEventListener('change',ev=>{if(!ev.target.matches('[data-fallback-vendor]'))return;
  const row=ev.target.closest('[data-fallback-role]'),role=row.getAttribute('data-fallback-role'),rows=fallbackRows(role);
  const index=[...document.querySelectorAll('[data-fallback-role="'+role+'"]')].indexOf(row),choice=runtimeFallbackCatalog.find(x=>x.vendor===ev.target.value);
  if(choice)rows[index].model=(choice.models[0]||{}).id||'';renderFallbacks(role,rows);});
document.querySelectorAll('[data-runtime-refresh]').forEach(button=>button.onclick=async()=>{
  const role=button.getAttribute('data-runtime-refresh'),row=runtimeRoles[role];if(!row||row.vendor==='human')return;
  button.disabled=true;button.textContent='Refreshing…';
  try{const result=await api('/api/models/refresh',{role,vendor:row.vendor,method:row.connection,endpoint:row.endpoint||''});
    row.models=result.models.map(id=>({id,hint:'visible to this account'}));const selected=runtimeModel(role);
    renderRuntimeRole(role,{...row,model:selected});button.textContent='Models updated';}
  catch(e){showInlineError('runtime-error',e);button.textContent='Refresh failed';}
  finally{button.disabled=false;setTimeout(()=>button.textContent='Refresh models',2500);}
});
document.getElementById('runtime-open').onclick=openRuntime;
document.getElementById('close-runtime').onclick=closeRuntime;
document.getElementById('cancel-runtime').onclick=closeRuntime;
runtimeModal.addEventListener('click',ev=>{if(ev.target===runtimeModal)closeRuntime();});
function renderRuntimeSkills(rows){runtimeSkills=rows||[];const select=document.getElementById('runtime-skill-select');
  select.innerHTML='<option value="__new__">Create new guidance…</option>'+runtimeSkills.map(row=>
    '<option value="'+esc(row.name)+'">'+esc(row.name)+'</option>').join('');select.value='__new__';selectRuntimeSkill();}
function selectRuntimeSkill(){const name=document.getElementById('runtime-skill-select').value;
  const row=runtimeSkills.find(item=>item.name===name);document.getElementById('runtime-skill-name').value=row?row.name:'';
  document.getElementById('runtime-skill-name').disabled=Boolean(row);
  document.getElementById('runtime-skill-scope').value=row?(row.applies_to||[]).join(', '):'';
  document.getElementById('runtime-skill-body').value=row?row.body:'';
  document.getElementById('runtime-skill-status').textContent=row?'Editing committed guidance':'Create reusable project guidance';}
document.getElementById('runtime-skill-select').onchange=selectRuntimeSkill;
document.getElementById('save-runtime-skill').onclick=async()=>{const button=document.getElementById('save-runtime-skill');
  const error=document.getElementById('runtime-error');error.className='wizard-error';button.disabled=true;
  const payload={name:document.getElementById('runtime-skill-name').value.trim(),
    applies_to:document.getElementById('runtime-skill-scope').value.split(',').map(x=>x.trim()).filter(Boolean),
    body:document.getElementById('runtime-skill-body').value};
  try{const result=await api('/api/skills',payload);renderRuntimeSkills(result.skills||[]);
    document.getElementById('runtime-skill-select').value=payload.name;selectRuntimeSkill();
    document.getElementById('runtime-skill-status').textContent=result.changed?'Saved and committed':'Already up to date';
    if(lastState&&lastState.runtime_config)lastState.runtime_config.skills=result.skills||[];}
  catch(e){showInlineError('runtime-error',e);}
  finally{button.disabled=Boolean(lastState&&lastState.progress&&!lastState.progress.finished);}};
runtimeForm.onsubmit=async ev=>{ev.preventDefault();const save=document.getElementById('save-runtime');
  const error=document.getElementById('runtime-error');error.className='wizard-error';save.disabled=true;
  const payload={generator_model:runtimeModel('generator'),auditor_model:runtimeModel('auditor'),
    generator_reasoning_effort:runtimeEl('generator','effort').value||'',
    auditor_reasoning_effort:runtimeEl('auditor','effort').value||'',
    generator_fallbacks:fallbackRows('generator'),auditor_fallbacks:fallbackRows('auditor'),
    max_rounds:Number(document.getElementById('runtime-max-rounds').value),
    max_attempts:Number(document.getElementById('runtime-max-attempts').value),
    initial_backoff_seconds:Number(document.getElementById('runtime-initial-backoff').value),
    max_backoff_seconds:Number(document.getElementById('runtime-max-backoff').value),
    retry_after_cap_seconds:Number(document.getElementById('runtime-retry-after-cap').value),
    circuit_breaker_failures:Number(document.getElementById('runtime-circuit-failures').value),
    circuit_breaker_cooldown_seconds:Number(document.getElementById('runtime-circuit-cooldown').value),
    daily_token_warning:document.getElementById('runtime-daily-token-warning').value,
    daily_token_limit:document.getElementById('runtime-daily-token-limit').value,
    monthly_cost_warning_usd:document.getElementById('runtime-monthly-cost-warning').value,
    monthly_cost_limit_usd:document.getElementById('runtime-monthly-cost-limit').value,
    prices:priceRows()};
  try{const result=await api('/api/runtime',payload);if(lastState)lastState.runtime_config=result;
    if(lastState)lastState.max_rounds=result.max_rounds;
    closeRuntime();route.className='route on';route.innerHTML='<b>Project controls updated.</b> Recovery routes, usage guardrails, models and loop limits apply to the next provider call.';}
  catch(e){showInlineError('runtime-error',e);syncRuntimeBusy(lastState);}
  finally{if(!lastState||!lastState.progress||lastState.progress.finished)save.disabled=false;}
};

const resolutionModal=document.getElementById('resolution-modal');
const resolutionForm=document.getElementById('resolution-form');
let activeResolution=null;
const promptedEscalations=new Set();
function currentEscalations(d){
  const rows=(d&&d.escalations)||[];
  const direct=rows.filter(row=>(row.chat_id||'history')===activeChatId);
  if(direct.length)return direct;
  const shas=new Set(chatCycles(d).map(row=>row.sha));
  return rows.filter(row=>shas.has(row.sha));
}
function resolutionChoice(action){
  document.getElementById('resolution-action').value=action||'';
  resolutionForm.querySelectorAll('input[name="resolution-choice"]').forEach(input=>input.checked=input.value===action);
  const label=document.getElementById('resolution-reason-label'),reason=document.getElementById('resolution-reason');
  const submit=document.getElementById('submit-resolution');
  const budget=Boolean(activeResolution&&activeResolution.kind==='budget');
  const provider=Boolean(activeResolution&&activeResolution.kind==='provider');
  // A provider outage and a budget pause both reopen by retrying the original
  // task, so the reason is an optional note, not required content guidance.
  const stopped=provider||budget;
  const guidance=reason.closest('label');guidance.hidden=stopped&&action==='reopen';
  reason.required=!(stopped&&action==='reopen');
  if(action==='reopen'&&stopped){
    label.textContent='Retry note (optional)';
    reason.placeholder='Optional note for the audit ledger.';
    submit.textContent=budget?'Raise the limit & retry':'Retry provider now';
  }else if(action==='reopen'){
    label.textContent='Correction guidance for the next round';
    reason.placeholder='Describe exactly what should change before the next audit.';
    submit.textContent='Record guidance & unlock round';
  }else if(action==='close'){
    label.textContent='Reason for stopping';
    reason.placeholder='Explain why this task should stop without admitting its current output.';
    submit.textContent='Stop without admission';
  }else{
    label.textContent='Your guidance or reason';
    reason.placeholder='Select an action, then explain what CrossAudit should do.';
    submit.textContent='Record human decision';
  }
}
// A stalled cycle (like a hard denial) names its remedies as typed
// RemediationAction values — errors.py, the same vocabulary slice one gave a
// parked run via waiting_reason. The modal decides which remediation
// affordance to show by reading that list, not by re-deriving it from the
// kind; these labels are the A40 contract strings, kept in one place.
const REMEDIATION={
  retry:{label:'Retry provider now'},
  validate_credential:{label:'Review provider connection',panel:'settings'},
  select_model:{label:'Change model or fallback',panel:'runtime'},
  open_billing:{label:'Adjust usage limits',panel:'runtime'},
  continue_later:{label:'Continue later'},
  stop:{label:'Stop this task'},
  revise:{label:'Revise and continue'}};
function hasRemediation(row,action){return ((row&&row.remediations)||[]).indexOf(action)>=0;}
// R5. Every ESCALATE branch of the auditor ladder tells the person what
// happened, why, and what to do next — through the existing slots, keyed on
// the structured cause (errors.escalation_cause). `hint` prefills the
// guidance box where the next step is obvious; `empty` is the findings slot
// when no finding was recorded. An unknown cause keeps the generic copy.
const CAUSE_COPY={
  nothing_audited:{flag:'Nothing to review yet',title:'The task produced no work in the audited folder',
    summary:'There is nothing to review yet: the generator produced no files inside the folder the auditor checks, so no audit could run and nothing was admitted.',
    limitTitle:'What happened',
    request:'Tell the generator what to create inside the audited folder and run one more round, or stop this task.',
    reopenTitle:'Revise and continue',
    reopenCopy:'Say which files should be created inside the audited folder, then unlock one additional audited round.',
    hint:'Create the deliverable inside the audited folder; nothing was produced there.',
    empty:'No audit findings were created because there was no work in the audited folder to review.'},
  invalid_reply:{flag:'Auditor reply unreadable',title:'The auditor\u2019s reply could not be read',
    summary:'The auditor answered, but its reply was not in the required form, so no verdict could be recorded. The files are unchanged and nothing was admitted.',
    limitTitle:'What happened',
    request:'Run the audit again on the same work, switch the auditor model, or stop this task.',
    reopenTitle:'Run the audit again',
    reopenCopy:'Unlock one more round with the work unchanged so the auditor can answer again.',
    hint:'Run the audit again on the same work; the previous auditor reply could not be read.',
    empty:'No audit findings were recorded because the auditor\u2019s reply could not be read.'},
  bounds_exceeded:{flag:'Task too large for one audit',title:'The task is too large for one audit',
    summary:'The work exceeds what one audit can read at once, so the auditor stopped rather than judge part of it. Nothing was admitted.',
    limitTitle:'What happened',
    request:'Narrow the scope or split the task into smaller pieces and run one more round, or stop this task.',
    reopenTitle:'Revise and continue',
    reopenCopy:'Name the smaller piece the next round should cover, then unlock one additional audited round.',
    hint:'',empty:'No audit findings were recorded because the work was too large to audit in one pass.'},
  auditor_escalated:{flag:'The auditor asked for you',title:'The auditor asked for your judgment',
    summary:'The auditor could not settle this round on its own and handed it to you. Its stated reason is below. Nothing was admitted.',
    limitTitle:'What the auditor said',
    request:'Read the auditor\u2019s reason, then tell the generator how to address it or stop this task.',
    reopenTitle:'Revise and continue',
    reopenCopy:'Tell the generator how to address the auditor\u2019s reason, then unlock one additional audited round.',
    hint:'',empty:'The auditor recorded no structured findings. Its stated reason is above.'},
  escalation_locked:{flag:'Waiting on an earlier decision',title:'This task is already waiting for your earlier decision',
    summary:'An earlier round of this task is still waiting for you. No new round can run until that decision is made.',
    limitTitle:'What happened',
    request:'Open the earlier decision and settle it; this task continues from there.',
    reopenTitle:'Settle the earlier decision',
    reopenCopy:'Open the earlier decision first. Guidance recorded here applies once it is settled.',
    hint:'',empty:'No new findings were recorded because the earlier decision is still open.'}};
function openResolution(value,action='',sha=''){
  let row=typeof value==='object'&&value?value:null;
  if(!row&&lastState)row=(lastState.escalations||[]).find(item=>item.cycle_id===value);
  row=row||{cycle_id:value,short_sha:sha,sha,round:1,max_rounds:lastState&&lastState.max_rounds||3,
    limit_reached:false,why:'The automatic audit loop stopped.',issues:[],attempts:[],
    requested:'Review why the loop stopped, then decide whether to revise or stop.'};
  activeResolution=row;promptedEscalations.add(row.cycle_id);
  const copy=CAUSE_COPY[String(row.cause||'')]||null;
  document.getElementById('resolution-cycle').value=row.cycle_id||'';
  // R5. The guidance box opens prefilled where the next step is obvious
  // (nothing produced, unreadable reply); the person can still change it.
  document.getElementById('resolution-reason').value=copy&&copy.hint?t(copy.hint):'';
  const used=Number(row.round||0),maximum=Number(row.max_rounds||(lastState&&lastState.max_rounds)||0);
  // A budget (usage-guardrail) pause is a provider-family stop — no audit ran,
  // nothing was admitted — but its remedy is to raise or clear the local limit,
  // never to review a connection, so it carries its own copy throughout.
  const budget=row.kind==='budget';
  const provider=row.kind==='provider';
  // The structured cause (additive): a known cause renders a fixed, fully
  // translatable explanation with concrete next steps; the raw technical
  // reason is demoted to the detail line instead of leading the screen.
  const formatCause=row.cause==='generator_format';
  const refusedCause=row.cause==='generator_refused';
  const noProgress=row.cause==='no_progress';
  const answered=row.cause==='answered';
  // D148. Two content stops that are not "the rounds ran out": the automatic
  // repair was refused (the revision left the audited directories or wrote a
  // binary; a single refusal on the last round also stops), and the escalate
  // dial handing a model-only blocker to a person. Same slots, no new elements.
  const repairRefused=row.cause==='repair_refused';
  const auditorConcern=row.cause==='auditor_concern';
  document.getElementById('resolution-flag').textContent=copy?copy.flag:budget?'Usage limit reached':provider?'Generator connection stopped':answered?'CrossAudit answered':formatCause?'Generator reply format problem':refusedCause?'Generator request refused':noProgress?'Nothing new to audit':repairRefused?'Automatic repair refused':auditorConcern?'The auditor raised a concern':row.limit_reached?'Automatic audit limit reached':'Automatic loop paused';
  document.getElementById('resolution-title').textContent=copy?copy.title:budget?'The task paused at a usage limit':provider?'The task is waiting for a working Generator connection':answered?'CrossAudit answered, but made no audited deliverable':formatCause?'The generator could not produce auditable work':noProgress?'The generator repeated the existing work':repairRefused?'The revision reached outside the audited files':row.limit_reached?'The audit needs your decision':'The audit needs your decision';
  document.getElementById('resolution-summary').textContent=copy?copy.summary:budget
    ?'CrossAudit stopped before spending past your usage limit. No result was admitted and the original task is ready once you raise or clear the limit.'
    :provider
    ?'CrossAudit stopped before an audit began. No result was admitted and the original task is ready to retry.'
    :repairRefused
    ?'The generator\u2019s revision was refused: it changed files outside the audited directories, or wrote a binary file that cannot be reviewed line by line. The refused attempt was rolled back, so the audited files are unchanged and nothing was admitted.'
    :auditorConcern
    ?'The auditor blocked this round on its own reading; no deterministic check reproduces the concern. CrossAudit does not let a model-only claim drive automatic rewrites, so it stopped and left the files unchanged.'
    :answered
    ?'This request could not become an audited deliverable — often because it refers to something that is not in the project. CrossAudit reply is shown below. Refine the task and run again, or stop it.'
    :formatCause
    ?'The generator was asked twice and still replied outside the required file format, so there was nothing to audit. No result was admitted.'
    :noProgress
    ?'The generator was asked twice and both replies matched the already-committed work byte for byte, so there was nothing new to audit. The existing files are untouched. Make the task more specific about what should change, or stop the task if the current work already satisfies it.'
    :row.limit_reached
    ?'CrossAudit used all '+used+' of '+maximum+' automatic rounds without a passing result. Nothing will continue or be admitted until you decide.'
    :'CrossAudit stopped safely. Nothing will continue or be admitted until you decide.';
  appendResolutionReset(row,budget,provider);   // billing: "Resets at midnight" / "resets in 2 h 10 min"
  document.getElementById('resolution-limit-title').textContent=copy?((row.cause==='auditor_escalated'&&!(row.issues||[]).length)?'What happened':copy.limitTitle):budget?'Usage limit reached':provider?'Generator connection stopped':answered?'CrossAudit reply':(formatCause||noProgress||auditorConcern)?'What happened':repairRefused?'Why the last revision was refused':row.limit_reached
    ?'Automatic rounds used: '+used+' / '+maximum:'The automatic loop could not continue safely';
  // A refused repair leads with the sentence the repair guard wrote (it names
  // the file and the pattern) rather than the round-numbered wrapper around it.
  document.getElementById('resolution-limit-copy').textContent=(formatCause
    ?'The reply was corrected once automatically and still failed to parse. Technical detail: '
    :noProgress?'One corrective retry was already made automatically. Technical detail: ':'')
    +String((repairRefused&&row.why)||(typeof currentLocale!=='undefined'&&currentLocale==='zh'&&(row.stop_reason_zh||row.why_zh))||row.stop_reason||row.why||'The audit controller paused this task.');
  const attemptRows=row.attempts||[];
  document.getElementById('resolution-attempts').innerHTML=attemptRows.map(item=>{
    const word=String(item.verdict||'').toLowerCase();
    // R1. The verdict word a person reads; the raw word stays as the class.
    return '<div class="decision-attempt"><span class="round-n">round '+esc(item.round)+'</span><span>'
      +esc(item.findings)+' issue'+(item.findings===1?'':'s')+'</span><span class="verdict-word '+esc(word)
      +'">'+esc(verdictWord(item.verdict))+'</span></div>';}).join('');
  document.getElementById('resolution-goal').textContent=(lastState?titleOf(lastState):'')||'The task this conversation asked for.';
  const issues=row.issues||[];
  document.getElementById('resolution-issue-count').textContent=String(issues.length);
  // R2. Each issue leads with the observation; severity as a consequence,
  // the place and the rule id on one muted details line under it.
  document.getElementById('resolution-issues').innerHTML=issues.length?issues.map((issue,index)=>
    '<article class="decision-issue"'+ruleTitle(issue.rule)+'><p class="finding-observation">'+esc(issue.observation||'No explanation was recorded.')+'</p>'
    +'<div class="finding-details"><span class="severity '+(severityWord(issue.severity||'BLOCKER')==='must fix'?'must-fix':'suggestion')+'">'+esc(severityWord(issue.severity||'BLOCKER'))+'</span>'
    +(issue.artifact?'<span class="finding-sep" aria-hidden="true">·</span><span class="finding-where">'+esc(issue.artifact)+'</span>':'')
    +'</div></article>').join('')
    :'<div class="decision-empty">'+(copy?copy.empty:budget
      ?'No audit findings were created because the task paused at a usage limit before producing a reviewable result.'
      :provider
      ?'No audit findings were created because the Generator stopped before producing a reviewable result.'
      :formatCause
      ?'No audit ran because the generator never produced readable work. What usually helps: rewrite the task as one concrete instruction, or switch the generator model in Settings, then run one more round.'
      :'No structured findings were recorded. Review the stop reason above before continuing.')+'</div>';
  document.getElementById('resolution-request').textContent=copy?copy.request:budget
    ?'Raise or clear the usage limit and rerun the original task, or stop this task.'
    :provider
    ?'Retry the same task now, review the model connection first, or stop this task.'
    :formatCause
    ?'Rewrite the task as one concrete instruction and run one more round, switch the generator model, or stop this task.'
    :(row.requested||'Choose whether to revise and continue, or stop this task.');
  document.getElementById('resolution-reopen-title').textContent=copy?copy.reopenTitle:budget?'Raise the limit & retry':provider?'Retry provider':'Revise and continue';
  document.getElementById('resolution-reopen-copy').textContent=copy?copy.reopenCopy:budget
    ?'Adjust the usage limit in Project controls, then rerun the original task.'
    :provider
    ?'Use the current connection and rerun the original task.'
    :repairRefused
    ?'Name the file inside the audited directories that should change, then unlock one additional audited round.'
    :auditorConcern
    ?'If the concern is right, tell the generator how to address it. If it is a misreading, say so here; your reason is recorded.'
    :'Give the generator specific correction guidance and unlock one additional audited round.';
  // The runtime affordance carries the budget person to the same Project
  // controls that hold the usage limits; relabel it so it names that, not a
  // model change, when the stop is a guardrail pause.
  document.getElementById('resolution-open-runtime').textContent=budget?'Adjust usage limits':'Change model or fallback';
  document.getElementById('resolution-open-runtime').hidden=!(hasRemediation(row,'select_model')||hasRemediation(row,'open_billing'));
  // R5. The one real action of a locked cycle is the EARLIER decision; the
  // secondary button carries it (relabelled, with the cycle to open) so no new
  // control is added. Cleared for every other row so the label stays honest.
  const settingsButton=document.getElementById('resolution-open-settings');
  const earlier=row.cause==='escalation_locked'?String(row.earlier_cycle_id||''):'';
  settingsButton.setAttribute('data-earlier-cycle',earlier);
  settingsButton.textContent=earlier?'Open the earlier decision':'Review provider connection';
  settingsButton.hidden=!hasRemediation(row,'validate_credential')&&!earlier;
  resolutionChoice(action||'reopen');
  document.getElementById('resolution-error').className='wizard-error';
  resolutionModal.classList.add('on');document.body.classList.add('deciding');
  // Being told a modal opened and not being told what it is about are the same
  // failure, so the flag and the title are announced as ONE sentence — the same
  // words that name the dialog, so what is heard and what is read agree.
  setDecidingInert(true);
  // Deferred one tick on purpose. The flag and the title were just written and
  // the locale observer translates them on the next microtask, so announcing
  // synchronously speaks the English source to a Chinese reader while the
  // name of the dialog — built from the same nodes — is already translated.
  setTimeout(()=>announce(decisionSentence()),0);
  if(lastState)renderDecisionBanner(lastState);
  setTimeout(()=>{const target=action?document.getElementById('resolution-reason')
    :resolutionForm.querySelector('input[name="resolution-choice"]');if(target)target.focus();},0);
}
function decisionSentence(){
  const flag=String((document.getElementById('resolution-flag')||{}).textContent||'').trim();
  const title=String((document.getElementById('resolution-title')||{}).textContent||'').trim();
  return flag&&title?flag+' \u2014 '+title:(title||flag);}
// The rest of the console is not merely covered while a decision is open, it is
// removed from the accessibility tree and from the tab order. aria-modal alone
// tells a screen reader the boundary exists; inert is what makes it true.
function setDecidingInert(on){
  const shell=document.querySelector('.app');
  if(!shell)return;
  if(on)shell.setAttribute('inert','');else shell.removeAttribute('inert');}
function closeResolution(){resolutionModal.classList.remove('on');document.body.classList.remove('deciding');
  setDecidingInert(false);
  resolutionForm.reset();activeResolution=null;resolutionChoice('');
  if(lastState)renderDecisionBanner(lastState);}
resolutionForm.querySelectorAll('input[name="resolution-choice"]').forEach(input=>input.onchange=()=>resolutionChoice(input.value));
document.getElementById('close-resolution').onclick=closeResolution;
document.getElementById('cancel-resolution').onclick=closeResolution;
document.getElementById('resolution-open-runtime').onclick=()=>{closeResolution();openRuntime();};
document.getElementById('resolution-open-settings').onclick=()=>{
  const earlier=document.getElementById('resolution-open-settings').getAttribute('data-earlier-cycle')||'';
  closeResolution();if(earlier)openResolution(earlier);else openSettings('providers');};
resolutionForm.onsubmit=async ev=>{ev.preventDefault();const button=document.getElementById('submit-resolution');
  const cycleId=document.getElementById('resolution-cycle').value;
  const action=document.getElementById('resolution-action').value,reason=document.getElementById('resolution-reason').value.trim();
  const provider=Boolean(activeResolution&&activeResolution.kind==='provider');
  if(!action){showInlineError('resolution-error','Choose whether to revise and continue, or stop this task.');return;}
  if(!reason&&!(provider&&action==='reopen')){showInlineError('resolution-error','Add concrete guidance or a reason so the decision is auditable.');return;}
  button.disabled=true;document.getElementById('resolution-error').className='wizard-error';
  try{await api('/api/escalation',{cycle_id:cycleId,action:provider&&action==='reopen'?'retry_provider':action,reason});
    closeResolution();route.className='route on';
    if(provider&&action==='reopen'){
      pendingContinuation={cycle:'',chat:''};
      route.innerHTML='<b>Provider retry started.</b> The original task is running again; live progress will appear here.';
    }else if(action==='reopen'){
      pendingContinuation={cycle:cycleId,chat:activeChatId};
      say.value=reason;route.innerHTML='<b>Another audited attempt is unlocked.</b> Your guidance is in the composer. Review it, then press Run task.';
      setTimeout(()=>say.focus(),0);
    }else route.innerHTML='<b>Task stopped.</b> The current output remains unadmitted and your reason was recorded.';}
  catch(e){showInlineError('resolution-error',e);}finally{button.disabled=false;}};

let projectState=null;
let projectSource=null;
let activeProjectJob=null;
let createdRoot=null;
let repoNameTouched={science:false,audit:false};
let repositoryCheckNonce=0;
let projectStep=1;
const projectModal=document.getElementById('project-modal');
const projectForm=document.getElementById('project-form');
const recoveryModal=document.getElementById('recovery-modal');
const recoveryForm=document.getElementById('recovery-form');
const deleteProjectModal=document.getElementById('delete-project-modal');
const deleteProjectForm=document.getElementById('delete-project-form');
let deleteProjectPreview=null,deleteNeedsGithubAuthorization=false;
const auditorVendor=document.getElementById('auditor-vendor');
const generatorVendor=document.getElementById('generator-vendor');
const auditorConnection=document.getElementById('auditor-connection');
const generatorConnection=document.getElementById('generator-connection');
const auditorEndpoint=document.getElementById('auditor-endpoint');
const generatorEndpoint=document.getElementById('generator-endpoint');
const auditorModel=document.getElementById('auditor-model');
const generatorModel=document.getElementById('generator-model');
const projectType=document.getElementById('project-type');

function modelOptions(vendor,target){
  const previous=target.value;
  const rows=(projectState&&projectState.models&&projectState.models[vendor])||[];
  target.innerHTML=rows.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.id)+' - '+esc(x.hint)+'</option>').join('')
    +'<option value="__custom__">Enter a custom model ID…</option>';
  if([...target.options].some(o=>o.value===previous))target.value=previous;
  syncCustomModel(target.id.startsWith('auditor')?'auditor':'generator');
}
function connectionOptions(vendor,target){
  const previous=target.value;const state=projectState&&projectState.connections&&projectState.connections[vendor]||{};
  const label=state.label||vendor[0].toUpperCase()+vendor.slice(1);
  const rows=[];
  if(vendor==='openai')rows.push({id:'chatgpt',label:'ChatGPT subscription',ready:Boolean(state.chatgpt&&state.chatgpt.connected)});
  rows.push({id:'api',label:label+' API key',ready:Boolean(state.api_key&&state.api_key.configured)});
  const readyRows=rows.filter(x=>x.ready);
  target.innerHTML=(readyRows.length?'':'<option value="" selected disabled>Connect '+esc(vendor)+' in Settings first</option>')
    +rows.map(x=>'<option value="'+x.id+'"'+(x.ready?'':' disabled')+'>'+esc(x.label)+(x.ready?'':' - connect in Settings')+'</option>').join('');
  if([...target.options].some(o=>o.value===previous&&!o.disabled))target.value=previous;
  else{const ready=[...target.options].find(o=>!o.disabled);if(ready)target.value=ready.value;}
}
function endpointOptions(vendor,target){
  const previous=target.value;const rows=(projectState&&projectState.endpoints&&projectState.endpoints[vendor])||[];
  target.innerHTML=rows.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.label)+'</option>').join('');
  if([...target.options].some(o=>o.value===previous))target.value=previous;
  target.closest('.field').hidden=rows.length<2;
}
function syncCustomModel(role){
  const select=role==='auditor'?auditorModel:generatorModel;
  const custom=select.value==='__custom__';
  document.getElementById(role+'-custom-wrap').className='field custom-model'+(custom?'':' off');
  if(custom)document.getElementById(role+'-details').open=true;
}
function syncRoleChoices(){
  const av=auditorVendor.value;const gv=generatorVendor.value;
  [...generatorVendor.options].forEach(o=>o.disabled=o.value===av);
  [...auditorVendor.options].forEach(o=>o.disabled=o.value===gv);
  if(generatorVendor.selectedOptions[0]&&generatorVendor.selectedOptions[0].disabled){
    generatorVendor.value=[...generatorVendor.options].find(o=>!o.disabled).value;
  }
  connectionOptions(auditorVendor.value,auditorConnection);connectionOptions(generatorVendor.value,generatorConnection);
  endpointOptions(auditorVendor.value,auditorEndpoint);endpointOptions(generatorVendor.value,generatorEndpoint);
  modelOptions(auditorVendor.value,auditorModel);modelOptions(generatorVendor.value,generatorModel);
}
function configureProjectForm(){
  if(!projectState)return;
  const vendors=Object.keys(projectState.models||{});
  if(!auditorVendor.options.length){
    const label=v=>(projectState.connections&&projectState.connections[v]&&projectState.connections[v].label)||v;
    auditorVendor.innerHTML=vendors.map(v=>'<option value="'+esc(v)+'">'+esc(label(v))+'</option>').join('');
    generatorVendor.innerHTML=vendors.map(v=>'<option value="'+esc(v)+'">'+esc(label(v))+'</option>').join('');
    auditorVendor.value=vendors.includes('openai')?'openai':vendors[0];
    generatorVendor.value=vendors.includes('anthropic')?'anthropic':vendors.find(v=>v!==auditorVendor.value);
    syncRoleChoices();
  }
  const gh=projectState.github||{};const auth=projectState.github_auth||{};
  const connection=document.getElementById('github-connection');
  if(gh.connected){connection.textContent=gh.detail||'GitHub connected';connection.className='connection ok';}
  else if(auth.status==='running'){
    connection.className='connection';connection.innerHTML='<div class="github-device"><b>'+esc(auth.detail)+'</b>'
      +(auth.code?'<div class="github-device-actions"><span class="device-code">'+esc(auth.code)+'</span>'
        +'<button type="button" class="secondary" data-copy-github="'+esc(auth.code)+'">Copy code</button>'
        +'<a href="'+esc(auth.url)+'" target="_blank" rel="noopener">Open GitHub ↗</a></div>'
        +'<small>Sign in, enter the code, and approve GitHub CLI. This page updates automatically.</small>':'')+'</div>';
  }else{const help=gh.url?'<a class="secondary" href="'+esc(gh.url)+'" target="_blank" rel="noopener">Install GitHub tool ↗</a>':'';
    connection.className='connection bad';connection.innerHTML='<div class="github-connect"><span>'
    +esc(auth.detail||gh.detail||'GitHub is not connected')+'</span>'+(gh.action==='install_github_cli'?help
      :'<button type="button" class="secondary" data-connect-github>Connect GitHub</button>')+'</div>';}
  document.getElementById('github-toggle').disabled=false;
  updateWorkspaceFields(projectState.workspace);syncGithubFields();renderRecoveryGithub();
}
function renderRecoveryGithub(){
  if(!recoveryModal.classList.contains('on')||!projectState)return;
  const gh=projectState.github||{},auth=projectState.github_auth||{};
  const box=document.getElementById('recovery-connection');
  const connect=document.getElementById('recovery-connect-github');
  if(gh.connected){box.textContent=gh.detail||'GitHub connected';box.className='connection ok';connect.hidden=true;}
  else if(auth.status==='running'){
    box.className='connection';box.innerHTML='<div class="github-device"><b>'+esc(auth.detail||'Authorize CrossAudit in GitHub')+'</b>'
      +(auth.code?'<div class="github-device-actions"><span class="device-code">'+esc(auth.code)+'</span>'
        +'<button type="button" class="secondary" data-copy-recovery-github="'+esc(auth.code)+'">Copy code</button>'
        +'<a href="'+esc(auth.url)+'" target="_blank" rel="noopener">Open GitHub ↗</a></div>'
        +'<small>Enter the code in GitHub. This dialog updates automatically after approval.</small>':'')+'</div>';
    connect.hidden=true;
  }else{box.textContent=auth.detail||gh.detail||'GitHub is not connected';box.className='connection bad';
    connect.hidden=false;connect.disabled=false;connect.textContent='Connect GitHub';}
}
function resetRepositoryCheck(){
  repositoryCheckNonce++;const state=document.getElementById('repo-check');
  state.textContent='Names will be checked again before anything is created.';state.className='repo-check';
}
function syncRepoNames(force=false){
  if(!projectState||!projectState.github||!projectState.github.owner)return;
  const name=document.getElementById('project-name').value.trim();
  if(!name)return;
  const owner=projectState.github.owner;
  if(force||!repoNameTouched.science)document.getElementById('science-repo').value=owner+'/'+name;
  if(force||!repoNameTouched.audit)document.getElementById('audit-repo').value=owner+'/'+name+'-audit';
  updateWorkspaceFields(projectState.workspace);resetRepositoryCheck();
}
function syncGithubFields(){
  const on=document.getElementById('github-toggle').checked;
  document.getElementById('github-fields').className='github-fields'+(on?'':' off');
}
function repositoryPayload(){return {name:document.getElementById('project-name').value.trim(),
  science_repo:document.getElementById('science-repo').value.trim(),
  audit_repo:document.getElementById('audit-repo').value.trim(),
  adopt_existing:document.getElementById('adopt-existing').checked};}
async function checkRepositoryNames(showError=true){
  const status=document.getElementById('repo-check');const nonce=++repositoryCheckNonce;
  status.textContent='Checking GitHub…';status.className='repo-check';
  try{const result=await api('/api/github/check',repositoryPayload());if(nonce!==repositoryCheckNonce)return result;
    const existing=(result.repositories||[]).filter(r=>r.exists).map(r=>r.repo);
    if(existing.length){status.textContent=(result.adopt_existing?'Ready to use: ':'Already exists: ')+existing.join(', ');
      status.className='repo-check '+(result.ready?'ok':'warn');}
    else{status.textContent='Both names are available · one click will create both repositories';status.className='repo-check ok';}
    return result;
  }catch(e){if(nonce===repositoryCheckNonce){status.textContent=e.message;status.className='repo-check warn';}
    if(showError)showInlineError('wizard-error',e);throw e;}
}
function syncProjectType(){
  const science=projectType.value==='science';
  document.getElementById('project-contract-hint').textContent=science
    ?'Scientific projects require the visible metadata.yml/results.json, units, convergence, and provenance contract.'
    :'General projects use format, reference, link, and completeness checks. They do not require scientific metadata sidecars.';
}
function guidanceMarkup(row){
  const issue=row&&row.issue;if(!issue)return '';
  const root=row.root||'';let actions='';
  if(issue.action==='connect_github')actions+='<button type="button" class="secondary" data-job-action="connect_github">Connect GitHub</button>';
  if(issue.action==='edit_repositories')actions+='<button type="button" class="secondary" data-job-action="'+(row.recoverable?'edit_repositories':'edit_new_repositories')+'" data-root="'+esc(root)+'">Edit repository names</button>';
  if(issue.action==='review_workspace')actions+='<button type="button" class="secondary" data-job-action="reveal_folder" data-root="'+esc(root)+'">Open folder</button>';
  if(issue.action==='review_workspace'||issue.action==='choose_workspace')actions+='<button type="button" class="secondary" data-job-action="choose_new_workspace">Choose another folder</button>';
  if(issue.retryable&&!row.recoverable)actions+='<button type="button" class="primary" data-job-action="retry_job">Try again</button>';
  if(issue.action==='retry'&&root)actions+='<button type="button" class="secondary" data-job-action="retry" data-root="'+esc(root)+'">Try again</button>';
  if(issue.url)actions+='<a class="secondary" href="'+esc(issue.url)+'" target="_blank" rel="noopener">Open help ↗</a>';
  if(row.status==='failed')actions+='<button type="button" class="secondary" data-job-action="dismiss_job">Dismiss</button>';
  return '<b>'+esc(issue.title||'Setup needs attention')+'</b><p>'+esc(row.detail||'Review the settings and retry.')+'</p>'
    +(actions?'<div class="guidance-actions">'+actions+'</div>':'');
}
function renderProjectJob(jobs){
  const rows=jobs||[];let row=rows.find(j=>j.id===activeProjectJob);
  if(!row){row=rows.filter(j=>j.status==='running'||j.status==='failed')
    .sort((a,b)=>Number(b.finished||b.started||0)-Number(a.finished||a.started||0))[0];
    if(row)activeProjectJob=row.id;}
  const panel=document.getElementById('project-job');
  if(!row){activeProjectJob=null;panel.className='job-panel';return;}
  panel.className='job-panel on '+row.status;
  document.getElementById('job-title').textContent=row.status==='complete'?'Project ready'
    :row.status==='failed'?'Project creation stopped':'Creating '+row.project;
  document.getElementById('job-detail').textContent=row.detail;
  document.getElementById('job-steps').innerHTML=(row.steps||[]).slice(-8).map(s=>
    '<li>'+esc(s.stage)+' - '+esc(s.detail)+'</li>').join('');
  const guidance=document.getElementById('job-guidance');guidance.innerHTML=guidanceMarkup(row);
  guidance.className='job-guidance'+(guidance.innerHTML?' on':'');
  createdRoot=row.result&&row.result.root||null;
  document.getElementById('open-created').hidden=row.status!=='complete';
}
function renderProjects(d){
  projectState=d;const cap=d.capacity||{active:0,limit:'?'};
  document.getElementById('workspace-label').textContent=d.items.length+' project'
    +(d.items.length===1?'':'s')+', '+cap.active+'/'+cap.limit+' active · '+d.workspace;
  const q=document.getElementById('project-search').value.trim().toLowerCase();
  const rows=d.items.filter(p=>!q||(p.name+' '+p.label+' '+p.auditor+' '+p.generator).toLowerCase().includes(q));
  document.getElementById('project-list').innerHTML=rows.length?rows.map(p=>
    '<div class="project-row" role="button" tabindex="0" data-root="'+esc(p.root)+'" data-current="'+(p.current?'1':'0')+'">'
    +'<span><span class="project-name">'+esc(p.name)+(p.current?' · current':'')+'</span>'
    +(p.label!==p.name?'<span class="project-path">'+esc(p.label)+'</span>':'')
    +(p.progress?'<span class="project-live"><span class="project-progress" role="progressbar" aria-label="Live project activity"><i></i></span>'
      +'<span class="project-live-copy">'+esc(p.progress.actor)+' · '+esc(p.progress.step)+'</span>'
      +'<span class="project-live-time">'+p.progress.elapsed+'s</span></span>':'')
    +(p.setup&&p.setup.recoverable?'<span class="project-recovery"><span>'+esc((p.setup.issue&&p.setup.issue.title)||p.setup.detail||'GitHub setup stopped')+'</span>'
      +'<span class="retry-setup" role="button" tabindex="0" data-resume-root="'+esc(p.root)+'">Fix & retry</span></span>':'')
    +(p.interrupted?'<span class="project-interrupted">Interrupted · open to review and run again</span>':'')+'</span>'
    +'<span class="project-models">'+esc(p.generator)+' → '+esc(p.auditor)+'</span>'
    +'<span class="project-stat">'+p.chats+' chats · '+p.cycles+' cycles</span><span class="status '+esc(p.status)+'">'+esc(p.status)+'</span>'
    +(p.paired?'<span class="paired-mark project-tier">GitHub paired</span>':'<span class="project-stat project-tier">Local</span>')
    +'<button type="button" class="project-pin'+(p.pinned?' pinned':'')+'" data-pin-project="'+esc(p.root)+'" '
      +'aria-label="'+(p.pinned?'Unpin':'Pin')+' project" title="'+(p.pinned?'Unpin':'Pin')+' project">'+(p.pinned?'★':'☆')+'</button>'
    +'<button type="button" class="project-delete" data-delete-project="'+esc(p.root)+'" '
      +(p.current?'disabled ':'')+'aria-label="Delete project from CrossAudit" title="'
      +(p.current?'Return to the main Projects window to delete this open project':'Delete project from CrossAudit')+'">⌫</button>'
    +'<span class="project-arrow">›</span></div>').join(''):'<div class="hub-empty">No matching projects.</div>';
  renderProjectJob(d.jobs);configureProjectForm();renderDeleteGithubAuthorization();
}
async function refreshProjects(){try{renderProjects(await api('/api/projects'));}catch(e){
  document.getElementById('project-list').innerHTML='<div class="hub-empty">'+esc(e.message)+'</div>';}}
function startProjectStream(){if(projectSource)return;try{
  projectSource=new EventSource('/api/projects/stream?t='+encodeURIComponent(T));
  projectSource.onmessage=ev=>{try{renderProjects(JSON.parse(ev.data));}catch(e){}};
  projectSource.onerror=()=>{};
}catch(e){}}
function showProjects(){document.body.classList.add('hub-mode');closePanels();refreshProjects();startProjectStream();
  history.replaceState(null,'',location.pathname+'?t='+encodeURIComponent(T)+'#projects');}
function returnToProjects(){try{const target=new URL(window.name);if(target.protocol==='http:'&&target.hostname==='127.0.0.1'
    &&target.hash==='#projects'&&target.origin!==location.origin){window.name='';location.href=target.href;return;}}catch(e){}
  showProjects();}
function hideProjects(){document.body.classList.remove('hub-mode');projectModal.className='project-modal';
  history.replaceState(null,'',location.pathname+'?t='+encodeURIComponent(T));}
async function openProject(root,current){
  if(current){hideProjects();return;}
  try{const r=await api('/api/projects/open',{root});window.name=location.href;location.href=r.url;}catch(e){
    const panel=document.getElementById('project-job');panel.className='job-panel on failed';
    document.getElementById('job-title').textContent='Could not open project';document.getElementById('job-detail').textContent=e.message;}
}
function closeDeleteProject(){deleteProjectModal.className='project-modal';deleteProjectForm.reset();
  deleteProjectPreview=null;deleteNeedsGithubAuthorization=false;
  document.getElementById('delete-project-error').className='wizard-error';}
function renderDeleteGithubAuthorization(){
  const box=document.getElementById('delete-github-authorization');
  const button=document.getElementById('authorize-delete-repositories');
  if(!deleteProjectModal.classList.contains('on')||!deleteNeedsGithubAuthorization){box.textContent='';button.hidden=true;return;}
  const auth=projectState&&projectState.github_auth||{},scopes=auth.scopes||[];
  if(scopes.includes('delete_repo')&&auth.status==='running'){
    button.hidden=true;box.className='connection';box.innerHTML='<div class="github-device"><b>'+esc(auth.detail||'Authorize permanent repository deletion')+'</b>'
      +(auth.code?'<div class="github-device-actions"><span class="device-code">'+esc(auth.code)+'</span>'
      +'<button type="button" class="secondary" data-copy-delete-github="'+esc(auth.code)+'">Copy code</button>'
      +(auth.url?'<a href="'+esc(auth.url)+'" target="_blank" rel="noopener">Open GitHub ↗</a>':'')+'</div>':'')+'</div>';return;
  }
  if(scopes.includes('delete_repo')&&auth.status==='complete'){
    deleteNeedsGithubAuthorization=false;button.hidden=true;box.className='connection ok';
    box.textContent='GitHub deletion authorized. Submit again to delete the selected repositories.';return;
  }
  box.className='connection bad';box.textContent='GitHub requires the delete_repo permission before it can delete a repository.';
  button.hidden=false;button.disabled=false;button.textContent='Authorize GitHub deletion';
}
function syncDeleteProject(){const working=document.getElementById('delete-working-repository').checked;
  const audit=document.getElementById('delete-audit-repository').checked,github=working||audit;
  document.getElementById('delete-github-confirm-wrap').className='field conditional-field'+(github?'':' off');
  const button=document.getElementById('confirm-delete-project');
  button.disabled=!(deleteProjectPreview&&deleteProjectPreview.can_delete);
  button.textContent=github?(currentLocale==='zh'?'移到废纸篓并删除所选 GitHub 仓库':'Move to Trash & delete selected GitHub repositories')
    :(currentLocale==='zh'?'将项目移到废纸篓':'Move project to Trash');}
async function openDeleteProject(root){deleteProjectForm.reset();deleteProjectPreview=null;deleteNeedsGithubAuthorization=false;
  document.getElementById('delete-project-root').value=root;document.getElementById('delete-project-name').textContent='Project';
  document.getElementById('delete-project-path').textContent=root;document.getElementById('delete-project-impact').textContent='Checking project state…';
  document.getElementById('delete-project-error').className='wizard-error';document.getElementById('confirm-delete-project').disabled=true;
  deleteProjectModal.className='project-modal on';
  try{const preview=await api('/api/projects/delete',{action:'preview',root});deleteProjectPreview=preview;
    document.getElementById('delete-project-name').textContent=preview.name;
    document.getElementById('delete-project-path').textContent=preview.root;
    const impact=[];
    impact.push(currentLocale==='zh'?'恢复位置：'+preview.trash:'Recovery location: '+preview.trash);
    if(preview.dirty_count)impact.push(currentLocale==='zh'?preview.dirty_count+' 个未提交改动会一同归档':preview.dirty_count+' uncommitted changes will be archived');
    if(preview.unpushed_commits)impact.push(currentLocale==='zh'?preview.unpushed_commits+' 个未推送提交会一同归档':preview.unpushed_commits+' unpushed commits will be archived');
    if(preview.activity.length)impact.push((currentLocale==='zh'?'目前不能删除：':'Cannot delete now: ')+preview.activity.join('; '));
    document.getElementById('delete-project-impact').textContent=impact.join(' · ');
    const working=preview.working_repository||'',audit=preview.audit_repository||'';
    const workingBox=document.getElementById('delete-working-repository');workingBox.disabled=!working;
    const auditBox=document.getElementById('delete-audit-repository');auditBox.disabled=!audit;
    document.getElementById('delete-working-repository-name').textContent=working
      ?(currentLocale==='zh'?'保留为默认；选择后永久删除：':'Preserved by default; select to permanently delete: ')+working
      :(currentLocale==='zh'?'未检测到工作仓库。':'No working repository detected.');
    document.getElementById('delete-audit-repository-name').textContent=audit
      ?(currentLocale==='zh'?'选择后永久删除：':'Select to permanently delete: ')+audit
      :(currentLocale==='zh'?'未检测到审计仓库。':'No audit repository detected.');
    document.getElementById('delete-project-confirmation').placeholder=preview.name;syncDeleteProject();
  }catch(e){showInlineError('delete-project-error',e);}}
document.getElementById('delete-project-confirmation').oninput=syncDeleteProject;
document.getElementById('delete-github-confirmation').oninput=syncDeleteProject;
document.getElementById('delete-working-repository').onchange=syncDeleteProject;
document.getElementById('delete-audit-repository').onchange=syncDeleteProject;
document.getElementById('delete-github-authorization').onclick=async ev=>{
  const copy=ev.target.closest('[data-copy-delete-github]');if(!copy)return;
  try{await navigator.clipboard.writeText(copy.getAttribute('data-copy-delete-github'));copy.textContent='Copied';}catch(e){}
};
document.getElementById('authorize-delete-repositories').onclick=async()=>{
  const button=document.getElementById('authorize-delete-repositories');button.disabled=true;button.textContent='Starting…';
  try{const result=await api('/api/github/connect',{scope:'delete_repo'});
    if(result.connected){deleteNeedsGithubAuthorization=false;button.hidden=true;
      const box=document.getElementById('delete-github-authorization');box.className='connection ok';box.textContent='GitHub deletion authorized. Submit again.';}
    else renderDeleteGithubAuthorization();}
  catch(e){showInlineError('delete-project-error',e);button.disabled=false;button.textContent='Authorize GitHub deletion';}
};
document.getElementById('close-delete-project').onclick=closeDeleteProject;
document.getElementById('cancel-delete-project').onclick=closeDeleteProject;
deleteProjectModal.addEventListener('click',ev=>{if(ev.target===deleteProjectModal)closeDeleteProject();});
deleteProjectForm.onsubmit=async ev=>{ev.preventDefault();if(!deleteProjectPreview)return;
  const button=document.getElementById('confirm-delete-project');button.disabled=true;button.textContent=currentLocale==='zh'?'正在删除…':'Deleting…';
  try{const result=await api('/api/projects/delete',{action:'delete',root:deleteProjectPreview.root,
      confirmation:document.getElementById('delete-project-confirmation').value,
      delete_working_repo:document.getElementById('delete-working-repository').checked,
      delete_audit_repo:document.getElementById('delete-audit-repository').checked,
      github_confirmation:document.getElementById('delete-github-confirmation').value});
    closeDeleteProject();await refreshProjects();const panel=document.getElementById('project-job');panel.className='job-panel on complete';
    document.getElementById('open-created').hidden=true;
    document.getElementById('job-title').textContent=currentLocale==='zh'?'项目已移到废纸篓':'Project moved to Trash';
    const failed=(result.github||[]).filter(row=>row.status==='failed');
    document.getElementById('job-detail').textContent=(currentLocale==='zh'?'可从以下位置恢复：':'Recover from: ')+result.archive
      +(failed.length?(currentLocale==='zh'?' · GitHub 删除未完全成功：':' · GitHub deletion incomplete: ')+failed.map(row=>row.repo).join(', '):'');
    document.getElementById('job-steps').innerHTML='';document.getElementById('job-guidance').className='job-guidance';
  }catch(e){if(e.action==='authorize_delete'){deleteNeedsGithubAuthorization=true;renderDeleteGithubAuthorization();}
    showInlineError('delete-project-error',e);syncDeleteProject();}};
function projectModelLabel(role){const select=role==='generator'?generatorModel:auditorModel;
  const vendor=role==='generator'?generatorVendor:auditorVendor;const custom=document.getElementById(role+'-custom');
  return (vendor.value||'-')+' · '+(select.value==='__custom__'?(custom.value.trim()||(currentLocale==='zh'?'自定义模型':'custom model')):(select.value||(currentLocale==='zh'?'未连接':'not connected')));}
function syncProjectReview(){const host=document.getElementById('project-review');if(!host)return;
  const github=document.getElementById('github-toggle').checked;
  const labels=currentLocale==='zh'
    ?[['项目',document.getElementById('project-name').value.trim()||'未命名'],['本地文件夹',selectedProjectFolder||'未选择'],
      ['生成者',projectModelLabel('generator')],['审计者',projectModelLabel('auditor')],['GitHub',github?'创建两个仓库':'仅本地']]
    :[['Project',document.getElementById('project-name').value.trim()||'Untitled'],['Local folder',selectedProjectFolder||'Not selected'],
      ['Generator',projectModelLabel('generator')],['Auditor',projectModelLabel('auditor')],['GitHub',github?'Create two repositories':'Local only']];
  host.innerHTML=labels.map(row=>'<div class="project-review-item"><span>'+esc(row[0])+'</span><b title="'+esc(row[1])+'">'+esc(row[1])+'</b></div>').join('');}
function setProjectStep(step,focus=true){projectStep=Math.max(1,Math.min(3,Number(step)||1));
  document.querySelectorAll('[data-project-step]').forEach(section=>section.hidden=Number(section.dataset.projectStep)!==projectStep);
  document.querySelectorAll('[data-project-indicator]').forEach(item=>{const n=Number(item.dataset.projectIndicator);
    item.classList.toggle('active',n===projectStep);item.classList.toggle('complete',n<projectStep);
    if(n===projectStep)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');});
  document.getElementById('project-back').hidden=projectStep===1;document.getElementById('project-next').hidden=projectStep===3;
  document.getElementById('submit-project').hidden=projectStep!==3;
  document.getElementById('project-foot-note').textContent=currentLocale==='zh'
    ?(projectStep===3?'检查确认后才会创建文件夹和仓库。':'完成当前步骤后继续；现在不会创建任何内容。')
    :(projectStep===3?'Nothing is created until you confirm this review.':'Continue after this step; nothing is created yet.');
  if(projectStep===3)syncProjectReview();
  if(focus)requestAnimationFrame(()=>{const pane=document.querySelector('[data-project-step="'+projectStep+'"]');
    (pane.querySelector('input:not([disabled]),select:not([disabled]),textarea:not([disabled]),button:not([disabled])')||pane).focus();});}
function validateProjectStep(step){document.getElementById('wizard-error').className='wizard-error';
  if(step===1&&!selectedProjectFolder){showInlineError('wizard-error',currentLocale==='zh'?'请选择本地项目文件夹。':'Choose a local project folder.');
    document.getElementById('choose-project-workspace').focus();return false;}
  const pane=document.querySelector('[data-project-step="'+step+'"]');const controls=[...pane.querySelectorAll('input,select,textarea')]
    .filter(control=>!control.disabled&&control.type!=='hidden');
  for(const control of controls){if(!control.checkValidity()){control.reportValidity();control.focus();return false;}}
  if(step===2){for(const role of ['generator','auditor']){const select=role==='generator'?generatorModel:auditorModel;
    if(select.value==='__custom__'&&!document.getElementById(role+'-custom').value.trim()){
      showInlineError('wizard-error',currentLocale==='zh'?(role==='generator'?'请输入生成者模型 ID。':'请输入审计者模型 ID。')
        :('Enter the '+role+' model ID.'));document.getElementById(role+'-custom').focus();return false;}}}
  return true;}
function openProjectModal(){projectForm.reset();document.getElementById('wizard-error').className='wizard-error';
  if(settingsState&&settingsState.doctor&&settingsState.doctor.status==='blocked'){
    openSettings('diagnostics');doctorMessage('Fix the required Environment Doctor items before creating a project.',true);return;}
  repoNameTouched={science:false,audit:false};selectedProjectFolder='';resetRepositoryCheck();
  configureProjectForm();const vendors=Object.keys((projectState&&projectState.models)||{});
  auditorVendor.value=vendors.includes('openai')?'openai':vendors[0];
  generatorVendor.value=vendors.includes('anthropic')?'anthropic':vendors.find(v=>v!==auditorVendor.value);
  syncRoleChoices();syncProjectType();syncRepoNames(true);updateWorkspaceFields(projectState&&projectState.workspace);
  projectModal.className='project-modal on';setProjectStep(1,false);
  setTimeout(()=>document.getElementById('project-name').focus(),0);}
function closeProjectModal(){projectModal.className='project-modal';setProjectStep(1,false);}

auditorVendor.onchange=()=>{syncRoleChoices();syncProjectReview();};generatorVendor.onchange=()=>{syncRoleChoices();syncProjectReview();};
auditorConnection.onchange=()=>{modelOptions(auditorVendor.value,auditorModel);syncProjectReview();};
generatorConnection.onchange=()=>{modelOptions(generatorVendor.value,generatorModel);syncProjectReview();};
auditorEndpoint.onchange=()=>{modelOptions(auditorVendor.value,auditorModel);syncProjectReview();};
generatorEndpoint.onchange=()=>{modelOptions(generatorVendor.value,generatorModel);syncProjectReview();};
auditorModel.onchange=()=>{syncCustomModel('auditor');syncProjectReview();};generatorModel.onchange=()=>{syncCustomModel('generator');syncProjectReview();};
document.getElementById('auditor-custom').oninput=syncProjectReview;document.getElementById('generator-custom').oninput=syncProjectReview;
document.querySelectorAll('[data-refresh-models]').forEach(button=>button.onclick=async()=>{
  const role=button.getAttribute('data-refresh-models');const vendor=role==='auditor'?auditorVendor.value:generatorVendor.value;
  const method=role==='auditor'?auditorConnection.value:generatorConnection.value;
  const endpoint=role==='auditor'?auditorEndpoint.value:generatorEndpoint.value;
  button.disabled=true;button.textContent='Refreshing…';
  try{const result=await api('/api/models/refresh',{role,vendor,method,endpoint});
    projectState.models[vendor]=result.models.map(id=>({id,hint:'visible to this account'}));
    modelOptions(vendor,role==='auditor'?auditorModel:generatorModel);
    button.textContent='Updated '+new Date(result.refreshed*1000).toLocaleTimeString();}
  catch(e){button.textContent='Refresh failed';const error=document.getElementById('wizard-error');
    error.textContent=e.message;error.className='wizard-error on';}
  finally{button.disabled=false;setTimeout(()=>button.textContent='Refresh from provider',3500);}
});
document.getElementById('project-name').addEventListener('input',()=>{syncRepoNames(false);syncProjectReview();});
document.getElementById('science-repo').addEventListener('input',()=>{repoNameTouched.science=true;resetRepositoryCheck();});
document.getElementById('audit-repo').addEventListener('input',()=>{repoNameTouched.audit=true;resetRepositoryCheck();});
document.getElementById('adopt-existing').onchange=resetRepositoryCheck;
document.getElementById('check-repositories').onclick=()=>checkRepositoryNames(true).catch(()=>{});
document.getElementById('choose-project-workspace').onclick=()=>chooseWorkspace('project');
document.getElementById('max-rounds-choice').onchange=ev=>{
  const n=Number(ev.target.value);document.getElementById('round-limit-help').textContent='Up to '+n
    +' generator → auditor round'+(n===1?'':'s')+', then the task pauses for you. It never auto-passes.';};
projectType.onchange=syncProjectType;
document.getElementById('github-toggle').onchange=()=>{syncGithubFields();syncProjectReview();};
document.getElementById('project-next').onclick=()=>{if(validateProjectStep(projectStep))setProjectStep(projectStep+1);};
document.getElementById('project-back').onclick=()=>setProjectStep(projectStep-1);
document.getElementById('github-connection').onclick=async ev=>{
  const connect=ev.target.closest('[data-connect-github]');const copy=ev.target.closest('[data-copy-github]');
  if(copy){try{await navigator.clipboard.writeText(copy.getAttribute('data-copy-github'));copy.textContent='Copied';}catch(e){}
    return;}
  if(connect){connect.disabled=true;connect.textContent='Connecting…';try{await api('/api/github/connect',{});}
    catch(e){connect.disabled=false;connect.textContent='Connect GitHub';showInlineError('wizard-error',e);}}
};
document.getElementById('create-project').onclick=openProjectModal;
document.getElementById('close-project-modal').onclick=closeProjectModal;
document.getElementById('cancel-project').onclick=closeProjectModal;
document.getElementById('projects-home').onclick=showProjects;
document.getElementById('back-projects').onclick=returnToProjects;
document.getElementById('project-switcher').onclick=showProjects;
document.getElementById('hub-brand').onclick=hideProjects;
document.getElementById('project-search').oninput=()=>projectState&&renderProjects(projectState);
document.getElementById('project-list').onclick=async ev=>{const row=ev.target.closest('[data-root]');
  const pin=ev.target.closest('[data-pin-project]');
  const remove=ev.target.closest('[data-delete-project]');
  const retry=ev.target.closest('[data-resume-root]');
  if(pin){ev.preventDefault();ev.stopPropagation();const root=pin.getAttribute('data-pin-project');
    const project=projectState&&projectState.items.find(p=>p.root===root);if(!project)return;
    pin.disabled=true;try{await api('/api/projects/pin',{root,pinned:!project.pinned});project.pinned=!project.pinned;
      renderProjects(projectState);}catch(e){pin.disabled=false;}return;}
  if(remove){ev.preventDefault();ev.stopPropagation();if(!remove.disabled)openDeleteProject(remove.getAttribute('data-delete-project'));return;}
  if(retry){ev.preventDefault();ev.stopPropagation();openRecovery(retry.getAttribute('data-resume-root'));return;}
  if(row)openProject(row.getAttribute('data-root'),row.getAttribute('data-current')==='1');};
document.getElementById('project-list').onkeydown=ev=>{
  if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('[data-root]')){ev.preventDefault();ev.target.click();}
  if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('[data-resume-root]')){ev.preventDefault();ev.target.click();}}
function openRecovery(root){
  const row=projectState&&projectState.items.find(p=>p.root===root);if(!row||!row.setup)return;
  const issue=row.setup.issue||{};document.getElementById('recovery-root').value=root;
  document.getElementById('recovery-science').value=row.setup.science||row.label||'';
  document.getElementById('recovery-audit').value=row.setup.audit||'';
  const note=document.getElementById('recovery-note');note.innerHTML='<b>'+esc(issue.title||'GitHub setup stopped')+'</b>'
    +esc(row.setup.detail||'Review the repository settings and retry.');
  const help=document.getElementById('recovery-help');help.hidden=!issue.url;if(issue.url)help.href=issue.url;
  document.getElementById('recovery-error').className='wizard-error';recoveryModal.className='project-modal on';
  renderRecoveryGithub();
  setTimeout(()=>document.getElementById('recovery-science').focus(),0);
}
function closeRecovery(){recoveryModal.className='project-modal';recoveryForm.reset();}
async function resumeProject(root,science,audit){
  try{const r=await api('/api/projects/resume',{root,science_repo:science,audit_repo:audit});activeProjectJob=r.job;createdRoot=null;
    closeRecovery();
    renderProjectJob([{id:r.job,status:'running',project:root.split('/').pop(),detail:'Resuming GitHub setup',steps:[]}]);}
  catch(e){const panel=document.getElementById('project-job');panel.className='job-panel on failed';
    document.getElementById('job-title').textContent='Could not resume setup';
    document.getElementById('job-detail').textContent=e.message;document.getElementById('job-steps').innerHTML='';}}
document.getElementById('close-recovery').onclick=closeRecovery;
document.getElementById('cancel-recovery').onclick=closeRecovery;
recoveryModal.addEventListener('click',ev=>{if(ev.target===recoveryModal)closeRecovery();});
document.getElementById('recovery-connect-github').onclick=async()=>{
  const button=document.getElementById('recovery-connect-github');button.disabled=true;button.textContent='Connecting…';
  try{await api('/api/github/connect',{});renderRecoveryGithub();}
  catch(e){button.disabled=false;button.textContent='Connect GitHub';showInlineError('recovery-error',e);}};
document.getElementById('recovery-connection').onclick=async ev=>{
  const copy=ev.target.closest('[data-copy-recovery-github]');if(!copy)return;
  try{await navigator.clipboard.writeText(copy.getAttribute('data-copy-recovery-github'));copy.textContent='Copied';}catch(e){}
};
recoveryForm.onsubmit=ev=>{ev.preventDefault();resumeProject(document.getElementById('recovery-root').value,
  document.getElementById('recovery-science').value.trim(),document.getElementById('recovery-audit').value.trim());};
function restoreProjectDraft(row){
  const draft=row&&row.draft||{};openProjectModal();if(!projectModal.classList.contains('on'))return false;
  const set=(selector,value)=>{const el=document.querySelector(selector);if(el&&value!==undefined&&value!==null)el.value=String(value);};
  set('#project-name',draft.name||row.project);set('[name="description"]',draft.description);
  set('#project-type',draft.project_type);set('#max-rounds-choice',draft.max_rounds);
  if([...auditorVendor.options].some(o=>o.value===draft.auditor_vendor))auditorVendor.value=draft.auditor_vendor;
  if([...generatorVendor.options].some(o=>o.value===draft.generator_vendor))generatorVendor.value=draft.generator_vendor;
  syncRoleChoices();
  const setRole=(role,connection,endpoint,model)=>{const connectionEl=role==='auditor'?auditorConnection:generatorConnection;
    const endpointEl=role==='auditor'?auditorEndpoint:generatorEndpoint,modelEl=role==='auditor'?auditorModel:generatorModel;
    if([...connectionEl.options].some(o=>o.value===connection&&!o.disabled))connectionEl.value=connection;
    if([...endpointEl.options].some(o=>o.value===endpoint))endpointEl.value=endpoint;
    modelOptions(role==='auditor'?auditorVendor.value:generatorVendor.value,modelEl);
    if([...modelEl.options].some(o=>o.value===model))modelEl.value=model;
    else if(model){modelEl.value='__custom__';document.getElementById(role+'-custom').value=model;}
    syncCustomModel(role);};
  setRole('auditor',draft.auditor_connection,draft.auditor_endpoint,draft.auditor_model);
  setRole('generator',draft.generator_connection,draft.generator_endpoint,draft.generator_model);
  document.getElementById('github-toggle').checked=draft.github===true;
  document.getElementById('adopt-existing').checked=draft.adopt_existing===true;
  document.querySelector('[name="public"]').checked=draft.public===true;
  set('#science-repo',draft.science_repo||row.science);set('#audit-repo',draft.audit_repo||row.audit);
  repoNameTouched={science:Boolean(draft.science_repo),audit:Boolean(draft.audit_repo)};
  selectedProjectFolder=String(draft.workspace||row.workspace||row.root||'');
  updateWorkspaceFields(selectedProjectFolder);syncProjectType();syncGithubFields();syncProjectReview();resetRepositoryCheck();
  return true;
}
document.getElementById('project-job').onclick=async ev=>{const action=ev.target.closest('[data-job-action]');if(!action)return;
  const kind=action.getAttribute('data-job-action'),root=action.getAttribute('data-root');
  const row=(projectState&&projectState.jobs||[]).find(j=>j.id===activeProjectJob);
  if(kind==='connect_github')document.querySelector('[data-connect-github]')?.click();
  else if(kind==='edit_repositories'&&root)openRecovery(root);
  else if(kind==='edit_new_repositories'&&row){restoreProjectDraft(row);setProjectStep(3);}
  else if(kind==='choose_new_workspace'&&row){if(restoreProjectDraft(row))chooseWorkspace('project');}
  else if(kind==='reveal_folder'&&root){if(!revealProjectFolder(root))document.getElementById('job-detail').textContent='Open this folder in Finder, commit or stash its local changes, then choose Try again.';}
  else if(kind==='retry'&&root)openRecovery(root);
  else if(kind==='retry_job'&&row){action.disabled=true;
    try{const result=await api('/api/projects/job',{action:'retry',job_id:row.id});activeProjectJob=result.job;
      renderProjectJob([{id:result.job,status:'running',project:row.project,detail:'Checking the project again',steps:[]}]);}
    catch(e){action.disabled=false;document.getElementById('job-detail').textContent=e.message;}}
  else if(kind==='dismiss_job'&&row){action.disabled=true;
    try{await api('/api/projects/job',{action:'dismiss',job_id:row.id});activeProjectJob=null;renderProjectJob([]);await refreshProjects();}
    catch(e){action.disabled=false;document.getElementById('job-detail').textContent=e.message;}}};
document.getElementById('open-created').onclick=()=>createdRoot&&openProject(createdRoot,false);
projectModal.addEventListener('click',ev=>{if(ev.target===projectModal)closeProjectModal();});
projectForm.onsubmit=async ev=>{ev.preventDefault();if(projectStep<3){if(validateProjectStep(projectStep))setProjectStep(projectStep+1);return;}
  const submit=document.getElementById('submit-project');
  const error=document.getElementById('wizard-error');error.className='wizard-error';submit.disabled=true;
  const fd=new FormData(projectForm);const payload=Object.fromEntries(fd.entries());
  payload.auditor_model=auditorModel.value==='__custom__'?document.getElementById('auditor-custom').value.trim():auditorModel.value;
  payload.generator_model=generatorModel.value==='__custom__'?document.getElementById('generator-custom').value.trim():generatorModel.value;
  payload.github=document.getElementById('github-toggle').checked;payload.public=fd.has('public');
  payload.adopt_existing=document.getElementById('adopt-existing').checked;
  payload.use_selected_folder=true;
  payload.workspace=selectedProjectFolder;
  payload.max_rounds=Number(payload.max_rounds);
  try{if(payload.github){const checked=await checkRepositoryNames(false);if(!checked.ready){
      throw new Error('Choose unused names, or explicitly allow CrossAudit to use the accessible repositories.');}}
    const r=await api('/api/projects/create',payload);activeProjectJob=r.job;createdRoot=null;
    closeProjectModal();renderProjectJob([{id:r.job,status:'running',project:payload.name,
      detail:'Starting local project setup'}]);}
  catch(e){showInlineError('wizard-error',e);}
  submit.disabled=false;};

function activeChat(d){return d&&d.chats&&(d.chats.items||[]).find(row=>row.id===activeChatId)||null;}
function chatCycles(d){return (d.cycles||[]).filter(row=>(row.chat_id||'history')===activeChatId);}
function chatProgress(d){const p=d.progress;return p&&(p.chat_id||'history')===activeChatId?p:null;}
function statusOf(d){
  const p=chatProgress(d),cycles=chatCycles(d);
  if(p && !p.finished) return 'running';
  if(p && p.finished) return p.outcome || 'ready';
  if(cycles.length) return cycles[cycles.length-1].status;
  return 'ready';
}
function titleOf(d){
  const chat=activeChat(d);if(chat)return chat.title;
  const users = [...d.generator_stream,...d.auditor_stream].filter(x => x.kind === 'you'&&(x.chat_id||'history')===activeChatId);
  if(users.length) return users.sort((a,b) => b.t-a.t)[0].utterance.replace(/\s+/g,' ').slice(0,88);
  const p=chatProgress(d);if(p&&p.task)return p.task.replace(/\s+/g,' ').slice(0,88);
  return 'New chat';
}
function fileUrl(path,view=false){return '/api/file?t=' + encodeURIComponent(T) + '&path=' + encodeURIComponent(path)
  +(view?'&view=1':'');}
async function previewData(path){
  const response=await fetch('/api/preview?t='+encodeURIComponent(T)+'&path='+encodeURIComponent(path));
  const raw=await response.text();let data={};try{data=raw?JSON.parse(raw):{};}catch(e){}
  if(!response.ok)throw new Error(denialText(data)||raw||('Preview failed ('+response.status+')'));
  return data;
}
function formatBytes(value){
  if(value===null||value===undefined) return '';
  const units=['B','KB','MB','GB','TB','PB'];let size=Number(value),unit=0;
  while(size>=1000&&unit<units.length-1){size/=1000;unit++;}
  return (unit===0?String(size):size.toFixed(size<10?1:0))+' '+units[unit];
}
function artifactRecord(item){
  if(typeof item==='string'){
    const name=item.split('/').pop();const extension=(name.includes('.')?name.split('.').pop():'FILE').toUpperCase();
    return {path:item,name,extension,kind:'File',bytes:null,available:true};
  }
  return item;
}
function auditStatus(d,sha){
  if(!d||!sha) return 'generated';
  const cycle=d.cycles.find(c=>c.sha===sha);
  return cycle ? cycle.status.toLowerCase() : 'generated';
}
function outputFile(item,status,context){
  const f=artifactRecord(item);const bits=[context||f.kind,formatBytes(f.bytes)].filter(Boolean);
  const core='<span class="artifact-icon">'+esc((f.extension||'FILE').slice(0,4))+'</span>'
    +'<span class="artifact-copy"><span class="artifact-name">'+esc(f.path)+'</span>'
    +'<span class="artifact-context">'+esc(bits.join(' · '))+'</span></span>';
  if(f.available===false) return '<div class="output-file unavailable"><span class="artifact-main">'+core+'</span>'
    +'<span class="artifact-action" aria-hidden="true">-</span></div>';
  const name=esc(f.name||f.path),path=esc(f.path);
  const primary='<button type="button" class="artifact-main" data-preview="'+path+'" aria-label="Preview '+name+'">'+core+'</button>';
  return '<div class="artifact output-file '+esc(String(status||'').toLowerCase())+'">'+primary+'<span class="artifact-actions">'
    +'<button type="button" class="artifact-action" data-preview="'+path+'" aria-label="Preview '+name+'" title="File preview">⌕</button>'
    +'<a class="artifact-action" href="'+fileUrl(f.path)+'" download aria-label="Download '+name+'" title="Download">↓</a>'
    +'</span></div>';
}

/* ---------- Universal file preview (North Star §11) -------------------------
   A type-dispatching framework: preview_artifact classifies the file server-side
   and this layer renders each kind. All untrusted file content reaches the DOM
   only through esc()/textContent or a controlled tokenizer whose text is
   escaped; images (incl. SVG) render via <img> so no embedded script runs, PDFs
   via a sandboxed iframe, HTML via a scriptless sandboxed iframe. The download
   is always the complete file.                                               */
const filePreviewModal=document.getElementById('file-preview-modal');
const filePreviewBody=document.getElementById('file-preview-body');
const filePreviewNote=document.getElementById('file-preview-note');
const filePreviewMeta=document.getElementById('file-preview-meta');
const previewToolbar=document.getElementById('file-preview-toolbar');
const previewFind=document.getElementById('file-preview-find');
const previewSearch=document.getElementById('file-preview-search');
const previewFindCount=document.getElementById('file-preview-find-count');
const previewFindPrev=document.getElementById('file-preview-find-prev');
const previewFindNext=document.getElementById('file-preview-find-next');
const previewZoom=document.getElementById('file-preview-zoom');
const previewZoomIn=document.getElementById('file-preview-zoom-in');
const previewZoomOut=document.getElementById('file-preview-zoom-out');
const previewZoomReset=document.getElementById('file-preview-zoom-reset');
const previewZoomLevel=document.getElementById('file-preview-zoom-level');
const previewOutlineToggle=document.getElementById('file-preview-outline-toggle');
const previewOutline=document.getElementById('file-preview-outline');
const previewSourceBtn=document.getElementById('file-preview-source');
const previewWrapBtn=document.getElementById('file-preview-wrap');
const previewCopyBtn=document.getElementById('file-preview-copy');
let filePreviewTrigger=null,previewSession=null;
const CODE_VIRT_LINES=1500,CODE_ROW_H=20;

function safeUrl(raw){
  const cleaned=String(raw==null?'':raw).replace(/[\u0000-\u0020]+/g,'');
  const lower=cleaned.toLowerCase();
  if(lower.startsWith('javascript:')||lower.startsWith('data:')||lower.startsWith('vbscript:')||lower.startsWith('file:'))return null;
  if(/^(https?:|mailto:)/i.test(cleaned))return cleaned;
  if(/^[a-z][a-z0-9+.-]*:/i.test(cleaned))return null;
  return cleaned;
}
function inlineMarkdown(value){
  let s=esc(value);
  // Bounded quantifiers (and no newline crossing) keep every replace linear: an
  // unbounded [^x]+ over a pathological line (e.g. a megabyte of '[') backtracks
  // O(N^2) and freezes this single-threaded console for minutes. The caps are
  // generous for real prose; an over-long span just renders as plain text.
  s=s.replace(/`([^`\n]{1,500})`/g,(m,g)=>'<code>'+g+'</code>');
  s=s.replace(/\*\*([^*\n]{1,500})\*\*/g,'<strong>$1</strong>');
  s=s.replace(/(^|[^*])\*([^*\n]{1,500})\*/g,'$1<em>$2</em>');
  s=s.replace(/\[([^\]\n]{1,500})\]\(([^)\n]{1,2048})\)/g,(m,text,url)=>{
    const href=safeUrl(url.replace(/&amp;/g,'&'));
    return href?'<a href="'+esc(href)+'" target="_blank" rel="noopener noreferrer nofollow">'+text+'</a>':m;});
  return s;
}
function renderMarkdown(value){
  const lines=String(value||'').replace(/\r\n?/g,'\n').split('\n');
  let html='',code=false,list='',hi=0;const outline=[];
  const closeList=()=>{if(list){html+='</'+list+'>';list='';}};
  for(const line of lines){
    if(line.startsWith('```')){closeList();html+=code?'</code></pre>':'<pre><code>';code=!code;continue;}
    if(code){html+=esc(line)+'\n';continue;}
    let m=line.match(/^(#{1,6})\s+(.+?)\s*#*$/);
    if(m){closeList();const level=Math.min(6,m[1].length);const id='pv-h-'+(hi++);const text=m[2].trim();
      outline.push({level,text,id});html+='<h'+level+' id="'+id+'">'+inlineMarkdown(text)+'</h'+level+'>';continue;}
    m=line.match(/^\s*[-*+]\s+(.+)$/);if(m){if(list!=='ul'){closeList();list='ul';html+='<ul>';}html+='<li>'+inlineMarkdown(m[1])+'</li>';continue;}
    m=line.match(/^\s*\d+[.)]\s+(.+)$/);if(m){if(list!=='ol'){closeList();list='ol';html+='<ol>';}html+='<li>'+inlineMarkdown(m[1])+'</li>';continue;}
    if(line.startsWith('> ')){closeList();html+='<blockquote>'+inlineMarkdown(line.slice(2))+'</blockquote>';continue;}
    closeList();
    if(/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line))html+='<hr>';
    else if(line.trim())html+='<p>'+inlineMarkdown(line)+'</p>';
  }
  closeList();if(code)html+='</code></pre>';return {html,outline};
}
function copyText(text,btn){
  const done=()=>{const old=btn.textContent;btn.textContent='Copied';setTimeout(()=>{btn.textContent=old;},1200);};
  const fallback=()=>{const ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.opacity='0';
    document.body.appendChild(ta);ta.select();try{document.execCommand('copy');done();}catch(e){}document.body.removeChild(ta);};
  if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(text).then(done,fallback);else fallback();
}
const CODE_KW={
  python:'False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case print self',
  javascript:'await async break case catch class const continue debugger default delete do else export extends finally for function if import in instanceof let new return super switch this throw try typeof var void while with yield of static get set null true false undefined NaN',
  typescript:'await async break case catch class const continue declare default delete do else enum export extends finally for function if implements import in instanceof interface let namespace new readonly return super switch this throw try type typeof var void while yield of static public private protected null true false undefined any number string boolean',
  json:'true false null',
  sql:'select from where insert into update delete create table drop alter add join left right inner outer full on group by order having limit offset union all as and or not null is in values set distinct count sum avg min max case when then end',
  bash:'if then else elif fi for while until do done case esac function in return export local readonly echo cd exit source',
  yaml:'true false null yes no on off',
  toml:'true false'};
const CODE_RULES={
  python:{line:['#'],block:[],str:['"',"'"]},
  javascript:{line:['//'],block:[['/*','*/']],str:['"',"'",'`']},
  typescript:{line:['//'],block:[['/*','*/']],str:['"',"'",'`']},
  json:{line:[],block:[],str:['"']},
  sql:{line:['--'],block:[['/*','*/']],str:["'"]},
  bash:{line:['#'],block:[],str:['"',"'"]},
  yaml:{line:['#'],block:[],str:['"',"'"]},
  toml:{line:['#'],block:[],str:['"',"'"]},
  css:{line:[],block:[['/*','*/']],str:['"',"'"]}};
function kwSet(lang){const s=new Set();for(const w of (CODE_KW[lang]||'').split(/\s+/))if(w)s.add(w);return s;}
function tokenizeCode(text,rules,kw){
  if(!rules)return esc(text);
  let out='',i=0;const n=text.length;
  const push=(cls,s)=>{out+=cls?'<span class="'+cls+'">'+esc(s)+'</span>':esc(s);};
  while(i<n){
    const c=text[i];
    const lc=rules.line.find(p=>text.startsWith(p,i));
    if(lc){push('tok-com',text.slice(i));break;}
    const bc=rules.block.find(pair=>text.startsWith(pair[0],i));
    if(bc){const end=text.indexOf(bc[1],i+bc[0].length);const stop=end<0?n:end+bc[1].length;push('tok-com',text.slice(i,stop));i=stop;continue;}
    if(rules.str.indexOf(c)>=0){let j=i+1;while(j<n){if(text[j]==='\\'){j+=2;continue;}if(text[j]===c){j++;break;}j++;}const stop=Math.min(j,n);push('tok-str',text.slice(i,stop));i=stop;continue;}
    if(c>='0'&&c<='9'&&(i===0||!/[\w.]/.test(text[i-1]))){const m=/^(0x[0-9a-f]+|\d[\d_]*\.?\d*(e[+-]?\d+)?)/i.exec(text.slice(i));if(m){push('tok-num',m[0]);i+=m[0].length;continue;}}
    if(/[A-Za-z_$]/.test(c)){const m=/^[A-Za-z_$][\w$]*/.exec(text.slice(i));const w=m[0];push(kw.has(w)?'tok-key':'',w);i+=w.length;continue;}
    push('',c);i++;
  }
  return out;
}
function tokenizeMarkup(text){
  let out='',i=0;const n=text.length;
  const push=(cls,s)=>{out+=cls?'<span class="'+cls+'">'+esc(s)+'</span>':esc(s);};
  while(i<n){
    if(text.startsWith('<!--',i)){const end=text.indexOf('-->',i);const stop=end<0?n:end+3;push('tok-com',text.slice(i,stop));i=stop;continue;}
    if(text[i]==='<'){const end=text.indexOf('>',i);const stop=end<0?n:end+1;push('tok-tag',text.slice(i,stop));i=stop;continue;}
    let j=text.indexOf('<',i);if(j<0)j=n;push('',text.slice(i,j));i=j;
  }
  return out;
}
function searchLineHTML(text,arr,activeGid){
  if(!arr||!arr.length)return esc(text);
  let out='',last=0;
  for(const mm of arr){out+=esc(text.slice(last,mm.start));
    out+='<mark class="preview-hit'+(mm.gid===activeGid?' on':'')+'">'+esc(text.slice(mm.start,mm.end))+'</mark>';last=mm.end;}
  out+=esc(text.slice(last));return out;
}
function resetPreviewChrome(){
  if(previewSession&&previewSession.teardown){try{previewSession.teardown();}catch(e){}}
  previewSession=null;
  previewToolbar.hidden=true;previewFind.hidden=true;previewZoom.hidden=true;
  for(const el of [previewOutlineToggle,previewSourceBtn,previewWrapBtn,previewCopyBtn]){el.hidden=true;el.disabled=false;el.removeAttribute('aria-pressed');el.title='';}
  previewOutline.hidden=true;previewOutline.replaceChildren();
  previewOutlineToggle.setAttribute('aria-pressed','false');
  previewSearch.value='';previewFindCount.textContent='';
  previewSearch.oninput=null;previewSearch.onkeydown=null;
  previewFindPrev.onclick=null;previewFindNext.onclick=null;previewFindPrev.disabled=false;previewFindNext.disabled=false;
  previewCopyBtn.onclick=null;previewWrapBtn.onclick=null;previewSourceBtn.onclick=null;previewOutlineToggle.onclick=null;
  previewZoomIn.onclick=null;previewZoomOut.onclick=null;previewZoomReset.onclick=null;previewZoomLevel.textContent='100%';
}
function closeFilePreview(){resetPreviewChrome();filePreviewModal.className='project-modal';
  filePreviewBody.classList.remove('fill');filePreviewBody.replaceChildren();
  if(filePreviewTrigger){filePreviewTrigger.focus();filePreviewTrigger=null;}}
function buildOutline(entries,navigate){
  if(!entries||!entries.length)return;
  previewToolbar.hidden=false;previewOutlineToggle.hidden=false;
  const frag=document.createDocumentFragment();
  entries.forEach((e,i)=>{
    const node=navigate?document.createElement('button'):document.createElement('div');
    if(navigate){node.type='button';node.onclick=()=>navigate(e,i);}
    node.className='lvl'+Math.min(6,Math.max(0,e.level||0));node.textContent=e.text||'';node.title=e.text||'';
    frag.appendChild(node);});
  previewOutline.replaceChildren(frag);previewOutline.hidden=false;previewOutlineToggle.setAttribute('aria-pressed','true');
  previewOutlineToggle.onclick=()=>{const show=previewOutline.hidden;previewOutline.hidden=!show;previewOutlineToggle.setAttribute('aria-pressed',String(show));};
}
function renderCode(data){
  filePreviewBody.classList.add('fill');
  const wholeText=String(data.text||'');
  const lines=wholeText.split('\n');const total=lines.length;
  const language=data.language||'';const markup=(language==='html'||language==='xml');
  const rules=CODE_RULES[language];const kw=kwSet(language);
  const virtual=total>CODE_VIRT_LINES;let wrap=false;
  const root=document.createElement('div');root.className='preview-code'+(virtual?' virtual':'');
  root.style.setProperty('--gutter-w',String(String(total).length));
  const scroll=document.createElement('div');scroll.className='preview-code-scroll';
  const host=document.createElement('div');host.className='preview-code-lines';
  scroll.appendChild(host);root.appendChild(scroll);
  let query='',byLine=new Map(),matchList=[],active=-1;
  function inner(idx){
    if(query){return searchLineHTML(lines[idx],byLine.get(idx),active);}
    const t=markup?tokenizeMarkup(lines[idx]):tokenizeCode(lines[idx],rules,kw);
    return t||' ';
  }
  function rowHTML(idx){return '<div class="preview-row" data-line="'+idx+'"><span class="preview-gutter">'+(idx+1)+'</span><span class="preview-line">'+inner(idx)+'</span></div>';}
  let winFirst=-1,winLast=-1;
  function renderWindow(force){
    const vh=scroll.clientHeight||520;
    const first=Math.max(0,Math.floor(scroll.scrollTop/CODE_ROW_H)-8);
    const count=Math.ceil(vh/CODE_ROW_H)+16;const last=Math.min(total,first+count);
    if(!force&&first===winFirst&&last===winLast)return;
    winFirst=first;winLast=last;
    let html='<div style="height:'+(first*CODE_ROW_H)+'px"></div>';
    for(let i=first;i<last;i++)html+=rowHTML(i);
    html+='<div style="height:'+((total-last)*CODE_ROW_H)+'px"></div>';host.innerHTML=html;
  }
  function renderFull(){let html='';for(let i=0;i<total;i++)html+=rowHTML(i);host.innerHTML=html;}
  function paint(){if(virtual)renderWindow(true);else renderFull();}
  let onScroll=null;
  if(virtual){onScroll=()=>renderWindow(false);scroll.addEventListener('scroll',onScroll,{passive:true});}
  paint();
  function compute(q){
    byLine=new Map();matchList=[];query=q;if(!q)return;
    const needle=q.toLowerCase();
    for(let i=0;i<total;i++){const hay=lines[i].toLowerCase();let from=0,idx;
      while((idx=hay.indexOf(needle,from))>=0){const gid=matchList.length;
        if(!byLine.has(i))byLine.set(i,[]);byLine.get(i).push({start:idx,end:idx+q.length,gid});
        matchList.push({line:i});from=idx+q.length;if(matchList.length>20000)return;}
    }
  }
  function updateCount(){previewFindCount.textContent=matchList.length?((active+1)+'/'+matchList.length):(query?'0/0':'');}
  function toActive(){if(active<0||!matchList[active])return;const ln=matchList[active].line;
    if(virtual){scroll.scrollTop=Math.max(0,ln*CODE_ROW_H-scroll.clientHeight/2);renderWindow(true);}
    else{const r=host.querySelector('.preview-row[data-line="'+ln+'"]');if(r)r.scrollIntoView({block:'center'});}}
  function run(q){compute(q);active=matchList.length?0:-1;paint();updateCount();toActive();}
  function step(d){if(!matchList.length)return;active=(active+d+matchList.length)%matchList.length;paint();updateCount();toActive();}
  previewToolbar.hidden=false;previewFind.hidden=false;previewCopyBtn.hidden=false;previewWrapBtn.hidden=false;
  previewWrapBtn.setAttribute('aria-pressed','false');
  if(virtual){previewWrapBtn.disabled=true;previewWrapBtn.title='Wrap is off for very long files';}
  previewSearch.oninput=()=>run(previewSearch.value);
  previewSearch.onkeydown=(e)=>{if(e.key==='Enter'){e.preventDefault();step(e.shiftKey?-1:1);}};
  previewFindNext.onclick=()=>step(1);previewFindPrev.onclick=()=>step(-1);
  previewWrapBtn.onclick=()=>{if(virtual)return;wrap=!wrap;root.classList.toggle('wrap',wrap);previewWrapBtn.setAttribute('aria-pressed',String(wrap));};
  previewCopyBtn.onclick=()=>copyText(wholeText,previewCopyBtn);
  filePreviewBody.appendChild(root);
  previewSession={teardown:()=>{if(onScroll)scroll.removeEventListener('scroll',onScroll);}};
}
function renderTable(data){
  filePreviewBody.classList.add('fill');
  const cols=data.columns||[],rows=data.rows||[];
  let nCols=data.col_count||cols.length;for(const r of rows)nCols=Math.max(nCols,r.length);
  const numRe=/^-?[$]?\d[\d,]*\.?\d*%?$/;const numeric=[];
  for(let c=0;c<nCols;c++){let any=false,allNum=true;for(const r of rows){const v=(r[c]||'').trim();if(!v)continue;any=true;if(!numRe.test(v)){allNum=false;break;}}numeric[c]=any&&allNum;}
  const wrap=document.createElement('div');wrap.className='preview-table-wrap';
  const table=document.createElement('table');table.className='preview-table';
  let html='<thead><tr><th></th>';
  for(let c=0;c<nCols;c++)html+='<th'+(numeric[c]?' class="num"':'')+'>'+esc(cols[c]!==undefined?cols[c]:'')+'</th>';
  html+='</tr></thead><tbody>';
  for(let r=0;r<rows.length;r++){html+='<tr><th>'+(r+1)+'</th>';const row=rows[r];
    for(let c=0;c<nCols;c++)html+='<td'+(numeric[c]?' class="num"':'')+'>'+esc(row[c]!==undefined?row[c]:'')+'</td>';html+='</tr>';}
  html+='</tbody>';table.innerHTML=html;wrap.appendChild(table);filePreviewBody.appendChild(wrap);
  const cells=Array.from(table.querySelectorAll('tbody td'));
  let hits=[],active=-1;
  function updateCount(){previewFindCount.textContent=hits.length?((active+1)+'/'+hits.length):(previewSearch.value?'0/0':'');}
  function focusActive(){for(const td of hits)td.querySelectorAll('mark').forEach(x=>x.classList.remove('on'));
    if(active>=0){const td=hits[active];td.querySelectorAll('mark').forEach(x=>x.classList.add('on'));td.scrollIntoView({block:'center',inline:'center'});}}
  function markCell(td,q){const txt=td.textContent,low=txt.toLowerCase(),needle=q.toLowerCase();let out='',from=0,idx;
    while((idx=low.indexOf(needle,from))>=0){out+=esc(txt.slice(from,idx))+'<mark class="preview-hit">'+esc(txt.slice(idx,idx+q.length))+'</mark>';from=idx+q.length;}
    out+=esc(txt.slice(from));td.innerHTML=out;}
  function run(q){for(const td of hits)td.textContent=td.textContent;hits=[];active=-1;
    const needle=(q||'').toLowerCase();
    if(needle){for(const td of cells){if(td.textContent.toLowerCase().indexOf(needle)>=0){markCell(td,q);hits.push(td);if(hits.length>20000)break;}}}
    active=hits.length?0:-1;updateCount();focusActive();}
  function step(d){if(!hits.length)return;active=(active+d+hits.length)%hits.length;updateCount();focusActive();}
  previewToolbar.hidden=false;previewFind.hidden=false;
  previewSearch.oninput=()=>run(previewSearch.value);
  previewSearch.onkeydown=(e)=>{if(e.key==='Enter'){e.preventDefault();step(e.shiftKey?-1:1);}};
  previewFindNext.onclick=()=>step(1);previewFindPrev.onclick=()=>step(-1);
}
function renderImage(data,path){
  filePreviewBody.classList.add('fill');
  const stage=document.createElement('div');stage.className='preview-stage';
  const img=document.createElement('img');img.className='preview-image';img.alt=data.name||'';img.decoding='async';img.src=fileUrl(path,true);
  stage.appendChild(img);filePreviewBody.appendChild(stage);
  let scale=1,tx=0,ty=0,drag=null;
  function apply(){img.style.transform='translate('+tx+'px,'+ty+'px) scale('+scale+')';img.classList.toggle('zoomed',scale!==1);previewZoomLevel.textContent=Math.round(scale*100)+'%';}
  function setScale(s){scale=Math.min(8,Math.max(1,s));if(scale===1){tx=0;ty=0;}apply();}
  previewToolbar.hidden=false;previewZoom.hidden=false;
  previewZoomIn.onclick=()=>setScale(scale*1.25);previewZoomOut.onclick=()=>setScale(scale/1.25);previewZoomReset.onclick=()=>setScale(1);
  const onWheel=(e)=>{e.preventDefault();setScale(scale*(e.deltaY<0?1.1:0.9));};
  const onDown=(e)=>{if(scale===1)return;drag={x:e.clientX,y:e.clientY,tx,ty};stage.classList.add('grabbing');e.preventDefault();};
  const onMove=(e)=>{if(!drag)return;tx=drag.tx+(e.clientX-drag.x);ty=drag.ty+(e.clientY-drag.y);apply();};
  const onUp=()=>{drag=null;stage.classList.remove('grabbing');};
  stage.addEventListener('wheel',onWheel,{passive:false});stage.addEventListener('mousedown',onDown);
  window.addEventListener('mousemove',onMove);window.addEventListener('mouseup',onUp);
  img.addEventListener('dblclick',()=>setScale(scale===1?2:1));apply();
  previewSession={teardown:()=>{stage.removeEventListener('wheel',onWheel);window.removeEventListener('mousemove',onMove);window.removeEventListener('mouseup',onUp);}};
}
function renderDocument(data){
  const outline=(data.outline||[]).map((o,i)=>({level:o.level,text:o.text,id:'pv-d-'+i,domId:null}));
  const byText=new Map();for(const o of outline)if(!byText.has(o.text))byText.set(o.text,o);
  const art=document.createElement('article');art.className='preview-document';const frag=document.createDocumentFragment();
  for(const ln of String(data.text||'').split('\n')){const div=document.createElement('div');div.textContent=ln||' ';
    const o=byText.get(ln.trim());if(o&&!o.domId){o.domId=o.id;div.id=o.id;}frag.appendChild(div);}
  art.appendChild(frag);filePreviewBody.appendChild(art);
  buildOutline(outline,(e)=>{if(e.domId){const el=document.getElementById(e.domId);if(el)el.scrollIntoView({block:'start'});}});
  filePreviewNote.textContent='Preview is reconstructed from the final audited DOCX binary.';
}
function renderBinary(data){
  const host=document.createElement('div');host.className='preview-hex';
  const dl=document.createElement('dl');dl.className='preview-meta-grid';
  const add=(k,v)=>{const dt=document.createElement('dt');dt.textContent=k;const dd=document.createElement('dd');dd.textContent=v;dl.appendChild(dt);dl.appendChild(dd);};
  add('Type',data.mime||'application/octet-stream');add('Size',formatBytes(data.bytes));
  if(data.sha256)add('SHA-256',data.sha256);
  host.appendChild(dl);
  if(data.hex){const cap=document.createElement('div');cap.className='preview-hex-cap';cap.textContent='Byte sample';host.appendChild(cap);
    const pre=document.createElement('pre');pre.textContent=data.hex;host.appendChild(pre);}
  filePreviewBody.appendChild(host);
}
function renderMarkdownView(data){
  const built=renderMarkdown(data.text);
  const article=()=>{const a=document.createElement('article');a.className='preview-markdown';a.innerHTML=built.html;return a;};
  filePreviewBody.appendChild(article());
  buildOutline(built.outline.map(o=>({level:o.level,text:o.text,id:o.id})),
    (e)=>{const el=document.getElementById(e.id);if(el)el.scrollIntoView({block:'start'});});
  previewToolbar.hidden=false;previewSourceBtn.hidden=false;previewCopyBtn.hidden=false;
  previewSourceBtn.setAttribute('aria-pressed','false');let showingSource=false;
  previewSourceBtn.onclick=()=>{showingSource=!showingSource;previewSourceBtn.setAttribute('aria-pressed',String(showingSource));
    filePreviewBody.replaceChildren();
    if(showingSource){const pre=document.createElement('pre');pre.className='preview-rawsrc';pre.textContent=data.text;filePreviewBody.appendChild(pre);previewOutline.hidden=true;}
    else{filePreviewBody.appendChild(article());}};
  previewCopyBtn.onclick=()=>copyText(data.text,previewCopyBtn);
}
async function openFilePreview(path,trigger){
  filePreviewTrigger=trigger||document.activeElement;filePreviewModal.className='project-modal on';
  document.getElementById('file-preview-title').textContent=path.split('/').pop()||'File preview';
  filePreviewMeta.textContent='Preparing preview…';
  const download=document.getElementById('file-preview-download');download.href=fileUrl(path);download.setAttribute('download','');
  resetPreviewChrome();filePreviewBody.classList.remove('fill');
  filePreviewBody.innerHTML='<div class="preview-loading">Loading audited deliverable…</div>';
  filePreviewNote.textContent='The complete file remains available to download.';
  let data;
  try{data=await previewData(path);}
  catch(error){filePreviewBody.classList.remove('fill');filePreviewBody.innerHTML='<div class="preview-unavailable">'+esc(error.message)+'</div>';return;}
  resetPreviewChrome();filePreviewBody.classList.remove('fill');filePreviewBody.replaceChildren();
  const metaBits=[data.mime||data.kind];
  try{
    if(data.kind==='pdf'){
      const frame=document.createElement('iframe');frame.className='preview-frame';frame.title=data.name||'PDF';frame.src=fileUrl(path,true);
      filePreviewBody.classList.add('fill');filePreviewBody.appendChild(frame);
      buildOutline((data.outline||[]).map(o=>({level:o.level,text:o.text})),null);
    }else if(data.kind==='image'){
      renderImage(data,path);if(data.width&&data.height)metaBits.push(data.width+'×'+data.height);
    }else if(data.kind==='html'){
      const frame=document.createElement('iframe');frame.className='preview-frame';frame.title=data.name;frame.setAttribute('sandbox','');
      frame.srcdoc='<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:"><style>body{font:15px/1.6 system-ui,sans-serif;margin:32px;color:#202124}img{max-width:100%}pre{white-space:pre-wrap}</style>'+data.text;
      filePreviewBody.classList.add('fill');filePreviewBody.appendChild(frame);
      filePreviewNote.textContent='HTML preview is isolated from the app and cannot access the network.';
    }else if(data.kind==='markdown'){renderMarkdownView(data);
    }else if(data.kind==='document'){renderDocument(data);
    }else if(data.kind==='table'){renderTable(data);metaBits.push((data.row_count||0)+'×'+(data.col_count||0));
    }else if(data.kind==='text'){renderCode(data);
    }else{renderBinary(data);}
    metaBits.push(formatBytes(data.bytes));
    filePreviewMeta.textContent=metaBits.filter(Boolean).join(' · ');
    if(data.truncated)filePreviewNote.textContent=(data.kind==='table')
      ?'Some rows or columns are hidden for responsiveness; the download is complete.'
      :'The reading preview is shortened for responsiveness; the download is complete.';
  }catch(error){resetPreviewChrome();filePreviewBody.classList.remove('fill');filePreviewBody.replaceChildren();
    filePreviewBody.innerHTML='<div class="preview-unavailable">'+esc(error.message)+'</div>';}
}
document.getElementById('close-file-preview').onclick=closeFilePreview;
filePreviewModal.addEventListener('click',event=>{if(event.target===filePreviewModal)closeFilePreview();});
document.addEventListener('click',event=>{const button=event.target.closest('[data-preview]');if(button){event.preventDefault();openFilePreview(button.getAttribute('data-preview'),button);}});
function artifactList(items,status,sha){
  if(!items||!items.length) return '';
  const rows=items.map(f=>outputFile(f,status,'')).join('');
  const head='<div class="output-head">Files produced<span class="output-count">'+items.length+'</span></div>';
  if(items.length<=2) return '<section class="output-files" aria-label="Generated files">'+head
    +'<div class="artifact-list">'+rows+'</div></section>';
  const key=esc(String(sha||'')+':'+items.length);
  const open=expandedGroups.has(String(sha||'')+':'+items.length);
  const first=artifactRecord(items[0]);
  return '<section class="output-files" aria-label="Generated files">'+head
    +'<div class="deliverable-group'+(open?' open':'')+'"><button type="button" class="group-head" data-group-toggle="'+key+'" aria-expanded="'+(open?'true':'false')+'">'
    +'<span class="deliverable-icon" aria-hidden="true"></span><span class="group-title"><b>'+items.length+' files</b>'
    +'<span>'+esc(first.name||first.path)+' +'+(items.length-1)+'</span></span>'
    +'<span class="group-chevron" aria-hidden="true"></span></button>'
    +'<div class="group-detail"><div class="group-detail-inner">'+rows
    +'<button type="button" class="output-more" data-open-artifacts>Open Files panel</button>'
    +'</div></div></div></section>';
}
// R1. The verdict a person reads. The raw vocabulary (PASS / BLOCKED /
// ESCALATE / DCL_ONLY) stays in --json, receipts, reports and the inspector;
// the main surface says what it means. An unknown word passes through.
const VERDICT_WORDS={PASS:'Passed',PASSED:'Passed',CONSUMED:'Admitted',BLOCKED:'Needs changes',
  ESCALATE:'Needs you',ESCALATED:'Needs you',DCL_ONLY:'Checks only'};
function verdictWord(v){const key=String(v||'').toUpperCase();return VERDICT_WORDS[key]||String(v||'');}
// R2. Severity as a consequence ("must fix") rather than a classification.
function severityWord(sev){return String(sev||'').toUpperCase()==='BLOCKER'?'must fix':'suggestion';}
// D148. What a finding rests on, from the evidence record in the receipt: a
// deterministic check verified it, or the auditor raised it and nothing has
// reproduced it yet. Shown only where findings are already listed, on the
// details line; a receipt without the record renders nothing here, and no
// route or state word is ever on screen.
function tierWord(f){if(!f||!f.tier)return '';
  return f.tier==='deterministic'?'verified by a check':f.verified?'raised by the auditor, verified':'raised by the auditor, not yet reproduced';}
// R2. A finding leads with what was observed. Severity, place and evidence
// tier share ONE muted details line under it. The rule id is NOT on the first
// paint: it is the tooltip of the details line (and, on the review card, a row of
// the collapsed Details block) — on demand only, as the owner directed.
function ruleTitle(rule){return rule?' title="'+esc('Rule id: '+rule)+'"':'';}
function findingCard(f){
  const parts=['<span class="severity '+(severityWord(f.severity)==='must fix'?'must-fix':'suggestion')+'">'+esc(severityWord(f.severity))+'</span>'];
  if(f.artifact)parts.push('<span class="finding-where">'+esc(f.artifact)+'</span>');
  if(tierWord(f))parts.push('<span class="finding-tier'+(f.verified?' verified':'')+'">'+esc(tierWord(f))+'</span>');
  return '<div class="finding"><p class="finding-observation">'+esc(f.observation||'No explanation was recorded.')+'</p>'
    +'<div class="finding-details"'+ruleTitle(f.rule)+'>'+parts.join('<span class="finding-sep" aria-hidden="true">·</span>')+'</div></div>';}
// R3. "anthropic · anthropic:claude-opus-4-8 · high" → "Claude Opus 4.8". The
// model specs carry ids and a capability note, not display names, so a name
// is given only to the id shapes the catalogue ships (Claude, GPT, Gemini,
// DeepSeek). Any other id renders BARE, without the provider prefix — an
// operator who typed it must be able to find it — never an invented name.
function friendlyModel(value){const raw=String(value||'').trim();if(!raw)return '';
  if(raw.toLowerCase()==='human')return 'Human';
  const segs=raw.split(' · ');const seg=segs.find(x=>x.includes(':'))||segs[0]||raw;
  const id=(seg.split(':').pop()||seg).trim();if(!id)return raw;
  const cap=w=>w.charAt(0).toUpperCase()+w.slice(1).toLowerCase();
  const names=[
    [/^claude-(opus|sonnet|haiku)-(\d+)-(\d+)(?:-\d{8})?$/i,m=>'Claude '+cap(m[1])+' '+m[2]+'.'+m[3]],
    [/^claude-(\d+)-(\d+)-(opus|sonnet|haiku)(?:-\d{8})?$/i,m=>'Claude '+m[1]+'.'+m[2]+' '+cap(m[3])],
    [/^gpt-(\d+(?:\.\d+)?)-(sol|terra|luna)$/i,m=>'GPT-'+m[1]+' '+cap(m[2])],
    [/^gemini-(\d+(?:\.\d+)?)-(pro|flash)$/i,m=>'Gemini '+m[1]+' '+cap(m[2])],
    [/^deepseek-v(\d+)-(pro|flash)$/i,m=>'DeepSeek V'+m[1]+' '+cap(m[2])]];
  for(const [pattern,name] of names){const m=id.match(pattern);if(m)return name(m);}
  return id;}
// R4. What this task will probably take, from the completed runs of this
// project (usage.run_forecast): the middle half of wall times when three or more
// runs exist, the median alone below that, and the median API value. One
// line; no new element. Localised here because the numbers are composed.
function forecastText(d){const f=d&&d.usage&&d.usage.forecast;const zh=currentLocale==='zh';
  if(!f||!f.runs||!f.seconds)return zh?'首次运行，暂无预估':'First run here — no estimate yet';
  const mins=x=>Math.max(1,Math.round(Number(x)/60));
  const lo=mins(f.seconds.p25),hi=mins(f.seconds.p75),mid=mins(f.seconds.p50);
  const ranged=f.runs>=3&&lo!==hi;
  // Sub-minute runs floor to "under a minute" rather than a rounded "1 min"
  // (or a "0 min" that reads as nothing at all).
  const brief=(ranged?Number(f.seconds.p75):Number(f.seconds.p50))<60;
  const time=zh?(brief?'通常不到 1 分钟':ranged?'通常 '+lo+'–'+hi+' 分钟':'通常约 '+mid+' 分钟')
    :(brief?'Usually under a minute':ranged?'Usually '+lo+'–'+hi+' min':'Usually about '+mid+' min');
  const cost=(f.usd&&f.usd.p50!=null)?(zh?' · 约 ':' · about ')+formatUsd(f.usd.p50):'';
  return time+cost;}
function forecastLine(d){return '<span class="run-forecast">'+esc(forecastText(d))+'</span>';}
function turn(m,d){
  if(m.kind === 'you'){
    const explicit=m.routing_mode==='explicit';const recipient=m.addressed_to||m.lane;
    const delivery=explicit?'@ '+recipient:recipient==='auditor'?'To Auditor':'To Generator';
    return '<article class="turn user"><div class="turn-main">'
    + '<div class="turn-meta"><b>You</b><span class="direct-mark">' + esc(delivery) + '</span>'
    + '<span class="turn-time">' + at(m.t) + '</span></div>'
    + '<div class="turn-body">' + esc(m.utterance) + '</div></div></article>';
  }
  if(m.kind === 'auditor_chat') return '<article class="turn audit"><div class="turn-main">'
    +'<div class="turn-meta"><span class="role-mark auditor" aria-hidden="true">A</span><b>Auditor</b><span>direct reply · no project files shared</span>'
    +'<span class="turn-time">'+at(m.t)+'</span></div><div class="turn-body">'+esc(m.response)+'</div></div></article>';
  if(m.kind === 'generator_chat') return '<article class="turn"><div class="turn-main">'
    +'<div class="turn-meta"><span class="role-mark generator" aria-hidden="true">G</span><b>Generator</b><span>conversational reply · not audited</span>'
    +'<span class="turn-time">'+at(m.t)+'</span></div><div class="turn-body">'+esc(m.response)+'</div></div></article>';
  if(m.kind === 'auditor'){
    const fs = (m.findings||[]).map(findingCard).join('');
    return '<article class="turn audit"><div class="turn-main">'
      + '<div class="turn-meta"><span class="role-mark auditor" aria-hidden="true">A</span><b>Auditor</b><span class="status ' + esc(m.verdict) + '">'
      + esc(verdictWord(m.verdict)) + '</span><span class="turn-time">' + at(m.t) + '</span></div>'
      + (fs || '<div class="turn-body">'+(m.verdict==='PASS'?'No findings. The audited increment passed.':'No structured findings were recorded.')+'</div>')
      // F1. What is shown above is the AUDITED report, read from the commit the
      // receipt cites. When the copy on disk says something else the person is
      // told, rather than silently corrected: they may have edited it for a
      // good reason, and the one thing worth handing them is the command that
      // settles it. Deliberately OUTSIDE the findings list — inside it, this
      // would read as something the auditor observed, which is the exact
      // confusion this whole fix exists to end.
      + (m.report_note ? '<p class="report-provenance">'+esc(m.report_note)+'</p>' : '')
      + '</div></article>';
  }
  if(m.kind === 'context_condensed'){
    // The runtime reduced what it sent. Localise from the wire fields the
    // event already carries; never re-translate prose or match text nodes.
    const full=localeText(m.summary_i18n,m.summary);
    const detail=String(m.notes||'');
    // `summary` is "<sentence>: <detail>". When the detail is locale-neutral
    // (paths, tool labels) it survives verbatim, so the tail can be split off
    // and shown as chips. When it was localised too (a byte count), the split
    // simply does not fire and the whole sentence is rendered — degrading to
    // correct-but-unsplit rather than to wrong.
    const tail=': '+detail;
    const head=(detail&&full.endsWith(tail))?full.slice(0,-tail.length):full;
    const chips=(detail&&full.endsWith(tail))
      ? '<div class="condense-paths">'+detail.split(',').map(part=>part.trim())
          .filter(Boolean).map(part=>'<span class="condense-path">'+esc(part)+'</span>').join('')
        +'</div>' : '';
    return '<article class="turn system-note"><div class="turn-main">'
      + '<div class="turn-meta"><span class="system-mark" aria-hidden="true">↻</span>'
      + '<b>' + esc(t('Context reduced')) + '</b>'
      + (m.round ? '<span>' + esc(t('round')) + ' ' + m.round + '</span>' : '')
      + '<span class="turn-time">' + at(m.t) + '</span></div>'
      + '<div class="turn-body">' + esc(head) + '</div>' + chips
      + '</div></article>';
  }
  return '<article class="turn"><div class="turn-main">'
    + '<div class="turn-meta"><span class="role-mark generator" aria-hidden="true">G</span><b>Generator</b>' + (m.round ? '<span>round ' + m.round + '</span>' : '')
    + '<span class="turn-time">' + at(m.t) + '</span></div><div class="turn-body">'
    + esc(m.summary) + '</div>' + artifactList(m.artifacts||m.files,auditStatus(d,m.sha),m.sha) + '</div></article>';
}
// The instant, optimistic echo of a just-sent message: the typed text plus a
// working indicator, so pressing Enter feels immediate.
// The intake the page is waiting on, if the state carries it and it belongs to
// this thread. A finished one is settled by settleIntake() and never rendered.
function intakeFor(d){const i=d&&d.intake;if(!i||i.finished)return null;
  if(pendingIntake&&i.id!==pendingIntake)return null;
  if((i.chat_id||'')!==(activeChatId||''))return null;return i;}
const AUDITOR_LANES=new Set(['auditor','amendment','dispute','resolve','query']);
// The last few phase lines of the message being handled: fixed sentences from
// the server catalogue, already in both locales — never an id, never prose
// the page composes about a process it cannot see.
function intakeLines(intake){
  const steps=((intake&&intake.steps)||[]).slice(-3);
  return steps.map((s,i)=>'<div class="intake-line'+(i===steps.length-1?' latest':'')+'">'
    +esc(localeText(s.text_i18n,s.text))+'</div>').join('');}
function optimisticTurn(text, queued, intake, replying){
  if(queued) return '<article class="turn user"><div class="turn-main">'
    + '<div class="turn-meta"><b>You</b><span class="direct-mark">'
    + (currentLocale==='zh'?'已排队 · 下一轮读取':'Queued — read at next round') + '</span>'
    + '<span class="turn-time">' + (currentLocale==='zh'?'刚刚':'now') + '</span></div>'
    + '<div class="turn-body">' + esc(text) + '</div></div></article>';
  const you='<article class="turn user"><div class="turn-main">'
    + '<div class="turn-meta"><b>You</b><span class="turn-time">'
    + (currentLocale==='zh'?'刚刚':'now') + '</span></div>'
    + '<div class="turn-body">' + esc(text) + '</div></div></article>';
  // A reply arriving live replaces the working indicator; nothing else here
  // changes, so the bubble does not jump.
  if(replying) return you;
  const auditorSide=intake&&AUDITOR_LANES.has(intake.lane||'');
  const who=auditorSide
    ?'<span class="role-mark auditor" aria-hidden="true">A</span><b>Auditor</b>'
    :'<span class="role-mark generator" aria-hidden="true">G</span><b>Generator</b>';
  return you + '<article class="turn"><div class="turn-main">'
    + '<div class="turn-meta">' + who + '</div><div class="turn-body"><span class="thinking-dots" aria-label="'
    + (currentLocale==='zh'?'处理中':'Working') + '"><i></i><i></i><i></i></span>'
    + (intake?'<div class="intake">'+intakeLines(intake)+'</div>':'')
    + '<div class="turn-forecast">' + esc(forecastText(lastState)) + '</div>'
    + '</div></div></article>';
}
function modelTag(value){const raw=String(value||'');if(!raw)return '';
  const tail=raw.split(':').pop()||raw;
  return (tail.split(' · ')[0]||'').trim()||raw;}
function userState(d){
  const p=chatProgress(d);
  if(p&&p.state==='PROVIDER_UNAVAILABLE'){
    // The run-side signal itself carries the ask: a parked run with a
    // waiting reason needs a person even when no cycle escalation could be
    // recorded (fail-closed verdict protection can refuse the decision
    // object). Rulings settle the run (waiting run is cancelled on close),
    // so a stale "decide" cannot outlive its decision.
    if(currentEscalations(d).length||p.waiting_reason)return {key:'decide',label:STATE_LABELS.decide,live:false};
    // Nothing pending and no waiting reason: fall through to the ledger
    // status instead of demanding a decision with no decision object.
  }
  if(p&&!p.finished){
    if(p.state==='CANCELLING')return {key:'work',label:'Stopping',live:true};
    const key=USER_STATES[p.state]||'work';
    return {key,label:STATE_LABELS[key],live:!['done','decide'].includes(key)};
  }
  const status=String(statusOf(d)).toLowerCase();
  if(status==='passed'||status==='consumed')return {key:'done',label:STATE_LABELS.done,live:false};
  if(status==='escalated')return {key:'decide',label:STATE_LABELS.decide,live:false};
  return null;
}
function setStatePill(d){
  const pill=document.getElementById('thread-status');
  const glyph=pill.querySelector('.pill-glyph'),label=pill.querySelector('.pill-label');
  const detail=pill.querySelector('.pill-detail');
  const s=newTaskMode?null:userState(d);
  const key=s?s.key:'';
  pill.className='state-pill'+(key?' pill-'+key:'')+(s&&s.live?' pill-live':'');
  glyph.hidden=!key;
  label.textContent=s?s.label:'Ready';
  const p=chatProgress(d);
  const rounds=p&&p.steps?p.steps.filter(step=>step.kind==='round_started'):[];
  const roundEvent=rounds.length?rounds[rounds.length-1]:null;
  const heartbeatAge=p&&p.heartbeat_at?Math.max(0,Math.floor(Date.now()/1000-p.heartbeat_at)):null;
  const lastStep=p&&p.steps&&p.steps.length?p.steps[p.steps.length-1]:null;
  if(p&&p.state==='PROVIDER_UNAVAILABLE'){detail.hidden=false;
    detail.textContent='Waiting for the provider'+(heartbeatAge===null?'':' · heartbeat '+relAge(heartbeatAge));}
  else if(lastStep&&lastStep.kind==='run_stalled'&&heartbeatAge!==null&&s&&s.live){
    detail.hidden=false;detail.textContent='last heartbeat '+relAge(heartbeatAge);}
  else if(roundEvent&&s&&s.live){detail.hidden=false;
    detail.textContent='round '+roundEvent.round_no+'/'+roundEvent.round_limit;}
  else{detail.hidden=true;detail.textContent='';}
  if(key!==lastPillKey){
    if(lastPillKey==='work'&&key==='check'){handoffDirection='check';handoffAt=Date.now();}
    else if(lastPillKey==='check'&&key==='revise'){handoffDirection='revise';handoffAt=Date.now();}
    lastPillKey=key;
    glyph.classList.remove('pill-swap');label.classList.remove('pill-swap');
    void pill.offsetWidth;
    glyph.classList.add('pill-swap');label.classList.add('pill-swap');
  }
}
// The decision the review card button opens: the row for THIS cycle first,
// then one for the same commit, then whatever the chat has open. The card and
// the banner used to read different lists (the banner every escalation, the
// card only those filed under the active chat), so a dismissed card could
// find nothing and open the models panel instead — "does nothing" to a person.
function decisionRowFor(d,cycleId,sha){const rows=(d&&d.escalations)||[];
  return rows.find(r=>r.cycle_id===cycleId)||rows.find(r=>sha&&r.sha&&(String(r.sha).startsWith(String(sha))||String(sha).startsWith(String(r.sha))))
    ||currentEscalations(d).slice(-1)[0]||null;}
// One line under the round rows when the pending decision is not about the
// rounds shown: a provider or usage stop, or a later round than the last
// report. Otherwise "" — the round rows already say it.
function pendingDecisionLine(row,lastRound){if(!row)return '';
  const what=row.kind==='provider'?'Waiting for the provider':row.kind==='budget'?'Usage limit reached':'Needs your decision';
  const round=Number(row.round||0),shown=Number(lastRound||0);
  if(row.kind!=='provider'&&row.kind!=='budget'&&(!round||round===shown))return '';
  return what+(round&&round!==shown?' · round '+round:'');}
function reviewCard(d){
  const cycles=chatCycles(d);if(!cycles.length)return '';
  const cycle=cycles[cycles.length-1];
  const status=String(cycle.status||'').toLowerCase();
  if(!['passed','consumed','blocked','escalated'].includes(status))return '';
  // R3. This card was suppressed for the whole duration of ANY run. The
  // suppression predates F1 and F7 — the run card takes the stage — but F1
  // attaches the report provenance to this card, so that line vanished
  // exactly while the surface is busiest. A person watching a live draft over a
  // completed cycle is precisely the person who needs to know what was reviewed
  // and against what. The F1 property held except while streaming, which is
  // except when it matters most.
  //
  // NARROWED, not removed. A run that is continuing THIS cycle is producing a
  // verdict that supersedes the one on this card, and showing the old outcome
  // while it is being replaced would be a false statement about what is
  // current. A run on anything else is different work: this card stays a true
  // statement about a settled cycle, it carries that cycle id in its Record,
  // and the run card directly above it says what is live.
  const p=chatProgress(d);
  if(p&&!p.finished&&String(p.continuation_cycle||'')===String(cycle.id||''))return '';
  const reports=d.auditor_stream.filter(m=>m.kind==='auditor'&&(m.chat_id||'history')===activeChatId);
  const related=reports.filter(m=>m.sha&&cycle.sha&&(String(cycle.sha).startsWith(String(m.sha))||String(m.sha).startsWith(String(cycle.sha))));
  const rows=(related.length?related:reports.slice(-Number(cycle.round||1))).slice(-8);
  const passed=status==='passed'||status==='consumed';
  const statusLabel = ({PASSED:'Passed review',CONSUMED:'Admitted',BLOCKED:'Needs changes',ESCALATED:'Needs your input'})[String(cycle.status||'').toUpperCase()] || cycle.status;
  const open=expandedReviews.has(cycle.id);
  const checks=checkRows(d);
  const roundLines=(rows.length?rows.map(m=>{
    const count=(m.findings||[]).length;
    return '<div class="review-round-row"><span class="round-n">Round '+esc(m.round)+'/'+esc(d.max_rounds)
      +'</span> · <span>'+(count?count+' finding'+(count===1?'':'s'):esc(verdictWord(m.verdict||'PASS')))
      +'</span></div>';}):['<div class="review-round-row"><span class="round-n">Round '
      +esc(cycle.round)+'/'+esc(d.max_rounds)+'</span></div>']).join('');
  // "N deterministic checks passed" counted the CONFIGURED checks and called
  // them passed. That is the same fabrication as the ticks below it: the console
  // is not told which checks ran. The claim is removed rather than restated, and
  // the check list in the detail carries its real state instead.
  const pending=status==='escalated'?decisionRowFor(d,cycle.id,cycle.sha):null;
  const pendingLine=pendingDecisionLine(pending,rows.length?rows[rows.length-1].round:cycle.round);
  const checkLines=passed
    ?'<ul class="review-checks"><li>Independent auditor approved the result</li>'
      +'<li>No blocking findings</li>'
      +'<li>Recorded in the audit ledger</li></ul>'
    :'';
  const ruleIds=[...new Set(rows.flatMap(m=>(m.findings||[]).map(f=>f.rule).filter(Boolean)))];
  const findingRows=rows.filter(m=>(m.findings||[]).length).map(m=>
    '<div class="review-round-row"><span class="round-n">round '+esc(m.round)+'</span></div>'
    +(m.findings||[]).map(findingCard).join('')).join('');
  const detail='<div class="review-detail"><div class="review-detail-inner">'
    +'<div class="review-section"><div class="review-section-title" id="review-checks-title-'+esc(cycle.id)+'">Automatic checks</div>'
    +'<p class="check-summary">'+esc(checkSummary(checks,auditCount(d)))+'</p>'
    +'<div role="list" aria-labelledby="review-checks-title-'+esc(cycle.id)+'">'+renderCheckRows(checks)+'</div>'
    +'<div class="review-rounds">'+esc(d.rules)+(d.rules===1?' rule':' rules')+'</div></div>'
    +(findingRows?'<div class="review-section"><div class="review-section-title">Findings</div>'+findingRows+'</div>':'')
    // F1. The review card is the surface a person actually reads for the audit
    // result, so the provenance of the bytes above belongs here and not only in
    // the Audits view. One line per distinct note, because several rounds of one
    // cycle share the same edited file and repeating it would read as several
    // problems.
    +([...new Set(rows.map(m=>m.report_note).filter(Boolean))]
        .map(note=>'<p class="report-provenance">'+esc(note)+'</p>').join(''))
    // R3. The record — who generated, who audited, which commit and cycle —
    // sits behind a closed disclosure. Models by their friendly names; the
    // identifiers never reach the first paint.
    +'<details class="review-section review-details"><summary class="review-section-title">Details</summary><div class="review-record">'
    +'<div class="review-record-row"><span>Generator</span><span>'+esc(friendlyModel(d.generator))+'</span></div>'
    +'<div class="review-record-row"><span>Auditor</span><span>'+esc(friendlyModel(d.auditor))+'</span></div>'
    +'<div class="review-record-row"><span>Commit</span><code>'+esc(String(cycle.sha||'').slice(0,12))+'</code></div>'
    +'<div class="review-record-row"><span>Cycle</span><code>'+esc(cycle.id)+'</code></div>'
    +(ruleIds.length?'<div class="review-record-row"><span>Rules</span><code>'+esc(ruleIds.join(', '))+'</code></div>':'')
    +'</div></details></div></div>';
  const actionRow=status==='passed'
    ?'<button type="button" class="review-action" data-admit data-admit-cycle="'+esc(cycle.id)+'">Admit result</button>'
    :status==='escalated'
    ?'<button type="button" class="review-action" data-open-decisions="'+esc(cycle.id)+'" data-open-decisions-sha="'+esc(cycle.sha||'')+'">Review issues & decide</button>'
    :'<button type="button" class="review-action" data-open-audits>View audit details</button>';
  return '<section class="review-card'+(open?' open':'')+'" aria-label="Independent review">'
    +'<button type="button" class="review-summary" data-review-toggle="'+esc(cycle.id)+'" aria-expanded="'+(open?'true':'false')+'">'
    +'<div class="review-top"><span class="review-mark" aria-hidden="true"></span><b>Independent review</b>'
    +'<span class="status '+esc(cycle.status)+'">'+esc(statusLabel)+'</span><span class="review-chevron" aria-hidden="true"></span></div>'
    +checkLines
    +'<div class="review-rounds">'+roundLines+(pendingLine?'<div class="review-round-row review-pending"><span>'+esc(pendingLine)+'</span></div>':'')+'</div>'
    +'</button>'+detail
    +'<div class="review-actions">'+actionRow+'</div></section>';
}
const ACTOR_NAMES = {generator:'Generator',auditor:'Auditor',compute:'Compute',tool:'Tool',loop:'Process',done:'Result',input:'You'};
const ACTOR_MARKS = {generator:'G',auditor:'A',compute:'H',tool:'M',loop:'↻',done:'✓'};
// The main surface carries words, never identifiers (D150 / North Star §12):
// a raw payload (the goal record is JSON for the Plan tab) is not shown at
// all, and a hash, sha, cycle id, provider:model route or rule id that an
// older event still carries in its detail is dropped from the line here.
function conciseDetail(s){
  const raw=String(s.detail||'');
  if(!raw||/^\s*[\x5b\x7b]/.test(raw))return '';
  return humaniseDetail(raw)
    .replace(/\bcycle [a-f0-9]{16}\b/g,'this cycle')
    .replace(/\b[a-f0-9]{40}\b/g,'').replace(/\b[a-f0-9]{16}\b/g,'').replace(/\b[a-f0-9]{12}\b/g,'')
    .replace(/\b[A-Za-z0-9_.-]+:(?:claude|gpt|gemini|deepseek|grok|o[0-9])[A-Za-z0-9_.-]*\b/g,'')
    .replace(/\bCA-[A-Z]+-\d+\b/g,'').replace(/\s{2,}/g,' ').replace(/^[\s·;,:—-]+|[\s·;,:—-]+$/g,'');}
// One live-activity row. A condensation notice is the runtime reporting on
// itself, so it does not borrow the generator name or mark, and every row
// localises from the wire fields (text_i18n) rather than showing English
// under 中文.
function activityRow(s){
  const system = s.kind === 'context_condensed';
  const mark = system ? '↻' : (ACTOR_MARKS[s.actor]||'·');
  const who = system ? t('Context reduced') : t(ACTOR_NAMES[s.actor]||s.actor);
  const line = (system || s.text_i18n) ? localeText(s.text_i18n, s.text) : s.text;
  const detail = system ? localeText(s.detail_i18n, s.detail) : conciseDetail(s);
  return '<div class="audit-event">'
  + '<span class="event-mark ' + esc(system ? 'runtime' : s.actor) + '">' + esc(mark) + '</span>'
  + '<div class="event-main"><div class="event-line"><b>' + esc(who)
  + '</b><span>' + esc(line) + '</span></div>'
  + (detail ? '<div class="event-detail">' + esc(detail) + '</div>' : '') + '</div>'
  + '<time class="event-time">' + at(s.t) + '</time></div>';}
function runCard(d){
  const p = chatProgress(d),cycles=chatCycles(d);
  const latestCycle=cycles.length?cycles[cycles.length-1]:null;
  const ownsPipeline=p||(latestCycle&&d.cycles.length&&latestCycle.sha===d.cycles[d.cycles.length-1].sha);
  const pipeline=ownsPipeline?d.pipeline:[];
  const show = p || pipeline.some(s => s.state !== 'pending');
  if(!show) return '';
  const rawOutcome = p ? (p.finished ? p.outcome : 'running') : statusOf(d);
  const outcome = rawOutcome==='provider_unavailable' ? 'escalated' : rawOutcome;
  const tone = String(outcome||'ready').toLowerCase();
  // Plain-language status the reader actually understands; the raw enum stays as
  // the CSS class for colour, but never as the words on screen.
  const outcomeLabel = ({running:'Working',ready:'Ready',passed:'Passed review',consumed:'Admitted',blocked:'Needs changes',escalated:'Needs your input',failed:'Stopped'})[tone] || outcome;
  const handoff = (Date.now()-handoffAt<700&&handoffDirection)?' data-handoff="'+esc(handoffDirection)+'"':'';
  const reached = pipeline.filter(s => s.state !== 'pending').length;
  const meter = pipeline.length ? Math.round(reached / pipeline.length * 100) : 0;
  const roundEvents = p && p.steps ? p.steps.filter(s => s.kind === 'round_started') : [];
  const roundEvent = roundEvents.length ? roundEvents[roundEvents.length-1] : null;
  const round = roundEvent ? roundEvent.round_no : latestCycle ? latestCycle.round : '-';
  const roundLimit = roundEvent&&roundEvent.round_limit ? roundEvent.round_limit : d.max_rounds;
  const focus = pipeline.find(s => s.state === 'current') || pipeline.find(s => s.state === 'failed')
    || pipeline.find(s => s.state === 'pending') || pipeline[pipeline.length-1];
  const focusLabel = focus.state === 'current' ? 'Current step' : focus.state === 'failed' ? 'Stopped at'
    : focus.state === 'pending' ? 'Next step' : 'Completed step';
  const stateNames = {done:'Done',failed:'Stopped',current:'Active',pending:'Waiting'};
  const eventRows = p && p.steps ? p.steps.slice(-12).map(activityRow).join('') : '';
  // D150: what is arriving right now, as one line each — a word count for the
  // draft (the text itself lives in the unaudited draft article above) and
  // the tail of the summarised thinking. Neither is a step; neither persists.
  const draft = liveDraftFor(d), thinking = liveThinkingFor(d);
  const liveRows = (thinking ? '<div class="audit-event live-thinking">'
      + '<span class="event-mark runtime">…</span><div class="event-main"><div class="event-line"><b>'
      + esc(currentLocale==='zh'?'思考中':'Thinking') + '</b><span>' + esc(thinking.text.slice(-160).replace(/\s+/g,' ')) + '</span></div></div>'
      + '<time class="event-time">' + (currentLocale==='zh'?'刚刚':'now') + '</time></div>' : '')
    + (draft ? '<div class="audit-event live-draft">'
      + '<span class="event-mark generator">G</span><div class="event-main"><div class="event-line"><b>'
      + esc(t('Generator')) + '</b><span>' + esc(currentLocale==='zh'
        ? '草稿：已写 ' + draftCount(draft.text) + ' 字'
        : 'Draft: ' + draftCount(draft.text) + ' words so far') + '</span></div></div>'
      + '<time class="event-time">' + (currentLocale==='zh'?'刚刚':'now') + '</time></div>' : '');
  const activityTitle = p && !p.finished ? 'Live activity' : 'Run activity';
  const activity = (eventRows + liveRows) || '<div class="activity-empty">The generator and auditor show what they are doing here while a task runs.</div>';
  const task = p && p.task ? p.task : titleOf(d);
  const live = p && !p.finished;
  const stopBtn = live ? '<button type="button" class="run-stop"'
    + (p.state==='CANCELLING'?' disabled':'') + ' onclick="requestStop()" '
    + 'aria-label="Stop this task"><span class="run-stop-glyph" aria-hidden="true"></span>'
    + (p.state==='CANCELLING'?'Stopping…':'Stop') + '</button>' : '';
  return '<section class="run-card ' + esc(tone) + '"' + handoff + ' aria-label="Audit loop">'
    + '<div class="run-overview"><div class="run-top">'
    + '<span class="run-eyebrow">Audit loop</span><span class="status ' + esc(outcome) + '">'
    + esc(outcomeLabel) + '</span>' + stopBtn + '</div><div class="run-task">' + esc(task) + '</div><div class="run-meta">'
    + '<span>Round <strong>' + esc(round) + '</strong> of ' + esc(roundLimit) + '</span>'
    + '<span><strong>' + reached + '</strong> of ' + pipeline.length + ' steps done</span>'
    + '<span>' + (p ? elapsedText(p.elapsed) : 'Ledger snapshot') + '</span>'
    + (p&&p.queued&&!p.finished?'<span><strong>'+esc(p.queued)+'</strong> queued</span>':'')
    + (live ? forecastLine(d) : '') + '</div>'
    + '<div class="run-handoff" aria-hidden="true"><i></i></div>'
    + '<div class="run-meter" role="progressbar" aria-label="Audit steps done" aria-valuemin="0" '
    + 'aria-valuemax="100" aria-valuenow="' + meter + '"><i style="width:' + meter + '%"></i></div></div>'
    + '<div class="loop">' + pipeline.map((s,i) => '<div class="loop-step ' + esc(s.state) + '" '
      + 'aria-label="' + esc(s.title + ': ' + stateNames[s.state]) + '"><div class="loop-track">'
      + '<div class="loop-mark">' + esc(MARK[s.state] || String(i+1)) + '</div></div>'
      + '<div class="loop-name">' + esc(s.title) + '</div>'
      + '<div class="loop-detail" title="' + esc(s.detail) + '">' + esc(s.detail) + '</div>'
      + '<div class="loop-state">' + esc(stateNames[s.state]) + '</div></div>').join('') + '</div>'
    + '<div class="loop-focus ' + esc(focus.state) + '"><div class="loop-focus-label">' + focusLabel + '</div>'
    + '<div class="loop-focus-copy"><b>' + esc(focus.title) + '</b><p>' + esc(focus.detail) + '</p></div></div>'
    + '<div class="activity"><div class="activity-head">' + activityTitle + '<span>'
    + (p && p.steps ? p.steps.length + ' event' + (p.steps.length===1?'':'s') : 'Ledger-backed state')
    + '</span></div><div class="activity-list">' + activity + '</div></div>' + runCostLine(d) + '</section>';
}
function approvalCard(d){
  // A live build proposed a Level 3+ action and paused for the user. The card
  // states what/why/scope/reversibility/cost; the buttons deliver the decision
  // (recorded as the grant by the waiting worker). Level 4+ offers only
  // once/deny — never a standing grant.
  const a = d && d.pending_approval;
  if(!a || (a.run_id && chatProgress(d) && chatProgress(d).run_id && a.run_id!==chatProgress(d).run_id)) return '';
  const label = {once:'Allow once',run:'Allow this run',project:'Allow this project',deny:'Deny'};
  const buttons = (a.scopes||['once','deny']).map(s =>
    '<button class="'+(s==='deny'?'deny':'allow')+'" data-decision="'+esc(s)+'" '
    + 'onclick="resolveApproval(this.getAttribute(\'data-decision\'))">'+esc(label[s]||s)+'</button>').join('');
  const facts=[];
  if(a.paths&&a.paths.length) facts.push('<span>Paths <strong>'+esc(a.paths.join(', '))+'</strong></span>');
  if(a.host) facts.push('<span>Host <strong>'+esc(a.host)+'</strong></span>');
  if(a.cost_usd) facts.push('<span>Est. cost <strong>$'+esc(a.cost_usd)+'</strong></span>');
  return '<section class="approval-card" role="alertdialog" aria-label="Approval needed">'
    + '<div class="approval-head"><span class="approval-badge">Level '+esc(a.level)+'</span>'
    + '<b>Approval needed</b></div>'
    + '<div class="approval-tool">'+esc(a.tool)+'</div>'
    + '<p class="approval-why">'+esc(a.reversibility)+(a.reason?' · '+esc(a.reason):'')+'</p>'
    + (facts.length?'<div class="approval-facts">'+facts.join('')+'</div>':'')
    + (a.preview?'<pre class="approval-preview">'+previewHtml(a.preview)+'</pre>':'')
    + '<div class="approval-actions">'+buttons+'</div></section>';
}
function previewHtml(text){
  // Colour a unified diff so removed/added lines read at a glance; non-diff
  // previews (a command, an HPC summary) have no +/- lines and stay plain.
  return String(text).split('\n').map(function(line){
    var cls='';
    if(/^(\+\+\+|---) /.test(line)) cls='pl-meta';
    else if(line.charAt(0)==='@') cls='pl-hunk';
    else if(line.charAt(0)==='+') cls='pl-add';
    else if(line.charAt(0)==='-') cls='pl-del';
    return '<span class="pl '+cls+'">'+esc(line)+'</span>';
  }).join('\n');
}
async function resolveApproval(decision){
  const a = lastState && lastState.pending_approval;
  if(!a || !a.run_id) return;
  document.querySelectorAll('.approval-actions button').forEach(b=>b.disabled=true);
  try{ await api('/api/approval',{run_id:a.run_id,decision}); }
  catch(e){ document.querySelectorAll('.approval-actions button').forEach(b=>b.disabled=false); }
}
function welcome(){
  return '<div class="welcome"><div class="welcome-mark">◇</div><h2>What should CrossAudit work on?</h2>'
    + '<p>Describe what you need or add files. CrossAudit will do the work and independently check the result before showing it here.</p></div>';
}
function allMessages(d){
  // Tasks is direct user input/output, never a raw audit log. Draft generator
  // rounds remain ledger evidence but do not become downloadable deliverables.
  const rows = [...d.generator_stream,...d.auditor_stream].filter(m=>{
    if((m.chat_id||'history')!==activeChatId)return false;
    if(m.kind==='auditor') return false;
    if(m.kind!=='generator') return true;
    return ['passed','consumed'].includes(auditStatus(d,m.sha));
  });
  const seen = new Set();
  // Same function the announcer keys on, so "two messages" means the same thing
  // to the renderer and to the thing that speaks about them.
  return rows.filter(m => {const key = turnKey(m);
    if(seen.has(key)) return false;seen.add(key);return true;}).sort((a,b) => a.t-b.t);
}
// §41.9 admission explanation — a transient, client-side card that answers:
// what happened · was work lost · what the system did · options · tech details.
let lastAdmission=null;
function admissionCard(){
  const a=lastAdmission;if(!a||a.chat!==(activeChatId||''))return '';
  if(a.ok)return '<section class="admission-card ok" aria-label="Admission result">'
    +'<div class="admission-head"><b>Admitted.</b><span>receipt '+esc(a.receipt||'')+'</span>'
    +(a.signed?'<span class="admission-signed" title="'+esc('key '+(a.signatureKeyid||''))+'">signed · verifiable offline</span>':'')
    +(a.reproducible?'<span class="admission-repro" title="'+esc((a.reproKinds||[]).join(', '))+'">reproducible · '+esc(String(a.reproLocks||0))+' lock'+((a.reproLocks===1)?'':'s')+'</span>':'')+'</div>'
    +(a.tier?'<p class="admission-tier">Admission tier '+esc(a.tier)+(a.tierMeaning?' · '+esc(a.tierMeaning):'')+'</p>':'')
    +'</section>';
  const remedies=(a.remediations||[]).map(r=>'<li>'+esc(r)+'</li>').join('');
  return '<section class="admission-card refused" aria-label="Admission explanation">'
    +'<div class="admission-head"><b>Not admitted.</b>'+(a.tier?'<span>tier '+esc(a.tier)+'</span>':'')+'</div>'
    +'<p class="admission-why">'+esc(a.reason||'')+'</p>'
    +'<p class="admission-safe">No work was lost — the report, receipt and ledger are unchanged, and nothing was consumed.</p>'
    +(remedies?'<div class="admission-options"><b>What would make it admissible</b><ul>'+remedies+'</ul></div>':'')
    +'<div class="admission-actions"><button type="button" data-open-audits>View audit details</button>'
    +(a.cycleId?'<button type="button" data-admit data-admit-cycle="'+esc(a.cycleId)+'">Try again</button>':'')
    +'</div></section>';
}
function deliveryStatus(d){
  const p=chatProgress(d),cycles=chatCycles(d),cycle=cycles.length?cycles[cycles.length-1]:null;
  const raw=p&&!p.finished?'running':p&&p.finished?p.outcome:cycle?cycle.status.toLowerCase():'';
  if(!raw)return'';const status=String(raw).toLowerCase();
  const escalation=status==='escalated'?currentEscalations(d).slice(-1)[0]:null;
  const copy=status==='running'?['Working','The result will appear here when it is ready.']
    :status==='passed'||status==='consumed'?['Ready','The delivered files passed the independent review.']
    :status==='blocked'?['Needs revision','The result did not pass review yet.']
    :status==='open'?['Ready for your correction','Send the approved guidance to start the human-authorized audited attempt.']
    :status==='escalated'&&escalation&&escalation.limit_reached?['Automatic audit limit reached',
      'CrossAudit paused after '+escalation.round+' of '+escalation.max_rounds+' rounds with '+(escalation.issues||[]).length+' issue'+((escalation.issues||[]).length===1?'':'s')+' remaining.']
    :status==='escalated'||status==='provider_unavailable'?['Needs your input','CrossAudit needs a decision before it can continue.']
    :['Stopped','The task did not complete.'];
  const action=status==='passed'?'<button type="button" data-admit data-admit-cycle="'+esc(cycle.id)+'">Admit result</button>'
    :status==='escalated'||status==='provider_unavailable'?'<button type="button" data-open-decisions>Review issues & decide</button>'
    :status==='open'?''
    :'<button type="button" data-open-audits>View audit details</button>';
  return '<div class="delivery-status '+esc(status)+'"><span class="delivery-dot"></span><span><b>'
    +copy[0]+'</b></span><span>'+copy[1]+'</span>'+action+'</div>';
}
function artifactRows(d){
  const files = new Map();
  d.generator_stream.filter(m => m.kind === 'generator'&&(m.chat_id||'history')===activeChatId).forEach(m => (m.artifacts||m.files||[]).forEach(item => {
    const status=auditStatus(d,m.sha);if(!['passed','consumed'].includes(status))return;
    const artifact=artifactRecord(item);files.set(artifact.path,{artifact,t:m.t,round:m.round,summary:m.summary,status});
  }));
  return [...files.values()].sort((a,b) => b.t-a.t);
}
function artifactsView(d){
  const files = artifactRows(d);
  const cards = files.map(f => outputFile(f.artifact,f.status,f.round?'round '+f.round:f.artifact.kind)).join('');
  return '<div class="view-heading"><h2>Delivered files</h2><p>Only final files that passed independent review.</p></div>'
    + (cards ? '<div class="artifact-grid">' + cards + '</div>'
      : '<div class="empty">No audited deliverables yet.</div>');
}
function auditsView(d){
  const audits = d.auditor_stream.filter(m => m.kind === 'auditor'&&(m.chat_id||'history')===activeChatId);
  return '<div class="view-heading"><h2>Audits</h2><p>Independent verdicts and findings reconstructed from the ledger.</p></div>'
    + runCard(d) + (audits.length ? '<div class="audit-evidence-head"><h3>Audit evidence</h3><span>'
      + audits.length + ' report' + (audits.length===1?'':'s') + '</span></div>'
      + audits.map(m=>turn(m,d)).join('') : '<div class="empty">No audit evidence yet.</div>');
}
function formatTokens(value){
  const n=Number(value||0);if(n>=1000000)return (n/1000000).toFixed(n>=10000000?0:1)+'M';
  if(n>=1000)return (n/1000).toFixed(n>=10000?0:1)+'K';return Math.round(n).toLocaleString();
}
function formatUsd(value){
  if(value===null||value===undefined)return '-';const n=Number(value||0);
  if(n===0)return '$0.00';if(n<0.01)return '$'+n.toFixed(4);return '$'+n.toFixed(2);
}
function usageQuality(row){
  if(row.unpriced_calls)return ['Unpriced','unpriced'];
  if(row.estimated_calls)return ['Estimated','estimated'];return ['Reported',''];
}
function usageView(d){
  const u=d.usage||{};const today=u.today||{};const month=u.month||{},guard=u.budget||{};
  const days=u.days||[];const peak=Math.max(1,...days.map(day=>Number(day.tokens||0)));
  // Audit-runtime metric the token-only view lacked: how many audits ran, and
  // how many passed the independent review.
  const cycleList=Object.values(d.cycles||{});const auditCount=cycleList.length;
  const passedAudits=cycleList.filter(c=>['passed','consumed'].includes(String(c.status||'').toLowerCase())).length;
  const dayBars=days.map(day=>{const date=new Date(day.date+'T00:00:00');
    return '<div class="usage-day"><span class="usage-day-value">'+formatTokens(day.tokens)+'</span>'
      +'<span class="usage-bar-track"><i class="usage-bar" style="height:'
      +Math.max(day.tokens?4:0,Math.round(Number(day.tokens||0)*100*Math.pow(peak,-1)))+'%"></i></span>'
      +'<span class="usage-day-label">'+esc(date.toLocaleDateString([],{weekday:'short'}))+'</span></div>';}).join('');
  const roles=u.roles||[];const roleMax=Math.max(1,...roles.map(row=>Number(row.tokens||0)));
  const roleRows=roles.map(row=>'<div class="usage-role '+esc(row.role)+'"><div class="usage-role-top"><b>'
    +esc(row.role)+'</b><span>'+formatTokens(row.tokens)+' tokens</span></div><div class="usage-role-meter"><i style="width:'
    +Math.round(Number(row.tokens||0)*100*Math.pow(roleMax,-1))+'%"></i></div><small>'+row.calls+' call'+(row.calls===1?'':'s')
    +' · '+formatUsd(row.api_value_usd)+' API value</small></div>').join('');
  const models=(u.models||[]).map(row=>{const q=usageQuality(row);return '<div class="usage-row"><div class="usage-model"><b>'
    +esc(row.model)+'</b><small>'+esc(row.role)+' · '+esc(row.provider)+'</small></div><span>'+formatTokens(row.tokens)
    +'</span><span>'+formatTokens(Number(row.cache_read||0)+Number(row.cache_write||0))+'</span><span>'
    +formatUsd(row.api_value_usd)+'</span><span class="usage-quality '+q[1]+'">'+q[0]+'</span></div>';}).join('');
  const recent=(u.recent||[]).map(row=>'<div class="usage-call"><span class="usage-call-mark '+esc(row.role)+'">'
    +(row.role==='auditor'?'A':'G')+'</span><div class="usage-call-main"><b>'+esc(row.model)+'</b><span>'
    +esc(row.role)+' · '+esc(row.phase)+', '+formatTokens(row.input)+' in / '+formatTokens(row.output)+' out</span></div>'
    +'<div class="usage-call-value"><b>'+formatTokens(row.tokens)+'</b><span>'
    +(row.api_value_usd===null?'unpriced':formatUsd(row.api_value_usd))+' · '
    +esc(new Date(row.t).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}))+'</span></div></div>').join('');
  const guardrail=guard.state&&guard.state!=='unconfigured'?'<div class="usage-note"><span>'+(guard.blocked?'!':'◉')+'</span><div><b>Usage guardrail · '+esc(guard.state)+'</b><br>'
    +esc([...(guard.reasons||[]),...(guard.warnings||[])].join(' ')||'Usage is below the configured thresholds.')
    +(guard.blocked&&resetWords(guard)?' '+esc(resetWords(guard)):'')+'</div></div>':'';
  // Billing slice: the fail-closed monthly limit names the model it could not
  // price; the alarms already raised this period are listed; the mode toggle
  // (≈ value / tokens) is remembered per viewer.
  const unpriced=unpricedSentences(guard).map(line=>'<div class="usage-note unpriced"><span>!</span><div>'+esc(line)+'</div></div>').join('');
  const fired=(guard.fired||[]).map(w=>'<div class="usage-note"><span>◉</span><div>'+esc(currentLocale==='zh'?(w.text_zh||w.text):w.text)+' · '+esc(currentLocale==='zh'?(w.resets_zh||w.resets):w.resets)+'</div></div>').join('');
  const mode=usageMode();
  const modeToggle='<div class="usage-mode" role="group" aria-label="Display mode"><button type="button" data-usage-mode="value" aria-pressed="'+(mode==='value')+'">≈ value</button><button type="button" data-usage-mode="tokens" aria-pressed="'+(mode==='tokens')+'">Tokens</button></div>';
  return '<div class="view-heading usage-heading"><div><h2>Token usage</h2><p>Project-level model consumption, updated with every completion.</p></div>'+modeToggle+'</div>'
    +unpriced+fired
    +'<div class="usage-note"><span>ⓘ</span><div><b>Local metering · '+esc(u.cost_label||'API-value estimate')+'</b><br>'
    +'Token counts come from the provider runtime when available. Costs use the '+esc(u.price_snapshot||'current')
    +' public API price snapshot and are not a provider invoice or subscription charge.</div></div>'+guardrail
    +'<div class="usage-cards"><div class="usage-card"><div class="usage-card-label">Audits run</div><div class="usage-card-value">'
    +auditCount+'</div><div class="usage-card-detail">'+passedAudits+' passed review</div></div>'
    +'<div class="usage-card"><div class="usage-card-label">Today</div><div class="usage-card-value">'
    +formatTokens(today.tokens)+'</div><div class="usage-card-detail">'+formatUsd(today.api_value_usd)+' API value</div></div>'
    +'<div class="usage-card"><div class="usage-card-label">This month</div><div class="usage-card-value">'
    +formatTokens(month.tokens)+'</div><div class="usage-card-detail">'+formatUsd(month.api_value_usd)+' API value</div></div>'
    +'<div class="usage-card"><div class="usage-card-label">Model calls</div><div class="usage-card-value">'
    +(month.calls||0)+'</div><div class="usage-card-detail">'+(month.reported_calls||0)+' provider-reported</div></div>'
    +'<div class="usage-card"><div class="usage-card-label">Cached tokens</div><div class="usage-card-value">'
    +formatTokens(Number(month.cache_read||0)+Number(month.cache_write||0))+'</div><div class="usage-card-detail">read + write this month</div></div></div>'
    +'<section class="usage-section"><div class="usage-section-head"><h3>Last 7 days</h3><span>all roles</span></div><div class="usage-bars">'
    +dayBars+'</div></section><section class="usage-section"><div class="usage-section-head"><h3>By role</h3><span>this month</span></div>'
    +(roleRows?'<div class="usage-roles">'+roleRows+'</div>':'<div class="empty">No model calls this month.</div>')+'</section>'
    +'<section class="usage-section"><div class="usage-section-head"><h3>Models</h3><span>this month</span></div>'
    +(models?'<div class="usage-table"><div class="usage-row head"><span>Model</span><span>Tokens</span><span>Cached</span><span>≈ value</span><span>Source</span></div>'
      +models+'</div>':'<div class="empty">Usage will appear after the first model completion.</div>')+'</section>'
    +monthlyReport(d)
    +'<section class="usage-section"><div class="usage-section-head"><h3>Recent calls</h3><span>counts only · no prompt content</span></div>'
    +(recent?'<div class="usage-recent">'+recent+'</div>':'<div class="empty">No calls recorded yet.</div>')+'</section>';
}
// ---------------------------------------------------------------- billing
// Header pill, threshold banner, per-run / per-turn cost lines, 429 reset
// countdown, price overrides, export and the cross-project roll-up. Every
// figure comes from the project ledger (state.usage); the page never
// reads the files of another app. No hash, id or provider:model string is ever
// rendered on the main surface by anything below.
const USAGE_MODE_KEY='crossaudit-usage-mode',USAGE_DISMISS_KEY='crossaudit-usage-dismissed';
function usageMode(){try{return localStorage.getItem(USAGE_MODE_KEY)==='tokens'?'tokens':'value';}catch(e){return 'value';}}
function setUsageMode(mode){try{localStorage.setItem(USAGE_MODE_KEY,mode==='tokens'?'tokens':'value');}catch(e){}if(lastState)render(lastState);}
function shortUsd(value){const n=Number(value||0);if(!isFinite(n)||n<=0)return '$0.00';
  if(n>=1000)return '$'+Math.round(n).toLocaleString();if(n>=100)return '$'+n.toFixed(0);return '$'+n.toFixed(2);}
function usageFigure(bucket){const b=bucket||{};return usageMode()==='tokens'?formatTokens(b.tokens):shortUsd(b.api_value_usd);}
function budgetState(g){g=g||{};if(g.state==='blocked')return 'blocked';if(g.state==='warning'||(g.fired||[]).length)return 'warning';return 'ok';}
function renderUsagePill(d){const pill=document.getElementById('usage-pill');if(!pill)return;
  const u=(d&&d.usage)||{};if(!Number((u.all||{}).calls||0)){pill.hidden=true;return;}
  const g=u.budget||{},state=budgetState(g),zh=currentLocale==='zh';
  const today=usageFigure(u.today),month=usageFigure(u.month);
  pill.hidden=false;pill.className='usage-pill '+state;
  pill.textContent=(zh?'今日 ':'Today ')+today+' · '+(zh?'本月 ':'Month ')+month;
  const words=zh?{ok:'预算内',warning:'预算预警',blocked:'已达上限暂停'}:{ok:'within budget',warning:'budget warning',blocked:'paused at limit'};
  const name=(zh?'用量：今日 ':'Usage: today ')+today+(zh?'，本月 ':', this month ')+month
    +(g.state&&g.state!=='unconfigured'?' · '+words[state]:'')+(zh?'。打开用量':'. Open usage');
  pill.setAttribute('aria-label',name);pill.title=name;}
function dismissedWarnings(){try{return JSON.parse(localStorage.getItem(USAGE_DISMISS_KEY)||'[]').filter(k=>typeof k==='string');}catch(e){return [];}}
function warningKey(d,w){return [(d&&d.project)||'',w.budget,w.period,w.threshold].join('|');}
function warningDismissed(d,w){const own=[(d&&d.project)||'',w.budget,w.period].join('|');
  // Dismissing 95 % also covers 80 % of the same period; a lower alarm never
  // resurfaces behind a higher one the person already waved away.
  return dismissedWarnings().some(k=>k.startsWith(own+'|')&&Number(k.split('|').pop())>=Number(w.threshold));}
function renderUsageBanner(d){const banner=document.getElementById('usage-banner');if(!banner)return;
  const fired=((d&&d.usage&&d.usage.budget&&d.usage.budget.fired)||[]).filter(w=>!warningDismissed(d,w));
  const top=fired.slice().sort((a,b)=>Number(b.threshold)-Number(a.threshold))[0];
  const show=Boolean(top)&&!document.body.classList.contains('hub-mode');banner.hidden=!show;if(!show)return;
  const zh=currentLocale==='zh';
  document.getElementById('usage-banner-text').textContent=zh?(top.text_zh||top.text):top.text;
  document.getElementById('usage-banner-reset').textContent=zh?(top.resets_zh||top.resets):top.resets;
  banner.dataset.key=warningKey(d,top);}
function dismissUsageBanner(){const banner=document.getElementById('usage-banner');const key=banner.dataset.key||'';if(!key)return;
  const keep=dismissedWarnings().filter(k=>k!==key).slice(-40);keep.push(key);try{localStorage.setItem(USAGE_DISMISS_KEY,JSON.stringify(keep));}catch(e){}banner.hidden=true;}
document.getElementById('usage-banner-dismiss').onclick=dismissUsageBanner;
document.getElementById('usage-pill').onclick=()=>openPanelTab('usage');
document.addEventListener('click',ev=>{const b=ev.target.closest('[data-usage-mode]');if(b)setUsageMode(b.getAttribute('data-usage-mode'));});
function countdownText(resetAt){const s=Math.floor(Number(resetAt)-Date.now()/1000),zh=currentLocale==='zh';
  if(s<=0)return zh?'现在':'now';if(s<60)return zh?'不到 1 分钟':'under a minute';
  const h=Math.floor(s/3600),m=Math.floor(s%3600/60);
  if(zh)return (h?h+' 小时 ':'')+(m||!h?m+' 分钟':'').trim();return ((h?h+' h ':'')+(m||!h?m+' min':'')).trim();}
function resetSentence(resetAt){const zh=currentLocale==='zh';
  return zh?'已达供应商额度上限 · '+countdownText(resetAt)+'后重置':'Provider limit reached · resets in '+countdownText(resetAt);}
function providerResetLine(p){const w=p&&p.waiting_reason;if(!w||!w.reset_at||p.state!=='PROVIDER_UNAVAILABLE')return '';
  return '<span class="run-reset" data-reset-at="'+esc(w.reset_at)+'">'+esc(resetSentence(w.reset_at))+'</span>';}
setInterval(()=>{document.querySelectorAll('[data-reset-at]').forEach(el=>{el.textContent=resetSentence(Number(el.getAttribute('data-reset-at')));});},30000);
function resetWords(g){g=g||{};const zh=currentLocale==='zh',r=g.resets||{};
  return (g.blocked_by||[]).filter(k=>k==='daily'||k==='monthly').map(k=>zh?(r[k+'_zh']||''):(r[k]||'')).filter(Boolean).join(' ');}
function appendResolutionReset(row,budget,provider){const summary=document.getElementById('resolution-summary');if(!summary)return;
  const g=lastState&&lastState.usage&&lastState.usage.budget||{},p=lastState&&lastState.progress;let extra='';
  if(budget)extra=resetWords(g);
  else if(provider&&p&&p.state==='PROVIDER_UNAVAILABLE'&&p.waiting_reason&&p.waiting_reason.reset_at)extra=resetSentence(p.waiting_reason.reset_at);
  if(extra)summary.textContent=summary.textContent+' '+extra;}
function runCostLine(d){const p=chatProgress(d);if(!p||!p.run_id)return '';
  const b=((d.usage&&d.usage.attribution&&d.usage.attribution.runs)||{})[p.run_id];const reset=providerResetLine(p);
  if(!b&&!reset)return '';const zh=currentLocale==='zh';let cost='';
  if(b){cost=(zh?'本次任务：':'This task: ')+formatTokens(b.tokens)+' tokens';
    if(!(b.unpriced_calls&&!b.api_value_usd))cost+=' · ≈'+formatUsd(b.api_value_usd);
    if(b.unpriced_calls)cost+=zh?' · '+b.unpriced_calls+' 次未计价':' · '+b.unpriced_calls+' unpriced';
    cost='<span>'+esc(cost)+'</span>';}
  return '<div class="run-cost">'+cost+reset+'</div>';}
function turnCost(m,d){const turns=(d&&d.usage&&d.usage.attribution&&d.usage.attribution.turns)||[];if(!turns.length)return '';
  const chat=activeChatId||'';const want={generator:['generator','generation'],auditor:['auditor','audit'],
    generator_chat:['generator','control'],auditor_chat:['auditor','control']}[m.kind];if(!want||!chat)return '';
  const limit=(Number(m.t)||0)*1000+3000;
  const hits=turns.filter(x=>x.role===want[0]&&x.phase===want[1]&&x.chat_id===chat&&x.t<=limit&&(!m.round||!x.round||x.round===m.round));
  if(!hits.length)return '';const x=hits[hits.length-1];
  const secs=x.duration_ms?Math.max(1,Math.round(x.duration_ms/1000))+' s':'';
  const money=(x.api_value_usd===null||x.api_value_usd===undefined)?formatTokens(x.tokens)+' tokens':'≈'+formatUsd(x.api_value_usd);
  return '<div class="turn-cost">'+esc(money+(secs?' · '+secs:''))+'</div>';}
function withTurnCost(html,m,d){const line=turnCost(m,d);if(!line)return html;
  const at=html.lastIndexOf('</div></article>');return at<0?html:html.slice(0,at)+line+html.slice(at);}
function unpricedSentences(g){g=g||{};return (g.unpriced_models||[]).map(row=>{const snap=row.price_snapshot||g.price_snapshot||'';
  return currentLocale==='zh'?'本月有 '+row.calls+' 次调用无法计价（模型 '+row.model+' 在 '+snap+' 的价格快照中没有价格）'
    :row.calls+' call'+(row.calls===1?'':'s')+' this month could not be priced (model '+row.model+' has no price in the snapshot of '+snap+')';});}
function monthlyReport(d){const u=(d&&d.usage)||{},month=u.month||{};const zh=currentLocale==='zh';
  const cycleList=Object.values(d.cycles||{});const passed=cycleList.filter(c=>['passed','consumed'].includes(String(c.status||'').toLowerCase())).length;
  const total=Math.max(1,Number(month.tokens||0));const roles={};(u.roles||[]).forEach(r=>{roles[r.role]=Math.round(Number(r.tokens||0)*100/total);});
  const top=(u.models||[]).slice().sort((a,b)=>Number(b.tokens||0)-Number(a.tokens||0)).slice(0,5);
  const row=(label,value)=>'<tr><th>'+label+'</th><td>'+esc(value)+'</td></tr>';
  const facts='<table class="usage-report"><tbody>'+row('Calls',String(month.calls||0))+row('Tokens',formatTokens(month.tokens))
    +row('≈ value',formatUsd(month.api_value_usd))+row('Generator share',(roles.generator||0)+'%')+row('Auditor share',(roles.auditor||0)+'%')
    +row('Passed audits',String(passed))+row('Unpriced calls',String(month.unpriced_calls||0))+'</tbody></table>';
  const models=top.length?'<table class="usage-report"><thead><tr><th>Top models</th><th>Tokens</th><th>≈ value</th></tr></thead><tbody>'
    +top.map(r=>'<tr><td>'+esc(r.model)+'</td><td>'+formatTokens(r.tokens)+'</td><td>'+(r.unpriced_calls?t('Unpriced'):formatUsd(r.api_value_usd))+'</td></tr>').join('')+'</tbody></table>':'';
  return '<section class="usage-section"><div class="usage-section-head"><h3>Monthly report</h3><span>this month</span></div>'+facts+models+'</section>';}
function renderPriceRows(rows){const host=document.getElementById('runtime-prices');if(!host)return;
  const labels={input:'Input',output:'Output',cache_write:'Cache write',cache_read:'Cache read'};
  host.innerHTML=(rows||[]).map(row=>'<div class="price-row" data-price-row><input data-price-model maxlength="120" value="'+esc(row.model||'')+'" aria-label="Model ID" placeholder="Exact model ID">'
    +Object.keys(labels).map(k=>'<input data-price-'+k+' type="number" min="0" step="0.01" value="'+esc(row[k]===undefined||row[k]===null?'':row[k])+'" aria-label="'+esc(t(labels[k]))+'" placeholder="0">').join('')
    +'<button type="button" class="fallback-remove" data-remove-price title="Remove">×</button></div>').join('')
    ||'<div class="fallback-empty">No overrides. Models missing from the price snapshot stay unpriced.</div>';}
function priceRows(){return [...document.querySelectorAll('[data-price-row]')].map(row=>({model:row.querySelector('[data-price-model]').value.trim(),
  input:row.querySelector('[data-price-input]').value,output:row.querySelector('[data-price-output]').value,
  cache_write:row.querySelector('[data-price-cache_write]').value,cache_read:row.querySelector('[data-price-cache_read]').value}));}
document.querySelectorAll('[data-add-price]').forEach(button=>button.onclick=()=>{const rows=priceRows();rows.push({model:'',input:'',output:'',cache_write:'',cache_read:''});renderPriceRows(rows);
  const last=document.querySelector('[data-price-row]:last-child [data-price-model]');if(last)last.focus();});
runtimeModal.addEventListener('click',ev=>{const button=ev.target.closest('[data-remove-price]');if(!button)return;button.closest('[data-price-row]').remove();if(!priceRows().length)renderPriceRows([]);});
function renderRuntimeBudgetNotes(guard){const note=document.getElementById('runtime-unpriced'),text=document.getElementById('runtime-unpriced-text');if(!note)return;
  const sentences=unpricedSentences(guard);note.hidden=!sentences.length;text.innerHTML=sentences.map(esc).join('<br>');}
function budgetWord(state){return {ok:'Within budget',warning:'Budget warning',blocked:'Paused at limit'}[state]||'No budget';}
function renderUsageRollup(r){const host=document.getElementById('settings-usage-rollup');if(!host)return;const rows=(r&&r.projects)||[],total=(r&&r.total)||{};
  if(!rows.length){host.innerHTML='<p class="settings-empty">Open a project to see usage across projects.</p>';return;}
  const cell=(tokens,value)=>usageMode()==='tokens'?formatTokens(tokens):formatUsd(value);
  host.innerHTML='<table class="usage-report" aria-label="Usage across projects"><thead><tr><th>Project</th><th>Today</th><th>This month</th><th>Unpriced</th><th>Budget</th></tr></thead><tbody>'
    +rows.map(p=>'<tr><td>'+esc(p.name)+'</td><td>'+cell(p.today_tokens,p.today_api_value_usd)+'</td><td>'+cell(p.month_tokens,p.month_api_value_usd)+'</td><td>'+esc(String(p.unpriced_calls||0))+'</td><td>'+esc(t(budgetWord(p.budget_state==='unconfigured'?'':p.budget_state)))+'</td></tr>').join('')
    +'<tr class="total"><th>This month across projects</th><td>'+cell(total.today_tokens,total.today_api_value_usd)+'</td><td>'+cell(total.month_tokens,total.month_api_value_usd)+'</td><td>'+esc(String(total.unpriced_calls||0))+'</td><td></td></tr></tbody></table>';}
async function loadUsageRollup(){const host=document.getElementById('settings-usage-rollup');if(!host)return;
  if(!(lastState&&lastState.runtime_config)){host.innerHTML='<p class="settings-empty">Open a project to see usage across projects.</p>';return;}
  try{renderUsageRollup(await api('/api/usage/rollup'));}catch(e){host.innerHTML='<p class="settings-empty">'+esc(e.message)+'</p>';}}
document.querySelectorAll('[data-usage-export]').forEach(button=>button.onclick=()=>{
  if(!(lastState&&lastState.runtime_config)){const note=button.parentElement.querySelector('[data-scope-note]');
    if(note){note.textContent=currentLocale==='zh'?'请先打开一个项目再进行配置。':'Open a project to configure this.';note.hidden=false;}return;}
  const period=document.getElementById('settings-usage-period').value||'month';
  location.href='/api/usage/export?format='+encodeURIComponent(button.getAttribute('data-usage-export'))+'&period='+encodeURIComponent(period)+'&t='+encodeURIComponent(T);});
const computePanels=new Map();
function computeFileUrl(job,path){return '/api/hpc/file?t='+encodeURIComponent(T)+'&job='
  +encodeURIComponent(job)+'&path='+encodeURIComponent(path);}
function computeView(d){
  const c=d.compute||{hosts:[],jobs:[],aliases:[],active:0,ssh_available:false};
  const hosts=(c.hosts||[]).map(host=>{const probe=host.probe||{};const resources=[];
    if(probe.cpus)resources.push(probe.cpus+' CPU');if(probe.memory_kb)resources.push(formatBytes(probe.memory_kb*1000));
    if((probe.gpus||[]).length)resources.push(probe.gpus.length+' GPU');if((probe.partitions||[]).length)resources.push(probe.partitions.join(', '));
    const agent=host.agent_policy||{};if(agent.enabled)resources.push('Generator tool · '+agent.max_jobs_per_task+' jobs/task · '+agent.max_cpus+' CPU · '+agent.max_gpus+' GPU');
    return '<div class="host-row"><div class="host-top"><b>'+esc(host.alias)+'</b>'
      +'<span class="host-kind">'+esc(probe.scheduler||'workstation')+'</span></div><div class="host-detail">'
      +esc((host.user?host.user+'@':'')+host.hostname+':'+host.port+(host.proxy_jump?' · ProxyJump':'')+' · '+host.scratch)
      +'</div><div class="host-resources">'+resources.map(v=>'<span class="host-resource">'+esc(v)+'</span>').join('')
      +'</div><div class="host-actions"><button type="button" class="secondary" data-hpc-probe="'+esc(host.id)+'">Probe</button>'
      +'<button type="button" class="secondary" data-hpc-run="'+esc(host.id)+'">Run job</button>'
      +'<button type="button" class="secondary" data-hpc-remove="'+esc(host.id)+'">Remove</button></div></div>';}).join('');
  const jobs=(c.jobs||[]).map(job=>{const cache=computePanels.get(job.id)||{};const open=Boolean(cache.open);
    const outputs=(cache.outputs||[]).map(file=>'<a class="hpc-output" href="'+computeFileUrl(job.id,file.path)+'" download>'
      +'<span>↓</span><b>'+esc(file.path)+'</b><span>'+formatBytes(file.bytes)+'</span></a>').join('');
    const consoleBody=cache.mode==='outputs'
      ?'<div class="hpc-output-list">'+(outputs||'<div class="compute-empty">No remote output files found.</div>')+'</div>'
      :'<pre>'+esc(((cache.logs||{}).stdout||'')+(((cache.logs||{}).stderr)?'\n[stderr]\n'+cache.logs.stderr:''))+'</pre>';
    const terminal=['completed','failed','cancelled','timeout','out_of_memory'].includes(job.status);
    return '<div class="hpc-job"><div class="hpc-job-top"><b>'+esc(job.name)+'</b>'+(job.origin==='generator'?'<span class="host-kind">Generator</span>':'')+'<span class="status '+esc(job.status)+'">'
      +esc(job.status)+'</span></div><div class="hpc-job-meta"><span>'+esc(job.host)+'</span><span>'+esc(job.scheduler)+' #'
      +esc(job.remote_id)+'</span><span>'+esc(job.elapsed||'')+'</span><span>'+new Date(job.submitted*1000).toLocaleString()+'</span></div>'
      +'<div class="hpc-job-detail">'+esc(job.detail||'')+'</div>'+(job.connection_error?'<div class="hpc-connection-error">Offline view · '
      +esc(job.connection_error)+' · the remote job continues independently</div>':'')+'<div class="hpc-job-actions">'
      +'<button type="button" class="secondary" data-hpc-logs="'+esc(job.id)+'">Live logs</button>'
      +'<button type="button" class="secondary" data-hpc-outputs="'+esc(job.id)+'">Outputs</button>'
      +(!terminal?'<button type="button" class="secondary" data-hpc-cancel="'+esc(job.id)+'">Cancel job</button>':'')
      +'</div><div class="hpc-console'+(open?' on':'')+'"><div class="hpc-console-tabs">'
      +(cache.mode==='outputs'?'Remote outputs':'Last 64 KB · stdout + stderr')+'<span class="spacer"></span>'
      +(cache.loading?'Updating…':cache.error?'<span style="color:var(--red)">'+esc(cache.error)+'</span>':'')
      +'</div>'+consoleBody+'</div></div>';}).join('');
  return '<div class="view-heading"><h2>Remote compute</h2><p>SSH workstations and Slurm clusters for manual jobs or Generator calculations.</p></div>'
    +'<div class="compute-note"><span>ⓘ</span><div><b>Remote-owned execution.</b> CrossAudit stores only host aliases and job identifiers. '
    +'Keys remain with OpenSSH; remote work continues if the app closes, the Mac sleeps, or the network drops. A host marked as a Generator tool can receive model-authored jobs automatically within its saved policy.</div></div>'
    +'<div class="compute-message" id="compute-message" role="alert"></div>'
    +'<div class="compute-toolbar"><button type="button" class="primary" data-hpc-add>＋ Add SSH host</button>'
    +'<button type="button" class="secondary" data-hpc-run="">Submit job</button><span class="spacer"></span>'
    +'<button type="button" class="secondary" data-hpc-refresh>Refresh now</button></div>'
    +'<div class="compute-grid"><section class="compute-section"><div class="compute-section-head"><b>Compute hosts</b><span>'
    +(c.hosts||[]).length+' connected</span></div>'+(hosts||'<div class="compute-empty">No SSH compute hosts yet.</div>')+'</section>'
    +'<section class="compute-section"><div class="compute-section-head"><b>Remote jobs</b><span>'+c.active+' active</span></div>'
    +(jobs||'<div class="compute-empty">No jobs submitted from this project.</div>')+'</section></div>';
}
const GOV_LEVELS={0:'infer',1:'read',2:'write',3:'command',4:'network',5:'high-impact',6:'destructive'};
const GOV_OUTCOME_CLASS={succeeded:'passed',failed:'blocked',refused:'blocked',needs_approval:'escalated',recorded:'running'};
function evidenceView(d){
  const rows=(d&&d.governed_actions)||[];
  const short=h=>h?String(h).slice(0,10):'';
  const body=rows.map(a=>{
    const level=(a.level==null?'':'<span class="gov-level">L'+esc(a.level)+' '+esc(GOV_LEVELS[a.level]||'')+'</span>');
    const meta=[];
    if(a.decision)meta.push('decision '+esc(a.decision));
    if(a.approval)meta.push('approval '+esc(a.approval));
    if(a.path)meta.push('path '+esc(a.path));
    const hashes=[];
    if(a.pre_sha256!=null||a.post_sha256!=null)hashes.push('sha '+esc(short(a.pre_sha256)||'∅')+' → '+esc(short(a.post_sha256)));
    else if(a.result_sha256)hashes.push('result '+esc(short(a.result_sha256)));
    if(a.args_sha256)hashes.push('args '+esc(short(a.args_sha256)));
    const flag=a.secret_flagged?'<div class="gov-flag">⚠ flagged: '+esc(a.secret_flagged)+'</div>':'';
    const cls=GOV_OUTCOME_CLASS[a.outcome]||'running';
    return '<div class="gov-row"><div class="gov-top"><b>'+esc(a.tool||'?')+'</b>'+level
      +'<span class="status '+cls+'">'+esc(a.outcome||'')+'</span></div>'
      +(meta.length?'<div class="gov-meta">'+meta.map(v=>'<span>'+v+'</span>').join(' · ')+'</div>':'')
      +(a.reason?'<div class="gov-reason">'+esc(a.reason)+'</div>':'')
      +(hashes.length?'<div class="gov-hashes">'+hashes.join(' · ')+'</div>':'')+flag+'</div>';
  }).join('');
  return '<div class="view-heading"><h2>Governed actions</h2><p>Every built-in action the agent proposed, the policy decision, your approval, and the content hashes recorded to the append-only evidence ledger.</p></div>'
    +'<div class="compute-note"><span>ⓘ</span><div><b>This is the audit trail.</b> The broker writes each proposal, decision, approval and result to a hash-chained ledger the independent auditor reviews and the receipt binds — no raw output is shown or stored, only hashes and decisions. Hashes are truncated for display.</div></div>'
    +(body?'<div class="gov-list">'+body+'</div>'
      :'<div class="compute-empty">No governed actions yet. When the agent uses a built-in tool — read, write, run a command, commit, or submit compute — each proposal, decision, approval and result appears here.</div>');
}
function planView(d){
  const p=chatProgress(d);
  if(!p)return '<div class="view-heading"><h2>Goal & plan</h2><p>The stated goal and the audited plan for the current task.</p></div>'
    +'<div class="compute-empty">No plan yet — the plan appears when a task starts.</div>';
  // The Goal event is emitted durably at run start; parse defensively and fall
  // back to the run task so an evicted or corrupt event never blanks the tab.
  let goal=null;
  const goalStep=(p.steps||[]).filter(s=>s.kind==='goal').slice(-1)[0];
  if(goalStep&&goalStep.detail){try{goal=JSON.parse(goalStep.detail);}catch(e){goal=null;}}
  const cons=goal&&goal.constraints||{};
  const consRows=goal?[
    ['Rounds','up to '+esc(cons.max_rounds)],
    ['Scope',esc((cons.scope_dirs||[]).join(', ')||'project')],
    ['Writes',cons.writes_authorized?'authorized (recoverable)':'read-only'],
    ['Commands',cons.commands_authorized?'allowlisted':'not authorized'],
    ['Compute',cons.compute_authorized?'configured':'not configured'],
  ].map(r=>'<div class="plan-const"><span>'+r[0]+'</span><b>'+r[1]+'</b></div>').join(''):'';
  const goalBlock=goal
    ?'<section class="plan-goal"><div class="plan-sec-title">Goal</div><p class="plan-task">'+esc(goal.task||p.task)+'</p>'
      +'<div class="plan-sec-title">Desired outputs</div><ul class="plan-list">'+(goal.desired_outputs||[]).map(o=>'<li>'+esc(o)+'</li>').join('')+'</ul>'
      +'<div class="plan-sec-title">Constraints</div>'+consRows
      +'<div class="plan-sec-title">Success criteria</div><ul class="plan-list">'+(goal.success_criteria||[]).map(o=>'<li>'+esc(o)+'</li>').join('')+'</ul></section>'
    :'<section class="plan-goal"><div class="plan-sec-title">Goal</div><p class="plan-task">'+esc(p.task||'')+'</p>'
      +'<p class="plan-note">The structured goal record is not available for this run.</p></section>';
  const gates=(d.pipeline||[]).map(g=>'<div class="plan-step '+esc(g.state)+'"><span class="plan-dot"></span><b>'+esc(g.title)+'</b><span>'+esc(g.detail)+'</span></div>').join('');
  const rounds=(p.steps||[]).filter(s=>['audit_passed','audit_blocked','audit_escalated'].includes(s.kind))
    .map(s=>'<div class="plan-round">round '+esc(s.round_no)+'<span aria-hidden="true"> — </span><span class="status '+esc(String(s.text).toLowerCase())+'">'+esc(s.text)+'</span></div>').join('');
  return '<div class="view-heading"><h2>Goal & plan</h2><p>The stated goal and the audited plan for the current task.</p></div>'
    +goalBlock
    +'<section class="plan-plan"><div class="plan-sec-title">Plan v1 · the audited loop</div>'
    +'<p class="plan-note">Derived from the supervised loop this run actually executes — generator-authored step plans arrive in a later slice.</p>'
    +(gates||'<div class="compute-empty">No gates to show.</div>')
    +(rounds?'<div class="plan-sec-title">Rounds</div>'+rounds:'')+'</section>';
}
function toolsView(d){
  const state=d.mcp||{servers:[],calls:[]},skills=((d.runtime_config||{}).skills||[]);
  const servers=(state.servers||[]).map(server=>{const approved=new Set(server.allowed_tools||[]);
    // The dialog spells these out; a bare glyph whose meaning lives in a title
    // attribute is unavailable on touch and unreliable for a screen reader, so
    // the list says the same words the approval screen said.
    const tools=(server.tools||[]).map(tool=>{const note=tool.annotations||{};
      const risk=note.destructiveHint?'<i class="mcp-risk destructive">May change data</i>'
        :note.readOnlyHint?'<i class="mcp-risk readonly">Read-only</i>'
        :'<i class="mcp-risk unlabelled">Not labelled by the server</i>';
      return '<span class="mcp-tool'+(approved.has(tool.name)?' approved':'')+'" title="'+esc((tool.description||'')
        +' · server annotations are untrusted')+'">'+(approved.has(tool.name)?'✓ ':'')+esc(tool.name)+risk+'</span>';}).join('');
    const endpoint=server.transport==='stdio'?[server.command,...(server.args||[])].join(' '):server.url;
    return '<div class="host-row"><div class="host-top"><b>'+esc(server.name)+'</b>'
      +'<span class="host-kind">'+esc(server.transport)+'</span></div><div class="host-detail">'+esc(endpoint||'')+'</div>'
      +'<div class="host-resources"><span class="host-resource">MCP '+esc(server.protocol_version||'')+'</span><span class="host-resource">'
      +(server.enabled?'Generator enabled':'Manual only')+'</span><span class="host-resource">'+esc(server.max_calls_per_task)+' calls/task</span></div>'
      +'<div class="mcp-tool-list">'+(tools||'<span class="field-help">No tools advertised.</span>')+'</div><div class="host-actions">'
      +'<button type="button" class="secondary" data-mcp-configure="'+esc(server.id)+'">Configure</button>'
      +'<button type="button" class="secondary" data-mcp-probe="'+esc(server.id)+'">Refresh tools</button>'
      +'<button type="button" class="secondary" data-mcp-remove="'+esc(server.id)+'">Remove</button></div></div>';}).join('');
  const calls=(state.calls||[]).map(call=>'<div class="mcp-call"><b>'+esc(call.tool)+' · '+esc(call.server)+'</b><span class="status '
    +esc(call.status)+'">'+esc(call.status)+'</span><small>'+new Date(call.started*1000).toLocaleString()+'</small><small>'
    +Math.round(Number(call.duration_ms||0))+' ms</small></div>').join('');
  const skillRows=skills.map(skill=>'<tr><td class="dt-name">'+esc(skill.name)+'</td><td class="dt-muted">'
    +esc((skill.applies_to||[]).length?skill.applies_to.join(', '):'Every task')+'</td></tr>').join('');
  return '<div class="view-heading"><h2>Tools & Skills</h2><p>Project-scoped MCP capabilities and committed Generator guidance.</p></div>'
    +'<div class="compute-note"><span>ⓘ</span><div><b>Explicit capability boundaries.</b> MCP servers and Skills are invisible until you configure them. Approved MCP output remains untrusted data; Skills guide only the Generator and never change the Constitution.</div></div>'
    +'<div class="compute-message" id="mcp-message" role="alert"></div><div class="compute-toolbar">'
    +'<button type="button" class="primary" data-mcp-add>＋ Add MCP server</button><button type="button" class="secondary" data-manage-skills>Manage Skills</button></div>'
    +'<div class="compute-grid tools-grid"><section class="compute-section"><div class="compute-section-head"><b>MCP servers</b><span>'
    +(state.servers||[]).length+' connected</span></div>'+(servers||'<div class="compute-empty">No MCP servers connected to this project.</div>')+'</section>'
    +'<section class="compute-section"><div class="compute-section-head"><b>Recent tool calls</b><span>'+(state.calls||[]).length+' recorded</span></div>'
    +(calls||'<div class="compute-empty">No MCP tools called in this project.</div>')+'</section>'
    +'<section class="compute-section"><div class="compute-section-head"><b>Skills</b><span>'+skills.length+' committed</span></div>'
    +(skills.length?'<table class="dt"><thead><tr><th>Skill</th><th>Applies to</th></tr></thead><tbody>'+skillRows+'</tbody></table>':'<div class="compute-empty">No project Skills yet.</div>')+'</section></div>';
}
// SPEC-9 §4. #conversation is replaced wholesale on every render, so it can
// never carry a live region — that would re-announce the whole transcript every
// two seconds. The DELTA is announced instead, and only that something arrived:
// reading a generated answer aloud through a live region is hostile, because a
// person cannot pause it, skim it or re-read it. They are told it is there; they
// read it themselves.
let announcedTurns=null;let announcedTurnChat=null;
// SPEC-20 §6, taken up rather than deferred. The design engineer recorded the
// live-region gap and fenced it as out of scope: it is older and wider than the
// turn-folding slice, and it is a property of the SHARED context_condensed
// renderer. That is exactly why it is fixed here — one renderer, so one fix
// covers turn folding AND the file-outlining notice that predates every merge
// in this cycle. Fixing it per mechanism would have been the wrong shape.
//
// The law the security auditor stated, one layer deeper: containers present,
// contents absent. This case had no container at all: the notice was visible
// page text and nothing announced it, so a screen-reader user was told nothing
// about any reduction.
//
// The sentence announced is the one the wire already localised, NOT the English
// source. The rule this renderer states is to localise from the wire fields the
// event carries and never re-translate prose; the combined "<sentence>: <detail>"
// string has no dictionary entry by design, so handing the English to
// localizeTree would speak English to a Chinese reader — the locale-timing
// defect arriving through the other door.
//
// EVENT, not state: two reductions of the same kind are two occurrences, and
// the second is news. Baselined in silence on first render, or opening a thread
// would announce every condensation it ever had.
let announcedCondensations=null;let announcedCondenseChat=null;
function announceCondensation(d){
  const chat=activeChatId||'';
  const rows=(d.generator_stream||[]).filter(m=>m.kind==='context_condensed'
    &&(m.chat_id||'history')===chat);
  const ids=new Set(rows.map(m=>String(m.event_id||m.t||'')));
  if(announcedCondenseChat!==chat||announcedCondensations===null){
    announcedCondenseChat=chat;announcedCondensations=ids;return false;}
  const fresh=rows.filter(m=>!announcedCondensations.has(String(m.event_id||m.t||'')));
  announcedCondensations=ids;
  if(!fresh.length)return false;
  const last=fresh[fresh.length-1];
  return announce(localeText(last.summary_i18n,last.summary),'event');}
// R2 S1. This key was kind + second + the first 40 characters of the content,
// and the auditor collided it: two DIFFERENT replies in the same second whose
// first 40 characters agree rendered as two articles and produced ONE
// announcement. A sighted person saw both; a screen-reader user lost one
// entirely. A lossy prefix is not an identity.
//
// The fix is not a longer prefix — that is the same defect at a bigger number.
// `allMessages` already establishes what "a distinct message" means, because it
// drops duplicates on kind + second + the WHOLE content; anything it returns is
// therefore distinct under that triple. So the announcer uses that same key, and
// the two functions cannot disagree about identity — which is the shape of
// almost every defect found on this codebase this week: canonical at the
// producer, lossy at the consumer.
function turnKey(m){
  return [m.kind,m.t,String(m.utterance||m.summary||m.verdict||m.response||'')].join('|');}
// R2 S2. The content limit was right and is unchanged — the reply body never
// enters this sentence, and the auditor confirmed nothing leaks. But a status
// heard while focus is elsewhere has to say WHICH thread moved, and with Alpha
// and Beta both present this said only "CrossAudit replied." Naming the thread
// is a different axis from the content limit, not a relaxation of it.
//
// The name is `titleOf(d)` — the exact string the visible <h1 id="thread-title">
// shows — so the announcement and the heading cannot drift apart. Untitled
// threads fall back to the bare sentence rather than announcing "New chat",
// which names nothing.
function threadArrivalSentence(d){
  const title=d?String(titleOf(d)||'').trim():'';
  return (!title||title==='New chat'||title==='New task')
    ?'CrossAudit replied.'
    :'CrossAudit replied in '+title+'.';}
function announceThread(messages,d){
  const chat=activeChatId||'';
  const keys=new Set(messages.map(turnKey));
  // A transcript that already existed is not news. The first render of a thread,
  // and every switch between threads, takes the baseline in silence — otherwise
  // opening an old conversation would announce all of it.
  if(announcedTurnChat!==chat||announcedTurns===null){
    announcedTurnChat=chat;announcedTurns=keys;return false;}
  const fresh=messages.filter(m=>m.kind!=='you'&&!announcedTurns.has(turnKey(m)));
  announcedTurns=keys;
  // Their own words are not read back to them.
  if(!fresh.length)return false;
  return announce(threadArrivalSentence(d),'event');}
// D150. The server answers Send at once and handles the message in a worker;
// the result say() used to return arrives on the intake record instead. It is
// applied here exactly once, from the state, so a reload or a reconnect sees
// the same outcome the original tab did.
function settleIntake(d){
  const i=d&&d.intake;
  if(!pendingIntake||!i||i.id!==pendingIntake||!i.finished)return;
  pendingIntake=null;liveReply=null;
  if(i.error){optimisticSend=null;route.className='route on error';
    route.innerHTML='<b>Refused.</b> '+esc(i.error.reason||'');}
  else applySayResult(i.result||{});
  releaseComposer();}
function releaseComposer(){
  transferBusy=false;document.getElementById('attach').disabled=false;
  send.disabled=false;say.disabled=false;say.focus();}
function applySayResult(r){
  if(r.asked){optimisticSend=null;route.innerHTML='<b class="ask">Needs clarification.</b> '+esc(r.clarify);return;}
  activeChatId=r.chat_id||activeChatId;if(optimisticSend)optimisticSend.chat=activeChatId||'';
  // chat is answered in the worker: the echo + reply land in the next snapshot,
  // so the optimistic bubble stays until the real turns take over (echo-detection).
  if(r.lane!=='generator'&&r.lane!=='chat'){optimisticSend=null;}route.innerHTML=r.queued
    ?'<b>Queued.</b> Will be read at the next generator round'+(r.position?' · #'+esc(r.position):'')
    :(r.lane==='generator'&&String(r.executed||'').indexOf('refused')===0)
    ?'<b>Refused.</b> '+esc(String(r.executed).slice(10))
    :r.lane==='generator'
    ?'<b>Task started.</b> The result will appear in this conversation.'
    :r.lane==='chat'?'<b>Answered.</b>'
    :'<b>Message delivered.</b>';
  if(!r.queued&&optimisticSend)optimisticSend.queued=false;
  if(r.lane==='generator')pendingContinuation={cycle:'',chat:''};
  if(!pendingFiles.length||r.attachments_accepted){say.value='';pendingFiles=[];uploadProgress=new Map();fileInput.value='';drawFiles();syncAudience();}}
// The live lane reply (chat, direct auditor): the same consumer rules as the
// generator draft — key by (intake, stream), accept only the next seq, discard
// the whole text on any gap, discard on done/aborted. Superseded by the
// committed routing record when the intake settles.
function replyChunk(row){
  const stream=row&&row.stream;
  if(!stream||typeof stream!=='object')return;
  const intake=String(row.intake_id||''),id=String(stream.id||'');
  const seq=Number(stream.seq),done=stream.done===true;
  if(!intake||!id||!Number.isInteger(seq)||seq<0)return;
  const same=liveReply&&liveReply.intake===intake&&liveReply.id===id;
  if(!same){
    if(seq!==0){liveReply={intake:intake,id:id,seq:seq,text:'',done:true,broken:true,lane:row.lane||''};return;}
    liveReply={intake:intake,id:id,seq:-1,text:'',done:false,broken:false,lane:row.lane||''};
  }
  if(liveReply.broken)return;
  if(seq!==liveReply.seq+1){liveReply.text='';liveReply.broken=true;liveReply.done=true;
    if(lastState)render(lastState);return;}
  liveReply.seq=seq;
  if(!done)liveReply.text+=String(row.text||'');
  else{liveReply.done=true;if(stream.outcome!=='complete'){liveReply.text='';liveReply.broken=true;}}
  if(lastState)render(lastState);}
function liveReplyTurn(d){
  if(!liveReply||liveReply.broken||!liveReply.text)return '';
  const i=d&&d.intake;
  if(!i||i.finished||String(i.id||'')!==liveReply.intake)return '';
  if((i.chat_id||'')!==(activeChatId||''))return '';
  const auditorSide=AUDITOR_LANES.has(liveReply.lane||i.lane||'');
  const label=auditorSide?'Auditor live reply · direct reply':'Generator live reply · not audited';
  return '<article class="turn draft"><div class="turn-main">'
    +'<div class="turn-meta"><span class="role-mark '+(auditorSide?'auditor':'generator')+'" aria-hidden="true">'
    +(auditorSide?'A':'G')+'</span><b class="draft-label">'+esc(t(label))+'</b>'
    +'<span class="spacer"></span><span class="turn-time">'
    +(currentLocale==='zh'?'刚刚':'now')+'</span></div>'
    +'<div class="turn-body draft-body">'+esc(liveReply.text)+'</div></div></article>';}
function renderConversation(d){
  const thread = document.getElementById('thread');
  const previousTop = thread.scrollTop;
  const distanceFromBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight;
  const followLive = distanceFromBottom < 80;
  let html;
  if(newTaskMode) html = welcome();
  else{
    const messages = allMessages(d);
    announceThread(messages,d);
    announceCondensation(d);
    const p = chatProgress(d);
    const live = p && !p.finished ? runCard(d) : '';
    const approval = approvalCard(d);
    const review = reviewCard(d);
    // Optimistic echo: keep the just-sent message + working indicator on screen
    // until the real state takes over (a live run appears, or the message is
    // echoed back in the stream), so the send feels instant.
    settleIntake(d);
    let optimistic = '';
    if(optimisticSend && (!optimisticSend.chat || optimisticSend.chat===(activeChatId||''))){
      const want=(optimisticSend.text||'').trim();
      const echoed = messages.some(m=>m.kind==='you' && (m.utterance||'').trim()===want && (m.t||0)>=Math.floor((optimisticSend.at||0)/1000)-2);
      // A queued steering message must NOT be cleared by the live run it is
      // steering — only its own echo in the stream releases it.
      if(optimisticSend.queued ? echoed : ((p && !p.finished) || echoed)) optimisticSend = null;
      else{const reply=liveReplyTurn(d);
        optimistic = optimisticTurn(optimisticSend.text, optimisticSend.queued, intakeFor(d), Boolean(reply)) + reply;}
    }
    // One protagonist per screen: the welcome empty state renders only when
    // the timeline holds nothing at all, and the delivery band only when no
    // review card already states the outcome of the same cycle.
    const body = messages.map(m=>withTurnCost(turn(m,d),m,d)).join('') + optimistic + liveDraftTurn(d) + live + approval + review
      + admissionCard() + (review ? '' : deliveryStatus(d));
    html = body || welcome();
  }
  document.getElementById('conversation').innerHTML = html;
  if(followLive && !newTaskMode) thread.scrollTop = thread.scrollHeight;
  else thread.scrollTop = Math.min(previousTop,Math.max(0,thread.scrollHeight-thread.clientHeight));
}
const PANEL_TITLES={artifacts:'Files',audits:'Audit history',models:'Models',usage:'Usage',
  compute:'Compute',tools:'Tools & Skills',evidence:'Governed actions',plan:'Goal & plan'};
function renderPanelTabs(){
  document.querySelectorAll('.panel-tabs .nav-item').forEach(button=>{
    const selected=button.getAttribute('data-view')===activeView;
    button.classList.toggle('active',selected);
    button.setAttribute('aria-pressed',selected?'true':'false');
  });
}
function renderPanel(d){
  if(!d)return;
  document.getElementById('panel-title').textContent=PANEL_TITLES[activeView]||'Context panel';
  const staticPane=document.getElementById('panel-models');
  const dynamic=document.getElementById('panel-dynamic');
  staticPane.hidden=activeView!=='models';
  if(activeView==='models')dynamic.innerHTML='';
  else if(activeView==='artifacts')dynamic.innerHTML=artifactsView(d);
  else if(activeView==='audits')dynamic.innerHTML=auditsView(d);
  else if(activeView==='usage')dynamic.innerHTML=usageView(d);
  else if(activeView==='compute')dynamic.innerHTML=computeView(d);
  else if(activeView==='tools')dynamic.innerHTML=toolsView(d);
  else if(activeView==='evidence')dynamic.innerHTML=evidenceView(d);
  else if(activeView==='plan')dynamic.innerHTML=planView(d);
  renderPanelTabs();
}
function openPanelTab(view){
  const allowed=['artifacts','audits','models','usage','compute','tools','evidence','plan'];
  activeView=allowed.includes(view)?view:'artifacts';
  if(activeView!=='compute')stopComputeTimers();
  closeRail();
  inspector.classList.add('open');
  document.getElementById('inspect-toggle').setAttribute('aria-expanded','true');
  syncScrim();
  if(lastState)renderPanel(lastState);
}
function renderTasks(d){
  const query=String(document.getElementById('rail-search').value||'').trim().toLowerCase();
  const matches=c=>!query||String(c.title).toLowerCase().includes(query);
  const rows=((d.chats&&d.chats.items)||[]).filter(matches);
  const archivedRows=((d.chats&&d.chats.archived)||[]).filter(matches);
  const chatRow=c=>{
    const status=String(c.status||'').toLowerCase();
    const dot=(!status||status==='ready')?'':'<span class="state-dot '+esc(status)+'" title="'+esc(status)+'"></span>';
    return '<div class="task'+(c.id===activeChatId?' active':'')+'" role="button" tabindex="0" data-chat-id="'+esc(c.id)+'">'
    +'<div class="task-copy">'+dot+'<span class="task-title">'+esc(c.title)+'</span>'
    +'<span class="task-meta"><span>'+esc(ago(c.updated))+'</span></span></div>'
    +'<button type="button" class="pin-button'+(c.pinned?' pinned':'')+'" data-pin-chat="'+esc(c.id)+'" '
    +'aria-label="'+(c.pinned?'Unpin':'Pin')+' chat" title="'+(c.pinned?'Unpin':'Pin')+' chat">'+(c.pinned?'★':'☆')+'</button>'
    +'<button type="button" class="task-act more" data-chat-menu-open="'+esc(c.id)+'" '
    +'aria-haspopup="menu" aria-expanded="false" aria-label="More chat actions" title="More chat actions">⋯</button></div>';};
  const archivedRow=c=>
    '<div class="task is-archived">'
    +'<div class="task-copy"><span class="task-title">'+esc(c.title)+'</span>'
    +'<span class="task-meta"><span>'+esc(ago(c.updated))+'</span></span></div>'
    +'<button type="button" class="task-act unarchive" data-unarchive-chat="'+esc(c.id)+'" '
    +'aria-label="Unarchive chat" title="Unarchive chat"></button>'
    +'<button type="button" class="task-delete" data-delete-chat="'+esc(c.id)+'" '
    +'aria-label="Delete chat from project" title="Delete chat from project">⌫</button></div>';
  const pinned=rows.filter(c=>c.pinned),recent=rows.filter(c=>!c.pinned);
  let html='';if(pinned.length)html+='<div class="side-label">Pinned</div>'+pinned.map(chatRow).join('');
  if(recent.length)html+='<div class="side-label">Recent</div>'+recent.map(chatRow).join('');
  if(!rows.length&&!archivedRows.length)html='<div class="empty">No chats yet</div>';
  if(archivedRows.length){
    html+='<button type="button" class="archived-toggle" data-archived-toggle '
      +'aria-expanded="'+(archivedExpanded?'true':'false')+'" aria-controls="archived-list">'
      +'<span class="archived-chevron" aria-hidden="true"></span><span>Archived</span>'
      +'<span class="archived-count">'+archivedRows.length+'</span></button>'
      +'<div id="archived-list" class="archived-list"'+(archivedExpanded?'':' hidden')+'>'
      +archivedRows.map(archivedRow).join('')+'</div>';
  }
  document.getElementById('task-list').innerHTML=html;
}
function renderDecisionBanner(d){
  const banner=document.getElementById('decision-banner');
  const rows=(d&&d.escalations)||[];
  // A parked run whose decision object could not be recorded (fail-closed
  // verdict protection) still needs a person: its own waiting reason keeps
  // it in the needs-attention count instead of vanishing.
  const p=d&&d.progress;
  const parkedAlone=(p&&p.state==='PROVIDER_UNAVAILABLE'&&p.waiting_reason&&!rows.length)?1:0;
  const count=rows.length+parkedAlone;
  const show=count>0&&!resolutionModal.classList.contains('on')
    &&!document.body.classList.contains('hub-mode');
  banner.hidden=!show;
  if(show)document.getElementById('decision-banner-text').textContent=
    count+' task'+(count===1?'':'s')+' need'+(count===1?'s':'')+' your decision';
}
// SPEC-2 — a claim may not be shown before it is true.
// Four states, one vocabulary, no surface invents a fifth: a check that ran and
// held, one that ran and did not, one that has NOT RUN, and one that ran with
// nothing in scope. The panel used to print a literal '✓' in front of every
// CONFIGURED check, so a project with zero audits and zero receipts opened on
// four green ticks claiming verification that had never happened.
const CHECK_STATES={
  passed :{glyph:'\u2713',cls:'passed' ,word:'passed'},
  failed :{glyph:'\u2715',cls:'failed' ,word:'did not pass'},
  not_run:{glyph:'\u00b7',cls:'not-run',word:'not run yet'},
  n_a    :{glyph:'\u2013',cls:'n-a'    ,word:'nothing to check'}};
// The server sends {name: contract}. SPEC-2 asks it to send
// {name:{description,state}}; that half is server-side and is not in this
// slice, so both shapes are read here. Anything unrecognised — an absent state,
// a state this build does not know — is NOT_RUN. Never the other way round: a
// client that ships ahead of its server has to fail in the honest direction.
function checkEntry(value){
  const row=(value&&typeof value==='object'&&!Array.isArray(value))?value:{description:value};
  const state=Object.prototype.hasOwnProperty.call(CHECK_STATES,row.state)?row.state:'not_run';
  return {description:String(row.description==null?'':row.description),state:state};}
function checkRows(d){const contracts=(d&&d.check_contracts)||{};
  return Object.keys(contracts).map(name=>{const row=checkEntry(contracts[name]);
    return {name:name,description:row.description,state:row.state};});}
function auditCount(d){const row=((d&&d.metrics)||[]).find(m=>m.label==='Audits');
  return Number((row&&row.value)||0);}
// The glyph alone leaves "· convergence" — quieter and still meaningless to
// someone who does not know what a deterministic check is. This line is the
// only thing such a person needs to read, and it never says more than the
// states it is counting.
function checkSummary(rows,audits){
  if(!rows.length)return '';
  const total=rows.length,count=state=>rows.filter(row=>row.state===state).length;
  const failed=count('failed'),notRun=count('not_run'),na=count('n_a'),passed=count('passed');
  const word=n=>n===1?'check':'checks';
  if(notRun===total)return audits>0
    ?'These run with every task; no result has been reported for the latest round.'
    :'Not run yet — these run automatically on your first task.';
  if(failed)return failed+' of '+total+' '+word(total)+' did not pass on the latest round.';
  if(notRun)return notRun+' of '+total+' '+word(total)+(notRun===1?' has':' have')+' not run on the latest round.';
  if(na)return passed+' '+word(passed)+' passed, '+na+' had nothing to check.';
  return 'All '+total+' '+word(total)+' passed on the latest round.';}
// Each row states its own state as text: a screen reader must never be left to
// interpret a bare '·'.
function renderCheckRows(rows){
  if(!rows.length)return '<div class="empty">No checks configured</div>';
  return rows.map(row=>{const ui=CHECK_STATES[row.state];
    return '<div class="check-row '+ui.cls+'" role="listitem" title="'+esc(row.description)
      +'" aria-label="'+esc(row.name+': '+ui.word)+'">'
      +'<span class="check-glyph" aria-hidden="true">'+ui.glyph+'</span>'
      +'<span class="check-name">'+esc(row.name)+'</span></div>';}).join('');}
// Which decisions this client has already spoken about. Announcing on the
// COUNT would re-announce whenever one was resolved and another arrived in the
// same snapshot; announcing on identity does not.
let announcedEscalations=new Set();
function announceEscalations(rows){
  const ids=(rows||[]).map(row=>String(row.cycle_id||''));
  const fresh=ids.filter(id=>id&&!announcedEscalations.has(id));
  announcedEscalations=new Set(ids);
  if(!fresh.length)return;
  // An arrival, not a state: two separate escalations produce the same sentence
  // and the second one is still news.
  announce(fresh.length===1
    ?'A task is waiting for your decision.'
    :fresh.length+' tasks are waiting for your decision.','event');}
function renderInspector(d){
  document.getElementById('runtime-generator').textContent = d.generator;
  document.getElementById('runtime-auditor').textContent = d.auditor;
  document.getElementById('max-rounds').textContent = d.max_rounds;
  const progress=chatProgress(d),cycles=chatCycles(d);
  const current = progress && progress.steps ? progress.steps.filter(s =>
    s.kind === 'round_started').slice(-1)[0] : null;
  document.getElementById('current-round').textContent = current
    ? current.round_no + ' / ' + current.round_limit
    : cycles.length ? cycles[cycles.length-1].round + ' / ' + d.max_rounds : '-';
  // The count is every rule in the constitution; how many of them GATE is not
  // in this payload, so the row no longer calls them all blockers. SPEC-2 4.1
  // wants "8 rules · 7 blocking"; the blocking half needs one additive server
  // field and is escalated, not guessed.
  document.getElementById('rules-count').textContent = d.rules + (d.rules===1?' rule':' rules');
  document.getElementById('tier-value').textContent = d.tier.tier;
  const rows = checkRows(d);
  document.getElementById('runtime-checks-state').textContent = checkSummary(rows, auditCount(d));
  document.getElementById('runtime-checks').innerHTML = renderCheckRows(rows);
  document.getElementById('mini-metrics').innerHTML = d.metrics.map(m => '<div class="mini-metric">'
    + '<div class="mini-value">' + esc(m.value ?? '-') + '</div><div class="mini-label">'
    + esc(m.label) + '</div></div>').join('');
  const escalations=currentEscalations(d);
  announceEscalations(escalations);
  document.getElementById('escalations').innerHTML = escalations.length ? escalations.map(e =>
    '<div class="escalation"><b>' +(e.limit_reached?'Automatic limit reached · ':'')+esc(e.round)+' / '+esc(e.max_rounds)+' rounds</b><p>'
    + esc(e.why) + '</p><small>'+(e.issues||[]).length+' remaining issue'+((e.issues||[]).length===1?'':'s')+'</small>'
    +'<p>'+esc(e.requested||'A human decision is required.')+'</p><div class="escalation-actions"><button type="button" class="secondary" data-resolve="reopen" data-cycle="'
    +esc(e.cycle_id)+'" data-sha="'+esc(e.short_sha||String(e.sha).slice(0,12))+'">Allow another round</button><button type="button" class="secondary" data-resolve="close" data-cycle="'
    +esc(e.cycle_id)+'" data-sha="'+esc(e.short_sha||String(e.sha).slice(0,12))+'">Stop task</button></div></div>').join('') : '<div class="empty">Nothing needs attention.</div>';
}
function maybePromptForHuman(d){
  if(document.body.classList.contains('hub-mode')||resolutionModal.classList.contains('on')||newTaskMode)return;
  const row=currentEscalations(d).slice(-1)[0];
  if(row&&!promptedEscalations.has(row.cycle_id))setTimeout(()=>{
    if(lastState===d&&!resolutionModal.classList.contains('on'))openResolution(row);
  },0);
}
function render(d){
  lastState = d;
  // A one-time entrance for the shell (topbar / rail / thread / composer). The
  // class is added on the first paint only, so it plays once on load and never
  // replays on an SSE snapshot — no per-frame flicker. Reduced-motion opts out.
  if(!document.body.classList.contains('booted'))
    requestAnimationFrame(()=>document.body.classList.add('booted'));
  const chatRows=(d.chats&&d.chats.items)||[];
  if(activeChatId&&!chatRows.some(row=>row.id===activeChatId))activeChatId='';
  if(!activeChatId&&chatRows.length&&!newTaskMode)activeChatId=chatRows[0].id;
  if(runtimeModal.classList.contains('on'))syncRuntimeBusy(d);
  const preview=document.getElementById('contract-preview');preview.className='contract-preview';preview.innerHTML='';
  document.getElementById('version-badge').textContent = 'V' + d.version;
  document.getElementById('hub-version').textContent = 'V' + d.version;
  // Top bar shows a clean project name, not the owner/repo GitHub slug; the
  // full slug + workspace folder stay available on hover.
  const projName = d.title || d.project;
  const projEl = document.getElementById('proj');
  projEl.textContent = projName;
  const switcher = document.getElementById('project-switcher');
  if(switcher) switcher.title = d.project + (d.folder ? '  ·  ' + d.folder : '');
  const branchLabel = document.getElementById('branch-label');
  if(branchLabel && d.folder) branchLabel.textContent = '/ ' + d.folder;
  document.getElementById('side-project').textContent = projName;
  const sampleBanner=document.getElementById('sample-banner');if(sampleBanner)sampleBanner.hidden=!d.demo;
  document.body.classList.toggle('is-demo',Boolean(d.demo));
  document.getElementById('tier-label').textContent = d.tier.tier + ' · local controller';
  document.getElementById('thread-title').textContent = newTaskMode ? 'New chat' : titleOf(d);
  setStatePill(d);
  renderDecisionBanner(d);
  renderUsagePill(d);renderUsageBanner(d);
  document.getElementById('model-summary').textContent = modelTag(d.generator) + ' → ' + modelTag(d.auditor);
  const activeRun=chatProgress(d),canCancel=Boolean(activeRun&&!activeRun.finished);
  stopRun.hidden=!canCancel;send.hidden=false;
  send.setAttribute('aria-label',canCancel?(currentLocale==='zh'?'向运行中的任务发送补充信息':'Send guidance to the running task'):(currentLocale==='zh'?'运行任务':'Run task'));send.title=send.getAttribute('aria-label');
  stopRun.disabled=Boolean(activeRun&&activeRun.state==='CANCELLING');
  stopRun.setAttribute('aria-label',currentLocale==='zh'?'停止正在运行的任务':'Cancel running task');
  stopRun.title=stopRun.getAttribute('aria-label');
  const projectPin=document.getElementById('current-project-pin'),projectPinned=Boolean(d.chats&&d.chats.project_pinned);
  projectPin.textContent=projectPinned?'★':'☆';projectPin.classList.toggle('pinned',projectPinned);
  projectPin.title=projectPinned?'Unpin project':'Pin project';projectPin.setAttribute('aria-label',projectPin.title);
  renderTasks(d);renderInspector(d);renderConversation(d);renderPanel(d);
  const iv = document.getElementById('interrupted');
  const interruptedChat=d.interrupted&&(d.interrupted.chat_id||'history');
  const interruptedChatExists=Boolean(interruptedChat&&(d.chats&&d.chats.items||[]).some(item=>item.id===interruptedChat));
  if(d.interrupted&&(interruptedChat===activeChatId||!interruptedChatExists) && !(chatProgress(d) && !chatProgress(d).finished)){
    const interruptedTask=esc(d.interrupted.task.replace(/\s+/g,' ').slice(0,72));
    const phaseNames=currentLocale==='zh'?{generator:'生成者',auditor:'审计者',input:'输入',loop:'审计循环',tool:'工具',compute:'远程计算',unknown:'未知'}:{};
    const interruptedPhase=esc(phaseNames[d.interrupted.phase]||d.interrupted.phase||'unknown');
    const interruptedDetail=d.interrupted.detail?'<span class="interrupted-detail">'+esc(d.interrupted.detail)+'</span>':'';
    iv.className = 'interrupted on';iv.innerHTML = currentLocale==='zh'
      ?'<b>任务已安全中断</b><br>“'+interruptedTask+'”。最后可见阶段：'+interruptedPhase+'。'+interruptedDetail+'已提交轮次均已保留；重试会从最近的持久 Git 提交继续，忽略提示也不会改动文件。<div class="interrupted-actions"><button type="button" data-interrupted="retry">重试任务</button><button type="button" data-interrupted="dismiss">忽略提示</button></div>'
      :'<b>Task interrupted safely</b><br>"'+interruptedTask+'". Last visible phase: '+interruptedPhase+'. '+interruptedDetail+'Committed rounds are preserved. Retry resumes from the last durable commit; dismiss keeps files unchanged.<div class="interrupted-actions"><button type="button" data-interrupted="retry">Retry task</button><button type="button" data-interrupted="dismiss">Dismiss notice</button></div>';
  }else iv.className = 'interrupted';
  maybePromptForHuman(d);
}
document.getElementById('interrupted').onclick=async ev=>{const button=ev.target.closest('[data-interrupted]');if(!button)return;
  button.disabled=true;const action=button.getAttribute('data-interrupted');
  try{await api('/api/interrupted',{action});route.className='route on';route.innerHTML=currentLocale==='zh'
    ?(action==='retry'?'<b>任务已重启</b> — 正从最近的持久 Git 提交继续。':'<b>提示已忽略</b> — 文件和已提交证据均已保留。')
    :(action==='retry'?'<b>Task restarted.</b> Continuing from the last durable Git commit.':'<b>Notice dismissed.</b> Files and committed evidence were preserved.');}
  catch(e){route.className='route on error';route.textContent=e.message;button.disabled=false;}};
function connected(on,why){
  document.getElementById('livedot').className='live-dot'+(on?' on':'');
  document.getElementById('conn-text').textContent=why;
  document.querySelector('.live-pill').title = on
    ? why + ' · updated ' + new Date().toLocaleTimeString() : why;
}
let poller=null;
function startPolling(why){connected(false,why);if(poller)return;poller=setInterval(async()=>{
  try{render(await api('/api/state'));connected(true,'polling');}catch(e){connected(false,'offline');}},2000);}
// F7. The transport was correct and nothing consumed it: production-shaped
// `generation_chunk` frames reached the browser as NAMED SSE events and the page
// registered no named listener. Thirty focused streaming tests passed because
// they stop at the transport, so the merge could claim a visible live draft
// while a person watching the console saw nothing arrive early.
//
// This is the page side of the contract held in the server module
// docstring for `_generation_sse_frame` (D4), implemented not re-derived:
// key by (run_id, stream.id); accept only seq == expected; on ANY gap discard
// the WHOLE accumulated draft and never concatenate across it; done/aborted
// discards; done/complete stays visibly provisional until the ordinary state
// leaves GENERATING, which supersedes it with the committed turn.
//
// Discarding on a gap rather than showing what arrived is the fail-closed
// choice and the only honest one: a draft with a hole in it is not what the
// generator wrote, and presenting it would be a smaller version of the defect
// F1 closes — text on screen that nothing stands behind.
let liveDraft=null;
// D150. The summarised thinking of the generator, on its own named frame and its own
// consumer: same gap rule, but only a bounded tail is kept, because it is a
// glance at what the model is weighing, not a document.
let liveThinking=null;
const THINKING_TAIL=600;
function thinkingChunk(row){
  const stream=row&&row.stream;
  if(!stream||typeof stream!=='object')return;
  const run=String(row.run_id||''),id=String(stream.id||'');
  const seq=Number(stream.seq),done=stream.done===true;
  if(!run||!id||!Number.isInteger(seq)||seq<0)return;
  const same=liveThinking&&liveThinking.run===run&&liveThinking.id===id;
  if(!same){
    if(seq!==0){liveThinking={run:run,id:id,seq:seq,text:'',done:true,broken:true};return;}
    liveThinking={run:run,id:id,seq:-1,text:'',done:false,broken:false};
  }
  if(liveThinking.broken)return;
  if(seq!==liveThinking.seq+1){liveThinking.text='';liveThinking.broken=true;liveThinking.done=true;return;}
  liveThinking.seq=seq;
  if(!done){liveThinking.text=(liveThinking.text+String(row.text||'')).slice(-THINKING_TAIL);}
  else liveThinking.done=true;
  if(lastState)render(lastState);}
function liveThinkingFor(d){
  if(!liveThinking||liveThinking.broken||!liveThinking.text||liveThinking.done)return null;
  const p=chatProgress(d);
  if(!p||p.finished||String(p.run_id||'')!==liveThinking.run)return null;
  if(String(p.state||'').toUpperCase()!=='GENERATING')return null;
  return liveThinking;}
// Words for the draft line: CJK counts by character, everything else by word.
function draftCount(text){const cjk=(String(text||'').match(/[\u4e00-\u9fff]/g)||[]).length;
  const words=(String(text||'').replace(/[\u4e00-\u9fff]/g,' ').match(/\S+/g)||[]).length;return cjk+words;}
function draftChunk(row){
  const stream=row&&row.stream;
  if(!stream||typeof stream!=='object')return;
  const run=String(row.run_id||''),id=String(stream.id||'');
  const seq=Number(stream.seq),done=stream.done===true;
  if(!run||!id||!Number.isInteger(seq)||seq<0)return;
  const same=liveDraft&&liveDraft.run===run&&liveDraft.id===id;
  if(!same){
    // A new stream may only begin at 0. Anything else means we joined midway —
    // a reconnect, a dropped frame — and there is no complete draft to show.
    if(seq!==0){liveDraft={run:run,id:id,seq:seq,text:'',done:true,broken:true};return;}
    liveDraft={run:run,id:id,seq:-1,text:'',done:false,broken:false};
  }
  if(liveDraft.broken)return;
  if(seq!==liveDraft.seq+1){liveDraft.text='';liveDraft.broken=true;liveDraft.done=true;
    if(lastState)render(lastState);return;}
  liveDraft.seq=seq;
  if(!done)liveDraft.text+=String(row.text||'');
  else{
    liveDraft.done=true;
    // Aborted means the completion did not finish. There is no draft.
    if(stream.outcome!=='complete'){liveDraft.text='';liveDraft.broken=true;}
  }
  if(lastState)render(lastState);}
// Shown only while the run it belongs to is still generating. Superseding is
// therefore driven by the ordinary state — a failure, a cancellation, an
// interruption or the move to AUDITING all end it — and never by a page-side
// timer, which would be the page guessing about a run it cannot see.
function liveDraftFor(d){
  if(!liveDraft||liveDraft.broken||!liveDraft.text)return null;
  const p=chatProgress(d);
  if(!p||p.finished||String(p.run_id||'')!==liveDraft.run)return null;
  if(String(p.state||'').toUpperCase()!=='GENERATING')return null;
  return liveDraft;}
function liveDraftTurn(d){
  const draft=liveDraftFor(d);
  if(!draft)return '';
  // Deliberately none of: a file card, a download, a delivery band, a PASS mark
  // or any audit styling. This is unaudited text and it may not borrow the
  // furniture of text that has been through the auditor.
  return '<article class="turn draft"><div class="turn-main">'
    +'<div class="turn-meta"><span class="role-mark" aria-hidden="true">G</span>'
    +'<b class="draft-label">Generator live draft · not yet audited</b>'
    +'<span class="spacer"></span><span class="turn-time">'
    +(currentLocale==='zh'?'刚刚':'now')+'</span></div>'
    +'<div class="turn-body draft-body">'+esc(draft.text)+'</div></div></article>';}
function startStream(){let source;try{source=new EventSource('/api/stream?t='+encodeURIComponent(T));}
  catch(e){startPolling('polling');return;}source.onopen=()=>{connected(true,'live');
  if(poller){clearInterval(poller);poller=null;}};source.onmessage=ev=>{try{const d=JSON.parse(ev.data);
  // A fresh frame that no longer carries the message we are waiting on means
  // the process that accepted it is gone; the composer is given back rather
  // than held for a reply that cannot come.
  if(pendingIntake&&!(d.intake&&d.intake.id===pendingIntake)){pendingIntake=null;liveReply=null;releaseComposer();}
  render(d);connected(true,'live');}catch(e){}};
  source.addEventListener('intake_chunk',ev=>{try{replyChunk(JSON.parse(ev.data));}catch(e){}});
  // The named listener this whole finding is about. `onmessage` never sees it:
  // a frame with an `event:` line is dispatched by name and by name only.
  source.addEventListener('generation_chunk',ev=>{try{draftChunk(JSON.parse(ev.data));}catch(e){}});
  source.addEventListener('thinking_chunk',ev=>{try{thinkingChunk(JSON.parse(ev.data));}catch(e){}});
  source.onerror=()=>startPolling('reconnecting');}

const form=document.getElementById('f');const say=document.getElementById('say');
const send=document.getElementById('send');const stopRun=document.getElementById('stop-run');
const route=document.getElementById('route');
// One safe path to stop a live run — the run card's Stop reuses the composer's
// vetted cancellation flow rather than duplicating it.
function requestStop(){if(stopRun&&!stopRun.hidden&&!stopRun.disabled)stopRun.click();}
const filesBox=document.getElementById('attachments');const fileInput=document.getElementById('file-input');
const sidebar=document.querySelector('.sidebar');const inspector=document.getElementById('inspector');
const scrim=document.getElementById('scrim');
function syncScrim(){
  const sideOpen=sidebar.classList.contains('open');const inspectOpen=inspector.classList.contains('open');
  scrim.className='scrim'+(sideOpen||inspectOpen?' on':'')+(sideOpen?' sidebar-open':'')
    +(inspectOpen?' inspector-open':'');
}
function closeRail(){sidebar.classList.remove('open');
  document.getElementById('sidebar-toggle').setAttribute('aria-expanded','false');syncScrim();}
function closePanels(){sidebar.classList.remove('open');inspector.classList.remove('open');
  document.getElementById('sidebar-toggle').setAttribute('aria-expanded','false');
  document.getElementById('inspect-toggle').setAttribute('aria-expanded','false');syncScrim();}
function toggleSidebar(){const opening=!sidebar.classList.contains('open');closePanels();
  if(opening){sidebar.classList.add('open');document.getElementById('sidebar-toggle').setAttribute('aria-expanded','true');}
  syncScrim();}
function toggleInspector(){
  if(inspector.classList.contains('open')){inspector.classList.remove('open');
    document.getElementById('inspect-toggle').setAttribute('aria-expanded','false');syncScrim();}
  else openPanelTab(activeView);}
function openInspector(){openPanelTab('models');}
function drawFiles(){filesBox.className='attachments'+(pendingFiles.length?' on':'');
  const visible=pendingFiles.slice(0,100);const total=pendingFiles.reduce((sum,e)=>sum+e.file.size,0);
  filesBox.innerHTML=visible.map((entry,i)=>{const f=entry.file;const progress=uploadProgress.get(entry);
    const failed=progress==='failed';const done=progress===100;const ext=(entry.name.includes('.')?entry.name.split('.').pop():'FILE').slice(0,4).toUpperCase();
    const state=failed?'Upload failed':done?'Uploaded':typeof progress==='number'?'Uploading · '+progress+'%':formatBytes(f.size);
    return '<div class="attachment'+(failed?' failed':'')+'"><span class="attachment-type">'+esc(ext)+'</span>'
      +'<span class="attachment-copy"><span class="attachment-name" title="'+esc(entry.name)+'">'+esc(entry.name)+'</span>'
      +'<span class="attachment-state">'+esc(state)+'</span></span><button type="button" data-remove="'+i+'" aria-label="Remove '+esc(entry.name)+'">×</button>'
      +(typeof progress==='number'&&progress<100?'<span class="attachment-progress"><i style="width:'+progress+'%"></i></span>':'')+'</div>';}).join('')
    +(pendingFiles.length?'<div class="attachment-note"><b>'+pendingFiles.length+' file'+(pendingFiles.length===1?'':'s')+' · '+formatBytes(total)+'</b>'
      +(pendingFiles.length>visible.length?'<span class="attachment-more">+'+(pendingFiles.length-visible.length)+' more selected</span>':'')
      +'<span>Stored in chunks without an app quota. Model inspection depends on file support and context.</span></div>':'');}
function uniqueFileName(original){let name=original||'untitled';const used=new Set(pendingFiles.map(e=>e.name.toLowerCase()));
  if(!used.has(name.toLowerCase()))return name;const dot=name.lastIndexOf('.');const base=dot>0?name.slice(0,dot):name;
  const ext=dot>0?name.slice(dot):'';let n=2;while(used.has((base+' ('+n+')'+ext).toLowerCase()))n++;
  return base+' ('+n+')'+ext;}
function addFiles(list){for(const file of Array.from(list||[])){
  if(transferBusy)return;
  pendingFiles.push({file,name:uniqueFileName(file.name)});
}drawFiles();}
function uploadId(){const bytes=crypto.getRandomValues(new Uint8Array(16));return [...bytes].map(v=>v.toString(16).padStart(2,'0')).join('');}
async function uploadFile(entry,batch,ordinal,count){const file=entry.file;const id=uploadId();const chunkSize=384000;let offset=0;
  do{const blob=file.slice(offset,Math.min(file.size,offset+chunkSize));
    const bytes=new Uint8Array(await blob.arrayBuffer());let binary='';
  for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
    await api('/api/upload',{id,batch,ordinal,batch_count:count,name:entry.name,
      type:file.type||'application/octet-stream',offset,total:file.size,data:btoa(binary)});offset+=bytes.length;
    uploadProgress.set(entry,file.size?Math.round(offset/file.size*100):100);drawFiles();
  }while(offset<file.size);return id;}
async function uploadFiles(files){const batch=uploadId();let next=0;const workers=[];
  for(let worker=0;worker<Math.min(3,files.length);worker++)workers.push((async()=>{while(next<files.length){
    const ordinal=next++;const entry=files[ordinal];try{await uploadFile(entry,batch,ordinal,files.length);}
    catch(error){uploadProgress.set(entry,'failed');drawFiles();throw error;}}})());
  const settled=await Promise.allSettled(workers);const failed=settled.find(result=>result.status==='rejected');
  if(failed)throw failed.reason;return batch;
}
const mentionPrefix=/^\s*@(generator|executor|auditor|audit|生成者|审计者|生成端|执行端|审计端|审计)(?=\s|[,:：-]|$)[\s,:：-]*/i;
function audienceOf(){const m=say.value.match(mentionPrefix);if(!m)return'auto';
  return ['generator','executor','生成者','生成端','执行端'].includes(m[1].toLowerCase())?'generator':'auditor';}
function syncAudience(){const audience=audienceOf();document.querySelectorAll('.audience-chip').forEach(button=>
  button.classList.toggle('active',button.getAttribute('data-audience')===audience));}
function setAudience(audience){const body=say.value.replace(mentionPrefix,'').trimStart();
  say.value=(audience==='auto'?'':audience==='generator'?'@Generator ':'@Auditor ')+body;
  say.dispatchEvent(new Event('input'));say.focus();}
document.getElementById('attach').onclick=()=>fileInput.click();fileInput.onchange=()=>{addFiles(fileInput.files);fileInput.value='';};
filesBox.onclick=ev=>{const button=ev.target.closest('[data-remove]');if(button){const i=Number(button.getAttribute('data-remove'));
  if(transferBusy)return;
  uploadProgress.delete(pendingFiles[i]);pendingFiles.splice(i,1);drawFiles();}};
const dropOverlay=document.getElementById('drop-overlay');let dragDepth=0;
function fileDrag(ev){return Array.from((ev.dataTransfer&&ev.dataTransfer.types)||[]).includes('Files');}
window.addEventListener('dragenter',ev=>{if(!fileDrag(ev))return;ev.preventDefault();dragDepth++;
  dropOverlay.className='drop-overlay on';dropOverlay.setAttribute('aria-hidden','false');form.classList.add('drag');});
window.addEventListener('dragover',ev=>{if(fileDrag(ev))ev.preventDefault();});
window.addEventListener('dragleave',ev=>{if(!fileDrag(ev))return;ev.preventDefault();dragDepth=Math.max(0,dragDepth-1);
  if(!dragDepth){dropOverlay.className='drop-overlay';dropOverlay.setAttribute('aria-hidden','true');form.classList.remove('drag');}});
window.addEventListener('drop',ev=>{if(!fileDrag(ev))return;ev.preventDefault();dragDepth=0;
  dropOverlay.className='drop-overlay';dropOverlay.setAttribute('aria-hidden','true');form.classList.remove('drag');
  addFiles(ev.dataTransfer.files);say.focus();});
say.addEventListener('input',()=>{say.style.height='auto';say.style.height=Math.min(say.scrollHeight,150)+'px';syncAudience();});
say.addEventListener('keydown',ev=>{if(ev.key==='Enter'&&!ev.shiftKey&&!ev.isComposing){ev.preventDefault();form.requestSubmit();}});
document.querySelectorAll('.audience-chip').forEach(button=>button.onclick=()=>setAudience(button.getAttribute('data-audience')));
const computeHostModal=document.getElementById('compute-host-modal');
const computeHostForm=document.getElementById('compute-host-form');
const computeJobModal=document.getElementById('compute-job-modal');
const computeJobForm=document.getElementById('compute-job-form');
const mcpModal=document.getElementById('mcp-modal');
const mcpForm=document.getElementById('mcp-form');
const computeLogTimers=new Map();
let computeInputFiles=[];
function computeError(id,error){showInlineError(id,error);}
function computeSurfaceError(error){const box=document.getElementById(activeView==='tools'?'mcp-message':'compute-message');if(!box)return;
  box.textContent=error&&error.message?error.message:String(error);box.className='compute-message on';}
function closeComputeHost(){computeHostModal.className='project-modal';computeHostForm.reset();}
function openComputeHost(){computeHostForm.reset();document.getElementById('compute-host-error').className='wizard-error';
  const aliases=(lastState&&lastState.compute&&lastState.compute.aliases)||[];
  document.getElementById('compute-aliases').innerHTML=aliases.map(value=>'<option value="'+esc(value)+'"></option>').join('');
  document.getElementById('hpc-agent-policy').className='hpc-policy off';
  computeHostModal.className='project-modal on';setTimeout(()=>document.getElementById('compute-alias').focus(),0);}
document.getElementById('hpc-agent-enabled').onchange=event=>{
  document.getElementById('hpc-agent-policy').className='hpc-policy'+(event.target.checked?'':' off');};
function closeComputeJob(){computeJobModal.className='project-modal';computeJobForm.reset();}
function openComputeJob(hostId){const hosts=(lastState&&lastState.compute&&lastState.compute.hosts)||[];
  if(!hosts.length){openComputeHost();return;}computeJobForm.reset();if(currentLocale==='zh')computeJobForm.querySelector('[name="name"]').value='CrossAudit 任务';computeInputFiles=[];renderComputeInputs();document.getElementById('compute-job-error').className='wizard-error';
  const select=document.getElementById('compute-job-host');select.innerHTML=hosts.map(host=>'<option value="'+esc(host.id)+'">'
    +esc(host.alias+' · '+((host.probe||{}).scheduler||'workstation'))+'</option>').join('');
  if(hostId&&hosts.some(host=>host.id===hostId))select.value=hostId;
  computeJobModal.className='project-modal on';}
function renderComputeInputs(){const total=computeInputFiles.reduce((sum,row)=>sum+row.file.size,0);
  document.getElementById('compute-input-summary').textContent=computeInputFiles.length
    ?computeInputFiles.length+' file'+(computeInputFiles.length===1?'':'s')+' · '+formatBytes(total)+' · copied to remote inputs/'
    :'Optional. Files are streamed to inputs/ on the remote host with no CrossAudit size or count quota.';
  document.getElementById('compute-input-list').innerHTML=computeInputFiles.map((row,index)=>'<span class="hpc-input"><b>'
    +esc(row.name)+'</b><span>'+formatBytes(row.file.size)+'</span><button type="button" data-compute-input="'+index+'" aria-label="Remove '
    +esc(row.name)+'">×</button></span>').join('');}
document.getElementById('add-compute-inputs').onclick=()=>document.getElementById('compute-input-files').click();
document.getElementById('compute-input-list').onclick=ev=>{const button=ev.target.closest('[data-compute-input]');if(!button)return;
  computeInputFiles.splice(Number(button.getAttribute('data-compute-input')),1);renderComputeInputs();};
document.getElementById('compute-input-files').onchange=ev=>{for(const file of Array.from(ev.target.files||[])){
  const used=new Set(computeInputFiles.map(row=>row.name.toLowerCase()));let name=file.name||'untitled';
  if(used.has(name.toLowerCase())){const dot=name.lastIndexOf('.'),base=dot>0?name.slice(0,dot):name,ext=dot>0?name.slice(dot):'';
    let n=2;while(used.has((base+' ('+n+')'+ext).toLowerCase()))n++;name=base+' ('+n+')'+ext;}
  computeInputFiles.push({file,name});}ev.target.value='';renderComputeInputs();};
document.getElementById('close-compute-host').onclick=closeComputeHost;
document.getElementById('cancel-compute-host').onclick=closeComputeHost;
document.getElementById('close-compute-job').onclick=closeComputeJob;
document.getElementById('cancel-compute-job').onclick=closeComputeJob;
computeHostModal.addEventListener('click',ev=>{if(ev.target===computeHostModal)closeComputeHost();});
computeJobModal.addEventListener('click',ev=>{if(ev.target===computeJobModal)closeComputeJob();});
computeHostForm.onsubmit=async ev=>{ev.preventDefault();const button=document.getElementById('save-compute-host');
  button.disabled=true;button.textContent='Connecting…';document.getElementById('compute-host-error').className='wizard-error';
  const fd=new FormData(computeHostForm);const payload=Object.fromEntries(fd.entries());payload.action='register';
  for(const key of ['concurrency','agent_max_jobs','agent_max_nodes','agent_max_cpus','agent_max_gpus'])payload[key]=Number(payload[key]);
  payload.trust_first_key=fd.has('trust_first_key');payload.agent_enabled=fd.has('agent_enabled');
  try{await api('/api/hpc',payload);closeComputeHost();if(lastState)lastState.compute=await api('/api/state').then(s=>s.compute);render(lastState);}
  catch(e){computeError('compute-host-error',e);}finally{button.disabled=false;button.textContent='Probe & add';}};
computeJobForm.onsubmit=async ev=>{ev.preventDefault();const button=document.getElementById('submit-compute-job');
  button.disabled=true;button.textContent='Submitting…';document.getElementById('compute-job-error').className='wizard-error';
  const fd=new FormData(computeJobForm);const payload=Object.fromEntries(fd.entries());payload.action='submit';
  for(const key of ['nodes','cpus','gpus'])payload[key]=Number(payload[key]);
  try{if(computeInputFiles.length){button.textContent='Uploading inputs…';payload.upload_batch=await uploadFiles(computeInputFiles);button.textContent='Submitting…';}
    await api('/api/hpc',payload);closeComputeJob();}
  catch(e){computeError('compute-job-error',e);}finally{button.disabled=false;button.textContent='Submit job';}};
function syncMcpTransport(){const stdio=document.getElementById('mcp-transport').value==='stdio';
  document.getElementById('mcp-stdio-fields').classList.toggle('off',!stdio);
  document.getElementById('mcp-http-fields').classList.toggle('off',stdio);
  document.getElementById('mcp-command').required=stdio;document.getElementById('mcp-url').required=!stdio;
  // Also on the way OUT of stdio: the local-command gate must be released when
  // the transport it belongs to is no longer the one selected.
  syncMcpApprovalState();}
// The dialog walks the same lifecycle /api/mcp already enforces: connect and
// read the tool list first, approve named tools second, and only then may the
// Generator be let near them. Step 1 never approves or enables anything, so a
// half-finished dialog always leaves the server switched off.
let mcpStep='connect';let mcpTools=[];let mcpApproved=new Set();let mcpReconnected=false;
// SERVER_NAME from mcp.py, mirrored so the refusal arrives in the field the
// person is looking at instead of as a round-trip denial. It is only ever a
// mirror: the
// server still decides, and this must never be looser than it is.
const MCP_NAME_RE=/^[A-Za-z0-9][A-Za-z0-9_. -]{0,79}$/;
// Step 1 has to POST to read the tool list, so a row exists while step 2 is on
// screen. That row is a draft, not a server the person agreed to keep: this
// holds its id until they press Save, and every close path deletes it. Declining
// therefore leaves nothing behind, which is what Cancel has always claimed.
let mcpCreatedId='';
// The exact local command the person has ALREADY approved for this server
// ({command, args}), or null when nothing is approved yet. A saved server
// carries the approval its owner gave when they connected it; that approval
// stays valid for that command and those arguments and for nothing else, so
// editing a timeout does not demand a fresh ritual while editing the command
// does. It is never invented: it comes from a stored server row or from the
// checkbox the person just ticked.
// An approval is a claim about ONE execution vector, so it is stored AS that
// vector, never as a bare flag:
//   mcpApprovedCommand — what the stored server row proves its owner approved
//                        when they connected it (null for a new server);
//   mcpTickedFor       — the exact command+args on screen at the moment the
//                        person ticked the consent box.
// Both are {command, args}. approve_local_code=true is sent only when the live
// form equals one of them, so anything sent is traceable to a human looking at
// that exact vector. A tick can never ride along to a command it was not given
// for; a mismatch is simply unapproved, and the server refuses.
let mcpApprovedCommand=null;let mcpTickedFor=null;
// What was rendered into the fields when the dialog opened, kept alongside the
// stored values so an UNTOUCHED form round-trips the row byte-for-byte. The
// textarea is lossy (it trims and drops blank lines), so a legacy row with an
// empty or whitespace-bearing argument must not be re-derived from the text.
let mcpRendered=null;
function mcpArgsValue(){return document.getElementById('mcp-args').value
  .split('\n').map(value=>value.trim()).filter(Boolean);}
function mcpSameTuple(left,right){
  if(!left||!right)return false;
  const a=left.args||[],b=right.args||[];
  return left.command===right.command&&a.length===b.length
    &&a.every((value,index)=>value===b[index]);}
// The vector the form currently describes. While the fields still hold exactly
// what was rendered, that is the stored row itself — not a re-parse of it.
function mcpLiveTuple(){
  const commandText=document.getElementById('mcp-command').value;
  const argsText=document.getElementById('mcp-args').value;
  if(mcpRendered&&commandText===mcpRendered.commandText&&argsText===mcpRendered.argsText)
    return {command:mcpRendered.command,args:(mcpRendered.args||[]).slice()};
  return {command:commandText.trim(),args:mcpArgsValue()};}
function mcpCommandUnchanged(){
  return Boolean(mcpApprovedCommand)&&mcpSameTuple(mcpLiveTuple(),mcpApprovedCommand);}
// The single question the submit asks. Both branches require the live vector to
// equal something a person actually granted.
function mcpApprovalGranted(){
  const live=mcpLiveTuple();
  if(mcpSameTuple(live,mcpApprovedCommand))return true;
  const box=document.querySelector('#mcp-approve-box [name="approve_local_code"]');
  return Boolean(box&&box.checked&&mcpSameTuple(live,mcpTickedFor));}
// Show the standing approval, or ask for a new one — so the rule the server
// enforces is visible in the form instead of arriving later as a denial. A tick
// whose vector no longer matches the form is revoked here as you type, so the
// screen can never show consent that the submit would not honour.
function syncMcpApprovalState(){const approved=mcpCommandUnchanged();
  const box=document.getElementById('mcp-approve-box');
  const note=document.getElementById('mcp-approved-note');
  if(!box||!note)return;
  const input=box.querySelector('[name="approve_local_code"]');
  if(input&&input.checked&&!mcpSameTuple(mcpLiveTuple(),mcpTickedFor)){
    input.checked=false;mcpTickedFor=null;}
  if(approved&&input){input.checked=false;mcpTickedFor=null;}
  box.hidden=approved;note.hidden=!approved;
  // The other rule on this dialog (Generator access with nothing approved) is
  // shown as a disabled control plus the reason, instead of being discovered
  // through a ConfigDenial. This is the same rule /api/mcp enforces for a local
  // command, given the same treatment: Connect is unavailable until the exact
  // command on screen has been approved, and the sentence beside it says why.
  const stdio=document.getElementById('mcp-transport').value==='stdio';
  const needed=mcpStep==='connect'&&stdio&&!mcpApprovalGranted();
  const ask=document.getElementById('mcp-approve-required');
  if(ask)ask.hidden=!needed;
  const save=document.getElementById('save-mcp');
  if(save)save.disabled=needed;}
function mcpText(id,text){const node=document.getElementById(id);if(node)node.textContent=text;}
function setMcpStep(step){mcpStep=step==='tools'?'tools':'connect';
  document.querySelectorAll('[data-mcp-step]').forEach(pane=>pane.hidden=pane.dataset.mcpStep!==mcpStep);
  document.querySelectorAll('[data-mcp-marker]').forEach(item=>{const active=item.dataset.mcpMarker===mcpStep;
    item.classList.toggle('active',active);item.classList.toggle('complete',item.dataset.mcpMarker==='connect'&&mcpStep==='tools');
    if(active)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');});
  document.getElementById('mcp-back').hidden=mcpStep!=='tools';
  mcpText('save-mcp',mcpStep==='tools'?'Save':'Connect');
  mcpText('mcp-foot-note',mcpStep==='tools'
    ?'Only the tools you tick are approved. Tools the server adds later stay blocked until you review them.'
    :'Bearer tokens are write-only Keychain items. Local commands are stored without secrets.');
  syncMcpApprovalState();
  setTimeout(()=>{const pane=document.querySelector('[data-mcp-step="'+mcpStep+'"]');if(pane)pane.scrollTop=0;
    const body=document.querySelector('.mcp-wizard-body');if(body)body.scrollTop=0;},0);}
function renderMcpConnected(server){const host=document.getElementById('mcp-connected');if(!host)return;
  const info=(server&&server.server_info)||{};const named=esc(info.name||(server&&server.name)||'');
  const version=info.version?' '+esc(info.version):'';
  const draft=mcpCreatedId?'<small class="mcp-draft-note">Not saved yet — Cancel removes this connection.</small>':'';
  host.innerHTML=server?'<b>Connected</b><small>'+named+version+' · MCP '+esc(server.protocol_version||'')
    +' · '+((server.tools||[]).length)+' tools advertised</small>'+draft:'';}
// Delete the step-1 draft row. /api/mcp already owns removal; nothing new is
// invented here. If the delete fails the list is left as it is and the person is
// told, rather than the dialog closing over a row it silently could not undo.
function discardMcpDraft(){const id=mcpCreatedId;if(!id)return;mcpCreatedId='';
  api('/api/mcp',{action:'remove',server_id:id})
    .then(()=>api('/api/state'))
    .then(state=>{if(lastState){lastState.mcp=state.mcp;render(lastState);}})
    .catch(error=>{const reason=(error&&error.message)?error.message:String(error);
      computeSurfaceError(new Error(reason+' — the cancelled connection is still listed; remove it there.'));});}
// A row already in this project with the same name, or the same local command,
// is indistinguishable from the one being added. Say so before creating a
// second one; the row being edited never counts as its own duplicate.
function mcpDuplicate(name,vector,selfId){
  const rows=((lastState&&lastState.mcp&&lastState.mcp.servers)||[]).filter(row=>row.id!==selfId);
  const wanted=String(name||'').trim().toLowerCase();
  if(rows.some(row=>String(row.name||'').trim().toLowerCase()===wanted))
    return 'This project already has an MCP server with that name. Choose a different name, or configure the existing one.';
  if(document.getElementById('mcp-transport').value==='stdio'&&vector.command
     &&rows.some(row=>(row.transport||'stdio')==='stdio'&&mcpSameTuple({command:row.command||'',args:(row.args||[]).slice()},vector)))
    return 'This project already has an MCP server running that exact command. Configure the existing one instead.';
  return '';}
function renderMcpTools(){const host=document.getElementById('mcp-tool-approve');if(!host)return;
  if(!mcpTools.length){host.innerHTML='<p class="mcp-empty">This server advertised no tools, so there is nothing to approve.</p>';
    document.getElementById('mcp-select-all').hidden=true;syncMcpApproval();return;}
  document.getElementById('mcp-select-all').hidden=false;
  host.innerHTML=mcpTools.map(tool=>{const note=tool.annotations||{};
    // Three states, not two. A tool the server did not label gets its own
    // badge: an empty space would read as "nothing notable" when what it
    // actually means is "the server said nothing" (AGENTS.md §1.5).
    const badge=note.destructiveHint?'<i class="mcp-risk destructive">May change data</i>'
      :note.readOnlyHint?'<i class="mcp-risk readonly">Read-only</i>'
      :'<i class="mcp-risk unlabelled">Not labelled by the server</i>';
    return '<label class="mcp-approve-row"><input type="checkbox" data-mcp-tool="'+esc(tool.name)+'"'
      +(note.destructiveHint?' data-mcp-destructive':'')
      +(mcpApproved.has(tool.name)?' checked':'')+'><span><b>'+esc(tool.name)+'</b><small>'
      +esc(tool.description||'No description provided.')+'</small></span>'+badge+'</label>';}).join('');
  syncMcpApproval();}
function syncMcpApproval(){const boxes=[...document.querySelectorAll('[data-mcp-tool]')];
  mcpApproved=new Set(boxes.filter(box=>box.checked).map(box=>box.getAttribute('data-mcp-tool')));
  document.getElementById('mcp-allowed-tools').value=[...mcpApproved].join(', ');
  const none=mcpApproved.size===0,enable=document.getElementById('mcp-enabled');
  // The server refuses "enabled with nothing approved"; say so instead of
  // letting the person find out through a denial.
  enable.disabled=none;if(none)enable.checked=false;
  const consent=enable.closest('.hpc-confirm');
  if(consent)consent.classList.toggle('awaiting',none);
  mcpText('mcp-approve-count',mcpApproved.size+' of '+boxes.length+' approved');
  mcpText('mcp-enable-note',none?'Approve at least one tool before the Generator can call this server.'
    :mcpReconnected?'Re-connecting cleared this server\'s approvals. Nothing can be called until you save.'
    :'Leave this off to keep the server manual-only. You can turn it on later.');
  // The bulk action covers the ordinary case and stops short of the two rows
  // where being wrong costs most: anything the server labelled destructive
  // needs its own deliberate tick. The label says exactly that, so the
  // behaviour is evident before it is used, and the count above stays a plain
  // count of every advertised tool.
  const safe=boxes.filter(box=>!box.hasAttribute('data-mcp-destructive'));
  const link=document.getElementById('mcp-select-all');
  if(link)link.hidden=!safe.length;
  mcpText('mcp-select-all',safe.length&&safe.every(box=>box.checked)?'Clear all':'Select all except destructive');}
function clearMcpError(){const box=document.getElementById('mcp-error');box.textContent='';box.className='wizard-error';}
function openMcp(serverId=''){mcpForm.reset();clearMcpError();
  mcpCreatedId='';document.getElementById('mcp-name').removeAttribute('aria-invalid');
  const server=((lastState&&lastState.mcp&&lastState.mcp.servers)||[]).find(row=>row.id===serverId);
  document.getElementById('mcp-title').textContent=server?'Configure MCP server':'Add MCP server';
  document.getElementById('mcp-server-id').value=server?server.id:'';
  mcpTools=server?(server.tools||[]):[];mcpApproved=new Set(server?(server.allowed_tools||[]):[]);mcpReconnected=false;
  // A stored stdio row is proof its owner approved that exact command already.
  mcpApprovedCommand=(server&&(server.transport||'stdio')==='stdio')
    ?{command:server.command||'',args:(server.args||[]).slice()}:null;
  mcpTickedFor=null;
  mcpRendered=server?{commandText:server.command||'',argsText:(server.args||[]).join('\n'),
                      command:server.command||'',args:(server.args||[]).slice()}:null;
  if(server){document.getElementById('mcp-name').value=server.name||'';document.getElementById('mcp-transport').value=server.transport||'stdio';
    document.getElementById('mcp-command').value=server.command||'';document.getElementById('mcp-args').value=(server.args||[]).join('\n');
    document.getElementById('mcp-url').value=server.url||'';mcpForm.elements.timeout.value=server.timeout||30;
    mcpForm.elements.max_calls_per_task.value=server.max_calls_per_task||5;
    mcpForm.elements.enabled.checked=Boolean(server.enabled);mcpForm.elements.allow_private_network.checked=Boolean(server.allow_private_network);}
  syncMcpTransport();syncMcpApprovalState();renderMcpConnected(server);renderMcpTools();
  // An already-connected server opens on its tool list; a new one starts at step 1.
  setMcpStep(server?'tools':'connect');
  mcpModal.className='project-modal on';
  setTimeout(()=>document.getElementById(server?'mcp-select-all':'mcp-name').focus(),0);}
function closeMcp(){discardMcpDraft();mcpModal.className='project-modal';mcpForm.reset();
  document.getElementById('mcp-name').removeAttribute('aria-invalid');
  mcpTools=[];mcpApproved=new Set();mcpReconnected=false;mcpApprovedCommand=null;
  mcpTickedFor=null;mcpRendered=null;
  setMcpStep('connect');syncMcpApprovalState();}
document.getElementById('mcp-transport').onchange=syncMcpTransport;
for(const id of ['mcp-command','mcp-args'])
  document.getElementById(id).addEventListener('input',syncMcpApprovalState);
// The tick is only ever recorded together with the vector it was given for.
document.querySelector('#mcp-approve-box [name="approve_local_code"]')
  .addEventListener('change',event=>{
    mcpTickedFor=event.target.checked?mcpLiveTuple():null;syncMcpApprovalState();});
// Cancel, Escape, x and the backdrop all run closeMcp, which deletes the draft.
// Closing the TAB runs none of them, so the same intent — leaving without
// saving — left the row behind. This is best effort by construction: the page
// is going away and the browser may cut the request, so it uses keepalive and
// makes no promise it always lands. It only ever fires when a draft exists.
window.addEventListener('pagehide',()=>{
  if(!mcpCreatedId)return;
  const id=mcpCreatedId;mcpCreatedId='';
  try{fetch('/api/mcp?t='+encodeURIComponent(T),{method:'POST',keepalive:true,
    headers:{'content-type':'application/json'},
    body:JSON.stringify({action:'remove',server_id:id})});}catch(e){}});
document.getElementById('close-mcp').onclick=closeMcp;document.getElementById('cancel-mcp').onclick=closeMcp;
document.getElementById('mcp-back').onclick=()=>setMcpStep('connect');
document.getElementById('mcp-tool-approve').addEventListener('change',ev=>{
  if(ev.target.matches('[data-mcp-tool]'))syncMcpApproval();});
document.getElementById('mcp-select-all').onclick=()=>{const boxes=[...document.querySelectorAll('[data-mcp-tool]')];
  const safe=boxes.filter(box=>!box.hasAttribute('data-mcp-destructive'));
  // Clearing is always safe, so the toggle still clears everything; filling
  // only ever fills the rows the server did not label destructive.
  if(safe.length&&safe.every(box=>box.checked))boxes.forEach(box=>{box.checked=false;});
  else safe.forEach(box=>{box.checked=true;});
  syncMcpApproval();};
mcpModal.addEventListener('click',ev=>{if(ev.target===mcpModal)closeMcp();});
mcpForm.onsubmit=async ev=>{ev.preventDefault();const button=document.getElementById('save-mcp');
  const connecting=mcpStep==='connect';
  clearMcpError();const fd=new FormData(mcpForm);
  const payload=Object.fromEntries(fd.entries());payload.action='register';
  const vector=mcpLiveTuple();
  const priorId=String(payload.server_id||'');
  const nameField=document.getElementById('mcp-name');
  if(connecting){
    // The two refusals a person can hit before anything is even attempted are
    // answered here, in the field, instead of as a denial after a round trip.
    nameField.removeAttribute('aria-invalid');
    const name=String(payload.name||'').trim();
    if(!MCP_NAME_RE.test(name)){
      nameField.setAttribute('aria-invalid','true');
      showInlineError('mcp-error',new Error('Server names use ASCII letters, digits, spaces and . _ - only, and must start with a letter or digit. Rename this server to continue.'));
      nameField.focus();return;}
    const clash=mcpDuplicate(name,vector,priorId);
    if(clash){nameField.setAttribute('aria-invalid','true');
      showInlineError('mcp-error',new Error(clash));nameField.focus();return;}}
  button.disabled=true;
  mcpText('save-mcp',connecting?'Connecting…':'Saving…');
  // An untouched legacy row keeps its stored arguments verbatim — the textarea
  // trims and drops blank lines, so re-deriving them would silently rewrite a
  // working configuration (and make it unsaveable).
  payload.args=vector.args;
  payload.timeout=Number(payload.timeout);payload.max_calls_per_task=Number(payload.max_calls_per_task);
  payload.allow_private_network=fd.has('allow_private_network');
  // Deny-by-default is the server's rule and stays the server's rule. What is
  // sent is either the box the person just ticked, or the approval they already
  // gave for this identical command and arguments — never an approval invented
  // because a row happens to exist. Change the command and this goes false, the
  // checkbox comes back, and the server refuses until it is ticked.
  payload.approve_local_code=payload.transport==='stdio'&&mcpApprovalGranted();
  // Step 1 is a pure connect: approve nothing, enable nothing. Step 2 sends the
  // exact set of ticked tools — never a blanket "all", so what is stored is
  // always the list the person actually saw.
  payload.allowed_tools=connecting?[]:[...mcpApproved];
  payload.enabled=connecting?false:fd.has('enabled');
  delete payload.args_text;delete payload.allowed_tools_text;
  try{const server=await api('/api/mcp',payload);
    if(lastState){lastState.mcp=await api('/api/state').then(state=>state.mcp);render(lastState);}
    if(connecting){document.getElementById('mcp-server-id').value=server.id||'';
      // Only a row this dialog just created is a draft. Re-connecting an existing
      // server, or an edit reached through Configure, is not one and is kept.
      if(!priorId&&server.id)mcpCreatedId=server.id;
      // Adopt what was actually stored (the resolved executable), and show it, so
      // the field, the standing approval and the server row all agree.
      if((server.transport||'stdio')==='stdio'){
        document.getElementById('mcp-command').value=server.command||'';
        document.getElementById('mcp-args').value=(server.args||[]).join('\n');
        mcpApprovedCommand={command:server.command||'',args:(server.args||[]).slice()};
        mcpRendered={commandText:server.command||'',argsText:(server.args||[]).join('\n'),
                     command:server.command||'',args:(server.args||[]).slice()};
      }else{mcpApprovedCommand=null;mcpRendered=null;}
      mcpTickedFor=null;
      syncMcpApprovalState();
      mcpTools=server.tools||[];const advertised=new Set(mcpTools.map(tool=>tool.name));
      // Keep prior approvals only where the server still advertises them.
      const kept=[...mcpApproved].filter(name=>advertised.has(name));
      mcpReconnected=mcpApproved.size>0&&kept.length<mcpApproved.size;
      mcpApproved=new Set(kept);
      renderMcpConnected(server);renderMcpTools();setMcpStep('tools');
      setTimeout(()=>document.getElementById('mcp-select-all').focus(),0);}
    else{mcpCreatedId='';closeMcp();}}
  catch(e){computeError('mcp-error',e);document.getElementById('mcp-error').focus();}
  finally{button.disabled=false;mcpText('save-mcp',mcpStep==='tools'?'Save':'Connect');syncMcpApprovalState();}};
function stopComputeTimers(except=''){for(const [id,timer] of computeLogTimers){if(id!==except){clearInterval(timer);computeLogTimers.delete(id);}}}
async function loadComputePanel(jobId,mode){const current=computePanels.get(jobId)||{};computePanels.set(jobId,{...current,open:true,mode,loading:true,error:''});
  if(lastState)render(lastState);try{const result=await api('/api/hpc',{action:mode==='outputs'?'outputs':'logs',job_id:jobId});
    const row=computePanels.get(jobId)||{};computePanels.set(jobId,{...row,open:true,mode,loading:false,
      ...(mode==='outputs'?{outputs:result.outputs||[]}:{logs:result})});}
  catch(e){const row=computePanels.get(jobId)||{};computePanels.set(jobId,{...row,open:true,mode,loading:false,error:e.message});}
  if(lastState)render(lastState);}
function followComputeLogs(jobId){stopComputeTimers(jobId);if(!computeLogTimers.has(jobId))computeLogTimers.set(jobId,setInterval(()=>{
  if(activeView==='compute'&&(computePanels.get(jobId)||{}).open)loadComputePanel(jobId,'logs');},2000));}
document.getElementById('inspector').addEventListener('click',ev=>{
  const tab=ev.target.closest('[data-view]');
  if(tab)openPanelTab(tab.getAttribute('data-view'));
});
document.getElementById('panel-open-runtime').onclick=openRuntime;
document.getElementById('model-summary').onclick=()=>openPanelTab('models');
document.getElementById('rail-search').addEventListener('input',()=>{if(lastState)renderTasks(lastState);});
function handleActionClick(ev){
  const groupToggle=ev.target.closest('[data-group-toggle]');
  if(groupToggle){const key=groupToggle.getAttribute('data-group-toggle');
    const card=groupToggle.closest('.deliverable-group');
    const open=!expandedGroups.has(key);
    if(open)expandedGroups.add(key);else expandedGroups.delete(key);
    if(card){card.classList.toggle('open',open);groupToggle.setAttribute('aria-expanded',String(open));}
    return;}
  const reviewToggle=ev.target.closest('[data-review-toggle]');
  if(reviewToggle){const key=reviewToggle.getAttribute('data-review-toggle');
    const card=reviewToggle.closest('.review-card');
    const open=!expandedReviews.has(key);
    if(open)expandedReviews.add(key);else expandedReviews.delete(key);
    if(card){card.classList.toggle('open',open);reviewToggle.setAttribute('aria-expanded',String(open));}
    return;}
  if(ev.target.closest('[data-open-artifacts]'))openPanelTab('artifacts');
  if(ev.target.closest('[data-open-audits]'))openPanelTab('audits');
  const openDecisions=ev.target.closest('[data-open-decisions]');
  if(openDecisions){
    const id=openDecisions.getAttribute('data-open-decisions')||'',sha=openDecisions.getAttribute('data-open-decisions-sha')||'';
    const row=lastState&&decisionRowFor(lastState,id,sha);
    if(row)openResolution(row);
    else if(id){expandedReviews.add(id);render(lastState);openPanelTab('audits');}
    else openInspector();
  }
  if(ev.target.closest('[data-hpc-add]'))openComputeHost();
  if(ev.target.closest('[data-mcp-add]'))openMcp();
  if(ev.target.closest('[data-manage-skills]'))openSkillsEditor();
  const configureMcp=ev.target.closest('[data-mcp-configure]');if(configureMcp)openMcp(configureMcp.getAttribute('data-mcp-configure'));
  const probeMcp=ev.target.closest('[data-mcp-probe]');if(probeMcp){probeMcp.disabled=true;probeMcp.textContent='Refreshing…';
    api('/api/mcp',{action:'probe',server_id:probeMcp.getAttribute('data-mcp-probe')}).catch(computeSurfaceError)
      .finally(()=>{probeMcp.disabled=false;probeMcp.textContent='Refresh tools';});}
  const removeMcp=ev.target.closest('[data-mcp-remove]');if(removeMcp&&confirm(currentLocale==='zh'?'从此项目移除这个 MCP 服务器？':'Remove this MCP server from this project?')){
    removeMcp.disabled=true;api('/api/mcp',{action:'remove',server_id:removeMcp.getAttribute('data-mcp-remove')})
      .catch(computeSurfaceError).finally(()=>{removeMcp.disabled=false;});}
  const run=ev.target.closest('[data-hpc-run]');if(run)openComputeJob(run.getAttribute('data-hpc-run'));
  const probe=ev.target.closest('[data-hpc-probe]');if(probe){probe.disabled=true;probe.textContent='Probing…';
    api('/api/hpc',{action:'probe',host_id:probe.getAttribute('data-hpc-probe')}).catch(computeSurfaceError)
      .finally(()=>{probe.disabled=false;probe.textContent='Probe';});}
  const remove=ev.target.closest('[data-hpc-remove]');if(remove&&confirm(currentLocale==='zh'?'从此项目移除这个计算主机？':'Remove this compute host from this project?')){
    remove.disabled=true;api('/api/hpc',{action:'remove',host_id:remove.getAttribute('data-hpc-remove')})
      .catch(computeSurfaceError).finally(()=>{remove.disabled=false;});}
  const refresh=ev.target.closest('[data-hpc-refresh]');if(refresh){refresh.disabled=true;refresh.textContent='Refreshing…';
    api('/api/hpc',{action:'refresh'}).catch(computeSurfaceError).finally(()=>{refresh.disabled=false;refresh.textContent='Refresh now';});}
  const logs=ev.target.closest('[data-hpc-logs]');if(logs){const id=logs.getAttribute('data-hpc-logs');loadComputePanel(id,'logs');followComputeLogs(id);}
  const outputs=ev.target.closest('[data-hpc-outputs]');if(outputs){const id=outputs.getAttribute('data-hpc-outputs');stopComputeTimers();loadComputePanel(id,'outputs');}
  const cancel=ev.target.closest('[data-hpc-cancel]');if(cancel&&confirm(currentLocale==='zh'?'取消这个远程任务？此操作无法撤销。':'Cancel this remote job? This cannot be undone.')){
    cancel.disabled=true;cancel.textContent='Cancelling…';api('/api/hpc',{action:'cancel',job_id:cancel.getAttribute('data-hpc-cancel')})
      .catch(computeSurfaceError).finally(()=>{cancel.disabled=false;cancel.textContent='Cancel job';});}
  const admit=ev.target.closest('[data-admit]');if(admit){const admitCycle=admit.getAttribute('data-admit-cycle');admit.disabled=true;admit.textContent='Verifying…';
    api('/api/admit',{cycle_id:admitCycle}).then(r=>{
      lastAdmission={ok:true,chat:activeChatId||'',cycleId:admitCycle,receipt:r.receipt||'',tier:r.tier||'',tierMeaning:r.tier_meaning||'',signed:!!r.signed,signatureKeyid:r.signature_keyid||'',reproducible:!!r.reproducible,reproLocks:r.repro_locks||0,reproKinds:r.repro_kinds||[]};
      if(lastState)render(lastState);})
    .catch(e=>{
      // §41.9: the refusal explains itself in place — and the button recovers.
      lastAdmission={ok:false,chat:activeChatId||'',cycleId:admitCycle,reason:e.message,
        remediations:e.remediations||[],why:e.why||null,tier:e.tier||'',tierMeaning:e.tier_meaning||'',receipt:e.receipt||''};
      admit.disabled=false;admit.textContent='Admit result';
      route.className='route on';route.innerHTML='<b>Not admitted.</b> '+esc(e.message);
      if(lastState)render(lastState);});}
}
document.getElementById('conversation').onclick=handleActionClick;
document.getElementById('panel-dynamic').onclick=handleActionClick;
const deleteChatModal=document.getElementById('delete-chat-modal');
const deleteChatForm=document.getElementById('delete-chat-form');
function closeDeleteChat(){deleteChatModal.className='project-modal';deleteChatForm.reset();
  document.getElementById('delete-chat-error').className='wizard-error';}
function findChat(id){if(!lastState||!lastState.chats)return null;
  return (lastState.chats.items||[]).find(row=>row.id===id)
    ||(lastState.chats.archived||[]).find(row=>row.id===id)||null;}
function openDeleteChat(id){const chat=findChat(id);if(!chat)return;
  document.getElementById('delete-chat-id').value=id;document.getElementById('delete-chat-name').textContent=chat.title;
  document.getElementById('delete-chat-impact').textContent=chat.cycles
    ?(currentLocale==='zh'?'此对话有 '+chat.cycles+' 个审计循环；导航会删除，但审计证据会保留。':'This chat has '+chat.cycles+' audit cycle'+(chat.cycles===1?'':'s')+'; navigation is removed while audit evidence remains.')
    :(currentLocale==='zh'?'这是一个空对话，将直接从侧栏移除。':'This is an empty chat and will be removed from the sidebar.');
  document.getElementById('delete-chat-error').className='wizard-error';deleteChatModal.className='project-modal on';}
document.getElementById('close-delete-chat').onclick=closeDeleteChat;
document.getElementById('cancel-delete-chat').onclick=closeDeleteChat;
deleteChatModal.addEventListener('click',ev=>{if(ev.target===deleteChatModal)closeDeleteChat();});
deleteChatForm.onsubmit=async ev=>{ev.preventDefault();const id=document.getElementById('delete-chat-id').value;
  const button=document.getElementById('confirm-delete-chat');button.disabled=true;button.textContent=currentLocale==='zh'?'正在删除…':'Deleting…';
  try{await api('/api/chats/delete',{chat_id:id});closeDeleteChat();
    if(lastState){lastState.chats.items=lastState.chats.items.filter(row=>row.id!==id);
      lastState.chats.archived=(lastState.chats.archived||[]).filter(row=>row.id!==id);
      if(activeChatId===id){activeChatId=lastState.chats.items[0]&&lastState.chats.items[0].id||'';newTaskMode=!activeChatId;}
      render(lastState);}}
  catch(e){showInlineError('delete-chat-error',e);}finally{button.disabled=false;button.textContent=currentLocale==='zh'?'删除对话':'Delete chat';}};
const renameChatModal=document.getElementById('rename-chat-modal');
const renameChatForm=document.getElementById('rename-chat-form');
function closeRenameChat(){renameChatModal.className='project-modal';renameChatForm.reset();
  document.getElementById('rename-chat-error').className='wizard-error';}
function openRenameChat(id){const chat=findChat(id);if(!chat)return;
  document.getElementById('rename-chat-id').value=id;
  const input=document.getElementById('rename-chat-input');input.value=chat.title||'';
  document.getElementById('rename-chat-error').className='wizard-error';renameChatModal.className='project-modal on';
  setTimeout(()=>{input.focus();input.select();},0);}
document.getElementById('close-rename-chat').onclick=closeRenameChat;
document.getElementById('cancel-rename-chat').onclick=closeRenameChat;
renameChatModal.addEventListener('click',ev=>{if(ev.target===renameChatModal)closeRenameChat();});
renameChatForm.onsubmit=async ev=>{ev.preventDefault();const id=document.getElementById('rename-chat-id').value;
  const title=String(document.getElementById('rename-chat-input').value||'').trim();
  if(!title){showInlineError('rename-chat-error',currentLocale==='zh'?'请输入对话标题。':'Enter a chat title.');return;}
  const button=document.getElementById('confirm-rename-chat');button.disabled=true;button.textContent=currentLocale==='zh'?'正在保存…':'Saving…';
  try{const r=await api('/api/chats/rename',{chat_id:id,title});
    if(lastState){const target=findChat(id);if(target)Object.assign(target,r.chat);render(lastState);}
    closeRenameChat();}
  catch(e){showInlineError('rename-chat-error',e);}finally{button.disabled=false;button.textContent=currentLocale==='zh'?'保存名称':'Save name';}};
function chatActionError(message,error){route.className='route on';
  route.innerHTML='<b>'+esc(message)+'</b> '+esc(error&&error.message?error.message:String(error||''));}
async function archiveChat(id){const chat=lastState&&lastState.chats.items.find(c=>c.id===id);if(!chat)return;
  try{const r=await api('/api/chats/archive',{chat_id:id});
    lastState.chats.items=lastState.chats.items.filter(c=>c.id!==id);
    lastState.chats.archived=[Object.assign(chat,r.chat),...(lastState.chats.archived||[])];
    if(activeChatId===id){activeChatId=lastState.chats.items[0]&&lastState.chats.items[0].id||'';newTaskMode=!activeChatId;}
    render(lastState);}
  catch(e){chatActionError(currentLocale==='zh'?'无法归档对话。':'Could not archive chat.',e);}}
async function unarchiveChat(id){const chat=lastState&&(lastState.chats.archived||[]).find(c=>c.id===id);if(!chat)return;
  try{const r=await api('/api/chats/unarchive',{chat_id:id});
    lastState.chats.archived=(lastState.chats.archived||[]).filter(c=>c.id!==id);
    lastState.chats.items=[Object.assign(chat,r.chat),...lastState.chats.items];
    render(lastState);}
  catch(e){chatActionError(currentLocale==='zh'?'无法取消归档对话。':'Could not unarchive chat.',e);}}
async function duplicateChat(id){try{const r=await api('/api/chats/duplicate',{chat_id:id});
    if(lastState){lastState.chats.items=[Object.assign({cycles:0,status:'ready'},r.chat),...lastState.chats.items];
      activeChatId=r.chat.id;newTaskMode=false;render(lastState);document.getElementById('thread').scrollTop=0;closeRail();}}
  catch(e){chatActionError(currentLocale==='zh'?'无法复制对话。':'Could not duplicate chat.',e);}}
async function togglePinChat(id){const chat=findChat(id);if(!chat)return;
  try{await api('/api/chats/pin',{chat_id:id,pinned:!chat.pinned});chat.pinned=!chat.pinned;render(lastState);}
  catch(e){chatActionError(currentLocale==='zh'?'无法更新置顶状态。':'Could not update pin.',e);}}
// One compact per-row overflow menu keeps the row clean: the secondary
// actions (rename/duplicate/pin/archive/delete) live behind a single ⋯ button
// instead of crowding the title. A shared, repositioned popover avoids the
// duplicate-id trap a per-row menu would create.
const chatMenu=document.getElementById('chat-menu');
let chatMenuTrigger=null;
function positionChatMenu(trigger){chatMenu.hidden=false;
  const rect=trigger.getBoundingClientRect(),mw=chatMenu.offsetWidth,mh=chatMenu.offsetHeight,gap=4;
  let left=rect.right-mw;if(left<8)left=8;
  let top=rect.bottom+gap;if(top+mh>window.innerHeight-8)top=Math.max(8,rect.top-mh-gap);
  chatMenu.style.left=left+'px';chatMenu.style.top=top+'px';}
function closeChatMenu(focusTrigger){if(chatMenu.hidden)return;chatMenu.hidden=true;
  const trigger=chatMenuTrigger;chatMenuTrigger=null;
  if(trigger){trigger.setAttribute('aria-expanded','false');if(focusTrigger&&trigger.isConnected)trigger.focus();}}
function openChatMenu(id,trigger){const chat=findChat(id);if(!chat)return;
  chatMenu.setAttribute('data-chat',id);
  document.getElementById('chat-menu-pin').textContent=chat.pinned?'Unpin chat':'Pin chat';
  chatMenuTrigger=trigger;trigger.setAttribute('aria-expanded','true');
  positionChatMenu(trigger);
  const first=chatMenu.querySelector('button');if(first)setTimeout(()=>first.focus(),0);}
chatMenu.addEventListener('click',async ev=>{const item=ev.target.closest('[data-chat-menu]');if(!item)return;
  ev.preventDefault();ev.stopPropagation();const id=chatMenu.getAttribute('data-chat'),action=item.getAttribute('data-chat-menu');
  closeChatMenu(false);if(!id)return;
  if(action==='rename')openRenameChat(id);
  else if(action==='duplicate')await duplicateChat(id);
  else if(action==='pin')await togglePinChat(id);
  else if(action==='archive')await archiveChat(id);
  else if(action==='delete')openDeleteChat(id);});
chatMenu.addEventListener('keydown',ev=>{
  if(ev.key==='Escape'){ev.preventDefault();ev.stopPropagation();closeChatMenu(true);return;}
  const items=[...chatMenu.querySelectorAll('button')];if(!items.length)return;const i=items.indexOf(document.activeElement);
  if(ev.key==='ArrowDown'){ev.preventDefault();items[(i+1+items.length)%items.length].focus();}
  else if(ev.key==='ArrowUp'){ev.preventDefault();items[(i-1+items.length)%items.length].focus();}
  else if(ev.key==='Home'){ev.preventDefault();items[0].focus();}
  else if(ev.key==='End'){ev.preventDefault();items[items.length-1].focus();}
  else if(ev.key==='Tab'){ev.preventDefault();closeChatMenu(true);}});
document.addEventListener('click',ev=>{if(chatMenu.hidden)return;
  if(chatMenu.contains(ev.target)||(chatMenuTrigger&&chatMenuTrigger.contains(ev.target)))return;closeChatMenu(false);});
window.addEventListener('resize',()=>closeChatMenu(false));
document.getElementById('task-list').addEventListener('scroll',()=>closeChatMenu(false),{passive:true});
document.getElementById('task-list').onclick=async ev=>{
  const toggle=ev.target.closest('[data-archived-toggle]');
  if(toggle){ev.preventDefault();ev.stopPropagation();archivedExpanded=!archivedExpanded;if(lastState)renderTasks(lastState);return;}
  const menuBtn=ev.target.closest('[data-chat-menu-open]');
  if(menuBtn){ev.preventDefault();ev.stopPropagation();const id=menuBtn.getAttribute('data-chat-menu-open');
    if(!chatMenu.hidden&&chatMenuTrigger===menuBtn)closeChatMenu(true);else{closeChatMenu(false);openChatMenu(id,menuBtn);}return;}
  const unarchive=ev.target.closest('[data-unarchive-chat]'),pin=ev.target.closest('[data-pin-chat]'),
    remove=ev.target.closest('[data-delete-chat]'),row=ev.target.closest('[data-chat-id]');
  if(unarchive){ev.preventDefault();ev.stopPropagation();unarchive.disabled=true;
    try{await unarchiveChat(unarchive.getAttribute('data-unarchive-chat'));}finally{unarchive.disabled=false;}return;}
  if(remove){ev.preventDefault();ev.stopPropagation();openDeleteChat(remove.getAttribute('data-delete-chat'));return;}
  if(pin){ev.preventDefault();ev.stopPropagation();await togglePinChat(pin.getAttribute('data-pin-chat'));return;}
  if(row){activeChatId=row.getAttribute('data-chat-id');newTaskMode=false;
    if(pendingContinuation.chat&&pendingContinuation.chat!==activeChatId)pendingContinuation={cycle:'',chat:''};
    if(resolutionModal.classList.contains('on'))closeResolution();
    render(lastState);document.getElementById('thread').scrollTop=0;closeRail();}
};
document.getElementById('task-list').onkeydown=ev=>{if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('[data-chat-id]')){
  ev.preventDefault();ev.target.click();}};
document.getElementById('current-project-pin').onclick=async()=>{if(!lastState)return;const button=document.getElementById('current-project-pin');
  const pinned=Boolean(lastState.chats&&lastState.chats.project_pinned);button.disabled=true;
  try{await api('/api/projects/pin',{root:lastState.root,pinned:!pinned});lastState.chats.project_pinned=!pinned;render(lastState);}
  catch(e){route.className='route on';route.innerHTML='<b>Could not pin project.</b> '+esc(e.message);}
  finally{button.disabled=false;}};
document.getElementById('new-task').onclick=async()=>{
  newTaskMode=true;say.value='';route.className='route';pendingFiles=[];
  pendingContinuation={cycle:'',chat:''};
  uploadProgress=new Map();
  syncAudience();
  fileInput.value='';drawFiles();
  if(resolutionModal.classList.contains('on'))closeResolution();
  try{const result=await api('/api/chats/new',{title:'New chat'});activeChatId=result.chat.id;
    if(lastState){lastState.chats.items.unshift({...result.chat,cycles:0,status:'ready'});render(lastState);}}
  catch(e){route.className='route on';route.innerHTML='<b>Could not create chat.</b> '+esc(e.message);}
  document.getElementById('thread').scrollTop=0;closeRail();say.focus();
};
document.getElementById('sidebar-toggle').onclick=toggleSidebar;
document.getElementById('inspect-toggle').onclick=toggleInspector;
document.getElementById('inspect-close').onclick=closePanels;
document.getElementById('escalations').onclick=ev=>{const button=ev.target.closest('[data-resolve]');if(!button)return;
  const cycle=button.getAttribute('data-cycle');const row=lastState&&(lastState.escalations||[]).find(item=>item.cycle_id===cycle);
  openResolution(row||cycle,button.getAttribute('data-resolve'),button.getAttribute('data-sha'));};
scrim.onclick=closePanels;
const modalReturnFocus=new WeakMap();
const modalObserver=new MutationObserver(records=>records.forEach(record=>{
  const modal=record.target;const wasOpen=(record.oldValue||'').split(/\s+/).includes('on');
  const isOpen=modal.classList.contains('on');
  if(isOpen&&!wasOpen)modalReturnFocus.set(modal,document.activeElement);
  if(wasOpen&&!isOpen){const trigger=modalReturnFocus.get(modal);modalReturnFocus.delete(modal);
    if(trigger&&trigger.isConnected)setTimeout(()=>trigger.focus(),0);}
}));
document.querySelectorAll('.project-modal').forEach(modal=>modalObserver.observe(modal,{attributes:true,attributeOldValue:true,attributeFilter:['class']}));
function activeModal(){const rows=[...document.querySelectorAll('.project-modal.on')];return rows.at(-1)||null;}
function closeActiveModal(modal){
  if(modal===filePreviewModal)closeFilePreview();
  else if(modal===projectModal)closeProjectModal();else if(modal===recoveryModal)closeRecovery();
  else if(modal===deleteProjectModal)closeDeleteProject();else if(modal===deleteChatModal)closeDeleteChat();
  else if(modal===renameChatModal)closeRenameChat();
  else if(modal===runtimeModal)closeRuntime();else if(modal===paletteModal)closePalette();
  else if(modal===settingsModal)closeSettings();else if(modal===computeHostModal)closeComputeHost();
  else if(modal===computeJobModal)closeComputeJob();else if(modal===mcpModal)closeMcp();
}
document.addEventListener('keydown',ev=>{const modal=activeModal();
  if(ev.key==='Tab'&&modal){const controls=[...modal.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')]
      .filter(element=>element.getClientRects().length);if(!controls.length){ev.preventDefault();return;}
    const first=controls[0],last=controls.at(-1);if(ev.shiftKey&&(document.activeElement===first||!modal.contains(document.activeElement))){ev.preventDefault();last.focus();}
    else if(!ev.shiftKey&&(document.activeElement===last||!modal.contains(document.activeElement))){ev.preventDefault();first.focus();}return;}
  if(ev.key==='Escape'){if(modal){ev.preventDefault();closeActiveModal(modal);}
    else if(filePreviewModal.classList.contains('on'))closeFilePreview();
    else if(resolutionModal.classList.contains('on'))closeResolution();
    else closePanels();}
});
document.addEventListener('keydown',ev=>{
  const meta=ev.metaKey||ev.ctrlKey;
  if(meta&&!ev.shiftKey&&!ev.altKey&&String(ev.key).toLowerCase()==='k'){
    ev.preventDefault();
    if(paletteModal.classList.contains('on'))closePalette();else openPalette();
    return;
  }
  if(meta&&ev.key==='.'){if(!stopRun.hidden&&!stopRun.disabled){ev.preventDefault();stopRun.click();}return;}
  if(activeModal()||resolutionModal.classList.contains('on'))return;
  const tag=String((document.activeElement||{}).tagName||'').toLowerCase();
  if(['input','textarea','select'].includes(tag))return;
  if(ev.key==='['){ev.preventDefault();toggleSidebar();}
  else if(ev.key===']'){ev.preventDefault();toggleInspector();}
});
const paletteModal=document.getElementById('palette');
const paletteInput=document.getElementById('palette-input');
const paletteList=document.getElementById('palette-list');
let paletteIndex=0;let paletteItems=[];
function paletteCommands(){
  const inHub=document.body.classList.contains('hub-mode');
  const items=[];
  if(!inHub){
    items.push({title:'New chat',hint:'⌘N',run:()=>document.getElementById('new-task').click()});
    items.push({title:'Files',context:'Context panel',run:()=>openPanelTab('artifacts')});
    items.push({title:'Audit history',context:'Context panel',run:()=>openPanelTab('audits')});
    items.push({title:'Models',context:'Context panel',run:()=>openPanelTab('models')});
    items.push({title:'Usage',context:'Context panel',run:()=>openPanelTab('usage')});
    items.push({title:'Remote compute',context:'Context panel',run:()=>openPanelTab('compute')});
    items.push({title:'Tools & Skills',context:'Context panel',run:()=>openPanelTab('tools')});
    items.push({title:'Project controls',run:openRuntime});
    const running=lastState&&chatProgress(lastState)&&!chatProgress(lastState).finished;
    if(running)items.push({title:'Stop current task',hint:'⌘.',run:()=>stopRun.click()});
  }
  items.push({title:'All projects',run:showProjects});
  items.push({title:'Open settings',run:()=>openSettings('general')});
  items.push({title:'Run Doctor',run:async()=>{await openSettings('diagnostics');
    document.getElementById('run-doctor').click();}});
  items.push({title:'Switch theme',run:()=>themeButton.onclick()});
  items.push({title:'Switch language',run:()=>document.getElementById('locale-toggle').onclick()});
  return items;
}
function paletteRow(item,index){
  return '<button type="button" class="palette-row'+(index===paletteIndex?' selected':'')
    +'" data-palette-index="'+index+'"><span>'+esc(item.title)+'</span>'
    +(item.context?'<span class="palette-context">'+esc(item.context)+'</span>':'')
    +(item.hint?'<kbd>'+esc(item.hint)+'</kbd>':'')+'</button>';
}
function renderPalette(){
  const q=String(paletteInput.value||'').trim().toLowerCase();
  const actions=paletteCommands().filter(item=>!q
    ||item.title.toLowerCase().includes(q)||zhValue(item.title).toLowerCase().includes(q));
  const chats=(document.body.classList.contains('hub-mode')||!lastState||!lastState.chats
    ?[]:lastState.chats.items||[])
    .filter(c=>!q||String(c.title).toLowerCase().includes(q)).slice(0,6)
    .map(c=>({title:c.title,context:'Chat',run:()=>{activeChatId=c.id;newTaskMode=false;
      if(resolutionModal.classList.contains('on'))closeResolution();render(lastState);}}));
  paletteItems=[...actions,...chats];
  if(paletteIndex>=paletteItems.length)paletteIndex=0;
  let html='';
  if(actions.length)html+='<div class="palette-section">Actions</div>'
    +actions.map((item,index)=>paletteRow(item,index)).join('');
  if(chats.length)html+='<div class="palette-section">Chats</div>'
    +chats.map((item,index)=>paletteRow(item,actions.length+index)).join('');
  paletteList.innerHTML=html||'<div class="palette-empty">No matching results.</div>';
}
function openPalette(){paletteIndex=0;paletteInput.value='';renderPalette();
  paletteModal.classList.add('on');setTimeout(()=>paletteInput.focus(),0);}
function closePalette(){paletteModal.classList.remove('on');}
function runPaletteItem(index){const item=paletteItems[index];if(!item)return;closePalette();item.run();}
paletteInput.addEventListener('input',()=>{paletteIndex=0;renderPalette();});
paletteInput.addEventListener('keydown',ev=>{
  if(ev.key==='ArrowDown'){ev.preventDefault();
    paletteIndex=Math.min(Math.max(0,paletteItems.length-1),paletteIndex+1);renderPalette();}
  else if(ev.key==='ArrowUp'){ev.preventDefault();paletteIndex=Math.max(0,paletteIndex-1);renderPalette();}
  else if(ev.key==='Enter'){ev.preventDefault();runPaletteItem(paletteIndex);}
});
paletteList.onclick=ev=>{const row=ev.target.closest('[data-palette-index]');
  if(row)runPaletteItem(Number(row.getAttribute('data-palette-index')));};
paletteModal.addEventListener('click',ev=>{if(ev.target===paletteModal)closePalette();});
document.getElementById('palette-open').onclick=openPalette;
document.getElementById('decision-banner-review').onclick=()=>{
  if(!lastState)return;
  const rows=lastState.escalations||[];
  const row=rows[rows.length-1];if(!row)return;
  const exists=(lastState.chats&&lastState.chats.items||[]).some(c=>c.id===row.chat_id);
  if(row.chat_id&&row.chat_id!==activeChatId&&exists){activeChatId=row.chat_id;newTaskMode=false;render(lastState);}
  openResolution(row);
};
window.addEventListener('resize',()=>{if(innerWidth>720)closeRail();});
stopRun.onclick=async()=>{const progress=lastState&&chatProgress(lastState);if(!progress||progress.finished)return;
  stopRun.disabled=true;route.className='route on';route.textContent=currentLocale==='zh'?'正在安全停止…':'Stopping safely…';
  try{await api('/api/run',{action:'cancel',run_id:progress.run_id||''});route.innerHTML=currentLocale==='zh'
    ?'<b>已请求停止。</b> 当前步骤结束后，任务会安全停止。'
    :'<b>Stop requested.</b> The task will stop safely at the next execution boundary.';}
  catch(e){route.className='route on error';route.textContent=e.message;stopRun.disabled=false;}};
function setupCardMarkup(missing){
  const both=missing.length>1,role=missing[0]||'generator';
  const sentence=both?'Neither the generator nor the auditor has a credential yet.'
    :role==='auditor'?'The auditor has no credential yet.':'The generator has no credential yet.';
  return '<div class="setup-card"><b>Connect a provider first</b><span>'+sentence+'</span>'
    +'<button type="button" class="primary setup-card-action" id="setup-open-providers">Open Settings → Providers</button></div>';}
form.onsubmit=async ev=>{ev.preventDefault();const rawText=say.value.trim();if(!rawText)return;
  const continuing=pendingContinuation.chat===activeChatId&&Boolean(pendingContinuation.cycle);
  const text=rawText;
  newTaskMode=false;
  // Echo the message immediately so the thread reacts the instant Enter is
  // pressed (Codex-style), before routing + the first token return.
  optimisticSend={text:rawText, chat:activeChatId||'', at:Date.now(), queued:Boolean(lastState&&chatProgress(lastState)&&!chatProgress(lastState).finished&&audienceOf()!=='auditor')};
  if(lastState)render(lastState);
  send.disabled=true;say.disabled=true;transferBusy=true;document.getElementById('attach').disabled=true;route.className='route on';
  route.textContent=pendingFiles.length?'Sending your files…':'Starting…';
  try{const uploadBatch=pendingFiles.length?await uploadFiles(pendingFiles):null;
    const r=await api('/api/say',{text,chat_id:activeChatId,upload_batch:uploadBatch,attachment_consent:pendingFiles.length>0,
      continuation_cycle:continuing?pendingContinuation.cycle:''});
    if(r.setup==='credentials'){optimisticSend=null;if(lastState)render(lastState);
    // A setup step, not an audit event: nothing started, the message stays in
    // the composer, and the one action is the place that fixes it.
    route.className='route on setup';route.innerHTML=setupCardMarkup(r.missing||[]);
    document.getElementById('setup-open-providers').onclick=()=>openSettings('providers');}
    else if(r.asked){optimisticSend=null;if(lastState)render(lastState);
    route.innerHTML='<b class="ask">Needs clarification.</b> '+esc(r.clarify);}
    else if(r.accepted){
      // Accepted, not answered: the server is routing it now and narrates each
      // phase into the state. The composer stays held until that settles —
      // exactly as long as it used to be held by the response itself.
      pendingIntake=r.intake;activeChatId=r.chat_id||activeChatId;if(optimisticSend)optimisticSend.chat=activeChatId||'';
      route.textContent=currentLocale==='zh'?'处理中…':'Working…';
      if(lastState)render(lastState);return;}
    else applySayResult(r);}
  catch(e){optimisticSend=null;if(lastState)render(lastState);route.innerHTML='<b>Refused.</b> '+esc(e.message);}
  releaseComposer();};
api('/api/state').then(render).catch(e=>{document.getElementById('thread-title').textContent='Disconnected: '+e.message;});
startStream();
/* ---- First-launch flow (North Star §4): shell + Welcome + Readiness ---- */
let firstRunStep=1,frSettingsSource=null,frScanning=false;
let frValidation={},frRoles=null;
function frBucket(row){return (row.status||'unknown')==='ready'?'ready':(row.blocking?'attention':'optional');}
function frStatusLabel(row){const s=row.status||'unknown';
  if(s==='ready')return 'Ready';if(row.blocking)return 'Needs attention';
  if(s==='waiting'||s==='unknown')return 'Checking…';return 'Optional';}
function frTechBody(row){const lines=[];if(row.detail)lines.push(row.detail);
  if(row.version)lines.push('version  '+row.version);if(row.minimum)lines.push('expected  '+row.minimum);
  const repair=row.repair||{};if(repair.url)lines.push('help  '+repair.url);return lines.join('\n');}
function frRowMarkup(row,bucket){
  const dot=bucket==='ready'?'fr-d-ready':bucket==='attention'?'fr-d-warn':'fr-d-opt';
  const stat=bucket==='ready'?'fr-s-ready':bucket==='attention'?'fr-s-warn'
    :((row.status==='waiting'||row.status==='unknown')?'fr-s-pending':'fr-s-opt');
  const repair=row.repair||{};let act='';
  if(bucket==='attention'){
    if(repair.url)act='<a class="fr-fix" href="'+esc(repair.url)+'" target="_blank" rel="noopener">'+esc(repair.label||'Fix automatically')+' ↗</a>';
    else if(repair.action)act='<button type="button" class="fr-fix" data-fr-fix="'+esc(repair.action)+'"'+(repair.inputs?' data-fr-inputs="1"':'')+'>'+esc(repair.label||'Fix automatically')+'</button>';
  }else if(bucket==='optional'){
    if(repair.url)act='<a class="fr-learn" href="'+esc(repair.url)+'" target="_blank" rel="noopener">Learn how →</a>';
    else if(repair.action)act='<button type="button" class="fr-learn" data-fr-fix="'+esc(repair.action)+'"'+(repair.inputs?' data-fr-inputs="1"':'')+'>Learn how →</button>';
  }
  const why=row.why?'<p class="fr-why">'+esc(row.why)+'</p>':(bucket!=='ready'&&row.detail?'<p class="fr-why">'+esc(row.detail)+'</p>':'');
  const body=frTechBody(row);
  const tech=(bucket!=='ready'&&body)?'<details class="fr-tech"><summary>Technical detail</summary><div class="fr-tech-body">'+esc(body)+'</div></details>':'';
  return '<div class="fr-row'+(bucket==='optional'?' soft':'')+'"><span class="fr-dot '+dot+'" aria-hidden="true"></span>'
    +'<div class="fr-row-main"><div class="fr-row-name"><span class="fr-name">'+esc(row.label||row.id)+'</span>'
    +'<span class="fr-stat '+stat+'">'+esc(frStatusLabel(row))+'</span></div>'+why+tech+'</div>'
    +'<div class="fr-row-act">'+act+'</div></div>';}
function frGroupMarkup(title,color,rows){if(!rows.length)return '';
  return '<div class="fr-group"><span class="fr-nameplate"'+(color?' style="color:'+color+'"':'')+'>'+esc(title)+'</span>'
    +'<div class="fr-rows">'+rows.join('')+'</div></div>';}
function frReadyGroup(rows){if(!rows.length)return '';
  const label=rows.length+(rows.length===1?' check passed':' checks passed');
  return '<details class="fr-group fr-ready-group"><summary class="fr-ready-sum">'
    +'<span class="fr-dot fr-d-ready" aria-hidden="true"></span>'
    +'<span class="fr-nameplate" style="color:var(--pass)">Ready</span>'
    +'<span class="fr-ready-n">'+label+'</span>'
    +'<span class="fr-ready-chev" aria-hidden="true">›</span></summary>'
    +'<div class="fr-rows">'+rows.join('')+'</div></details>';}
function renderFirstRunReadiness(doctor,error){
  const groups=document.getElementById('fr-groups'),rollup=document.getElementById('fr-rollup');
  const railStatus=document.getElementById('fr-rail-status'),railQueue=document.getElementById('fr-rail-queue'),railDot=document.getElementById('fr-rail-dot');
  const recheck=document.getElementById('fr-recheck'),recheckLabel=recheck.querySelector('.fr-recheck-label');
  const value=doctor||{};const status=value.status||'idle';const checks=Array.isArray(value.checks)?value.checks:[];
  const scanning=frScanning||status==='running'||(status==='idle'&&!checks.length&&!error);
  recheck.disabled=scanning;recheckLabel.textContent=scanning?'Checking…':'Re-check';
  if(error){groups.innerHTML='<div class="fr-offline">Environment status is unavailable — the check could not run. You can continue and re-check later.</div>';
    rollup.textContent='Environment status unavailable';
    railStatus.textContent='Doctor unavailable';railQueue.textContent='';railDot.className='fr-dot fr-rail-warn';return;}
  if(scanning){groups.innerHTML='<div class="fr-scanning">Checking required software…</div>';
    rollup.textContent='Checking your Mac…';railStatus.textContent='Preflight — probing environment';
    railQueue.textContent=(checks.length||3)+' checks queued';railDot.className='fr-dot fr-live';return;}
  const ready=[],attention=[],optional=[];
  for(const row of checks){const b=frBucket(row);
    if(b==='ready')ready.push(frRowMarkup(row,'ready'));
    else if(b==='attention')attention.push(frRowMarkup(row,'attention'));
    else optional.push(frRowMarkup(row,'optional'));}
  const req=attention.length;
  groups.innerHTML=[frReadyGroup(ready),
    frGroupMarkup('Needs attention','var(--escalated)',attention),
    frGroupMarkup('Optional enhancement','',optional)].join('')
    ||'<div class="fr-offline">No checks to show yet. Re-check to inspect this Mac.</div>';
  const noun=req===1?' required item needs attention':' required items need attention';
  if(req>0)rollup.innerHTML='<b>'+req+esc(noun)+'</b>';
  else rollup.innerHTML='<span class="done">Everything required is ready</span>';
  railDot.className='fr-dot '+(req>0?'fr-rail-warn':'fr-rail-ok');
  railStatus.textContent=req>0?(req+noun):'Environment ready';
  railQueue.textContent=(ready.length+attention.length+optional.length)+' checks';}
async function startFirstRunReadiness(){
  renderFirstRunReadiness(settingsState&&settingsState.doctor);
  try{const s=await api('/api/settings');settingsState=s;renderFirstRunReadiness(s.doctor);}
  catch(e){renderFirstRunReadiness(null,e);}
  if(!frSettingsSource){try{frSettingsSource=new EventSource('/api/settings/stream?t='+encodeURIComponent(T));
    frSettingsSource.onmessage=ev=>{try{const s=JSON.parse(ev.data);settingsState=s;
      if(!document.body.classList.contains('first-run'))return;
      if(firstRunStep===2)renderFirstRunReadiness(s.doctor);
      else if(firstRunStep===3)renderFirstRunProviders();
      else if(firstRunStep===4)renderFirstRunRoles();}catch(e){}};
    frSettingsSource.onerror=()=>{};}catch(e){}}}
const FR_HINTS={2:'You can re-run these checks any time from Settings.',
  3:'Two different providers is enough to begin — one to build, one to check.',
  4:'You can swap either model later without losing history.'};
function setFirstRunStep(step,focus=true){firstRunStep=Math.max(1,Math.min(4,Number(step)||1));
  document.querySelectorAll('[data-fr-step]').forEach(sec=>sec.hidden=Number(sec.dataset.frStep)!==firstRunStep);
  document.querySelectorAll('[data-fr-indicator]').forEach(item=>{const n=Number(item.dataset.frIndicator);
    item.classList.toggle('active',n===firstRunStep);item.classList.toggle('complete',n<firstRunStep);
    if(n===firstRunStep)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');});
  document.getElementById('fr-footbar').hidden=firstRunStep<2;
  document.querySelector('#fr-continue .fr-continue-label').textContent=firstRunStep===4?'Start using CrossAudit':'Continue';
  frSetContinue(true);
  document.getElementById('fr-hint').textContent=FR_HINTS[firstRunStep]||FR_HINTS[2];
  if(firstRunStep===2)startFirstRunReadiness();
  else if(firstRunStep===3)renderFirstRunProviders();
  else if(firstRunStep===4)renderFirstRunRoles();
  if(focus)requestAnimationFrame(()=>{const pane=document.querySelector('[data-fr-step="'+firstRunStep+'"]');if(pane)pane.focus();});}
function showFirstRun(){document.body.classList.add('first-run');if(typeof closePanels==='function')closePanels();
  frValidation={};frRoles=null;
  setFirstRunStep(1,false);startFirstRunReadiness();
  history.replaceState(null,'',location.pathname+'?t='+encodeURIComponent(T)+'#first-run');}
function hideFirstRun(){document.body.classList.remove('first-run');
  if((location.hash||'')==='#first-run')history.replaceState(null,'',location.pathname+'?t='+encodeURIComponent(T));}
async function completeOnboarding(action){const s=await api('/api/onboarding',{action:action||'complete'});
  if(s&&typeof s==='object')settingsState=s;return s;}

// ── Step 3 · Providers ──────────────────────────────────────────────────────
function frProvVendors(){
  const providers=(settingsState&&settingsState.providers)||{};
  // connections.status() lists exactly the key-needing built-in vendors; the
  // ChatGPT-only Codex runtime and the replay provider are not vendors here, so
  // iterating its keys is the capability-driven "needs a key" set — no hardcoded
  // provider list, and openai_codex / replay are excluded for free.
  return Object.keys(providers).sort((a,b)=>{
    const rank=v=>v==='openai'?0:(providers[v]||{}).configured?1:2;
    return rank(a)-rank(b)||String((providers[a]||{}).label||a).localeCompare(String((providers[b]||{}).label||b));});
}
// SPEC-13 §3.1. Every per-provider control is named after its provider.
//
// Observed in the frozen bundle: eleven key fields with NO accessible name at
// all, distinguished only by a `data-fr-*` attribute, and a placeholder — which
// is not a name: it is not reliably announced as one and it disappears on the
// first keystroke. Tabbing the stage produced "Validate. Validate. Validate."
// eleven times.
//
// The buttons take `aria-label`, because no single visible node carries the
// whole name. The INPUT does not: it points at the visible provider name plus a
// hidden "API key", so the accessible name is built from the same node the eye
// reads and there is no translatable duplicate to drift. In zh that yields
// "OpenAI API 密钥" without a composed string at all — the provider name is not
// translated, and "API key" is one ordinary dictionary entry.
//
// Beyond the three controls SPEC-13 §3.1 tabulates, Reveal, Replace and Remove
// carry the identical defect — Reveal shipped ONE shared aria-label on all
// eleven rows. G2 is arithmetic (distinct names must equal control count), so
// it forces them in whether or not the table lists them. Naming three and
// leaving three would fail the guard the spec itself wrote, which is it working.
const FR_KEY_ACTIONS={paste:'Paste',clear:'Clear',validate:'Validate',
                      reveal:'Reveal',replace:'Replace',remove:'Remove'};
function frKeyLabel(action,label){
  return FR_KEY_ACTIONS[action]+' '+label+' API key';}
function frProvRow(vendor,p){
  const label=p.label||vendor;const mark=esc(String(label).slice(0,1).toUpperCase());
  const nameId='fr-name-'+esc(vendor);
  const aria=action=>' aria-label="'+esc(frKeyLabel(action,label))+'"';
  // The two per-row links were the same defect as the buttons and are NOT in
  // SPEC-13 §3.1: ten rows shipped ten identical "Get key ↗" and ten identical
  // "API docs ↗". G2 is arithmetic — distinct names must equal the control
  // count — so the spec caught them through its own guard rather than through
  // its table, which is the guard being better than the list.
  // The visible text is unchanged and is CONTAINED in the accessible name
  // (WCAG 2.5.3): a speech-input user still says "Get key".
  const links=(p.console_url?'<a class="fr-learn" href="'+esc(p.console_url)+'" target="_blank" rel="noopener"'
      +' aria-label="'+esc('Get key — '+label)+'">Get key ↗</a> ':'')
    +(p.docs_url?'<a class="fr-learn" href="'+esc(p.docs_url)+'" target="_blank" rel="noopener"'
      +' aria-label="'+esc('API docs — '+label)+'">API docs ↗</a>':'');
  const configured='<div class="fr-configured" data-fr-configured hidden><span class="fr-mask" aria-hidden="true">•••• •••• ••••</span>'
    +'<span>Stored in your macOS Keychain.</span>'
    +'<button type="button" class="fr-tool" data-fr-replace="'+esc(vendor)+'"'+aria('replace')+'>Replace</button>'
    +'<button type="button" class="fr-tool" data-fr-remove="'+esc(vendor)+'"'+aria('remove')+'>Remove</button></div>';
  const field='<div class="fr-keyfield">'
    +'<span class="sr-only" id="fr-apikey-'+esc(vendor)+'">API key</span>'
    +'<input class="fr-key" type="password" id="fr-key-'+esc(vendor)+'" data-fr-key="'+esc(vendor)+'"'
    +' aria-labelledby="'+nameId+' fr-apikey-'+esc(vendor)+'"'
    +' autocomplete="new-password" placeholder="Paste your API key">'
    +'<button type="button" class="fr-tool" data-fr-paste="'+esc(vendor)+'"'+aria('paste')+'>Paste</button>'
    +'<button type="button" class="fr-tool" data-fr-reveal="'+esc(vendor)+'" aria-pressed="false"'+aria('reveal')+'>'
    +'<svg viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M1.5 10S4.5 4 10 4s8.5 6 8.5 6-3 6-8.5 6-8.5-6-8.5-6Z"/><circle cx="10" cy="10" r="2.3"/></svg></button>'
    +'<button type="button" class="fr-tool" data-fr-clear="'+esc(vendor)+'"'+aria('clear')+'>Clear</button>'
    +'<button type="button" class="fr-tool fr-tool-cta" data-fr-validate="'+esc(vendor)+'"'+aria('validate')+'>Validate</button></div>';
  const chatgpt=vendor==='openai'
    ?'<div class="fr-divider">or</div><button type="button" class="fr-chatgpt" id="fr-chatgpt"><svg viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="M10 3.5v13M3.5 10h13"/></svg> Sign in with ChatGPT (official)</button>':'';
  const honesty=(p.subscription&&p.subscription.detail)?'<p class="fr-honesty">'+esc(p.subscription.detail)+'</p>':'';
  // §3.2. The provider is announced once on entering the row. Per-control names
  // stay regardless: group context is a convenience of good screen readers, not
  // something a spec may lean on.
  return '<div class="fr-prov" role="group" aria-labelledby="'+nameId+'" data-fr-prov="'+esc(vendor)+'">'
    +'<div class="fr-prov-id"><span class="fr-prov-mark" aria-hidden="true">'+mark+'</span>'
    +'<div><div class="fr-prov-name" id="'+nameId+'">'+esc(label)+'</div><div class="fr-prov-sub">'+esc(vendor)+'</div></div>'
    +'<span class="fr-stat fr-s-pending" data-fr-stat>Checking…</span></div>'
    +'<div class="fr-prov-body"><span class="fr-prov-label"><span>New API key</span> · '+links+'</span>'
    +configured+field+chatgpt+honesty
    +'<p class="fr-keymsg" data-fr-msg></p></div></div>';
}
function renderFirstRunProviders(){
  const host=document.getElementById('fr-provs');if(!host)return;
  const providers=(settingsState&&settingsState.providers)||{};
  const vendors=frProvVendors();
  if(!vendors.length){host.innerHTML='<div class="fr-scanning">Loading providers…</div>';host.removeAttribute('data-vendors');return;}
  if(host.getAttribute('data-vendors')!==vendors.join(',')){
    host.setAttribute('data-vendors',vendors.join(','));
    host.innerHTML=vendors.map(v=>frProvRow(v,providers[v]||{})).join('');
  }
  updateFirstRunProviderStates();
}
function updateFirstRunProviderStates(){
  const providers=(settingsState&&settingsState.providers)||{};
  document.querySelectorAll('#fr-provs [data-fr-prov]').forEach(row=>{
    const vendor=row.getAttribute('data-fr-prov');const p=providers[vendor]||{};
    const configured=!!p.configured;const chatgpt=p.chatgpt&&p.chatgpt.connected;
    const v=frValidation[vendor];
    let cls='fr-s-opt',text='Not connected';
    if(v&&v.state==='ready'){cls='fr-s-ready';text='Ready';}
    else if(v&&v.state==='invalid'){cls='fr-s-invalid';text='Invalid';}
    else if(v&&v.state==='no_access'){cls='fr-s-warn';text='No access';}
    else if(v&&v.state==='unreachable'){cls='fr-s-warn';text='Unavailable';}
    else if(chatgpt){cls='fr-s-ready';text='Connected';}
    else if(configured){cls='fr-s-info';text='Configured';}
    const stat=row.querySelector('[data-fr-stat]');if(stat){stat.className='fr-stat '+cls;stat.textContent=text;}
    const note=row.querySelector('[data-fr-configured]');if(note)note.hidden=!configured;
    const input=row.querySelector('[data-fr-key]');
    if(input)input.placeholder=configured?'Paste a new key to replace the saved one':'Paste your API key';
    frAnnounceValidation(vendor,p.label||vendor,v&&v.state?String(v.state):'');
    const msg=row.querySelector('[data-fr-msg]');
    if(msg){
      if(v&&v.state==='ready'){msg.className='fr-keymsg ok';msg.textContent='Connection verified.';}
      else if(v&&v.state==='invalid'){msg.className='fr-keymsg bad';msg.textContent='This key was rejected. Check it and try again.';}
      else if(v&&v.state==='no_access'){msg.className='fr-keymsg bad';msg.textContent='The key works, but no models are available to it.';}
      else if(v&&v.state==='unreachable'){msg.className='fr-keymsg bad';msg.textContent='Could not reach the provider. Check your connection and try again.';}
      else if(!v){msg.className='fr-keymsg';msg.textContent='';}
    }
  });
}
// SPEC-13 §3.4. Seven per-row states change with no page load, on nodes with no
// role and no aria-live, so a screen-reader user pressed Validate and received
// NOTHING — including in the three states where something went wrong and the
// message is the only guidance.
//
// Routed through the shared announcer from slice 0 rather than giving eleven rows
// their own live regions, which is what the spec prefers and what stops the
// stage having eleven things that can speak.
//
// Announced as an EVENT, not a state: two providers can fail the same way, and
// re-validating the same key is a second answer to a second question. That
// distinction is the R2 finding from SPEC-9 slice 2, and it applies here for the
// same reason.
//
// Once per OUTCOME. `updateFirstRunProviderStates` runs on every render, so the
// transition is what is announced, not the value — otherwise a re-render speaks.
let frAnnouncedValidation={};
const FR_OUTCOME_SENTENCE={
  ready:label=>label+' key verified.',
  invalid:label=>label+' key rejected. Check it and try again.',
  no_access:label=>label+' key works, but no models are available to it.',
  unreachable:label=>'Could not reach '+label+'. Check your connection and try again.'};
function frAnnounceValidation(vendor,label,state){
  if(frAnnouncedValidation[vendor]===state)return false;
  frAnnouncedValidation[vendor]=state;
  const sentence=FR_OUTCOME_SENTENCE[state];
  return sentence?announce(sentence(label),'event'):false;}
function frShowKeyMsg(vendor,text,cls){const el=document.querySelector('#fr-provs [data-fr-msg]');
  const row=document.querySelector('#fr-provs [data-fr-prov="'+vendor+'"]');const m=row?row.querySelector('[data-fr-msg]'):el;
  if(!m)return;m.className='fr-keymsg'+(cls?' '+cls:'');m.textContent=text||'';}
async function frValidate(vendor){
  const input=document.getElementById('fr-key-'+vendor);const typed=input?input.value.trim():'';
  const btn=document.querySelector('#fr-provs [data-fr-validate="'+vendor+'"]');const original=btn?btn.textContent:'';
  if(btn){btn.disabled=true;btn.textContent='Checking…';}    // §26 loading state
  // The check itself is announced, because pressing Validate and hearing nothing
  // is indistinguishable from pressing a button that does not work. Cleared so
  // the OUTCOME that follows is a transition and speaks.
  {const providers=(settingsState&&settingsState.providers)||{};
   const label=(providers[vendor]&&providers[vendor].label)||vendor;
   frAnnouncedValidation[vendor]='checking';
   announce('Checking '+label+' key…','event');}
  try{
    if(typed){await api('/api/settings',{[vendor+'_key']:typed});if(input){input.value='';input.type='password';}}
    frValidation[vendor]=await api('/api/providers/validate',{vendor});
    try{settingsState=await api('/api/settings');}catch(e){}
  }catch(e){frValidation[vendor]={ok:false,state:'unreachable'};}
  if(btn){btn.disabled=false;btn.textContent=original||'Validate';}
  renderFirstRunProviders();
}
async function frConnectChatGPT(btn){
  const label=btn.textContent;btn.disabled=true;btn.textContent='Starting…';
  try{const result=await api('/api/providers/connect',{provider:'openai',method:'chatgpt'});
    if(result.url){const link=document.createElement('a');link.href=result.url;document.body.appendChild(link);link.click();link.remove();}
    try{settingsState=await api('/api/settings');}catch(e){}renderFirstRunProviders();
  }catch(e){frShowKeyMsg('openai',e.message,'bad');btn.disabled=false;btn.textContent=label;}
}
document.getElementById('fr-provs').addEventListener('click',async ev=>{
  const t=ev.target.closest('button');if(!t)return;
  if(t.id==='fr-chatgpt'){await frConnectChatGPT(t);return;}
  const vendor=t.getAttribute('data-fr-paste')||t.getAttribute('data-fr-reveal')||t.getAttribute('data-fr-clear')
    ||t.getAttribute('data-fr-replace')||t.getAttribute('data-fr-remove')||t.getAttribute('data-fr-validate');
  if(!vendor)return;const input=document.getElementById('fr-key-'+vendor);
  if(t.hasAttribute('data-fr-paste')){
    try{const text=await navigator.clipboard.readText();if(input){input.value=(text||'').trim();input.focus();}}
    catch(e){if(input)input.focus();}return;}
  if(t.hasAttribute('data-fr-reveal')){if(!input)return;const on=t.getAttribute('aria-pressed')==='true';
    input.type=on?'password':'text';t.setAttribute('aria-pressed',String(!on));return;}
  if(t.hasAttribute('data-fr-clear')){if(input){input.value='';input.type='password';
    const r=document.querySelector('#fr-provs [data-fr-reveal="'+vendor+'"]');if(r)r.setAttribute('aria-pressed','false');input.focus();}return;}
  if(t.hasAttribute('data-fr-replace')){if(input){input.value='';input.focus();}return;}
  if(t.hasAttribute('data-fr-remove')){
    try{settingsState=await api('/api/settings',{['remove_'+vendor]:true});delete frValidation[vendor];renderFirstRunProviders();}
    catch(e){frShowKeyMsg(vendor,e.message,'bad');}return;}
  if(t.hasAttribute('data-fr-validate')){await frValidate(vendor);return;}
});

// ── Step 4 · Generator / Auditor ────────────────────────────────────────────
function frConfiguredVendors(){
  const providers=(settingsState&&settingsState.providers)||{};
  return Object.keys(providers).filter(v=>(providers[v]||{}).configured);
}
function frRecommendRoles(){
  const configured=frConfiguredVendors();
  const pref=['anthropic','openai','google','xai','deepseek','qwen','moonshot','zhipu','minimax','mistral'];
  const rank=v=>{const i=pref.indexOf(v);return i<0?pref.length:i;};
  const pool=configured.slice().sort((a,b)=>rank(a)-rank(b)||a.localeCompare(b));
  const cat=(settingsState&&settingsState.model_catalog)||{};
  const def=v=>(cat[v]&&cat[v].default_model)||'';
  if(pool.length>=2){const gen=pool[0],aud=pool.find(v=>v!==gen);
    return {gen:{vendor:gen,model:def(gen)},aud:{vendor:aud,model:def(aud)}};}
  return null;
}
function frFmtContext(n){if(!n)return '';if(n>=1000000)return (n/1000000).toFixed(n%1000000?1:0).replace(/\.0$/,'')+'M';
  if(n>=1000)return Math.round(n/1000)+'K';return String(n);}
function frOptions(items,selected){return items.map(o=>'<option value="'+esc(o.value)+'"'+(o.value===selected?' selected':'')+'>'+esc(o.label)+'</option>').join('');}
function frFillSelect(id,items,selected){const el=document.getElementById(id);if(!el)return;
  el.innerHTML=frOptions(items,selected);if(items.some(o=>o.value===selected))el.value=selected;}
function frRenderRoleCard(role,sel){
  const cat=(settingsState&&settingsState.model_catalog)||{};const providers=(settingsState&&settingsState.providers)||{};
  const meta=cat[sel.vendor]||{};const label=meta.label||sel.vendor;
  const model=(meta.models||[]).find(m=>m.id===sel.model)||{};const cap=model.capability||{};
  document.getElementById('fr-'+role+'-name').textContent=label+' · '+(sel.model||'—');
  document.getElementById('fr-'+role+'-mid').textContent=sel.vendor+' · '+(sel.model||'');
  const chips=[];
  if(cap.context_window)chips.push('<span class="fr-chip"><span class="n">'+esc(frFmtContext(cap.context_window))+'</span> <span>context</span></span>');
  if(cap.vision)chips.push('<span class="fr-chip">Vision</span>');
  if(cap.structured_output)chips.push('<span class="fr-chip">Structured output</span>');
  if(cap.reasoning)chips.push('<span class="fr-chip">Reasoning</span>');
  const price=cap.price||{};
  if(price.state==='reported')chips.push('<span class="fr-chip fr-chip-price"><span class="n">$'+esc(price.input)+' · $'+esc(price.output)+'</span> <span>/ Mtok</span></span>');
  else if(price.state==='estimated')chips.push('<span class="fr-chip fr-chip-price"><span class="n">~$'+esc(price.input)+' · $'+esc(price.output)+'</span> <span>/ Mtok</span></span>');
  else chips.push('<span class="fr-chip fr-chip-muted">Price not published</span>');
  const p=providers[sel.vendor]||{};const check='<svg viewBox="0 0 20 20" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 10.5 8.2 14.5 16 6"/></svg>';
  if(p.chatgpt&&p.chatgpt.connected)chips.push('<span class="fr-chip fr-chip-auth">'+check+' ChatGPT</span>');
  else if(p.configured)chips.push('<span class="fr-chip fr-chip-auth">'+check+' <span>Keychain key</span></span>');
  document.getElementById('fr-'+role+'-chips').innerHTML=chips.join('');
}
// SPEC-13 §3.3. `disabled` removes the control from the tab order, so the
// on-screen reason — "Connect at least two different providers…" — is
// unreachable WITH it. The person meets a stage they cannot complete and nothing
// tells them why. This is the reason-attached pattern rather than convention for
// its own sake: an explanation that can only be reached by reaching the thing it
// explains is not an explanation.
//
// So the button stays focusable and in the tab order, says it is unavailable,
// points at the reason, and the handler declines the action. One mechanism for
// every blocked case, including the transient in-flight one, because two would
// drift — and the in-flight case gets its own reason rather than an unexplained
// refusal.
function frSetContinue(enabled,reasonId){
  const cont=document.getElementById('fr-continue');if(!cont)return;
  cont.disabled=false;
  if(enabled){cont.removeAttribute('aria-disabled');cont.removeAttribute('aria-describedby');}
  else{cont.setAttribute('aria-disabled','true');
    if(reasonId)cont.setAttribute('aria-describedby',reasonId);
    else cont.removeAttribute('aria-describedby');}}
function frContinueBlocked(){
  const cont=document.getElementById('fr-continue');
  return !!cont&&cont.getAttribute('aria-disabled')==='true';}
function frUpdateIndependence(){
  const banner=document.getElementById('fr-independent');const msg=document.getElementById('fr-role-msg');
  const cont=document.getElementById('fr-continue');if(!frRoles){banner.hidden=true;return;}
  banner.hidden=false;const same=frRoles.gen.vendor&&frRoles.gen.vendor===frRoles.aud.vendor;
  const _g=banner.querySelector('svg path');if(_g)_g.setAttribute('d',same?'M6 6 14 14M14 6 6 14':'M4 10.5 8.2 14.5 16 6');
  if(same){banner.classList.add('bad');
    document.getElementById('fr-independent-text').textContent='Same provider — independent review is not possible.';
    msg.className='fr-role-msg';liveText(msg,'Generator and auditor must run on different providers. Independent review is the core of the protocol and cannot be turned off.');
    frSetContinue(false,'fr-role-msg');
  }else{banner.classList.remove('bad');
    document.getElementById('fr-independent-text').textContent='Independent — your auditor runs on a different provider than your generator.';
    msg.className='fr-role-msg';liveText(msg,'');frSetContinue(true);}
}
function renderFirstRunRoles(){
  if(firstRunStep!==4)return;
  const cat=(settingsState&&settingsState.model_catalog)||{};const providers=(settingsState&&settingsState.providers)||{};
  const configured=frConfiguredVendors();
  const msg=document.getElementById('fr-role-msg');const cont=document.getElementById('fr-continue');
  const pair=document.getElementById('fr-pair');const banner=document.getElementById('fr-independent');
  if(!frRoles||!configured.includes(frRoles.gen.vendor)||!configured.includes(frRoles.aud.vendor)
     ||frRoles.gen.vendor===frRoles.aud.vendor){frRoles=frRecommendRoles();}
  if(!frRoles){pair.hidden=true;banner.hidden=true;
    msg.className='fr-role-msg';liveText(msg,'Connect at least two different providers on the previous step to form an independent Generator / Auditor pair.');
    frSetContinue(false,'fr-role-msg');return;}
  pair.hidden=false;
  const label=v=>(cat[v]&&cat[v].label)||(providers[v]&&providers[v].label)||v;
  const modelOpts=v=>((cat[v]&&cat[v].models)||[]).map(m=>({value:m.id,label:m.id}));
  const vendorOpts=exclude=>configured.filter(v=>v!==exclude).map(v=>({value:v,label:label(v)}));
  // The generator vendor picker excludes the auditor vendor and vice versa, so
  // independence cannot be selected away (mirrors the wizard.py:310 exclusion).
  frFillSelect('fr-gen-vendor',vendorOpts(frRoles.aud.vendor),frRoles.gen.vendor);
  frFillSelect('fr-aud-vendor',vendorOpts(frRoles.gen.vendor),frRoles.aud.vendor);
  const ensure=role=>{const v=frRoles[role].vendor;const models=(cat[v]&&cat[v].models)||[];
    if(!models.some(m=>m.id===frRoles[role].model))frRoles[role].model=(cat[v]&&cat[v].default_model)||(models[0]&&models[0].id)||'';};
  ensure('gen');ensure('aud');
  frFillSelect('fr-gen-model',modelOpts(frRoles.gen.vendor),frRoles.gen.model);
  frFillSelect('fr-aud-model',modelOpts(frRoles.aud.vendor),frRoles.aud.model);
  frRenderRoleCard('gen',frRoles.gen);frRenderRoleCard('aud',frRoles.aud);
  frUpdateIndependence();
}
document.getElementById('fr-gen-vendor').onchange=e=>{if(!frRoles)return;frRoles.gen.vendor=e.target.value;frRoles.gen.model='';renderFirstRunRoles();};
document.getElementById('fr-gen-model').onchange=e=>{if(!frRoles)return;frRoles.gen.model=e.target.value;frRenderRoleCard('gen',frRoles.gen);frUpdateIndependence();};
document.getElementById('fr-aud-vendor').onchange=e=>{if(!frRoles)return;frRoles.aud.vendor=e.target.value;frRoles.aud.model='';renderFirstRunRoles();};
document.getElementById('fr-aud-model').onchange=e=>{if(!frRoles)return;frRoles.aud.model=e.target.value;frRenderRoleCard('aud',frRoles.aud);frUpdateIndependence();};
async function frEnterHub(action,note){
  try{await completeOnboarding(action);}catch(e){}
  hideFirstRun();showProjects();try{await refreshProjects();}catch(e){}
  if(note){const n=document.getElementById('hub-note');if(n){n.hidden=false;
    n.textContent='Your provider setup is saved. Create your first project to put the recommended pair to work.';}}
  try{openProjectModal();}catch(e){}
}
async function frFinishOnboarding(){
  const cont=document.getElementById('fr-continue');const msg=document.getElementById('fr-role-msg');
  if(!frRoles){await frEnterHub('complete');return;}
  if(frRoles.gen.vendor===frRoles.aud.vendor){frUpdateIndependence();return;} // hard refusal
  // In flight. Same mechanism, and it states its reason rather than going quiet.
  msg.className='fr-role-msg';liveText(msg,'Saving your provider setup…');
  frSetContinue(false,'fr-role-msg');
  // Persist the chosen models onto the current project via the real runtime path
  // (projects.update_runtime → atomic crossaudit.yml rewrite; the server refuses
  // the write while a loop runs, TRACKER.running). update_runtime rewrites the
  // model/effort of a role, never its vendor — so send a role model only when
  // the project role vendor already matches the selection, else leave it as is.
  try{
    const opts=await api('/api/runtime/options',{});const roles=(opts&&opts.roles)||{};
    const cat=(settingsState&&settingsState.model_catalog)||{};
    const keep=(role,sel)=>{const cur=roles[role]||{};if(cur.vendor===sel.vendor)return sel.model;
      return cur.model||(cat[cur.vendor]&&cat[cur.vendor].default_model)||sel.model;};
    await api('/api/runtime',{generator_model:keep('generator',frRoles.gen),
                              auditor_model:keep('auditor',frRoles.aud)});
    await frEnterHub('complete');
  }catch(e){
    if(e&&e.issue==='runtime_busy'){frSetContinue(true);msg.className='fr-role-msg';liveText(msg,e.message);return;}
    // No writable project yet (first launch may have no repo). Do not fabricate a
    // config write — finish onboarding honestly and let them create their first.
    await frEnterHub('complete',true);
  }
}
document.getElementById('fr-create').onclick=()=>setFirstRunStep(2);
document.getElementById('fr-back').onclick=()=>setFirstRunStep(firstRunStep-1);
document.getElementById('fr-skip').onclick=async()=>{const b=document.getElementById('fr-skip');b.disabled=true;
  try{await completeOnboarding('skip');}catch(e){}hideFirstRun();showProjects();};
document.getElementById('fr-recheck').onclick=async()=>{frScanning=true;renderFirstRunReadiness(settingsState&&settingsState.doctor);
  try{const d=await api('/api/doctor',{action:'scan'});frScanning=false;renderFirstRunReadiness(d);if(settingsState)settingsState.doctor=d;}
  catch(e){frScanning=false;renderFirstRunReadiness(settingsState&&settingsState.doctor,e);}};
document.getElementById('fr-continue').onclick=async()=>{
  // aria-disabled does not stop a click, so the handler is where the action is
  // actually declined. That is the trade for the reason being reachable.
  if(frContinueBlocked())return;
  if(firstRunStep<4){setFirstRunStep(firstRunStep+1);return;}
  await frFinishOnboarding();};
document.getElementById('fr-open').onclick=async()=>{try{await completeOnboarding('complete');}catch(e){}hideFirstRun();showProjects();};
document.getElementById('fr-import').onclick=async()=>{
  try{await completeOnboarding('complete');hideFirstRun();showProjects();await refreshProjects();openProjectModal();}catch(e){}};
document.getElementById('fr-demo').onclick=async()=>{
  // Credential-free local SAMPLE: mark onboarding complete, materialize-or-reuse
  // the seeded demo project (no provider, no key), and open it. The demo project
  // carries a persistent "not a real audit" banner on every surface.
  const btn=document.getElementById('fr-demo');btn.disabled=true;
  try{
    await completeOnboarding('complete');
    const r=await api('/api/projects/demo',{});
    window.name=location.origin+location.pathname+'?t='+encodeURIComponent(T)+'#projects';
    location.href=r.url;
  }catch(e){
    btn.disabled=false;hideFirstRun();showProjects();
    const note=document.getElementById('hub-note');if(note){note.hidden=false;
      note.textContent='The local demo could not be prepared: '+e.message+' — you can still create or import a project.';}}};
document.getElementById('fr-groups').onclick=async ev=>{
  const btn=ev.target.closest('[data-fr-fix]');if(!btn)return;
  const action=btn.getAttribute('data-fr-fix');
  if(btn.getAttribute('data-fr-inputs')==='1'||action==='choose_workspace'){hideFirstRun();openSettings('files');return;}
  const before=btn.textContent;btn.disabled=true;btn.textContent='Working…';
  try{const d=await api('/api/doctor',{action});frScanning=false;renderFirstRunReadiness(d);if(settingsState)settingsState.doctor=d;}
  catch(e){btn.disabled=false;btn.textContent=before;document.getElementById('fr-rail-status').textContent=e.message;}};
async function bootRoute(){let s=null;
  try{s=await api('/api/settings');settingsState=s;}catch(e){}
  if(s&&s.app_mode&&!(s.onboarding&&s.onboarding.completed)){showFirstRun();return;}
  if(location.hash==='#projects')showProjects();
  initialReadiness();}
async function initialReadiness(){
  for(let attempt=0;attempt<12;attempt++){
    try{const s=await api('/api/settings');settingsState=s;
      const providers=Object.values(s.providers||{}).filter(p=>p.configured).length;
      const blocked=s.doctor&&s.doctor.status==='blocked';
      if(s.app_mode&&location.hash==='#projects'&&(providers<2||blocked)){
        await openSettings(blocked?'diagnostics':'providers');if(blocked)doctorMessage('Required setup needs attention before creating a project.',true);return;}
      if(!s.doctor||s.doctor.status!=='running')return;
    }catch(e){return;}
    await new Promise(resolve=>setTimeout(resolve,500));
  }
}
bootRoute();
</script></body></html>"""
