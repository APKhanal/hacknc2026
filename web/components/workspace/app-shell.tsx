"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode, type CSSProperties, type PointerEvent } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Minus, Square, X, Copy, Volume2, ChevronRight, Power } from "lucide-react";
import { PocketwatchLogo } from "@/components/ui/aero";
import { signOut, useSession } from "@/lib/auth";

export type WorkspaceView = "overview" | "scenarios" | "replays" | "preferences";
const navigation = [
  { id: "overview", label: "Overview" },
  { id: "scenarios", label: "Scenarios" },
  { id: "replays", label: "Replays" },
  { id: "preferences", label: "Preferences" },
] as const;

function ApplicationIcon({ view, size, className = "" }: { view: WorkspaceView; size: number; className?: string }) {
  return <img className={`xp-application-icon ${className}`} src={`/images/icons/xp-${view}.png`} width={size} height={size} alt="" aria-hidden="true" draggable={false} />;
}

export function AppShell({ children, view = null, accent, transparent, background, renderView }: {
  children?: ReactNode;
  view?: WorkspaceView | null;
  accent?: "ocean" | "meadow";
  transparent?: boolean;
  background?: "water" | "city" | "globe" | "flight";
  renderView?: (view: WorkspaceView) => ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const session = useSession();
  const [savedAppearance, setSavedAppearance] = useState<{ accent: "ocean" | "meadow"; transparent: boolean; background: "water" | "city" | "globe" | "flight" }>({ accent: "ocean", transparent: true, background: "water" });
  const [openApps, setOpenApps] = useState<WorkspaceView[]>(view ? [view] : []);
  const [active, setActive] = useState<WorkspaceView | null>(view);
  const [maximized, setMaximized] = useState(false);
  const [startOpen, setStartOpen] = useState(false);
  const [clock, setClock] = useState("");
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const windowRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; baseX: number; baseY: number; minX: number; maxX: number; minY: number; maxY: number; nextX: number; nextY: number } | null>(null);
  const iconRefs = useRef<Partial<Record<WorkspaceView, HTMLAnchorElement | null>>>({});
  const contentRef = useRef<HTMLElement>(null);

  useEffect(() => {
    setActive(view);
    if (view) setOpenApps(current => current.includes(view) ? current : [...current, view]);
  }, [view]);
  useEffect(() => {
    if (accent !== undefined && transparent !== undefined && background !== undefined) return;
    try {
      const saved = JSON.parse(localStorage.getItem("counterfactual.workspace.v1") ?? "null");
      const preferences = saved?.preferences;
      if (preferences) setSavedAppearance({ accent: preferences.accent === "meadow" ? "meadow" : "ocean", transparent: preferences.transparent !== false, background: saved.wallpaperVersion === 2 && (preferences.background === "city" || preferences.background === "globe" || preferences.background === "flight") ? preferences.background : "water" });
    } catch { /* Default appearance also works without browser storage. */ }
  }, [accent, transparent, background]);
  useEffect(() => {
    const update = () => setClock(new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date()));
    update();
    const timer = window.setInterval(update, 60000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (active) contentRef.current?.focus({ preventScroll: true });
  }, [active]);
  useEffect(() => {
    const reset = () => setPosition({ x: 0, y: 0 });
    window.addEventListener("resize", reset);
    return () => window.removeEventListener("resize", reset);
  }, []);

  function openApp(id: WorkspaceView) {
    setStartOpen(false);
    if (pathname !== "/" && id !== "replays") { router.push(`/?view=${id}`); return; }
    setOpenApps(current => current.includes(id) ? current : [...current, id]);
    setActive(id);
    if (pathname === "/") router.push(`/?view=${id}`, { scroll: false });
  }
  function minimize() {
    if (active) iconRefs.current[active]?.focus();
    setActive(null);
    if (pathname === "/") router.push("/", { scroll: false });
  }
  function close() {
    if (!active) return;
    const closing = active;
    const remaining = openApps.filter(id => id !== closing);
    setOpenApps(remaining);
    setActive(null);
    setMaximized(false);
    setPosition({ x: 0, y: 0 });
    iconRefs.current[closing]?.focus();
    router.push("/", { scroll: false });
  }
  function dragStart(event: PointerEvent<HTMLElement>) {
    if (maximized || event.button !== 0 || (event.target as HTMLElement).closest("button")) return;
    const rect = windowRef.current?.getBoundingClientRect();
    if (!rect) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, y: event.clientY, baseX: position.x, baseY: position.y, minX: position.x - rect.left + 8, maxX: position.x + window.innerWidth - rect.right - 8, minY: position.y - rect.top + 8, maxY: position.y + window.innerHeight - rect.top - 90, nextX: position.x, nextY: position.y };
  }
  function dragMove(event: PointerEvent<HTMLElement>) {
    const current = drag.current;
    if (!current || !windowRef.current) return;
    current.nextX = Math.min(current.maxX, Math.max(current.minX, current.baseX + event.clientX - current.x));
    current.nextY = Math.min(current.maxY, Math.max(current.minY, current.baseY + event.clientY - current.y));
    windowRef.current.style.transform = `translate(${current.nextX}px, ${current.nextY}px)`;
  }
  function dragEnd() {
    if (!drag.current) return;
    setPosition({ x: drag.current.nextX, y: drag.current.nextY });
    drag.current = null;
  }
  const currentApp = navigation.find(item => item.id === active);
  return <div className="aero-desktop xp-desktop" data-accent={accent ?? savedAppearance.accent} data-transparent={transparent ?? savedAppearance.transparent} data-background={background ?? savedAppearance.background}>
    <a className="skip-link" href={active ? "#workspace-content" : "#desktop-icons"}>Skip to {active ? "window" : "desktop icons"}</a>
    <nav className="desktop-icons" id="desktop-icons" aria-label="Desktop applications">
      {navigation.map(({ id, label }) => <Link ref={element => { iconRefs.current[id] = element; }} key={id} href={`/?view=${id}`} className="desktop-icon" aria-current={active === id ? "page" : undefined} onClick={event => { if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return; event.preventDefault(); openApp(id); }}><ApplicationIcon view={id} size={64} className="desktop-icon-art" /><span>{label}</span></Link>)}
    </nav>
    <div className="desktop-stage">
      {active && <div ref={windowRef} className="xp-window" data-maximized={maximized} style={{ transform: maximized ? "none" : `translate(${position.x}px, ${position.y}px)` } as CSSProperties} role="region" aria-label={`${currentApp?.label ?? "Replay"} window`}>
        <header className="xp-titlebar" onPointerDown={dragStart} onPointerMove={dragMove} onPointerUp={dragEnd} onPointerCancel={dragEnd} onDoubleClick={event => { if (!(event.target as HTMLElement).closest("button")) { setMaximized(current => !current); setPosition({ x: 0, y: 0 }); } }}>
          <div className="xp-window-title"><PocketwatchLogo size={24} /><span>{currentApp?.label} <span className="xp-title-brand">— Pocketwatch</span></span></div>
          <div className="xp-window-controls"><button type="button" onClick={minimize} aria-label="Minimize window"><Minus size={16} aria-hidden="true" /></button><button type="button" onClick={() => { setMaximized(current => !current); setPosition({ x: 0, y: 0 }); }} aria-label={maximized ? "Restore window" : "Maximize window"}>{maximized ? <Copy size={13} aria-hidden="true" /> : <Square size={13} aria-hidden="true" />}</button><button type="button" className="xp-close" onClick={close} aria-label="Close window"><X size={18} aria-hidden="true" /></button></div>
        </header>
        <div className="xp-menubar"><span>{currentApp?.label}</span><span>Local workspace</span></div>
        <main ref={contentRef} className="workspace-content xp-window-content" id="workspace-content" tabIndex={-1}><div className="view-enter" key={active}>{renderView ? renderView(active) : children}</div></main>
        <footer className="xp-statusbar"><span>{currentApp?.label}</span><span>{maximized ? "Double-click the title bar to restore" : "Drag the title bar to move"}</span></footer>
      </div>}
    </div>
    <div className="xp-taskbar">
      <div className="xp-start-area" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setStartOpen(false); }} onKeyDown={event => { if (event.key === "Escape") { setStartOpen(false); document.getElementById("xp-start")?.focus(); } }}>
        {startOpen && <nav className="xp-start-menu" aria-label="Start menu"><div className="xp-start-heading"><PocketwatchLogo />Pocketwatch</div>{navigation.map(({ id, label }) => <button key={id} type="button" onClick={() => openApp(id)}><ApplicationIcon view={id} size={30} />{label}<ChevronRight size={14} aria-hidden="true" /></button>)}<div className="xp-start-footer">{session ? <><span>Signed in as {session.user.name}</span><button type="button" className="xp-log-off" onClick={async () => { setStartOpen(false); await signOut(); router.push("/login"); }}><Power size={14} aria-hidden="true" />Log off</button></> : <><span>Not signed in</span><button type="button" className="xp-log-off" onClick={() => router.push(`/login?next=${encodeURIComponent(pathname)}`)}><Power size={14} aria-hidden="true" />Sign in</button></>}</div></nav>}
        <button id="xp-start" className="xp-start-button" type="button" aria-expanded={startOpen} aria-label="Start menu" onClick={() => setStartOpen(open => !open)}><PocketwatchLogo size={32} /><span>start</span></button>
      </div>
      <nav className="xp-task-list" aria-label="Open windows">{openApps.map(id => { const app = navigation.find(item => item.id === id)!; return <button key={id} type="button" className="xp-task" data-active={active === id} onClick={() => active === id ? minimize() : openApp(id)} aria-label={active === id ? `Minimize ${app.label}` : `Restore ${app.label}`}><ApplicationIcon view={id} size={18} /><span>{app.label}</span></button>; })}</nav>
      <div className="xp-system-tray"><Volume2 size={15} aria-hidden="true" /><time suppressHydrationWarning>{clock}</time></div>
    </div>
  </div>;
}
