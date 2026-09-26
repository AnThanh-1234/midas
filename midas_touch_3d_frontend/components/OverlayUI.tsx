'use client';

import React from 'react';
import { useGazeStore } from '../store/useGazeStore';
import { Activity, ShieldCheck, ShieldAlert, Cpu, Eye, Zap } from 'lucide-react';

export const OverlayUI: React.FC = () => {
  const { x, y, velocity, label, labelName, isConnected, graspedTargetId, targets, resetAllTargets, isWebcamMode, setWebcamMode, screenGaze, isGazeCloudLoaded } = useGazeStore();

  const getLabelBadge = () => {
    switch (label) {
      case 0:
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 animate-pulse">
            <Zap className="w-3.5 h-3.5 fill-emerald-400" /> Label 0: Fixation (GRASP)
          </span>
        );
      case 1:
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/40">
            <Eye className="w-3.5 h-3.5" /> Label 1: Smooth Pursuit (IGNORE)
          </span>
        );
      case 2:
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40">
            <Activity className="w-3.5 h-3.5" /> Label 2: Saccade (IGNORE)
          </span>
        );
      default:
        return null;
    }
  };

  const graspedTarget = targets.find((t) => t.id === graspedTargetId);
  const activeHoverTarget = targets.find((t) => t.id === useGazeStore.getState().activeHoverTargetId);

  return (
    <div className="absolute inset-0 pointer-events-none flex flex-col justify-between p-6 z-50">
      {/* Top Header */}
      <div className="flex justify-end items-start w-full">

        {/* Realtime Metrics */}
        <div className="bg-slate-900/80 backdrop-blur-md border border-slate-700/50 p-4 rounded-2xl shadow-xl flex flex-col gap-3 min-w-[250px] pointer-events-auto">
          <div className="flex justify-between items-center text-xs">
            <span className="text-slate-400">Gaze X, Y:</span>
            <span className="font-mono text-slate-200">{x.toFixed(3)}, {y.toFixed(3)}</span>
          </div>
          <div className="flex justify-between items-center text-xs">
            <span className="text-slate-400">Vận Tốc (v):</span>
            <span className="font-mono text-cyan-400 font-bold">{velocity.toFixed(3)} px/s</span>
          </div>
          <div className="flex justify-between items-center mt-1">
            {getLabelBadge()}
          </div>
          <div className="flex items-center justify-between text-xs mt-2 pt-2 border-t border-slate-700/50">
            <span className="text-slate-400">Eye Tracking:</span>
            <button 
              onClick={() => setWebcamMode(!isWebcamMode)}
              disabled={!isGazeCloudLoaded && !isWebcamMode}
              className={`px-2 py-1 rounded transition-colors pointer-events-auto ${
                !isGazeCloudLoaded && !isWebcamMode
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                  : isWebcamMode 
                    ? 'bg-emerald-500 hover:bg-emerald-400 text-white' 
                    : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
              }`}
            >
              {!isGazeCloudLoaded && !isWebcamMode ? 'Đang tải AI...' : (isWebcamMode ? 'Webcam (Bật)' : 'Chuột (Giữa màn hình)')}
            </button>
          </div>
        </div>
      </div>

      {/* Crosshair (Center or WebGazer position) */}
      <div 
        className="absolute pointer-events-none -translate-x-1/2 -translate-y-1/2"
        style={isWebcamMode 
            ? { left: `${(screenGaze.x + 1) * 50}%`, top: `${(-screenGaze.y + 1) * 50}%` }
            : { left: '50%', top: '50%' }}
      >
        <div className={`w-4 h-4 rounded-full transition-all duration-75 ${
            label === 0 ? 'bg-emerald-500 scale-150 shadow-[0_0_15px_#10b981]' : 
            'bg-red-500 shadow-[0_0_10px_#ef4444]'
        }`} />
        
        {/* Progress ring if hovering */}
        {activeHoverTarget && !activeHoverTarget.isGrasped && (
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-10">
            <svg className="w-full h-full -rotate-90">
              <circle cx="20" cy="20" r="18" className="stroke-slate-700 fill-none" strokeWidth="2" />
              <circle cx="20" cy="20" r="18" className="stroke-emerald-400 fill-none transition-all duration-75" strokeWidth="2" strokeDasharray="113" strokeDashoffset={113 - (113 * activeHoverTarget.graspProgress) / 100} />
            </svg>
          </div>
        )}
      </div>

      {/* Bottom Status */}
      <div className="flex justify-center mt-auto pointer-events-auto">
        <div className="bg-slate-900/80 backdrop-blur-md border border-slate-700/50 px-6 py-3 rounded-2xl shadow-xl flex items-center gap-4">
           {graspedTarget ? (
              <>
                <ShieldCheck className="w-6 h-6 text-emerald-400" />
                <div>
                  <div className="text-sm font-bold text-emerald-400">Đã gắp an toàn: {graspedTarget.name}</div>
                  <div className="text-[10px] text-slate-400 uppercase tracking-wide">Không có Midas Touch</div>
                </div>
                <button 
                  onClick={resetAllTargets}
                  className="ml-4 text-xs bg-slate-800 hover:bg-slate-700 text-white px-3 py-1.5 rounded-lg border border-slate-600 transition-colors"
                >
                  Reset Cảnh
                </button>
              </>
            ) : (
              <>
                <ShieldAlert className="w-6 h-6 text-amber-400" />
                <div>
                  <div className="text-sm font-bold text-slate-200">Hệ Thống Sẵn Sàng</div>
                  <div className="text-[10px] text-slate-400 uppercase tracking-wide">Robot chờ lệnh (Fixation &gt; 0.8s)</div>
                </div>
              </>
            )}
        </div>
      </div>
    </div>
  );
};
