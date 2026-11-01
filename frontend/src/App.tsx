/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useEffect, useState } from "react";
import { ConsoleProvider } from "./lib/console";
import { Navbar } from "./components/Navbar";
import { HeroSection } from "./components/HeroSection";
import { ProofSection } from "./components/ProofSection";
import { DashboardSection } from "./components/DashboardSection";
import { CtaAndFooter } from "./components/CtaAndFooter";

function Shell() {
  const [path, setPath] = useState(window.location.pathname);
  const operational = path === "/dashboard";
  useEffect(() => {
    function update() {
      setPath(location.pathname);
      requestAnimationFrame(() => {
        if (location.hash)
          document.getElementById(location.hash.slice(1))?.scrollIntoView();
        else window.scrollTo(0, 0);
      });
    }
    function follow(event: MouseEvent) {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      )
        return;
      const link = (event.target as Element).closest("a");
      if (!link || link.target || link.hasAttribute("download")) return;
      const url = new URL(link.href);
      if (
        url.origin === location.origin &&
        (url.pathname === "/" || url.pathname === "/dashboard") &&
        !link.getAttribute("href")?.startsWith("#")
      ) {
        event.preventDefault();
        history.pushState({}, "", url.pathname + url.hash);
        update();
      }
    }
    window.addEventListener("popstate", update);
    document.addEventListener("click", follow);
    return () => {
      window.removeEventListener("popstate", update);
      document.removeEventListener("click", follow);
    };
  }, []);
  const [isCliModalOpen, setIsCliModalOpen] = useState(false);

  return (
    <div className="min-h-screen bg-white text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-full focus:bg-moss focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      <Navbar onOpenCliModal={() => setIsCliModalOpen(true)} />

      <main id="main">
        {operational ? (
          <DashboardSection compact />
        ) : (
          <>
            <HeroSection />
            <ProofSection />
            <DashboardSection />
          </>
        )}
      </main>

      <CtaAndFooter
        compact={operational}
        isCliModalOpen={isCliModalOpen}
        onOpenCliModal={() => setIsCliModalOpen(true)}
        onCloseCliModal={() => setIsCliModalOpen(false)}
      />
    </div>
  );
}

export default function App() {
  return (
    <ConsoleProvider>
      <Shell />
    </ConsoleProvider>
  );
}
