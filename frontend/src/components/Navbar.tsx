import React, { useEffect, useRef, useState } from "react";

interface NavbarProps {
  onOpenCliModal: () => void;
}

export function BrandLogo({
  className = "h-[26px] sm:h-[31px]",
}: {
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="currentColor"
      aria-hidden="true"
      className={`w-auto shrink-0 ${className}`}
    >
      <path
        d="M16 29.5V15"
        fill="none"
        stroke="currentColor"
        strokeWidth="3.4"
        strokeLinecap="round"
      />
      <path d="M15.2 19.5C8 19.5 3.5 14.6 3.5 7.6c7 0 11.7 4.6 11.7 11.9Z" />
      <path d="M16.8 15.6c0-7.4 4.6-12.1 11.7-12.1 0 7.1-4.5 12.1-11.7 12.1Z" />
    </svg>
  );
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenCliModal }) => {
  const [hidden, setHidden] = useState(false);
  const header = useRef<HTMLElement>(null);
  useEffect(() => {
    let previous = Math.max(0, window.scrollY);
    function scroll() {
      const current = Math.max(0, window.scrollY);
      if (current <= 40 || header.current?.querySelector(":focus-visible")) {
        setHidden(false);
        previous = current;
        return;
      }
      if (Math.abs(current - previous) < 6) return;
      setHidden(current > previous && current > 80);
      previous = current;
    }
    window.addEventListener("scroll", scroll, { passive: true });
    return () => window.removeEventListener("scroll", scroll);
  }, []);
  return (
    <header
      ref={header}
      inert={hidden}
      aria-hidden={hidden}
      className="pointer-events-none fixed inset-x-0 top-0 z-50 flex justify-center px-4 pt-4 transition-transform duration-200 motion-reduce:transition-none sm:pt-7 lg:pt-10"
      style={{ transform: hidden ? "translateY(-100%)" : "translateY(0)" }}
    >
      <nav
        aria-label="Main"
        className="pointer-events-auto flex items-center gap-7 rounded-full border border-black/[0.07] bg-white/85 py-1 pr-1 pl-4 shadow-[0_12px_32px_-16px_rgba(20,23,15,0.3)] backdrop-blur-md motion-safe:animate-intro-drop sm:gap-12 sm:pl-5"
      >
        <a
          aria-label="Swarmtest home"
          href="/#hero"
          className="flex items-center self-stretch rounded-full focus-visible:ring-2 focus-visible:ring-moss focus-visible:ring-offset-4 focus-visible:outline-none whitespace-nowrap shrink-0"
        >
          <span className="inline-flex items-center gap-2.5 text-ink translate-y-px">
            <BrandLogo />
            <span className="font-heading text-[26px] leading-none font-medium tracking-[-0.035em] sm:text-[31px]">
              swarmtest
            </span>
          </span>
        </a>

        <ul className="hidden items-center gap-1 lg:flex">
          <li>
            <a
              className="rounded-full px-3.5 py-2 text-[15px] font-medium text-ink/75 transition-colors hover:bg-sage hover:text-ink focus-visible:ring-2 focus-visible:ring-moss focus-visible:outline-none whitespace-nowrap shrink-0"
              href="/dashboard"
            >
              Dashboard
            </a>
          </li>
        </ul>

        <button
          type="button"
          onClick={onOpenCliModal}
          className="inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-full bg-moss font-semibold text-white transition-[background-color,transform] duration-200 hover:bg-moss-deep active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-moss focus-visible:ring-offset-2 focus-visible:outline-none h-11 px-4 text-[15px] sm:h-12 sm:px-5 sm:text-[17px] whitespace-nowrap"
        >
          Get started
        </button>
      </nav>
    </header>
  );
};
