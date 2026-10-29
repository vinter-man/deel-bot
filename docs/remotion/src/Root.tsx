import React from 'react';
import {Composition, Still} from 'remotion';
import {Banner, BANNER_H, BANNER_W} from './Banner';
import {Demo, FPS, H, TOTAL, W} from './Demo';
import {Shot, type ShotName} from './shots';

/** Each shot is as tall as its own content, so the README has no letterboxing. */
export const SHOTS: Partial<Record<ShotName, number>> = {
  start: 760,
  team: 820,
  plan: 900,
  scale: 940,
  cost: 830,
  compare: 640,
  sources: 1060,
  errors: 600,
  de: 820,
};
const SHOT_W = 1000;

export const Root: React.FC = () => (
  <>
    <Still id="banner" component={Banner} width={BANNER_W} height={BANNER_H} />
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
