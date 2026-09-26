'use client';

import React, { useState, useEffect } from 'react';
import { Scene3D } from '@/components/Scene3D';
import { OverlayUI } from '@/components/OverlayUI';
import { GazeCloudManager } from '@/components/GazeCloudManager';

export default function Home() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <main className="relative w-screen h-screen overflow-hidden bg-slate-950 font-sans antialiased select-none">
      <GazeCloudManager />
      <OverlayUI />
      <Scene3D />
      
      {/* Starting overlay if pointer is not locked */}
      <div className="absolute inset-0 z-40 flex items-center justify-center pointer-events-none group">
        <div className="bg-slate-900/90 text-white px-6 py-4 rounded-2xl border border-slate-700 shadow-2xl backdrop-blur transition-opacity duration-300 opacity-100 group-has-[:focus-visible]:opacity-0">
          <p className="text-center font-semibold mb-1">Click vào màn hình để bắt đầu</p>
          <p className="text-xs text-slate-400 text-center">Di chuyển chuột để nhìn xung quanh (Mô phỏng ánh nhìn)</p>
        </div>
      </div>
    </main>
  );
}
