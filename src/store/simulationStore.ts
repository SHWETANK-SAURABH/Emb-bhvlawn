import { create } from 'zustand';
import { MapGrid } from '../simulation/MapGrid';
import type { MowerState } from '../simulation/PhysicsEngine';

export interface TrajectoryPoint {
  x: number;
  y: number;
  theta: number;
  v: number;
  timestamp: number;
}

export type Mode = 'manual' | 'learning' | 'auto';

interface SimulationState {
  mode: Mode;
  mower: MowerState;
  map: MapGrid; // A simplified instance or reactive wrapper. In Zustand we usually want immutable, but for per-frame 60Hz games we often mutate refs. For React rendering we can shallow copy or trigger discrete updates.
  trajectory: TrajectoryPoint[];
  learnedRules: {
    direction: 'horizontal' | 'vertical';
    rowSpacing: number;
    obstacleMargin: number;
  } | null;
  timeElapsed: number; // in seconds
  plannedPath: { x: number; y: number }[];
  isRerouting: boolean; // true when A* is actively rerouting around an obstacle
  
  // Actions
  setMode: (mode: Mode) => void;
  updateMower: (mower: MowerState) => void;
  addTrajectoryPoint: (point: TrajectoryPoint) => void;
  resetMap: (width: number, height: number, resolution: number) => void;
  addObstacle: (x: number, y: number, radius: number) => void;
  setRules: (rules: { direction: 'horizontal' | 'vertical'; rowSpacing: number; obstacleMargin: number }) => void;
  setPath: (path: { x: number; y: number }[]) => void;
  setRerouting: (v: boolean) => void;
}

export const useSimulationStore = create<SimulationState>((set) => ({
  mode: 'manual',
  mower: { x: 5, y: 5, theta: 0, v: 0, steering: 0 },
  map: new MapGrid(50, 50, 0.5), // Default 50x50 meters yard
  trajectory: [],
  learnedRules: null,
  timeElapsed: 0,
  plannedPath: [],
  isRerouting: false,

  setMode: (mode) => set({ mode }),
  updateMower: (mower) => set((state) => {
    // Note: Reacting to 60fps updates via Zustand will be heavy. We may optimize by using transient updates or a ref for the canvas, but Zustand is fine for a lightweight demo.
    state.map.updateCoverage(mower.x, mower.y, 1.0); // Assuming 1.0m cutting radius
    return { mower, map: state.map }; // Map ref remains identical, we manually trigger if we need coverage UI updates or let a loop handle it.
  }),
  addTrajectoryPoint: (point) => set((state) => ({ trajectory: [...state.trajectory, point] })),
  resetMap: (width, height, resolution) => set({
    map: new MapGrid(width, height, resolution),
    trajectory: [],
    mower: { x: 5, y: 5, theta: 0, v: 0, steering: 0 },
    plannedPath: [],
    timeElapsed: 0,
  }),
  addObstacle: (x, y, radius) => set((state) => {
    state.map.addObstacle(x, y, radius);
    return { map: state.map };
  }),
  setRules: (rules) => set({ learnedRules: rules }),
  setPath: (path) => set({ plannedPath: path }),
  setRerouting: (isRerouting) => set({ isRerouting }),
}));
