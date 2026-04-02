# 🌿 Lawn Mower — Learning from Demonstration Simulator

A pygame simulator that lets you manually drive a mower, then learns your behaviour and autonomously replicates it.

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

## Controls

| Screen   | Keys |
|----------|------|
| Chooser  | Click lawn card → **Start Demo** |
| Demo     | **Arrow keys** to drive · **SPACE** finish · **ESC** back |
| Learning | Watch analysis · **Enter / click** to proceed |
| Auto     | **R / ESC** to restart |

---

## Module function reference

### `src/constants.py`
| Name           | Description |
|----------------|-------------|
| `load_fonts()` | Initialise and return the five application fonts as a dict (call after `pygame.init`).|

### `src/math_utils.py`
| Name                                | Description |
|-------------------------------------|-------------|
| `v2add(a, b)`                       | Add two 2-D vectors. |
| `v2sub(a, b)`                       | Subtract vector b from vector a. |
| `v2scale(a, s)`                     | Scale a vector by scalar s. |
| `v2len(a)`                          | Euclidean length of a vector. |
| `v2norm(a)`                         | Normalise a vector to unit length (returns (1,0) if near-zero). |
| `v2dot(a, b)`                       | Dot product of two vectors. |
| `v2perp(a)`                         | Left-perpendicular (90° CCW rotation) of a vector. |
| `angle_diff(a, b)`                  | Signed angular difference a − b, wrapped to (−π, π]. |
| `bezier4(P0,P1,P2,P3, u)`           | Evaluate a cubic Bézier at parameter u ∈ [0,1]. |
| `sample_bezier(P0,P1,P2,P3, n)`     | Sample n evenly-spaced points along a cubic Bézier. |
| `savgol_smooth(vals, window, poly)` | Savitzky-Golay smooth via least-squares polynomial fitting. |
| `smooth_angle_list(thetas)` | Unwrap, smooth, and re-wrap a list of angles. |
| `clip_segment_to_rect(p1, p2, rect)`| Cohen-Sutherland line clip against an axis-aligned rectangle. |

### `src/world.py`
| Name                                                   | Description |
|--------------------------------------------------------|-------------|
| `Obstacle`                                             | Circular obstacle with x, y, radius attributes. |
| `LawnWorld`                                            | Procedurally-generated lawn: manages obstacles, surfaces, and cut-grass overlay. |
| `LawnWorld.build_surface()`                            | Render grass texture and obstacles into the world pygame surface. |
| `LawnWorld.mark_cut(x, y, radius)`                     | Paint a cut-grass circle onto the transparent overlay. |
| `LawnWorld.thumbnail(w, h)`                            | Return a smoothly-scaled thumbnail of the world surface. |
| `draw_mower(surf, x, y, theta)`                        | Render the top-down circular mower with direction arrow and sensor dots. |
| `draw_sensor_cone(surf, x, y, theta, angle_off, dist)` | Render a single translucent ultrasonic sensor cone. |

### `src/planner.py`
| Name                                                    | Description |
|---------------------------------------------------------|-------------|
| `DemoRecorder`                                          | Records mower pose samples and simulated 3-zone ultrasonic ranges at 20 Hz. |
| `DemoRecorder.tick(dt, x, y, theta, v, obstacles)`      | Accumulate time and append a sample when the interval elapses. |
| `BehaviourParams`                                       | Container for the five extracted behavioural parameters (θ_pref, d_pass, R_turn, M_safe, V_pref). |
| `extract_behaviour(poses, ranges)`                      | Smooth trajectory, segment by curvature, and extract all behaviour parameters. |
| `Lane`                                                  | Single straight mowing lane defined by start and end world coordinates. |
| `generate_lanes(bp, W, H)`                              | Generate a full set of parallel coverage lanes snapped to the nearest cardinal axis. |
| `bezier_turn(lane_a, lane_b, R_turn)`                   | Cubic Bézier arc connecting the end of one lane to the start of the next. |
| `obstacle_bypass(p_entry, p_exit, obs, M_safe, R_turn)` | S-curve detour around an obstacle using two Bézier arcs. |
| `build_full_path(lanes, bp, obstacles)`                 | Build the complete waypoint list combining straights, bypasses, turns, and smoothing. |

### `src/controller.py`
| Name                                    | Description |
|-----------------------------------------|-------------|
| `AutoMower`                             | Autonomous mower that follows a waypoint path with pure-pursuit control and obstacle avoidance. |
| `AutoMower.update(dt, obstacles, lawn)` | Advance physics, avoidance logic, sensor ray-cast, and cut-grass marking for one frame. |
| `AutoMower.progress()`                  | Return mowing completion fraction in [0, 1]. |

### `src/screens.py`
| Name                                           | Description |
|------------------------------------------------|-------------|
| `set_fonts(fonts)`                             | Inject the application font dict into the screens module. |
| `run_chooser(screen, lawns)`                   | Display four lawn thumbnails; returns the selected index or `'regen'`. |
| `run_demo(screen, lawn)`                       | Manual driving screen; returns a `DemoRecorder` when the user finishes. |
| `run_learning(screen, lawn, rec)`              | Animated analysis panel; extracts parameters, previews plan, returns `(bp, lanes, waypoints)`. |
| `run_auto(screen, lawn, bp, lanes, waypoints)` | Autonomous mowing screen; mower follows the learned plan until done or user restarts. |

### `main.py`
| Name           | Description |
|----------------|-------------|
| `make_lawns()` | Generate four randomly-seeded, named `LawnWorld` instances for the chooser. |
| `main()`       | Initialise pygame and run the four-screen application loop. |
