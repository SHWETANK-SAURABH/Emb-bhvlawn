import React, { useRef, useEffect } from 'react';
import { useSimulationStore } from '../store/simulationStore';
import { PhysicsEngine, DEFAULT_CONFIG } from '../simulation/PhysicsEngine';
import { PurePursuitController } from '../planning/PurePursuitController';
import { AStar } from '../planning/AStar';
import type { Waypoint } from '../planning/BoustrophedonPlanner';

const METER_TO_PIXEL = 10; // 1 meter = 10 pixels
const BOUNDARY_MARGIN = 0.6; // meters — how close to the edge the mower can get

export const CanvasMap: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const {
    mode, map,
    addTrajectoryPoint, updateMower, addObstacle,
  } = useSimulationStore();

  // High-frequency refs — avoided in Zustand to not trigger re-renders on every frame
  const inputRef       = useRef({ throttle: 0, steerTarget: 0 });
  const timeRef        = useRef<number>(performance.now());
  const physicsEngine  = useRef(new PhysicsEngine(DEFAULT_CONFIG));
  const pursuitCtrl    = useRef(new PurePursuitController(1.5)); // 1.5m lookahead

  // A* rerouting refs
  const isReroutingRef       = useRef(false);
  const reroutePathRef       = useRef<Waypoint[]>([]);
  const rerouteResumeIdxRef  = useRef(0);

  // Anti-stuck refs
  const stuckCounterRef      = useRef(0);  // frames near-zero velocity
  const backingUpRef         = useRef(0);  // countdown: frames left in backup maneuver
  const rerouteCooldownRef   = useRef(0); // countdown: frames before A* can retry

  // Reset controller & rerouting state whenever we switch to auto
  useEffect(() => {
    if (mode === 'auto') {
      pursuitCtrl.current.reset();
      isReroutingRef.current      = false;
      reroutePathRef.current      = [];
      rerouteResumeIdxRef.current = 0;
      useSimulationStore.getState().setRerouting(false);
    }
  }, [mode]);

  // ── Keyboard controls (manual mode only) ─────────────────────────────────
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (mode !== 'manual') return;
      if (e.key === 'w' || e.key === 'ArrowUp')    inputRef.current.throttle    =  1;
      if (e.key === 's' || e.key === 'ArrowDown')  inputRef.current.throttle    = -1;
      if (e.key === 'a' || e.key === 'ArrowLeft')  inputRef.current.steerTarget = -1;
      if (e.key === 'd' || e.key === 'ArrowRight') inputRef.current.steerTarget =  1;
    };
    const up = (e: KeyboardEvent) => {
      if (mode !== 'manual') return;
      if (e.key === 'w' || e.key === 'ArrowUp'   || e.key === 's' || e.key === 'ArrowDown')
        inputRef.current.throttle    = 0;
      if (e.key === 'a' || e.key === 'ArrowLeft' || e.key === 'd' || e.key === 'ArrowRight')
        inputRef.current.steerTarget = 0;
    };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup',   up);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  }, [mode]);

  // ── Click-to-add-obstacle ─────────────────────────────────────────────────
  const handleMapClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    addObstacle(
      (e.clientX - rect.left)  / METER_TO_PIXEL,
      (e.clientY - rect.top)   / METER_TO_PIXEL,
      1.0
    );
  };

  // ── Main game loop ────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const gameLoop = (timestamp: number) => {
      const dt = (timestamp - timeRef.current) / 1000;
      timeRef.current = timestamp;

      const s = useSimulationStore.getState(); // snapshot — avoids stale closures
      let nextMower = { ...s.mower };

      // ── Physics + control ─────────────────────────────────────────────
      if (dt > 0 && dt < 0.1) {
        let cmd = { ...inputRef.current };

        if (s.mode === 'auto') {

          // ── 0. Skip any boustrophedon waypoints that sit inside obstacles ──────
          if (!isReroutingRef.current && s.plannedPath.length > 0) {
            let idx = pursuitCtrl.current.getWaypointIndex();
            while (idx < s.plannedPath.length - 1 && s.map.isObstacle(s.plannedPath[idx].x, s.plannedPath[idx].y)) {
              idx++;
              pursuitCtrl.current.setWaypointIndex(idx);
            }
          }

          // ── 1. Stuck detection — increment when velocity is near-zero ─────────
          if (Math.abs(s.mower.v) < 0.08) {
            stuckCounterRef.current++;
          } else {
            stuckCounterRef.current = 0;
          }

          // Tick down cooldowns
          if (rerouteCooldownRef.current > 0) rerouteCooldownRef.current--;

          // ── 2. Backup maneuver — highest priority, overrides everything ────────
          if (backingUpRef.current > 0) {
            backingUpRef.current--;
            // Oscillate turn direction while reversing to escape corners
            const turnSign = Math.sin(backingUpRef.current * 0.35) >= 0 ? 1 : -1;
            cmd = { throttle: -0.9, steerTarget: turnSign * 0.9 };

          } else if (stuckCounterRef.current > 70) {
            // ── 3. Trigger backup when stuck for ~1.2 s (≈70 frames @ 60 fps) ───
            stuckCounterRef.current    = 0;
            backingUpRef.current       = 50; // ~0.85 s of backup
            rerouteCooldownRef.current = 40;
            // Cancel a reroute that clearly isn't working
            if (isReroutingRef.current) {
              isReroutingRef.current = false;
              reroutePathRef.current = [];
              // Jump past the problem zone
              pursuitCtrl.current.setWaypointIndex(
                Math.min(rerouteResumeIdxRef.current + 6, s.plannedPath.length - 1)
              );
              s.setRerouting(false);
            }
            const turnSign = Date.now() % 1000 < 500 ? 1 : -1;
            cmd = { throttle: -0.9, steerTarget: turnSign * 0.9 };

          } else {
            // ── 4. Normal auto navigation ─────────────────────────────────────

            // Multi-point obstacle probe: centre + 25° left/right fans
            const cx  = s.mower.x, cy  = s.mower.y, th = s.mower.theta;
            const obstacleAhead =
              s.map.isObstacle(cx + Math.cos(th)        * 2.0, cy + Math.sin(th)        * 2.0) ||
              s.map.isObstacle(cx + Math.cos(th - 0.44) * 1.8, cy + Math.sin(th - 0.44) * 1.8) ||
              s.map.isObstacle(cx + Math.cos(th + 0.44) * 1.8, cy + Math.sin(th + 0.44) * 1.8);

            // Re-reroute trigger (not already rerouting, cooldown expired)
            if (obstacleAhead && !isReroutingRef.current &&
                rerouteCooldownRef.current === 0 && s.plannedPath.length > 0) {

              const currentIdx = pursuitCtrl.current.getWaypointIndex();
              let found = false;

              // Scan forward to find the nearest reachable (non-obstacle) target
              for (let skip = 8; skip <= 40; skip += 4) {
                const targetIdx = Math.min(currentIdx + skip, s.plannedPath.length - 1);
                const goal = s.plannedPath[targetIdx];
                if (s.map.isObstacle(goal.x, goal.y)) continue; // goal is blocked — try further

                const astarPath = AStar.findPath(s.map, { x: s.mower.x, y: s.mower.y }, goal);
                if (astarPath.length > 0) {
                  reroutePathRef.current      = astarPath;
                  rerouteResumeIdxRef.current = targetIdx;
                  pursuitCtrl.current.reset();
                  isReroutingRef.current = true;
                  s.setRerouting(true);
                  found = true;
                  break;
                }
              }

              if (!found) {
                // Every reachable target is blocked — back up and cool down
                backingUpRef.current       = 50;
                rerouteCooldownRef.current = 80;
              }
            }

            // Allow re-reroute if the A* detour itself hits a NEW obstacle
            if (isReroutingRef.current && rerouteCooldownRef.current === 0) {
              const cx2 = s.mower.x, cy2 = s.mower.y, th2 = s.mower.theta;
              if (s.map.isObstacle(cx2 + Math.cos(th2) * 2.0, cy2 + Math.sin(th2) * 2.0)) {
                // Abort current reroute, cooldown, let the main re-route logic pick a new path
                isReroutingRef.current = false;
                reroutePathRef.current = [];
                pursuitCtrl.current.setWaypointIndex(rerouteResumeIdxRef.current);
                rerouteCooldownRef.current = 30;
                s.setRerouting(false);
              }
            }

            // Reroute complete — resume original path
            if (isReroutingRef.current &&
                pursuitCtrl.current.getWaypointIndex() >= reroutePathRef.current.length) {
              isReroutingRef.current = false;
              reroutePathRef.current = [];
              pursuitCtrl.current.setWaypointIndex(rerouteResumeIdxRef.current);
              s.setRerouting(false);
            }

            const activePath = isReroutingRef.current ? reroutePathRef.current : s.plannedPath;
            cmd = pursuitCtrl.current.computeCommand(s.mower, activePath, DEFAULT_CONFIG);
          }

        } else {
          // Manual / learning: simple front-obstacle bounce
          const frontX = nextMower.x + Math.cos(nextMower.theta) * 1.5;
          const frontY = nextMower.y + Math.sin(nextMower.theta) * 1.5;
          if (s.map.isObstacle(frontX, frontY)) {
            cmd = { throttle: -0.5, steerTarget: cmd.steerTarget };
          }
        }

        nextMower = physicsEngine.current.step(s.mower, cmd, dt);

        // ── Boundary enforcement (hard lawn edge) ────────────────────
        const mapMaxX = s.map.width  * s.map.resolution;
        const mapMaxY = s.map.height * s.map.resolution;

        if (nextMower.x < BOUNDARY_MARGIN) {
          nextMower.x = BOUNDARY_MARGIN;
          nextMower.v = Math.max(0, nextMower.v);
        }
        if (nextMower.x > mapMaxX - BOUNDARY_MARGIN) {
          nextMower.x = mapMaxX - BOUNDARY_MARGIN;
          nextMower.v = Math.min(0, nextMower.v);
        }
        if (nextMower.y < BOUNDARY_MARGIN) {
          nextMower.y = BOUNDARY_MARGIN;
          nextMower.v = Math.max(0, nextMower.v);
        }
        if (nextMower.y > mapMaxY - BOUNDARY_MARGIN) {
          nextMower.y = mapMaxY - BOUNDARY_MARGIN;
          nextMower.v = Math.min(0, nextMower.v);
        }

        updateMower(nextMower);

        if (s.mode === 'manual' && cmd.throttle !== 0) {
          addTrajectoryPoint({ x: nextMower.x, y: nextMower.y, theta: nextMower.theta, v: nextMower.v, timestamp });
        }
      }

      // ── Render ────────────────────────────────────────────────────────────
      const s2 = useSimulationStore.getState(); // re-read after state update
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Grid cells
      const resPx = s2.map.resolution * METER_TO_PIXEL;
      for (let y = 0; y < s2.map.height; y++) {
        for (let x = 0; x < s2.map.width; x++) {
          const val = s2.map.grid[y][x];
          ctx.fillStyle = val === 1 ? '#a3e635' : val === 2 ? '#ef4444' : '#22c55e';
          ctx.fillRect(x * resPx, y * resPx, resPx, resPx);
        }
      }

      // Grid lines
      ctx.strokeStyle = '#15803d';
      ctx.lineWidth = 0.5;
      for (let y = 0; y <= s2.map.height; y++) {
        ctx.beginPath(); ctx.moveTo(0, y * resPx); ctx.lineTo(canvas.width, y * resPx); ctx.stroke();
      }
      for (let x = 0; x <= s2.map.width; x++) {
        ctx.beginPath(); ctx.moveTo(x * resPx, 0); ctx.lineTo(x * resPx, canvas.height); ctx.stroke();
      }

      // Original boustrophedon path (dashed blue; greyed-out while A* rerouting)
      if (s2.plannedPath.length > 0 && s2.mode === 'auto') {
        ctx.strokeStyle = isReroutingRef.current ? '#94a3b8' : '#3b82f6';
        ctx.lineWidth   = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(s2.plannedPath[0].x * METER_TO_PIXEL, s2.plannedPath[0].y * METER_TO_PIXEL);
        for (let i = 1; i < s2.plannedPath.length; i++) {
          ctx.lineTo(s2.plannedPath[i].x * METER_TO_PIXEL, s2.plannedPath[i].y * METER_TO_PIXEL);
        }
        ctx.stroke();
        ctx.setLineDash([]);

        // Waypoint dots
        ctx.fillStyle = isReroutingRef.current ? '#cbd5e1' : '#1d4ed8';
        s2.plannedPath.forEach(pt => {
          ctx.beginPath();
          ctx.arc(pt.x * METER_TO_PIXEL, pt.y * METER_TO_PIXEL, 2, 0, Math.PI * 2);
          ctx.fill();
        });
      }

      // A* reroute path (solid orange — shown on top of the blue path)
      if (isReroutingRef.current && reroutePathRef.current.length > 0) {
        const rp = reroutePathRef.current;
        ctx.strokeStyle = '#f97316';
        ctx.lineWidth   = 3;
        ctx.beginPath();
        ctx.moveTo(rp[0].x * METER_TO_PIXEL, rp[0].y * METER_TO_PIXEL);
        for (let i = 1; i < rp.length; i++) {
          ctx.lineTo(rp[i].x * METER_TO_PIXEL, rp[i].y * METER_TO_PIXEL);
        }
        ctx.stroke();
        ctx.fillStyle = '#fb923c';
        rp.forEach(pt => {
          ctx.beginPath();
          ctx.arc(pt.x * METER_TO_PIXEL, pt.y * METER_TO_PIXEL, 4, 0, Math.PI * 2);
          ctx.fill();
        });
      }

      // ── Lawn fence / boundary ─────────────────────────────────────────
      // Outer rail
      ctx.strokeStyle = '#92400e';
      ctx.lineWidth   = 5;
      ctx.strokeRect(2, 2, canvas.width - 4, canvas.height - 4);
      // Inner rail
      ctx.strokeStyle = '#b45309';
      ctx.lineWidth   = 2;
      ctx.strokeRect(7, 7, canvas.width - 14, canvas.height - 14);
      // Fence posts
      const postSize    = 8;
      const postSpacing = 50;
      ctx.fillStyle = '#78350f';
      for (let px = 0; px <= canvas.width; px += postSpacing) {
        ctx.fillRect(px - postSize / 2, 0,                     postSize, postSize);
        ctx.fillRect(px - postSize / 2, canvas.height - postSize, postSize, postSize);
      }
      for (let py = postSpacing; py < canvas.height; py += postSpacing) {
        ctx.fillRect(0,                    py - postSize / 2, postSize, postSize);
        ctx.fillRect(canvas.width - postSize, py - postSize / 2, postSize, postSize);
      }

      // ── Mower sprite ─────────────────────────────────────────────────
      const mx = nextMower.x * METER_TO_PIXEL;
      const my = nextMower.y * METER_TO_PIXEL;
      ctx.save();
      ctx.translate(mx, my);
      ctx.rotate(nextMower.theta);
      ctx.fillStyle = '#f97316'; // body
      ctx.fillRect(-10, -8, 20, 16);
      ctx.fillStyle = '#facc15'; // front direction marker
      ctx.fillRect(6, -4, 4, 8);
      ctx.restore();

      animId = requestAnimationFrame(gameLoop);
    };

    animId = requestAnimationFrame(gameLoop);
    return () => cancelAnimationFrame(animId);
  }, []); // stable — reads store via getState() inside the loop

  return (
    <div className="relative">
      <canvas
        ref={canvasRef}
        width={map.width  * map.resolution * METER_TO_PIXEL}
        height={map.height * map.resolution * METER_TO_PIXEL}
        className="rounded shadow-xl border-4 border-yellow-900 cursor-crosshair"
        onClick={handleMapClick}
      />
      {mode === 'manual' && (
        <div className="absolute top-4 left-4 text-white bg-black/60 px-3 py-2 rounded-lg text-xs pointer-events-none">
          🎮 <strong>WASD / Arrows</strong> to drive<br />
          🖱️ <strong>Click</strong> to drop obstacles
        </div>
      )}
    </div>
  );
};
