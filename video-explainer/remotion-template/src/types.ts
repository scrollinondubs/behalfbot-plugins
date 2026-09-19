/** A mark is a box in fractions of the visual's own area, 0 to 1, so it
 *  survives any resize. Same vocabulary the slide renderer uses. */
export type Mark = {
  box: [number, number, number, number];
  color?: string;
  style?: 'fill' | 'ring' | 'outline';
  alpha?: number;
  /** Seconds into the segment at which this mark appears. */
  at?: number;
  /** Optional destination box; the mark travels there over `travelSeconds`. */
  to?: [number, number, number, number];
  travelSeconds?: number;
};

export type Segment = {
  audio?: string;
  durationSeconds: number;
  visual?: string;
  kicker?: string;
  title: string;
  lines?: [string, string][];
  marks?: Mark[];
  footer?: string;
};

export type Storyboard = {
  width: number;
  height: number;
  fps: number;
  segments: Segment[];
};
