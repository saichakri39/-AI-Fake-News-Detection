import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { FiGlobe, FiArrowRight } from 'react-icons/fi'

const API_BASE_URL = "https://saichakri.pythonanywhere.com"

export default function TrendingNews({ onSelectArticle }) {
  const [trends, setTrends] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    axios.get(`${API_BASE_URL}/trending`)
      .then(res => {
        setTrends(res.data)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div className="bg-[#0f172a]/55 rounded-2xl border border-slate-800 p-6 flex flex-col gap-4 shadow-xl backdrop-blur-md">
      <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
        <FiGlobe className="text-teal-400 animate-pulse" /> Trending News Radar
      </h3>
      <div className="flex flex-col gap-3 max-h-[350px] overflow-y-auto pr-1">
        {loading ? (
          <span className="text-xs text-slate-500 font-mono animate-pulse">Syncing global trends...</span>
        ) : (
          trends.map((art, idx) => (
            <div 
              key={idx} 
              className="p-3 bg-slate-900/40 hover:bg-slate-900 border border-slate-800/60 rounded-xl transition flex justify-between items-start gap-3"
            >
              <div className="flex flex-col gap-1">
                <h4 className="text-xs font-bold text-slate-200 line-clamp-1">{art.title}</h4>
                <p className="text-[10px] text-slate-500 line-clamp-1">{art.description}</p>
              </div>
              <button
                onClick={() => onSelectArticle(art.url)}
                className="p-1.5 bg-indigo-600/10 text-indigo-400 hover:bg-indigo-600 hover:text-white rounded-lg transition"
                title="Inspect instantly"
              >
                <FiArrowRight />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}