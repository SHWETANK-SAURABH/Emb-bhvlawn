import { useEffect, useState } from 'react';
import { useSimulationStore } from './store/simulationStore';
import { CanvasMap } from './components/CanvasMap';
import { BehaviorExtractor } from './learning/BehaviorExtractor';
import { BoustrophedonPlanner } from './planning/BoustrophedonPlanner';
import { Brain, Settings2, Play, MousePointerClick, RefreshCcw, Activity } from 'lucide-react';

function App() {
  const { mode, setMode, trajectory, learnedRules, setRules, setPath, map, resetMap, isRerouting } = useSimulationStore();
  const [coverage, setCoverage] = useState(0);

  // Update metrics loop
  useEffect(() => {
    const timer = setInterval(() => {
      setCoverage(useSimulationStore.getState().map.getCoveragePercentage());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleExtractRules = () => {
    if (trajectory.length === 0) {
      alert("No trajectory recorded! Drive the mower manually first.");
      return;
    }
    const rules = BehaviorExtractor.extract(trajectory);
    setRules(rules);
    setMode('learning');
  };

  const handlePlanPath = () => {
    if (!learnedRules) {
      alert("No rules learned yet.");
      return;
    }
    const waypoints = BoustrophedonPlanner.plan(
      useSimulationStore.getState().map,
       learnedRules.direction,
       learnedRules.rowSpacing,
       learnedRules.obstacleMargin
    );
    setPath(waypoints);
    setMode('auto');
  };

  const currentRules = useSimulationStore.getState().learnedRules;

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col items-center py-10 font-sans text-slate-800">
      <h1 className="text-3xl font-bold mb-2 text-indigo-700">LawnBot AI Simulator</h1>
      <p className="text-slate-500 mb-8 italic">Imitation Learning via Behavioral Cloning</p>
      
      <div className="flex gap-8 w-full max-w-6xl justify-center">
        {/* LEFT COLUMN: Controls & Metrics */}
        <div className="flex flex-col gap-6 w-[350px]">

          {/* Algorithm Status Badge */}
          {(() => {
            const info = mode === 'manual'
              ? { label: 'Manual Control',          algo: 'Keyboard / WASD input',          icon: '🎮', color: 'border-indigo-300 bg-indigo-50', badge: 'bg-indigo-600 text-white',    pulse: false }
              : mode === 'learning'
              ? { label: 'Behavioral Cloning',      algo: 'Imitation Learning (extracting rules)', icon: '🧠', color: 'border-amber-300 bg-amber-50',  badge: 'bg-amber-500 text-white',     pulse: false }
              : isRerouting
              ? { label: 'A* Pathfinding',          algo: 'Shortest-path obstacle rerouting',  icon: '🔀', color: 'border-orange-300 bg-orange-50', badge: 'bg-orange-500 text-white',    pulse: true  }
              : { label: 'Pure Pursuit',            algo: 'Boustrophedon coverage planning',   icon: '🤖', color: 'border-green-300 bg-green-50',  badge: 'bg-green-600 text-white',     pulse: false };
            return (
              <div className={`p-4 rounded-xl border-2 ${info.color} flex items-center gap-4`}>
                <div className="relative flex-shrink-0">
                  {info.pulse && (
                    <span className="absolute inset-0 rounded-full bg-orange-400 opacity-75 animate-ping" />
                  )}
                  <div className={`relative w-10 h-10 rounded-full ${info.badge} flex items-center justify-center text-lg`}>
                    {info.icon}
                  </div>
                </div>
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold">Active Algorithm</p>
                  <p className="font-bold text-slate-800 text-sm">{info.label}</p>
                  <p className="text-xs text-slate-500">{info.algo}</p>
                </div>
              </div>
            );
          })()}
          
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2"><Settings2 className="w-5 h-5 text-indigo-600"/> Dashboard</h2>
            <div className="flex flex-col gap-4">
              
              <button 
                className={`py-2 px-4 rounded font-medium flex gap-2 justify-center items-center transition ${mode === 'manual' ? 'bg-indigo-600 text-white shadow' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                onClick={() => setMode('manual')}
              >
                 <MousePointerClick className="w-4 h-4"/> 1. Manual Drive
              </button>

              <button 
                className={`py-2 px-4 rounded font-medium flex gap-2 justify-center items-center transition ${mode === 'learning' ? 'bg-amber-500 text-white shadow' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                onClick={handleExtractRules}
              >
                  <Brain className="w-4 h-4"/> 2. Extract AI Rules
              </button>

              <button 
                className={`py-2 px-4 rounded font-medium flex gap-2 justify-center items-center transition ${mode === 'auto' ? 'bg-green-600 text-white shadow' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                onClick={handlePlanPath}
                disabled={!currentRules}
              >
                 <Play className="w-4 h-4"/> 3. Autonomous Run
              </button>

              <button 
                className="py-2 px-4 mt-4 rounded border border-slate-300 text-slate-500 hover:bg-slate-50 flex gap-2 justify-center items-center transition"
                onClick={() => resetMap(50, 50, 0.5)}
              >
                  <RefreshCcw className="w-4 h-4"/> Reset Map
              </button>
            </div>
          </div>

          {currentRules && (
            <div className="bg-white p-6 rounded-xl shadow-sm border border-amber-200">
              <h2 className="text-lg font-semibold mb-4 text-amber-600 flex items-center gap-2"><Brain className="w-5 h-5"/> Learned Rules</h2>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between items-center border-b pb-2">
                  <span className="text-slate-500">Direction Preference:</span>
                  <span className="font-bold text-slate-700 uppercase">{currentRules.direction}</span>
                </div>
                <div className="flex justify-between items-center border-b pb-2">
                  <span className="text-slate-500">Row Spacing:</span>
                  <span className="font-bold text-slate-700">{currentRules.rowSpacing.toFixed(1)}m</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Obstacle Distance:</span>
                  <span className="font-bold text-slate-700">{currentRules.obstacleMargin.toFixed(1)}m</span>
                </div>
              </div>
            </div>
          )}

          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
             <h2 className="text-lg font-semibold mb-4 flex items-center gap-2"><Activity className="w-5 h-5 text-indigo-600"/> Metrics</h2>
             <div className="flex items-end justify-between">
                <span className="text-slate-500 text-sm">Coverage Area</span>
                <span className="text-2xl font-bold text-green-600">{coverage.toFixed(1)}%</span>
             </div>
             <div className="w-full bg-slate-200 h-2 mt-2 rounded overflow-hidden">
                <div className="bg-green-500 h-full transition-all duration-500" style={{ width: `${coverage}%`}}></div>
             </div>
             
             <div className="mt-4 flex flex-col gap-2 text-sm text-slate-500">
               <div>Data Points: <span className="font-bold text-slate-700">{trajectory.length}</span> recorded</div>
               <div>Map Size: <span className="font-bold text-slate-700">{map.width * map.resolution}m x {map.height * map.resolution}m</span></div>
             </div>
          </div>
          
        </div>

        {/* RIGHT COLUMN: Canvas */}
        <div className="flex flex-col">
          <CanvasMap />
        </div>

      </div>
    </div>
  );
}

export default App;
