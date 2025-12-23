import React, { useEffect, useState } from 'react';
import { ChartSection } from './components/ChartSection';
import { TechCard } from './components/TechCard';
import { AnalysisPanel } from './components/AnalysisPanel'; // Import the new component
import { RefreshCw, TrendingUp, Clock, Activity, Layers, BarChart2,Zap } from 'lucide-react';
const API_URL = "/api";
const formatDisplaySymbol = (symbol) => {
  if (!symbol) return "";
  if (symbol.endsWith("USDT")) return symbol.replace("USDT", "/USDT");
  return symbol;
};
function App() {
  const [latestData, setLatestData] = useState([]);
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [techData, setTechData] = useState([]);
  const [timeframe, setTimeframe] = useState("1m");
  const [loading, setLoading] = useState(false);
  
  const [showBB, setShowBB] = useState(true);
  const [activeSubIndicator, setActiveSubIndicator] = useState("macd");

  const fetchLatest = async () => {
    const targets = ["BTCUSDT", "ETHUSDT"]; 
    try {
      const requests = targets.map(async (sym) => {
        const res = await fetch(`${API_URL}/technical?symbol=${sym}&timeframe=1m&limit=1`);
        const data = await res.json();
        if (data && data.length > 0) return data[data.length - 1]; 
        return null;
      });
      const results = await Promise.all(requests);
      const validData = results.filter((item) => item !== null);
      setLatestData(validData);
      if (!selectedSymbol && validData.length > 0) setSelectedSymbol(validData[0].symbol);
    } catch (e) { console.error("Error fetching latest:", e); }
  };

  const fetchTechnical = async (symbol, tf) => {
    if (!symbol) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/technical?symbol=${symbol}&timeframe=${tf}&limit=100`);
      const data = await res.json();
      setTechData(data);
    } catch (e) { console.error(e); } 
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchLatest();
    const interval = setInterval(fetchLatest, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedSymbol) fetchTechnical(selectedSymbol, timeframe);
  }, [selectedSymbol, timeframe]);

  const currentChartData = techData.length > 0 ? techData[techData.length - 1] : {};
  const currentListData = latestData.find((d) => d.symbol === selectedSymbol) || {};
  
  const displayPrice = currentChartData.close || currentListData.close || 0;
  const displayRsi = currentChartData.rsi_14 || currentListData.rsi_14 || 0;

  return (
    <div className="min-h-screen bg-[#050505] text-[#eaecef] font-sans overflow-hidden">
      
      {/* HEADER */}
      <header className="border-b border-white/10 bg-[#0b0e11]/80 backdrop-blur-md sticky top-0 z-50 h-16">
        <div className="max-w-[1800px] mx-auto px-6 h-full flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Zap size={20} className="text-white fill-current" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white leading-none">
                Spark <span className="text-blue-500">Terminal</span>
              </h1>
              <span className="text-[10px] text-gray-500 font-mono">AI-POWERED ANALYTICS</span>
            </div>
          </div>
          <button onClick={fetchLatest} className="p-2 bg-white/5 rounded-full hover:bg-white/10 transition border border-white/5">
             <RefreshCw size={18} className="text-gray-400" />
          </button>
        </div>
      </header>

      {/* MAIN LAYOUT */}
      <main className="max-w-[1800px] mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-64px)]">
        
        {/* LEFT COLUMN: LIST */}
        <div className="lg:col-span-3 bg-[#111418] rounded-2xl border border-white/5 flex flex-col overflow-hidden shadow-xl">
           <div className="p-4 border-b border-white/5 bg-white/[0.02]">
             <h3 className="font-semibold text-gray-400 text-xs tracking-wider uppercase flex items-center gap-2">
                <Activity size={14} /> Live Markets
             </h3>
           </div>
           
           <div className="flex-1 overflow-y-auto">
             <table className="w-full text-left border-collapse">
               <thead className="text-[10px] text-gray-500 sticky top-0 bg-[#111418] z-10 uppercase tracking-wider">
                 <tr>
                   <th className="p-3 pl-4">Asset</th>
                   <th className="p-3 text-right">Price</th>
                   <th className="p-3 text-right pr-4">RSI</th>
                 </tr>
               </thead>
               <tbody className="divide-y divide-white/5">
                 {latestData.map((item) => {
                   const isSelected = selectedSymbol === item.symbol;
                   return (
                     <tr 
                       key={item.symbol} 
                       onClick={() => setSelectedSymbol(item.symbol)}
                       className={`cursor-pointer transition duration-150 group ${isSelected ? 'bg-blue-500/10 border-l-2 border-blue-500' : 'hover:bg-white/5 border-l-2 border-transparent'}`}
                     >
                       <td className="p-3 pl-4">
                         <div className={`font-bold text-sm ${isSelected ? 'text-white' : 'text-gray-300'}`}>
                            {formatDisplaySymbol(item.symbol)}
                         </div>
                       </td>
                       <td className="p-3 text-right font-mono text-sm text-gray-300">${item.close?.toFixed(2)}</td>
                       <td className={`p-3 text-right pr-4 font-mono text-xs ${item.rsi_14 > 70 ? 'text-red-400' : item.rsi_14 < 30 ? 'text-green-400' : 'text-gray-500'}`}>
                           {item.rsi_14?.toFixed(1)}
                       </td>
                     </tr>
                   )
                 })}
               </tbody>
             </table>
           </div>
        </div>

        {/* MIDDLE COLUMN: CHART */}
        <div className="lg:col-span-7 flex flex-col gap-4">
            
            {/* Toolbar */}
            <div className="bg-[#111418] border border-white/5 p-2 rounded-xl flex justify-between items-center shadow-lg">
                <div className="flex gap-1">
                    {["1m", "5m", "15m", "1h"].map((tf) => (
                        <button key={tf} onClick={() => setTimeframe(tf)}
                            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition ${timeframe === tf ? "bg-gray-700 text-white" : "text-gray-500 hover:text-gray-300 hover:bg-white/5"}`}>
                            {tf.toUpperCase()}
                        </button>
                    ))}
                </div>
                
                <div className="flex items-center gap-3 pr-2">
                    <button 
                        onClick={() => setShowBB(!showBB)}
                        className={`text-xs px-2 py-1 rounded border transition ${showBB ? 'border-blue-500 text-blue-400 bg-blue-500/10' : 'border-gray-700 text-gray-500'}`}
                    >
                        BB
                    </button>
                    <div className="w-px h-4 bg-gray-700"></div>
                    <div className="flex gap-1">
                        {['vol', 'rsi', 'macd', 'stoch'].map(id => (
                            <button 
                                key={id} 
                                onClick={() => setActiveSubIndicator(id)}
                                className={`text-[10px] uppercase font-bold px-2 py-1 rounded transition ${activeSubIndicator === id ? 'bg-gray-700 text-white' : 'text-gray-600 hover:text-gray-400'}`}
                            >
                                {id}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Chart Container */}
            <div className="bg-[#111418] border border-white/5 rounded-2xl p-1 flex-1 relative min-h-[500px] shadow-xl">
                 {loading && (
                     <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/60 backdrop-blur-[2px] rounded-2xl">
                         <div className="flex flex-col items-center gap-3">
                            <div className="animate-spin rounded-full h-8 w-8 border-2 border-t-blue-500 border-r-blue-500 border-b-transparent border-l-transparent"></div>
                            <span className="text-xs text-blue-400 font-mono animate-pulse">ANALYZING DATA...</span>
                         </div>
                     </div>
                 )}
                 <ChartSection data={techData} showBB={showBB} activeSubIndicator={activeSubIndicator} />
            </div>
        </div>

        {/* RIGHT COLUMN: INFO */}
        <div className="lg:col-span-2 flex flex-col gap-4">
            
            {/* Header Info */}
            <div className="bg-[#111418] p-5 rounded-2xl border border-white/5 shadow-xl">
                <h2 className="text-2xl font-bold text-white mb-1">{selectedSymbol ? formatDisplaySymbol(selectedSymbol) : "SELECT ASSET"}</h2>
                <div className="text-3xl font-mono text-blue-400 mb-4">${displayPrice?.toFixed(2)}</div>
                
                {/* FIX: Cards will stack nicely now if space is tight */}
                <div className="grid grid-cols-2 gap-2">
                    <TechCard label="24h High" value={currentListData.high?.toFixed(2) || "--"} />
                    <TechCard label="24h Low" value={currentListData.low?.toFixed(2) || "--"} />
                </div>
            </div>

            {/* AI Analysis Panel - Uses new Vertical Layout */}
            <div className="flex-1 min-h-[200px]">
                 <AnalysisPanel data={currentChartData} />
            </div>

            {/* Technical Detail Grid */}
            <div className="bg-[#111418] p-4 rounded-2xl border border-white/5 shadow-xl space-y-3">
                <div className="flex items-center gap-2 text-gray-400 border-b border-white/5 pb-2">
                    <Layers size={14} />
                    <span className="text-xs font-bold uppercase">Tech Indicators</span>
                </div>
                
                <div className="space-y-3">
                    <div className="flex justify-between items-center text-sm">
                        <span className="text-gray-500">RSI (14)</span>
                        <span className="font-mono text-white">{displayRsi?.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                        <span className="text-gray-500">MACD Hist</span>
                        <span className={`font-mono ${currentChartData.macd_hist >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {currentChartData.macd_hist?.toFixed(4) || "--"}
                        </span>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                        <span className="text-gray-500">ATR (14)</span>
                        <span className="font-mono text-yellow-500">{currentChartData.atr_14?.toFixed(2) || "--"}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                        <span className="text-gray-500">Stoch K</span>
                        <span className="font-mono text-blue-400">{currentChartData.stoch_k?.toFixed(2) || "--"}</span>
                    </div>
                </div>
            </div>

        </div>

      </main>
    </div>
  );
}
export default App;