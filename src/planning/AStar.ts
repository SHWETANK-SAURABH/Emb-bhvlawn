import { MapGrid } from '../simulation/MapGrid';
import type { Waypoint } from './BoustrophedonPlanner';

export class AStar {
  
  // Basic A* pathfinding over Grid coordinates
  public static findPath(map: MapGrid, startWorld: Waypoint, goalWorld: Waypoint): Waypoint[] {
    const startObj = map.worldToGrid(startWorld.x, startWorld.y);
    const start = { x: startObj.cx, y: startObj.cy };
    
    const goalObj = map.worldToGrid(goalWorld.x, goalWorld.y);
    const goal = { x: goalObj.cx, y: goalObj.cy };

    if (!map.isValid(start.x, start.y) || !map.isValid(goal.x, goal.y)) return [];
    if (map.grid[goal.y][goal.x] === 2) return []; // Obstacle

    const openSet: any[] = [{ pos: start, g: 0, f: this.heuristic(start, goal) }];
    const closedSet = new Set<string>();
    const cameFrom = new Map<string, {x:number, y:number}>();

    while (openSet.length > 0) {
      openSet.sort((a, b) => a.f - b.f);
      const current = openSet.shift();
      const currentKey = `${current.pos.x},${current.pos.y}`;

      if (current.pos.x === goal.x && current.pos.y === goal.y) {
        return this.reconstructPath(cameFrom, current.pos, map.resolution);
      }

      closedSet.add(currentKey);

      const neighbors = [
        { x: current.pos.x + 1, y: current.pos.y },
        { x: current.pos.x - 1, y: current.pos.y },
        { x: current.pos.x, y: current.pos.y + 1 },
        { x: current.pos.x, y: current.pos.y - 1 },
      ];

      for (const neighbor of neighbors) {
        if (!map.isValid(neighbor.x, neighbor.y)) continue;
        if (map.grid[neighbor.y][neighbor.x] === 2) continue; // Obstacle

        const neighborKey = `${neighbor.x},${neighbor.y}`;
        if (closedSet.has(neighborKey)) continue;

        const tentativeG = current.g + 1;

        let existing = openSet.find(n => n.pos.x === neighbor.x && n.pos.y === neighbor.y);
        
        if (!existing) {
          existing = { pos: neighbor, g: Infinity, f: Infinity };
          openSet.push(existing);
        }

        if (tentativeG < existing.g) {
          cameFrom.set(neighborKey, current.pos);
          existing.g = tentativeG;
          existing.f = existing.g + this.heuristic(neighbor, goal);
        }
      }
    }
    return []; // No path found
  }

  private static heuristic(a: {x:number, y:number}, b: {x:number, y:number}) {
    // Manhattan distance
    return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
  }

  private static reconstructPath(cameFrom: Map<string, {x:number, y:number}>, current: {x:number, y:number}, res: number): Waypoint[] {
    const totalPath: Waypoint[] = [{
        x: current.x * res + res/2,
        y: current.y * res + res/2
    }];
    
    let currentKey = `${current.x},${current.y}`;
    
    while (cameFrom.has(currentKey)) {
      current = cameFrom.get(currentKey)!;
      currentKey = `${current.x},${current.y}`;
      totalPath.unshift({
        x: current.x * res + res/2,
         y: current.y * res + res/2
      });
    }
    return totalPath;
  }
}
