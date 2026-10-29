/**
 * The README header: a pencil-on-paper chart of the bot's own answer for one real case.
 *
 * Every number on it comes from banner.json, which scripts/export_shots.py computes with the
 * bot's calculation for the README's team (Germany 2, UK 1, Spain 1, Poland 1, two years):
 * change the data or the model and the banner follows on the next render.
 */
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {loadFont as loadSans} from '@remotion/google-fonts/InterTight';
import {loadFont as loadMono} from '@remotion/google-fonts/IBMPlexMono';
import {
  siDocker,
  siGithubactions,
  siPydantic,
  siPytest,
  siPython,
  siRuff,
  siTelegram,
  siUv,
} from 'simple-icons';
import data from './banner.json';

const sans = loadSans().fontFamily;
const mono = loadMono().fontFamily;

const PAPER = '#F7F6F2';
const INK = '#151515';
const GREY = '#6E6D69';
const RULE = '#C9C7C0';

export const BANNER_W = 2000;
export const BANNER_H = 1000;

const euro = (n: number) => `€${Math.round(n).toLocaleString('en-US')}`;

/* chart geometry */
const X0 = 930;
const X1 = 1875;
const Y0 = 680; // zero line
const Y1 = 120; // top of the axis
const maxY = Math.max(...data.eor, ...data.entity) * 1.04;
const x = (m: number) => X0 + ((X1 - X0) * m) / data.months;
const y = (v: number) => Y0 - ((Y0 - Y1) * v) / maxY;
const path = (values: number[]) =>
  values.map((v, m) => `${m ? 'L' : 'M'}${x(m).toFixed(1)},${y(v).toFixed(1)}`).join(' ');

/** A stroke drawn twice through a displacement filter, so it reads as pencil, not vector. */
const Pencil: React.FC<{d: string; width?: number}> = ({d, width = 4.5}) => (
  <g filter="url(#pencil)" fill="none" stroke={INK} strokeLinecap="round" strokeLinejoin="round">
    <path d={d} strokeWidth={width} />
    <path d={d} strokeWidth={width * 0.45} opacity={0.55} transform="translate(0.8,-0.6)" />
  </g>
);

const Icon: React.FC<{path: string}> = ({path}) => (
  <svg viewBox="0 0 24 24" width={36} height={36}>
    <path d={path} fill={INK} />
  </svg>
);

const Boxed: React.FC<{children: React.ReactNode}> = ({children}) => (
  <span
    style={{
      fontFamily: mono,
      fontSize: 17,
      color: INK,
      border: `2px solid ${INK}`,
      padding: '5px 9px',
      lineHeight: 1,
    }}
  >
    {children}
  </span>
);

const Mono: React.FC<{
  children: React.ReactNode;
  size?: number;
  color?: string;
  style?: React.CSSProperties;
}> = ({children, size = 21, color = GREY, style}) => (
  <div style={{fontFamily: mono, fontSize: size, color, letterSpacing: 0.6, ...style}}>
    {children}
  </div>
);

const Label: React.FC<{
  x: number;
  y: number;
  children: React.ReactNode;
  color?: string;
  size?: number;
}> = ({x: lx, y: ly, children, color = INK, size = 21}) => (
  <text x={lx} y={ly} fontFamily={mono} fontSize={size} fill={color}>
    {children}
  </text>
);

