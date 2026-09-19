import React from 'react';
import {Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {colorOf} from './theme';
import type {Mark} from './types';

type Box = {left: number; top: number; width: number; height: number};

export const Visual: React.FC<{
  src: string;
  marks: Mark[];
  box: Box;
}> = ({src, marks, box}) => (
  <div style={{position: 'absolute', ...box}}>
    <Img src={staticFile(src)} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
    {marks.map((m, i) => (
      <MarkLayer key={i} mark={m} />
    ))}
  </div>
);

/** Marks are positioned in percentages of the parent, which is the visual
 *  itself, so nothing has to know the pixel size of anything. */
const MarkLayer: React.FC<{mark: Mark}> = ({mark}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const delay = Math.round((mark.at ?? 0) * fps);
  const appear = spring({frame: frame - delay, fps, config: {damping: 200}});
  if (frame < delay) return null;

  const [x, y, w, h] = mark.box;
  let left = x;
  let top = y;
  if (mark.to) {
    const travel = Math.max(1, Math.round((mark.travelSeconds ?? 1) * fps));
    const t = interpolate(frame - delay, [0, travel], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    left = x + (mark.to[0] - x) * t;
    top = y + (mark.to[1] - y) * t;
  }

  const colour = colorOf(mark.color);
  const style = mark.style ?? 'fill';
  const filled = style === 'fill';

  return (
    <div
      style={{
        position: 'absolute',
        left: `${left * 100}%`,
        top: `${top * 100}%`,
        width: `${w * 100}%`,
        height: `${h * 100}%`,
        boxSizing: 'border-box',
        background: filled ? colour : 'transparent',
        border: filled ? 'none' : `6px solid ${colour}`,
        borderRadius: style === 'ring' ? '50%' : 6,
        opacity: (filled ? (mark.alpha ?? 0.25) : 1) * appear,
        transform: `scale(${interpolate(appear, [0, 1], [0.6, 1])})`,
      }}
    />
  );
};
