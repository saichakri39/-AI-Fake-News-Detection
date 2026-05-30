import React, { useState, useEffect } from 'react'
import axios from 'axios'

// Dynamic network base URL resolver
const API_BASE_URL = `http://${window.location.hostname}:5000`

export default function HistoryLog() {
  const [logs, setLogs] = useState([])
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    axios.get(`${API_BASE_URL}/history?query=${search}&category=${filter}`)
      .then(res => {
        if (Array.isArray(res.data)) {
          setLogs(res.data)
          setError(null)
        } else {
          setLogs([])
          setError("Invalid database response format.")
        }
        setLoading(false)
      })
      .catch(err => {
        console.error(err)
        setError("Unable to connect to full-stack database. Ensure your python backend is running.")
        setLoading(false)
      })
  }, [search, filter])

  // CHIP RENDER VARIABLE PATTERN: Safe, clean, and error-proof
  let content

  if (error) {
    content = (
      <div className="p-4 bg-rose-500/10 border border-rose-500/25 text-rose-400 rounded-xl flex items-center gap-2.5 text-xs">
        {/* Simple Inline SVG Alert Triangle */}
        <svg className="w-5 h-5 flex-shrink-0 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
        </svg>
        <span>{error}</span>
      </div>
    )
  } else if (loading) {
    content = (
      <div className="text-center py-12 text-xs text-slate-500 font-mono animate-pulse">
        Querying secure PostgreSQL transaction logs...
      </div>
    )
  } else if (logs.length === 0) {
    content = (
      <div className="flex flex-col items-center justify-center p-12 border border-dashed border-slate-800/80 bg-[#080c14]/40 rounded-xl text-slate-500 text-center gap-3">
        {/* Simple Inline SVG Database */}
        <svg className="w-8 h-8 text-slate-600 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"></path>
        </svg>
        <div>
          <span className="text-xs font-bold text-slate-400 block">No database logs found</span>
          <span className="text-[10px] text-slate-500 block mt-1">Analyze an article in the workspace to log your first database record!</span>
        </div>
      </div>
    )
  } else {
    content = (
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-500 text-[10px] tracking-widest uppercase">
              <th className="pb-3 font-semibold">Source</th>
              <th className="pb-3 font-semibold">Type</th>
              <th className="pb-3 font-semibold">Trust Score</th>
              <th className="pb-3 font-semibold">Verdict</th>
              <th className="pb-3 font-semibold">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-xs">
            {logs.map((log) => (
              <tr key={log.id} className="hover:bg-slate-900/20">
                <td className="py-3.5 font-semibold text-slate-300 max-w-[200px] truncate">{log.source_name}</td>
                <td className="py-3.5 text-slate-500 capitalize">{log.input_type}</td>
                <td className="py-3.5 font-mono font-bold text-slate-200">{log.trust_score}%</td>
                <td className="py-3.5">
                  <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider ${
                    log.category === 'Trusted' ? 'bg-teal-500/10 text-teal-400' :
                    log.category === 'Suspicious' ? 'bg-amber-500/10 text-amber-400' : 'bg-rose-500/10 text-rose-400'
                  }`}>
                    {log.category}
                  </span>
                </td>
                <td className="py-3.5 text-slate-500 font-mono">{log.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="bg-[#0f172a]/55 rounded-2xl border border-slate-800 p-6 flex flex-col gap-6 shadow-xl backdrop-blur-md">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-200">Historical Classification Logs</h2>
          <p className="text-xs text-slate-500">Persistent secure transaction history of prediction runs.</p>
        </div>
        
        {/* Filters */}
        <div className="flex gap-3 w-full md:w-auto">
          <div className="relative flex-grow md:flex-grow-0">
            {/* Inline SVG Search */}
            <svg className="w-4 h-4 absolute left-3 top-3 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
            <input 
              type="text" 
              placeholder="Search history..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-[#080c14] border border-slate-800 focus:border-indigo-500 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-200 focus:outline-none w-full"
            />
          </div>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="bg-[#080c14] border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none"
          >
            <option value="">All Categories</option>
            <option value="Trusted">Trusted</option>
            <option value="Suspicious">Suspicious</option>
            <option value="Fake">Fake</option>
          </select>
        </div>
      </div>

      {/* Render our safe local content variable */}
      {content}
    </div>
  )
}