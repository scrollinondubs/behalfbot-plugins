import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile} from 'remotion';
import {Visual} from './annotate';
import {Panel} from './panel';
import {COL, FONT_STACK} from './theme';
import storyboard from './storyboard.json';
import type {Segment, Storyboard} from './types';

const board = storyboard as Storyboard;

const VIS_X = 45;
const VIS_Y = 40;
const GAP = 55;

export const framesFor = (s: Segment) => Math.max(1, Math.round(s.durationSeconds * board.fps));
export const TOTAL = board.segments.reduce((a, s) => a + framesFor(s), 0);

const Slide: React.FC<{segment: Segment}> = ({segment}) => {
  const visSide = Math.min(1000, board.height - 2 * VIS_Y);
  const hasVisual = Boolean(segment.visual);
  const panelLeft = hasVisual ? VIS_X + visSide + GAP : VIS_X;
  const panelWidth = board.width - panelLeft - 50;

  return (
    <AbsoluteFill style={{background: COL.bg, fontFamily: FONT_STACK}}>
      {segment.audio ? <Audio src={staticFile(segment.audio)} /> : null}
      {hasVisual ? (
        <Visual
          src={segment.visual as string}
          marks={segment.marks ?? []}
          box={{left: VIS_X, top: VIS_Y, width: visSide, height: visSide}}
        />
      ) : null}
      <Panel
        kicker={segment.kicker}
        title={segment.title}
        lines={segment.lines ?? []}
        left={panelLeft}
        width={panelWidth}
        footer={segment.footer}
        height={board.height}
      />
    </AbsoluteFill>
  );
};

export const Explainer: React.FC = () => {
  let at = 0;
  return (
    <AbsoluteFill style={{background: COL.bg}}>
      {board.segments.map((segment, i) => {
        const from = at;
        const dur = framesFor(segment);
        at += dur;
        return (
          <Sequence key={i} from={from} durationInFrames={dur}>
            <Slide segment={segment} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
