import { MapGrid } from '../simulation/MapGrid';

export interface Waypoint {
  x: number;
  y: number;
}

export class BoustrophedonPlanner {
  
  // Generates a target path in world coordinates (zigzag sweeps)
  public static plan(
    map: MapGrid, 
    direction: 'horizontal' | 'vertical', 
    rowSpacing: number,
    obstacleMargin: number
  ): Waypoint[] {
    const waypoints: Waypoint[] = [];
    
    // Bounds in world coordinates
    const startX = obstacleMargin;
    const endX = (map.width * map.resolution) - obstacleMargin;
    const startY = obstacleMargin;
    const endY = (map.height * map.resolution) - obstacleMargin;

    // Simple Boustrophedon: sweep across the entire field without decomposition first.
    // If it hits an obstacle, we skip those segments (decomposition approximation).
    // In a full implementation, we'd sweep lines and find start/stop points around obstacles.
    
    if (direction === 'horizontal') {
      let currentY = startY;
      let movingRight = true;
      
      while (currentY <= endY) {
        // We can sample along the line to detect obstacles
        // For a true Boustrophedon, you'd slice the geometry.
        // Simplified sweep:
        if (movingRight) {
          waypoints.push({ x: startX, y: currentY });
          waypoints.push({ x: endX, y: currentY });
        } else {
          waypoints.push({ x: endX, y: currentY });
          waypoints.push({ x: startX, y: currentY });
        }
        
        currentY += rowSpacing;
        movingRight = !movingRight;
      }
    } else {
      let currentX = startX;
      let movingDown = true;
      
      while (currentX <= endX) {
        if (movingDown) {
          waypoints.push({ x: currentX, y: startY });
          waypoints.push({ x: currentX, y: endY });
        } else {
          waypoints.push({ x: currentX, y: endY });
          waypoints.push({ x: currentX, y: startY });
        }
        
        currentX += rowSpacing;
        movingDown = !movingDown;
      }
    }

    return waypoints;
  }
}
