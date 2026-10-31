import React from 'react';

const BIRD_CONFIGS = [
  { top: '17%', duration: '30s', delay: '-9s', rest: '24%', w: 40, h: 16, flapDur: '1.8s', flapDelay: '0s', hideSm: false },
  { top: '20.5%', duration: '30s', delay: '-8.2s', rest: '19%', w: 30, h: 12, flapDur: '1.6s', flapDelay: '-0.37s', hideSm: false },
  { top: '14.5%', duration: '30s', delay: '-7.7s', rest: '16%', w: 27, h: 10.8, flapDur: '1.7s', flapDelay: '-0.74s', hideSm: true },
  { top: '24%', duration: '38s', delay: '-25s', rest: '66%', w: 32, h: 12.8, flapDur: '2s', flapDelay: '-1.11s', hideSm: false },
  { top: '26.5%', duration: '38s', delay: '-24.1s', rest: '62%', w: 24, h: 9.6, flapDur: '1.7s', flapDelay: '-1.48s', hideSm: true },
  { top: '11%', duration: '46s', delay: '-34s', rest: '80%', w: 22, h: 8.8, flapDur: '1.9s', flapDelay: '-1.85s', hideSm: false },
];

const LEFT_GLASS_TILES = [
  { col: 1, row: 0, popDelay: '1100ms', breatheDelay: '0s' },
  { col: 2, row: 0, popDelay: '1210ms', breatheDelay: '-2.3s' },
  { col: 0, row: 1, popDelay: '1320ms', breatheDelay: '-4.6s' },
  { col: 2, row: 1, popDelay: '1430ms', breatheDelay: '-6.9s' },
  { col: 3, row: 1, popDelay: '1540ms', breatheDelay: '-2.2s' },
  { col: 1, row: 2, popDelay: '1650ms', breatheDelay: '-4.5s' },
];

const RIGHT_GLASS_TILES = [
  { col: 1, row: 0, popDelay: '1250ms', breatheDelay: '0s' },
  { col: 1, row: 1, popDelay: '1360ms', breatheDelay: '-2.3s' },
  { col: 0, row: 2, popDelay: '1470ms', breatheDelay: '-4.6s' },
  { col: 2, row: 2, popDelay: '1580ms', breatheDelay: '-6.9s' },
  { col: 1, row: 3, popDelay: '1690ms', breatheDelay: '-2.2s' },
  { col: 3, row: 3, popDelay: '1800ms', breatheDelay: '-4.5s' },
  { col: 0, row: 4, popDelay: '1910ms', breatheDelay: '-6.8s' },
];

const CENTER_GLASS_TILES = [
  { col: 0, row: 0, popDelay: '1600ms', breatheDelay: '0s' },
  { col: 2, row: 0, popDelay: '1710ms', breatheDelay: '-2.3s' },
  { col: 1, row: 1, popDelay: '1820ms', breatheDelay: '-4.6s' },
  { col: 2, row: 2, popDelay: '1930ms', breatheDelay: '-6.9s' },
];

