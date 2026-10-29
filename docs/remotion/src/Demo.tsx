/**
 * The 10-second demo GIF: type a question, get the answer, tap a horizon, watch it change.
 * Both replies are the bot's real output (shots.json: `plan` and `plan24`).
 */
import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import data from './shots.json';
import {TgHtml} from './html';
import {DayDivider, In, Out, Window} from './telegram';

export const FPS = 30;
export const W = 1000;
export const H = 880;
export const TOTAL = 11 * FPS;

const QUESTION = 'Germany 80k 5 people';
const TYPE_END = Math.round(1.6 * FPS);
const SENT = TYPE_END + 6;
const ANSWER = SENT + Math.round(0.7 * FPS);
const TAP = Math.round(5.6 * FPS);
const EDITED = TAP + 8;

type Reply = {html: string; keyboard: string[][]};
const plan12 = (data.plan[1] as {in: Reply}).in;
const plan24 = (data.plan24[1] as {in: Reply}).in;

export const Demo: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const typed = QUESTION.slice(
    0,
    Math.floor(
      interpolate(frame, [6, TYPE_END], [0, QUESTION.length], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      }),
    ),
  );
  const answerIn = spring({frame: frame - ANSWER, fps, config: {damping: 18}});
  const reply = frame >= EDITED ? plan24 : plan12;
  const pressed = frame >= TAP && frame < EDITED + 6;
  const keyboard = reply.keyboard.map((row, r) =>
    row.map((label) => ({
      label: r === 0 && pressed && label.endsWith('24 mo') ? `👆 ${label}` : label,
    })),
  );

  return (
    <AbsoluteFill>
      <Window composer={frame < SENT ? typed || undefined : undefined}>
        <DayDivider />
        {frame >= SENT ? <Out time="10:14">{QUESTION}</Out> : null}
        {frame >= ANSWER ? (
          <div style={{opacity: answerIn, transform: `translateY(${(1 - answerIn) * 24}px)`}}>
            <In time="10:14" width="88%" keyboard={keyboard}>
              <TgHtml html={reply.html} />
            </In>
          </div>
        ) : null}
      </Window>
    </AbsoluteFill>
  );
};
