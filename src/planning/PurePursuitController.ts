import type { MowerState, MowerConfig } from '../simulation/PhysicsEngine';
import type { Waypoint } from './BoustrophedonPlanner';

// Pure Pursuit algorithm for smooth path tracking of kinematic models
export class PurePursuitController {
  private lookaheadDistance: number;
  private currentWaypointIndex: number = 0;

  constructor(lookaheadDistance: number = 1.0) {
    this.lookaheadDistance = lookaheadDistance;
  }

  public reset(): void {
    this.currentWaypointIndex = 0;
  }

  public getWaypointIndex(): number {
    return this.currentWaypointIndex;
  }

  public setWaypointIndex(idx: number): void {
    this.currentWaypointIndex = idx;
  }

  // Returns { throttle, steerTarget }
  public computeCommand(mower: MowerState, path: Waypoint[], config: MowerConfig): { throttle: number, steerTarget: number } {
    if (path.length === 0 || this.currentWaypointIndex >= path.length) {
      return { throttle: 0, steerTarget: 0 }; // STOP
    }

    // Goal is to find the point on the path that is `lookaheadDistance` away
    let target = path[this.currentWaypointIndex];
    let dist = Math.hypot(target.x - mower.x, target.y - mower.y);

    // If we've reached the current waypoint within a tolerance, move to next
    if (dist < this.lookaheadDistance) {
      this.currentWaypointIndex++;
      if (this.currentWaypointIndex >= path.length) {
        return { throttle: 0, steerTarget: 0 }; // Reached end
      }
      target = path[this.currentWaypointIndex];
    }

    // Alpha is the angle to the lookahead point from the mower's heading
    const angleToTarget = Math.atan2(target.y - mower.y, target.x - mower.x);
    let alpha = angleToTarget - mower.theta;
    
    // Normalize alpha
    alpha = Math.atan2(Math.sin(alpha), Math.cos(alpha));

    // Calculate steering angle based on Pure Pursuit kinematic geometry
    // steer = atan( (2 * L * sin(alpha)) / lookahead_distance )
    const steerRaw = Math.atan( (2 * config.wheelbase * Math.sin(alpha)) / this.lookaheadDistance );
    
    // Normalize to [-1, 1] for our physics engine interface
    let steerTarget = steerRaw / config.maxSteer;
    steerTarget = Math.max(-1, Math.min(1, steerTarget));

    // Slow down on sharp turns
    let throttle = 1.0;
    if (Math.abs(alpha) > Math.PI / 4) {
      throttle = 0.5; // slow down for sharp corner
    }

    return { throttle, steerTarget };
  }
}
