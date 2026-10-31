/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState } from 'react';
import { Navbar } from './components/Navbar';
import { HeroSection } from './components/HeroSection';
import { ProofSection } from './components/ProofSection';
import { WorkflowSection } from './components/WorkflowSection';
import { OversightSection } from './components/OversightSection';
import { DashboardSection } from './components/DashboardSection';
import { ValueSection } from './components/ValueSection';
import { CtaAndFooter } from './components/CtaAndFooter';

export default function App() {
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
        <HeroSection />
        <ProofSection />
        <WorkflowSection />
        <OversightSection />
        <DashboardSection />
        <ValueSection onOpenCliModal={() => setIsCliModalOpen(true)} />
      </main>

      <CtaAndFooter
        isCliModalOpen={isCliModalOpen}
        onOpenCliModal={() => setIsCliModalOpen(true)}
        onCloseCliModal={() => setIsCliModalOpen(false)}
      />
    </div>
  );
}
