import React from 'react';

/** Decorative CSS motion without timers or an additional rendering loop. */
export const CrystalAtmosphere: React.FC = () => (
  <div className="crystal-atmosphere" aria-hidden="true">
    <div className="ice-halo ice-halo-one" /><div className="ice-halo ice-halo-two" />
    {Array.from({ length: 8 }, (_, index) => <span className="ambient-shard" key={index} style={{
      '--shard-x': `${(index * 17 + 3) % 100}%`, '--shard-y': `${(index * 29 + 8) % 100}%`,
      '--shard-size': `${38 + (index % 4) * 23}px`, '--drift-time': `${18 + index * 3}s`,
      '--drift-delay': `${-index * 4}s`,
    } as React.CSSProperties} />)}
    {Array.from({ length: 18 }, (_, index) => <i className="ice-mote" key={index} style={{
      left: `${(index * 37 + 9) % 100}%`, top: `${(index * 23 + 4) % 100}%`,
      animationDelay: `${-index * 1.7}s`, animationDuration: `${12 + index % 7}s`,
    }} />)}
  </div>
);

export const CrystalCore: React.FC = () => (
  <div className="crystal-core" aria-hidden="true">
    <div className="core-orbit core-orbit-one" /><div className="core-orbit core-orbit-two" />
    <svg className="core-gem" viewBox="0 0 300 340" fill="none">
      <defs><linearGradient id="ice-facet" x1="40" y1="20" x2="260" y2="320" gradientUnits="userSpaceOnUse">
        <stop stopColor="#e1ffff" stopOpacity=".95" /><stop offset=".48" stopColor="#6ed9f1" stopOpacity=".38" /><stop offset="1" stopColor="#296792" stopOpacity=".1" />
      </linearGradient></defs>
      <path d="M150 12 246 95 274 183 150 328 26 183 54 95Z" fill="url(#ice-facet)" stroke="#b2f1ff" strokeOpacity=".8" />
      <path d="m150 12-35 116 35 200 36-200Z" fill="#d4fbff" fillOpacity=".15" stroke="#d4fbff" strokeOpacity=".6" />
      <path d="m54 95 61 33-89 55 124 145M246 95l-60 33 88 55-124 145M26 183h248M54 95h192M115 128h71" stroke="#c0f7ff" strokeOpacity=".5" />
      <path d="m54 95 96-83-35 116Z" fill="#efffff" fillOpacity=".22" /><path d="m186 128 60-33 28 88Z" fill="#8debff" fillOpacity=".25" />
    </svg>
    <span className="core-spark core-spark-one">✦</span><span className="core-spark core-spark-two">✧</span><span className="core-spark core-spark-three">✦</span>
    <div className="core-caption">MANY CAPABILITIES. ONE ZAYA.</div>
  </div>
);
