"use client";

import { useEffect, useRef, useState } from "react";

const sections = [
  ["market", "Market"],
  ["growth", "Growth"],
  ["sellers", "Companies"],
  ["generics", "Generics"],
  ["protection", "Patents"],
  ["states", "States"],
  ["outlook", "Outlook"],
  ["quality", "Quality"],
] as const;

export function ReportNavigation() {
  const [active, setActive] = useState<string>("market");
  const navigation = useRef<HTMLElement>(null);

  useEffect(() => {
    const targets = sections.map(([id]) => document.getElementById(id));
    const toolbar = navigation.current?.closest(".report-toolbar");
    let frame = 0;
    function update() {
      frame = 0;
      const offset = (toolbar?.getBoundingClientRect().height ?? 0) + 24;
      let current: string = sections[0][0];
      for (const target of targets) {
        if (target && target.getBoundingClientRect().top <= offset) current = target.id;
      }
      setActive(current);
    }
    function schedule() {
      if (!frame) frame = requestAnimationFrame(update);
    }
    const resize = new ResizeObserver(() => {
      document.documentElement.style.setProperty("--report-toolbar-height", `${toolbar?.getBoundingClientRect().height ?? 0}px`);
      schedule();
    });
    if (toolbar) resize.observe(toolbar);
    update();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      document.documentElement.style.removeProperty("--report-toolbar-height");
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, []);

  useEffect(() => {
    const nav = navigation.current;
    const link = nav?.querySelector<HTMLElement>('[aria-current="location"]');
    if (!nav || !link || nav.scrollWidth <= nav.clientWidth) return;
    const bounds = nav.getBoundingClientRect();
    const item = link.getBoundingClientRect();
    if (item.left < bounds.left || item.right > bounds.right) {
      nav.scrollTo({ left: nav.scrollLeft + item.left - bounds.left - 12 });
    }
  }, [active]);

  return (
    <nav ref={navigation} className="report-sections" aria-label="Sections">
      {sections.map(([id, label]) => (
        <a key={id} href={`#${id}`} aria-current={active === id ? "location" : undefined}>
          {label}
        </a>
      ))}
    </nav>
  );
}
