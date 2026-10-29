import React from 'react';
import {Composition, Still} from 'remotion';
import {Demo, FPS, H, TOTAL, W} from './Demo';
import {Shot, type ShotName} from './shots';

/** Each shot is as tall as its own content, so the README has no letterboxing. */
export const SHOTS: Partial<Record<ShotName, number>> = {
  start: 800,
  team: 1180,
  plan: 900,
  cost: 830,
  compare: 640,
  sources: 1060,
  errors: 600,
};
const SHOT_W = 1000;

export const Root: React.FC = () => (
  <>
    <Composition
      id="demo"
      component={Demo}
      durationInFrames={TOTAL}
      fps={FPS}
      width={W}
      height={H}
    />
    {(Object.keys(SHOTS) as ShotName[]).map((name) => (
      <Still
        key={name}
        id={`shot-${name}`}
        component={() => <Shot name={name} />}
        width={SHOT_W}
        height={SHOTS[name]!}
      />
    ))}
  </>
);
