// Physics engine implementation based on the Kinematic Bicycle Model
// This ensures realistic movement and cornering.

export interface MowerState {
  x: number;          // X position (meters or world units)
  y: number;          // Y position
  theta: number;      // Heading angle in radians
  v: number;          // Velocity (units per second)
  steering: number;   // Steering angle in radians
}

export interface MowerConfig {
  wheelbase: number;      // Distance between front and rear axles
  maxSpeed: number;
  maxReverseSpeed: number;
  maxSteer: number;       // Maximum steering angle
  acceleration: number;   // Acceleration rate
  deceleration: number;   // Braking / friction rate
}

export const DEFAULT_CONFIG: MowerConfig = {
  wheelbase: 2.0,
  maxSpeed: 5.0,
  maxReverseSpeed: -2.0,
  maxSteer: Math.PI / 4, // 45 degrees
  acceleration: 2.5,
  deceleration: 5.0,
};

export class PhysicsEngine {
  private config: MowerConfig;

  constructor(config: MowerConfig = DEFAULT_CONFIG) {
    this.config = config;
  }

  // Updates the state using Euler integration
  // dt is delta time in seconds
  // input is the desired user command
  public step(
    state: MowerState,
    input: { throttle: number; steerTarget: number }, // throttle: -1 to 1, steerTarget: -1 to 1
    dt: number
  ): MowerState {
    const newState = { ...state };

    // 1. Update Velocity (Acceleration / Braking)
    if (input.throttle === 0) {
      // Apply friction/deceleration if no throttle
      if (newState.v > 0) {
        newState.v = Math.max(0, newState.v - this.config.deceleration * dt);
      } else if (newState.v < 0) {
        newState.v = Math.min(0, newState.v + this.config.deceleration * dt);
      }
    } else {
      newState.v += input.throttle * this.config.acceleration * dt;
    }

    // Clamp velocity
    newState.v = Math.max(this.config.maxReverseSpeed, Math.min(this.config.maxSpeed, newState.v));

    // 2. Update Steering (Smooth transition towards target)
    const targetSteer = input.steerTarget * this.config.maxSteer;
    // For simplicity in this iteration, we set steering instantly, but could add limits on max steering rate.
    newState.steering = targetSteer;

    // 3. Update Position & Heading (Bicycle Kinematics)
    // dx/dt = v * cos(theta)
    // dy/dt = v * sin(theta)
    // dtheta/dt = (v / L) * tan(steering)
    
    newState.x += newState.v * Math.cos(newState.theta) * dt;
    newState.y += newState.v * Math.sin(newState.theta) * dt;
    newState.theta += (newState.v / this.config.wheelbase) * Math.tan(newState.steering) * dt;

    // Normalize theta to -PI to PI
    newState.theta = Math.atan2(Math.sin(newState.theta), Math.cos(newState.theta));

    return newState;
  }
}
