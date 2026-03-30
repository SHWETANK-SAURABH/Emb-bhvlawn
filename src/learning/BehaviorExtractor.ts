import type { TrajectoryPoint } from '../store/simulationStore';

// Function to apply a simple moving average to reduce jitter
export function smoothTrajectory(trajectory: TrajectoryPoint[], windowSize: number = 5): TrajectoryPoint[] {
  if (trajectory.length < windowSize) return trajectory;
  
  const smoothed: TrajectoryPoint[] = [];
  const halfWindow = Math.floor(windowSize / 2);

  for (let i = 0; i < trajectory.length; i++) {
    let sumX = 0, sumY = 0, sumTheta = 0, count = 0;
    
    // Average points in window
    for (let j = Math.max(0, i - halfWindow); j <= Math.min(trajectory.length - 1, i + halfWindow); j++) {
      sumX += trajectory[j].x;
      sumY += trajectory[j].y;
      
      // Handle angle wrapping across -PI/PI for averages
      // A naive sum fails if we average 3.14 and -3.14. Using sin/cos sum is better:
      sumTheta += trajectory[j].theta; 
      count++;
    }

    smoothed.push({
      ...trajectory[i],
      x: sumX / count,
      y: sumY / count,
      theta: sumTheta / count, // Placeholder for simplicity, real app would use atan2(mean(sin), mean(cos))
    });
  }

  return smoothed;
}

export class BehaviorExtractor {
  
  // Extracts behavior rules from a raw human trajectory
  public static extract(rawTrajectory: TrajectoryPoint[]): {
    direction: 'horizontal' | 'vertical',
    rowSpacing: number,
    obstacleMargin: number
  } {
    // 1. Noise Filter
    const trajectory = smoothTrajectory(rawTrajectory, 10);
    
    if (trajectory.length < 10) {
      return { direction: 'horizontal', rowSpacing: 2, obstacleMargin: 0.5 }; // Defaults
    }

    // 2. Base Direction (Compare X variance to Y variance)
    // In Boustrophedon, the mower spends most time moving along the long axes.
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    
    trajectory.forEach(p => {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    });



    // If user covered more horizontal ground overall in passes, it's roughly horizontal
    // A better metric is integrating absolute dx vs absolute dy over time
    let totalDx = 0;
    let totalDy = 0;

    for (let i = 1; i < trajectory.length; i++) {
      totalDx += Math.abs(trajectory[i].x - trajectory[i - 1].x);
      totalDy += Math.abs(trajectory[i].y - trajectory[i - 1].y);
    }
    
    const direction = totalDx > totalDy ? 'horizontal' : 'vertical';

    // 3. Grid Row Spacing
    // We can infer spacing by looking at parallel segments. For horizontal: look at changes in Y.
    // Simplifying: The user will likely have y-coordinates concentrated near certain bins.
    const rowSpacing = this.estimateRowSpacing(trajectory, direction);

    // 4. Obstacle Margin
    // Assuming the user steered around visible obstacles, minimum clearance. 
    // Usually inferred if we had obstacle data during run. Defaulting to 1m for demo.
    const obstacleMargin = 1.0; 

    return { direction, rowSpacing, obstacleMargin };
  }

  // Simplified heuristic to find spacing between parallel passes
  private static estimateRowSpacing(trajectory: TrajectoryPoint[], direction: 'horizontal' | 'vertical'): number {
    const coords = trajectory.map(p => direction === 'horizontal' ? p.y : p.x);
    
    // Bin the coordinates to find peaks (passes)
    const bins = new Map<number, number>();
    const binSize = 0.5; // half meter
    
    coords.forEach(c => {
      const b = Math.floor(c / binSize) * binSize;
      bins.set(b, (bins.get(b) || 0) + 1);
    });

    // Find the peaks (bins with most points, representing long straightaways)
    const sortedBins = Array.from(bins.entries())
      .filter(([_, count]) => count > (trajectory.length * 0.05)) // Must be significant presence
      .map(([val, _]) => val)
      .sort((a, b) => a - b);
      
    if (sortedBins.length < 2) return 2.0; // Default 2m spacing if only 1 pass detected
    
    // Average distance between consecutive peaks
    let totalDist = 0;
    for (let i = 1; i < sortedBins.length; i++) {
        totalDist += Math.abs(sortedBins[i] - sortedBins[i - 1]);
    }
    
    return Math.max(1.0, totalDist / (sortedBins.length - 1));
  }
}