export const Banner: React.FC = () => {
  const last = data.months;
  const lastEor = y(data.eor[last]!);
  const lastEntity = y(data.entity[last]!);
  const ticks = Array.from({length: last / 4 + 1}, (_, i) => i * 4);
  // The EOR label runs along its line, in the gap between the two.
  const eorAngle = (Math.atan2(lastEor - y(0), x(last) - x(0)) * 180) / Math.PI;
  const labelAt = Math.round(last * 0.54);
  const labelX = x(labelAt);
  const labelY = y(data.eor[labelAt]!) - 16; // just above the line, inside the gap
  // The callout points into the gap a third of the way along.
  const mid = Math.round(last / 3);
  const midX = x(mid);
  const midY = (y(data.eor[mid]!) + y(data.entity[mid]!)) / 2;

  return (
    <AbsoluteFill style={{backgroundColor: PAPER}}>
      {/* ── left column: what it is ─────────────────────────────────────── */}
      <div style={{position: 'absolute', left: 100, top: 70, width: 760, color: INK}}>
        <Mono>github.com/vinter-man/deel-bot</Mono>
        <div
          style={{
            fontFamily: sans,
            fontWeight: 600,
            fontSize: 112,
            letterSpacing: -5,
            lineHeight: 1,
            marginTop: 14,
          }}
        >
          hire or entity
        </div>
        <div style={{fontFamily: sans, fontSize: 28, color: GREY, lineHeight: 1.35, marginTop: 30}}>
          Employer cost of employment, EOR vs your own entity, and the point where it is time to
          switch.
        </div>
        <div style={{borderTop: `2px solid ${INK}`, marginTop: 72, width: 735}} />
        <Mono style={{marginTop: 26}}>your own entity is cheaper when</Mono>
        <div style={{borderLeft: `4px solid ${INK}`, paddingLeft: 18, marginTop: 14}}>
          <Mono size={25} color={INK}>
            N·(M − setup)·(fee − payroll)
          </Mono>
          <Mono size={25} color={INK} style={{marginTop: 8}}>
            &gt; setup + exit + M·fixed
          </Mono>
        </div>
        <Mono style={{marginTop: 16}}>N people, M months; every cost line has a source</Mono>
        <div style={{borderTop: `1px solid ${RULE}`, marginTop: 120, width: 735}} />
        <div style={{display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 24}}>
          <Mono size={26} color={INK}>
            @deel_hea_unofficial_bot
          </Mono>
          <Mono>· 2026 rates</Mono>
        </div>
        <Mono style={{marginTop: 12}}>Germany · United Kingdom · Spain · Poland · Bulgaria</Mono>
        <Mono style={{marginTop: 6}}>English · Deutsch · Español · Polski · Български</Mono>
        <Mono style={{marginTop: 6}}>unofficial · estimates only · not affiliated with Deel</Mono>
      </div>

      {/* ── right: the chart ─────────────────────────────────────────────── */}
      <svg width={BANNER_W} height={BANNER_H} style={{position: 'absolute', inset: 0}}>
        <defs>
          <filter id="pencil" x="-5%" y="-5%" width="110%" height="110%">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.9"
              numOctaves={2}
              seed={4}
              result="noise"
            />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale={2.6} />
          </filter>
          <filter id="grain">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.75"
              numOctaves={3}
              stitchTiles="stitch"
            />
            <feColorMatrix type="saturate" values="0" />
          </filter>
        </defs>

        {/* axes */}
        <Pencil d={`M${X0},${Y1 - 20} L${X0},${Y0} L${X1 + 10},${Y0}`} width={3.5} />
        <Label x={X0 - 28} y={Y1 - 8} size={22}>
          €
        </Label>
        {ticks.map((m) => (
          <g key={m}>
            <Pencil d={`M${x(m)},${Y0} L${x(m)},${Y0 + 9}`} width={2.5} />
            <text
              x={x(m)}
              y={Y0 + 40}
              textAnchor="middle"
              fontFamily={mono}
              fontSize={22}
              fill={INK}
            >
              {m}
            </text>
          </g>
        ))}
        <text x={X1} y={Y0 + 72} textAnchor="end" fontFamily={mono} fontSize={22} fill={INK}>
          months
        </text>

        {/* the two lines */}
        <Pencil d={path(data.eor)} width={5} />
        <Pencil d={path(data.entity)} width={5} />

        <text
          x={labelX}
          y={labelY}
          fontFamily={mono}
          fontSize={21}
          fill={INK}
          transform={`rotate(${eorAngle} ${labelX} ${labelY})`}
        >
          EOR · {data.people} people × {euro(data.fee)} a month
        </text>
        <Label x={x(2)} y={y(data.entity[13]!) - 80}>
          {data.entities} own entities on Deel Payroll
        </Label>
        <Label x={x(2)} y={y(data.entity[13]!) - 52} color={GREY}>
          {euro(data.entity[0]!)} before the first payslip
        </Label>

        {/* the point of the picture: the gap never closes */}
        <circle cx={midX} cy={midY} r={9} fill={INK} filter="url(#pencil)" />
        {/* the callout sits under the EOR line on the right, where the chart is empty */}
        <Pencil d={`M${midX + 10},${midY + 14} L${x(12.4)},${Y0 - 140}`} width={2.5} />
        <text x={x(12.6)} y={Y0 - 105} fontFamily={sans} fontSize={34} fontWeight={500} fill={INK}>
          EOR is cheaper every month
        </text>
        <text x={x(12.6)} y={Y0 - 63} fontFamily={sans} fontSize={34} fontWeight={500} fill={INK}>
          of the two years
        </text>

        {/* the gap at the end of the horizon */}
        <Pencil
          d={`M${X1 + 26},${lastEor} L${X1 + 26},${lastEntity} M${X1 + 18},${lastEor} L${X1 + 34},${lastEor} M${X1 + 18},${lastEntity} L${X1 + 34},${lastEntity}`}
          width={2.5}
        />
        <text
          x={X1 - 6}
          y={(lastEor + lastEntity) / 2 + 40}
          textAnchor="end"
          fontFamily={sans}
          fontSize={38}
          fontWeight={500}
          fill={INK}
        >
          ~{euro(data.saving)}
        </text>

        <Label x={X0} y={Y0 + 120} color={GREY}>
          Team: {data.team} × {euro(data.salary)} · overhead only.
        </Label>
        <Label x={X0} y={Y0 + 148} color={GREY}>
          Salary + contributions are identical either way.
        </Label>

        <rect width="100%" height="100%" filter="url(#grain)" opacity={0.05} />
      </svg>

      {/* ── stack ─────────────────────────────────────────────────────────── */}
      <div
        style={{
          position: 'absolute',
          left: 100,
          right: 100,
          top: 895,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Icon path={siPython.path} />
        <Icon path={siTelegram.path} />
        <Boxed>aiogram</Boxed>
        <Icon path={siPydantic.path} />
        <Boxed>httpx</Boxed>
        <Icon path={siUv.path} />
        <Icon path={siDocker.path} />
        <Icon path={siPytest.path} />
        <Icon path={siRuff.path} />
        <Boxed>mypy</Boxed>
        <Icon path={siGithubactions.path} />
        <Boxed>Remotion</Boxed>
      </div>
      <svg width={BANNER_W} height={BANNER_H} style={{position: 'absolute', inset: 0}}>
        <Pencil d="M90,945 L1910,945" width={3} />
      </svg>
    </AbsoluteFill>
  );
};
