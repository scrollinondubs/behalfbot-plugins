import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COL, FONT_STACK} from './theme';

const useReveal = (delay: number) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: frame - delay, fps, config: {damping: 200}});
};

export const Panel: React.FC<{
  kicker?: string;
  title: string;
  lines: [string, string][];
  left: number;
  width: number;
  footer?: string;
  height: number;
}> = ({kicker, title, lines, left, width, footer, height}) => {
  const k = useReveal(0);
  const t = useReveal(6);
  return (
    <div style={{position: 'absolute', left, top: 70, width, fontFamily: FONT_STACK}}>
      {kicker ? (
        <div
          style={{
            fontSize: 30,
            letterSpacing: 2.4,
            fontWeight: 700,
            color: COL.amber,
            opacity: k,
            transform: `translateY(${interpolate(k, [0, 1], [18, 0])}px)`,
          }}
        >
          {kicker.toUpperCase()}
        </div>
      ) : null}
      <div
        style={{
          fontSize: 62,
          fontWeight: 700,
          lineHeight: 1.16,
          color: COL.ink,
          marginTop: kicker ? 18 : 0,
          opacity: t,
          transform: `translateY(${interpolate(t, [0, 1], [24, 0])}px)`,
        }}
      >
        {title}
      </div>
      <div style={{marginTop: 38}}>
        {lines.map(([text, style], i) => (
          <Line key={i} text={text} style={style} delay={16 + i * 10} />
        ))}
      </div>
      {footer ? (
        <div style={{position: 'absolute', top: height - 140, fontSize: 26, color: COL.grey}}>
          {footer}
        </div>
      ) : null}
    </div>
  );
};

const Line: React.FC<{text: string; style: string; delay: number}> = ({text, style, delay}) => {
  const p = useReveal(delay);
  const bullet = style === 'bullet';
  return (
    <div
      style={{
        display: 'flex',
        gap: 16,
        marginBottom: 20,
        fontSize: 38,
        lineHeight: 1.32,
        color: style === 'muted' ? COL.grey : COL.ink,
        opacity: p,
        transform: `translateX(${interpolate(p, [0, 1], [28, 0])}px)`,
      }}
    >
      {bullet ? (
        <div
          style={{
            width: 13,
            height: 13,
            borderRadius: '50%',
            background: COL.amber,
            marginTop: 18,
            flexShrink: 0,
          }}
        />
      ) : null}
      <div>{text}</div>
    </div>
  );
};
