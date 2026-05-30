import React from 'react'

export default function MultiModelCompare({ models }) {
  if (!models) return null;

  const data = [
    { name: 'Naive Bayes', ...models.nb },
    { name: 'Logistic Regression', ...models.lr },
    { name: 'Random Forest', ...models.rf }
  ];

  // Identifies the highest confidence score for the winning classifier highlight
  const maxConf = Math.max(...data.map(m => m.conf));

  return (
    <div className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6 flex flex-col gap-4 shadow-xl">
      <h3 className="text-xs text-slate-400 uppercase tracking-widest font-black border-b border-slate-800/80 pb-3">
        Multi-Classifier Voting Matrices
      </h3>
      <div className="flex flex-col gap-3">
        {data.map((model, idx) => {
          const isWinner = model.conf === maxConf;
          return (
            <div 
              key={idx} 
              className={`p-3.5 rounded-xl border flex justify-between items-center transition-all ${
                isWinner ? 'bg-indigo-600/10 border-indigo-500/50 shadow-md' : 'bg-slate-950/40 border-slate-800/60'
              }`}
            >
              <div>
                <h4 className="text-sm font-bold text-slate-100">{model.name}</h4>
                <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded border mt-1.5 inline-block ${
                  model.label === 'Real' ? 'bg-teal-500/10 text-teal-400 border-teal-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                }`}>
                  {model.label} Verdict
                </span>
              </div>
              <div className="text-right">
                <span className="text-lg font-black text-slate-100 font-mono">{model.conf}%</span>
                <span className="text-[10px] text-slate-500 block">Confidence</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}