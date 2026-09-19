import React from 'react';
import {Composition} from 'remotion';
import {Explainer, TOTAL} from './Explainer';
import storyboard from './storyboard.json';
import type {Storyboard} from './types';

const board = storyboard as Storyboard;

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Explainer"
    component={Explainer}
    durationInFrames={TOTAL}
    fps={board.fps}
    width={board.width}
    height={board.height}
  />
);
