export enum CellState {
  UNCOVERED = 0,
  COVERED = 1,
  OBSTACLE = 2,
}

export class MapGrid {
  public width: number;
  public height: number;
  public resolution: number; // Size of one cell in world units (e.g., meters)
  public grid: number[][]; // [y][x] format for easier visualization (row-major)

  constructor(widthUnits: number, heightUnits: number, resolution: number = 0.5) {
    this.width = Math.ceil(widthUnits / resolution);
    this.height = Math.ceil(heightUnits / resolution);
    this.resolution = resolution;
    
    // Initialize empty grid
    this.grid = new Array(this.height).fill(0).map(() => new Array(this.width).fill(CellState.UNCOVERED));
  }

  // Convert world coordinates to grid indices
  public worldToGrid(x: number, y: number): { cx: number; cy: number } {
    const cx = Math.floor(x / this.resolution);
    const cy = Math.floor(y / this.resolution);
    return { cx, cy };
  }

  // Check bounds
  public isValid(cx: number, cy: number): boolean {
    return cx >= 0 && cx < this.width && cy >= 0 && cy < this.height;
  }

  // Update a radius around the mower as COVERED
  public updateCoverage(worldX: number, worldY: number, coverageRadius: number): void {
    const rCells = Math.ceil(coverageRadius / this.resolution);
    const { cx, cy } = this.worldToGrid(worldX, worldY);

    for (let dy = -rCells; dy <= rCells; dy++) {
      for (let dx = -rCells; dx <= rCells; dx++) {
        const nx = cx + dx;
        const ny = cy + dy;
        
        // Circular check
        if (this.isValid(nx, ny) && (dx * dx + dy * dy) <= rCells * rCells) {
          if (this.grid[ny][nx] !== CellState.OBSTACLE) {
            this.grid[ny][nx] = CellState.COVERED;
          }
        }
      }
    }
  }

  // Inject a dynamic obstacle at runtime
  public addObstacle(worldX: number, worldY: number, radius: number): void {
    const rCells = Math.ceil(radius / this.resolution);
    const { cx, cy } = this.worldToGrid(worldX, worldY);

    for (let dy = -rCells; dy <= rCells; dy++) {
      for (let dx = -rCells; dx <= rCells; dx++) {
        const nx = cx + dx;
        const ny = cy + dy;
        if (this.isValid(nx, ny) && Math.sqrt(dx * dx + dy * dy) <= rCells) {
          this.grid[ny][nx] = CellState.OBSTACLE;
        }
      }
    }
  }

  // Check if a point is an obstacle (used for physics collision and planning)
  public isObstacle(worldX: number, worldY: number): boolean {
    const { cx, cy } = this.worldToGrid(worldX, worldY);
    if (!this.isValid(cx, cy)) return true; // Treat boundaries as obstacles
    return this.grid[cy][cx] === CellState.OBSTACLE;
  }

  // Calculate coverage metric
  public getCoveragePercentage(): number {
    let totalGrass = 0;
    let coveredGrass = 0;

    for (let y = 0; y < this.height; y++) {
      for (let x = 0; x < this.width; x++) {
        const state = this.grid[y][x];
        if (state !== CellState.OBSTACLE) {
          totalGrass++;
          if (state === CellState.COVERED) {
            coveredGrass++;
          }
        }
      }
    }
    
    if (totalGrass === 0) return 0;
    return (coveredGrass / totalGrass) * 100;
  }
}
