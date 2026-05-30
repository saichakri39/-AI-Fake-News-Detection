import React from 'react'

export default function TrustMeter({ score, category }) {
  const getColors = () => {
    if (category === 'Trusted') return { text: 'text-teal-400', stroke: '#14b8a6', bg: 'bg-teal-500/10 border-teal-500/20' };
    if (category === 'Suspicious') return { text: 'text-amber-400', stroke: '#f59e0b', bg: 'bg-amber-500/10 border-amber-500/20' };
    return { text: 'text-rose-400', stroke: '#f43f5e', bg: 'bg-rose-500/10 border-rose-500/20' };
  };

  const colors = getColors();
  const circumference = 2 * Math.PI * 45;
  const strokeOffset = circumference - (circumference * score) / 100;

  return (
    <div className={`rounded-2xl border p-6 flex flex-col items-center justify-center text-center shadow-lg transition-all duration-300 ${colors.bg}`}>
      <span className="text-xs text-slate-400 font-bold tracking-widest uppercase mb-4">Authenticity Index</span>
      
      <div className="relative w-32 h-32 flex items-center justify-center">
        <svg className="w-full h-full transform -rotate-90">
          <circle cx="64" cy="64" r="45" stroke="#1e293b" strokeWidth="8" fill="transparent" />
          <circle 
            cx="64"
            cy="64"
            r="45"
            stroke={colors.stroke}
            strokeWidth="8"
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeOffset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <span className={`absolute text-2xl font-black ${colors.text}`}>{score}%</span>
      </div>
      
      <div className="mt-4">
        <span className={`px-3 py-1 rounded-full text-xs font-extrabold uppercase border ${colors.bg}`}>
          {category}
        </span>
      </div>
    </div>
  )
}