import { create } from 'zustand';

export interface TargetObject {
  id: string;
  name: string;
  position: [number, number, number];
  color: string;
  geometry: 'box' | 'cylinder' | 'sphere';
  isGrasped: boolean;
  graspProgress: number;
}

export interface GazeState {
  x: number;
  y: number;
  velocity: number;
  label: number;
  labelName: string;
  isConnected: boolean;
  isWebcamMode: boolean;
  screenGaze: { x: number, y: number }; // Normalized Device Coordinates [-1, 1] for 3D Raycasting
  targets: TargetObject[];
  activeHoverTargetId: string | null;
  graspedTargetId: string | null;
  isCalibrated: boolean;
  robotPosition: [number, number, number]; // target position for robot arm
  
  setGazeData: (x: number, y: number, velocity: number, label: number, labelName: string) => void;
  setConnected: (connected: boolean) => void;
  setWebcamMode: (mode: boolean) => void;
  setCalibrated: (calibrated: boolean) => void;
  setScreenGaze: (x: number, y: number) => void;
  setHoverTarget: (id: string | null) => void;
  updateTargetGraspProgress: (id: string, progress: number, isGrasped: boolean) => void;
  resetAllTargets: () => void;
}

export const useGazeStore = create<GazeState>((set) => ({
  x: 0.5,
  y: 0.5,
  velocity: 0,
  label: 0,
  labelName: 'Fixation',
  isConnected: false,
  isWebcamMode: false,
  isCalibrated: false,
  screenGaze: { x: 0, y: 0 },
  robotPosition: [2, 2.5, -3], // default rest position
  targets: [
    { id: 'obj-1', name: 'Red Box', position: [-2, 0.5, -2], color: '#ef4444', geometry: 'box', isGrasped: false, graspProgress: 0 },
    { id: 'obj-2', name: 'Blue Sphere', position: [0, 0.5, -3], color: '#3b82f6', geometry: 'sphere', isGrasped: false, graspProgress: 0 },
    { id: 'obj-3', name: 'Green Cylinder', position: [2, 0.5, -2], color: '#10b981', geometry: 'cylinder', isGrasped: false, graspProgress: 0 },
  ],
  activeHoverTargetId: null,
  graspedTargetId: null,
  
  setGazeData: (x, y, velocity, label, labelName) => set({ x, y, velocity, label, labelName }),
  setConnected: (connected) => set({ isConnected: connected }),
  setWebcamMode: (mode) => set({ isWebcamMode: mode }),
  setCalibrated: (calibrated) => set({ isCalibrated: calibrated }),
  setScreenGaze: (x, y) => set({ screenGaze: { x, y } }),
  setHoverTarget: (id) => set({ activeHoverTargetId: id }),
  updateTargetGraspProgress: (id, progress, isGrasped) => 
    set((state) => {
      let robotPos = state.robotPosition;
      if (isGrasped) {
        const target = state.targets.find((t) => t.id === id);
        if (target) {
           robotPos = [target.position[0], target.position[1] + 1.5, target.position[2]]; // Move robot above target
        }
      }
      return {
        targets: state.targets.map((t) => t.id === id ? { ...t, graspProgress: progress, isGrasped } : t),
        graspedTargetId: isGrasped ? id : state.graspedTargetId,
        robotPosition: isGrasped ? robotPos : state.robotPosition,
      };
    }),
  resetAllTargets: () => 
    set((state) => ({
      targets: state.targets.map((t) => ({ ...t, isGrasped: false, graspProgress: 0 })),
      graspedTargetId: null,
      robotPosition: [2, 2.5, -3],
    }))
}));