export const HeroSection: React.FC = () => {
  return (
    <section
      id="hero"
      aria-labelledby="hero-title"
      className="relative isolate flex min-h-[max(100svh,680px)] flex-col overflow-hidden bg-white"
    >
      {/* Left Cloud */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-[3%] -left-[5%] z-0 w-[clamp(220px,38vw,580px)] mix-blend-multiply motion-safe:animate-intro-left"
        style={{ animationDelay: '150ms' }}
      >
        <div
          className="[--drift-x:70px] [--drift-y:-10px] motion-safe:animate-drift"
          style={{ animationDuration: '16s' }}
        >
          <img
            alt=""
            src="/images/cloud.jpg"
            referrerPolicy="no-referrer"
            className="h-auto w-full"
          />
        </div>
      </div>

      {/* Right Cloud */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-[7%] -right-[6%] z-0 w-[clamp(200px,33vw,520px)] mix-blend-multiply motion-safe:animate-intro-right"
        style={{ animationDelay: '300ms' }}
      >
        <div
          className="[--drift-x:-70px] [--drift-y:8px] motion-safe:animate-drift"
          style={{ animationDelay: '-8s', animationDuration: '19s' }}
        >
          <img
            alt=""
            src="/images/cloud.jpg"
            referrerPolicy="no-referrer"
            className="h-auto w-full -scale-x-100"
          />
        </div>
      </div>

      {/* Animated Birds */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 overflow-hidden [--bird-scale:0.7] sm:[--bird-scale:1] z-0"
      >
        {BIRD_CONFIGS.map((bird, idx) => (
          <span
            key={idx}
            className={`absolute left-0 motion-safe:animate-fly ${bird.hideSm ? 'max-sm:hidden' : ''}`}
            style={{
              top: bird.top,
              animationDuration: bird.duration,
              animationDelay: bird.delay,
            }}
          >
            <svg
              viewBox="0 0 40 16"
              fill="currentColor"
              className="block origin-[50%_60%] text-[#27303b]/80 motion-safe:animate-flap"
              style={{
                width: `calc(${bird.w}px * var(--bird-scale))`,
                height: `calc(${bird.h}px * var(--bird-scale))`,
                animationDuration: bird.flapDur,
                animationDelay: bird.flapDelay,
              }}
            >
              <path d="M0 6C6 1 12 1 20 9C28 1 34 1 40 6C33 4 27 6 20 13C13 6 7 4 0 6Z" />
            </svg>
          </span>
        ))}
      </div>

      {/* Bottom Painted Mountain Landscape & Glass Tiles */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 z-0 h-[min(64svh,580px)] motion-safe:animate-intro-settle"
      >
        <div className="relative h-full w-full">
          <img
            alt=""
            src="/images/hero-landscape.jpg"
            referrerPolicy="no-referrer"
            className="fade-top h-full w-full object-cover object-[50%_72%] [--fade:14%]"
          />

          {/* Left Glass Tile Cluster */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute bottom-[6%] -left-[3%]"
            style={
              {
                '--tile': 'clamp(42px, 6.2vw, 90px)',
                '--tile-gap': '3px',
                width: 'calc(4 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))',
                height: 'calc(3 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))',
              } as React.CSSProperties
            }
          >
            {LEFT_GLASS_TILES.map((t, idx) => (
              <span
                key={idx}
                className="absolute motion-safe:animate-pop"
                style={{
                  left: `calc(${t.col} * (var(--tile) + var(--tile-gap)))`,
                  top: `calc(${t.row} * (var(--tile) + var(--tile-gap)))`,
                  width: 'var(--tile)',
                  height: 'var(--tile)',
                  borderRadius: 'calc(var(--tile) * 0.17)',
                  animationDelay: t.popDelay,
                }}
              >
                <span
                  className="glass-tile absolute inset-0 motion-safe:animate-breathe"
                  style={{ borderRadius: 'inherit', animationDelay: t.breatheDelay }}
                />
              </span>
            ))}
          </div>

          {/* Right Glass Tile Cluster */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-[5%] -bottom-[4%]"
            style={
              {
                '--tile': 'clamp(42px, 6.4vw, 96px)',
                '--tile-gap': '3px',
                width: 'calc(4 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))',
                height: 'calc(5 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))',
              } as React.CSSProperties
            }
          >
            {RIGHT_GLASS_TILES.map((t, idx) => (
              <span
                key={idx}
                className="absolute motion-safe:animate-pop"
                style={{
                  left: `calc(${t.col} * (var(--tile) + var(--tile-gap)))`,
                  top: `calc(${t.row} * (var(--tile) + var(--tile-gap)))`,
                  width: 'var(--tile)',
                  height: 'var(--tile)',
                  borderRadius: 'calc(var(--tile) * 0.17)',
                  animationDelay: t.popDelay,
                }}
              >
                <span
                  className="glass-tile absolute inset-0 motion-safe:animate-breathe"
                  style={{ borderRadius: 'inherit', animationDelay: t.breatheDelay }}
                />
              </span>
            ))}
          </div>

          {/* Center Glass Tile Cluster */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute bottom-[16%] left-[41%] max-sm:hidden"
            style={
              {
                '--tile': 'clamp(24px, 3.1vw, 46px)',
                '--tile-gap': '3px',
                width: 'calc(3 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))',
                height: 'calc(3 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))',
              } as React.CSSProperties
            }
          >
            {CENTER_GLASS_TILES.map((t, idx) => (
              <span
                key={idx}
                className="absolute motion-safe:animate-pop"
                style={{
                  left: `calc(${t.col} * (var(--tile) + var(--tile-gap)))`,
                  top: `calc(${t.row} * (var(--tile) + var(--tile-gap)))`,
                  width: 'var(--tile)',
                  height: 'var(--tile)',
                  borderRadius: 'calc(var(--tile) * 0.17)',
                  animationDelay: t.popDelay,
                }}
              >
                <span
                  className="glass-tile absolute inset-0 motion-safe:animate-breathe"
                  style={{ borderRadius: 'inherit', animationDelay: t.breatheDelay }}
                />
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Hero Title */}
      <div className="relative z-10 mx-auto flex w-full max-w-5xl flex-1 flex-col items-center px-5 pt-[clamp(8.5rem,28svh,15.5rem)] pb-[46svh] text-center">
        <h1
          id="hero-title"
          className="font-heading text-[clamp(2.5rem,4.6vw,4.2rem)] leading-[1.14] font-normal tracking-[-0.03em] text-balance text-ink"
        >
          <span className="inline-block motion-safe:animate-intro-words" style={{ animationDelay: '350ms' }}>
            Unleash
          </span>{' '}
          <span className="inline-block motion-safe:animate-intro-words" style={{ animationDelay: '430ms' }}>
            a
          </span>{' '}
          <span className="inline-block motion-safe:animate-intro-words" style={{ animationDelay: '510ms' }}>
            simulated
          </span>{' '}
          <em className="italic text-moss">
            <span className="inline-block motion-safe:animate-intro-words" style={{ animationDelay: '590ms' }}>
              community
            </span>
          </em>{' '}
          <br className="max-md:hidden" />
          <span className="inline-block motion-safe:animate-intro-words" style={{ animationDelay: '670ms' }}>
            before
          </span>{' '}
          <span className="inline-block motion-safe:animate-intro-words" style={{ animationDelay: '750ms' }}>
            real
          </span>{' '}
          <span className="inline-block motion-safe:animate-intro-words" style={{ animationDelay: '830ms' }}>
            users
          </span>{' '}
          <span className="inline-block motion-safe:animate-intro-words" style={{ animationDelay: '910ms' }}>
            collide.
          </span>
        </h1>
      </div>
    </section>
  );
};
