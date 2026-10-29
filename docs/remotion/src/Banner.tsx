/**
 * The README header, in the same system as the other banners: near-black, cream type, one gold
 * accent, printed grain, the illustration on the left and the pitch on the right.
 */
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {siDocker, siGithubactions, siPydantic, siPython, siSqlite, siTelegram} from 'simple-icons';
import {C} from './theme';
import {Grain, MONO, SANS} from './ui';

const OUTLINE = '#0B0B0B';
const STROKE = 7;

/** A head-and-shoulders figure: one of the team on the EOR pan. */
const Person: React.FC<{x: number; y: number; s?: number; fill?: string}> = ({
  x,
  y,
  s = 1,
  fill = '#9A9994',
}) => (
  <g
    transform={`translate(${x} ${y}) scale(${s})`}
    stroke={OUTLINE}
    strokeWidth={STROKE / s}
    strokeLinejoin="round"
  >
    <path d="M-34 40 C-34 8 -20 -4 0 -4 C20 -4 34 8 34 40 Z" fill={fill} />
    <circle cx="0" cy="-26" r="20" fill={fill} />
  </g>
);

/** The scale: EOR (a team) on one pan, an entity (a building) on the other, a coin at the pivot. */
const Illustration: React.FC = () => (
  <svg viewBox="0 0 640 640" width={640} height={640}>
    <defs>
      <radialGradient id="metal" cx="35%" cy="30%" r="80%">
        <stop offset="0%" stopColor="#5C5C59" />
        <stop offset="100%" stopColor="#2A2A28" />
      </radialGradient>
      <radialGradient id="coin" cx="35%" cy="30%" r="75%">
        <stop offset="0%" stopColor="#F2C25A" />
        <stop offset="100%" stopColor="#B07F1F" />
      </radialGradient>
    </defs>
    <g stroke={OUTLINE} strokeWidth={STROKE} strokeLinejoin="round" strokeLinecap="round">
      {/* floor shadow and base */}
      <ellipse cx="320" cy="586" rx="210" ry="22" fill="#000" opacity="0.35" stroke="none" />
      <path d="M220 580 C220 548 262 530 320 530 C378 530 420 548 420 580 Z" fill="url(#metal)" />
      <rect x="304" y="196" width="32" height="340" rx="10" fill="#4A4A47" />

      {/* beam, tilted towards the heavier side: the entity, for a small team */}
      <g transform="rotate(-8 320 190)">
        <rect x="70" y="176" width="500" height="28" rx="14" fill="#5A5A57" />
        {/* left chains + pan with the team */}
        <path d="M100 204 L58 330 M100 204 L142 330" fill="none" stroke="#8E8D89" strokeWidth={5} />
        <path
          d="M24 330 L176 330 C170 372 140 388 100 388 C60 388 30 372 24 330 Z"
          fill="url(#metal)"
        />
        {/* right chains + pan with the building */}
        <path
          d="M540 204 L498 330 M540 204 L582 330"
          fill="none"
          stroke="#8E8D89"
          strokeWidth={5}
        />
        <path
          d="M464 330 L616 330 C610 372 580 388 540 388 C500 388 470 372 464 330 Z"
          fill="url(#metal)"
        />
      </g>

      {/* the coin at the pivot, the one gold thing */}
      <circle cx="320" cy="168" r="44" fill="url(#coin)" />
      <circle cx="320" cy="168" r="30" fill="none" stroke="#7A5512" strokeWidth={4} />
      <text
        x="320"
        y="182"
        textAnchor="middle"
        fontFamily={SANS}
        fontWeight={800}
        fontSize="40"
        fill="#6B4A0E"
        stroke="none"
      >
        €
      </text>
    </g>

    {/* sparkle */}
    <g stroke={C.cream} strokeWidth={6} strokeLinecap="round">
      <path d="M392 96 L404 74" />
      <path d="M408 120 L432 112" />
      <path d="M372 86 L370 62" />
    </g>

    {/* the team on the left pan (positions follow the -8° beam) */}
    <g transform="rotate(-8 320 190)">
      <Person x={68} y={294} s={0.62} fill="#7E7D79" />
      <Person x={132} y={294} s={0.62} fill="#7E7D79" />
      <Person x={100} y={286} s={0.74} fill="#B5B4AF" />
    </g>

    {/* the building on the right pan */}
    <g transform="rotate(-8 320 190)" stroke={OUTLINE} strokeWidth={STROKE} strokeLinejoin="round">
      <rect x="498" y="214" width="84" height="116" rx="4" fill="#A8A7A2" />
      <path d="M490 218 L540 186 L590 218 Z" fill="#7E7D79" />
      {[0, 1, 2].map((r) =>
        [0, 1].map((c) => (
          <rect
            key={`${r}${c}`}
            x={510 + c * 36}
            y={234 + r * 28}
            width="24"
            height="16"
            rx="2"
            fill="#2E2E2C"
            strokeWidth={4}
          />
        )),
      )}
      <rect x="528" y="298" width="24" height="32" rx="2" fill="#2E2E2C" strokeWidth={4} />
    </g>
  </svg>
);

const Icon: React.FC<{path: string; size?: number}> = ({path, size = 34}) => (
  <svg viewBox="0 0 24 24" width={size} height={size}>
    <path d={path} fill={C.cream} />
  </svg>
);

const Boxed: React.FC<{children: React.ReactNode}> = ({children}) => (
  <span
    style={{
      fontFamily: MONO,
      fontSize: 19,
      color: C.cream,
      border: `2px solid ${C.cream}`,
      padding: '3px 9px',
      lineHeight: 1,
    }}
  >
    {children}
  </span>
);

export const Banner: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: C.bg, fontFamily: SANS}}>
    <div style={{position: 'absolute', left: 0, top: 10}}>
      <Illustration />
    </div>
    <div style={{position: 'absolute', left: 680, top: 52, right: 48, color: C.cream}}>
      <div style={{fontFamily: MONO, fontSize: 21, color: C.grey}}>
        github.com/vinter-man/deel-bot
      </div>
      <div
        style={{fontSize: 92, fontWeight: 700, letterSpacing: -4.5, lineHeight: 1.0, marginTop: 22}}
      >
        hire or
        <br />
        entity
      </div>
      <div style={{fontSize: 31, lineHeight: 1.22, marginTop: 26, letterSpacing: -0.4}}>
        “Three people? EOR. Thirty? Your own company. In between, it’s arithmetic.”
      </div>
      <div style={{fontSize: 19, color: C.grey, marginTop: 10}}>
        — me, before every expansion call
      </div>
      <div style={{fontSize: 20, lineHeight: 1.45, marginTop: 22, color: C.greyBright}}>
        Full employer cost in five countries, EOR versus your own entity, and the team size where
        the entity starts to pay off.
      </div>
      <div style={{fontFamily: MONO, fontSize: 18.5, color: C.grey, marginTop: 14}}>
        country → salary → people → <span style={{color: C.gold, fontWeight: 700}}>break-even</span>
      </div>
      <div style={{display: 'flex', alignItems: 'center', gap: 22, marginTop: 24}}>
        <Icon path={siPython.path} />
        <Icon path={siTelegram.path} />
        <Boxed>aiogram</Boxed>
        <Icon path={siPydantic.path} />
        <Icon path={siSqlite.path} />
        <Icon path={siDocker.path} />
        <Icon path={siGithubactions.path} />
      </div>
    </div>
    <Grain opacity={0.07} />
  </AbsoluteFill>
);
