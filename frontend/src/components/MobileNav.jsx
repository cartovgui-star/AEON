import React from 'react';
import { 
  LayoutDashboard, LineChart, Activity, History, Bell, 
  Settings, Bot, Zap, BarChart3
} from 'lucide-react';

/**
 * Mobile Bottom Navigation - Fixed bottom bar for quick access
 */
const MobileNav = ({ currentPage, onNavigate }) => {
  const navItems = [
    { id: 'dashboard', icon: LayoutDashboard, label: 'Home' },
    { id: 'trading', icon: LineChart, label: 'Trade' },
    { id: 'scalper', icon: Zap, label: 'Scalper' },
    { id: 'alerts', icon: Bell, label: 'Alerts' },
    { id: 'analytics', icon: BarChart3, label: 'Stats' },
  ];

  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-50 bg-zinc-950/95 backdrop-blur-xl border-t border-zinc-800/50 safe-area-inset-bottom">
      <div className="flex items-center justify-around px-2 py-1">
        {navItems.map(item => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            data-testid={`mobile-bottom-nav-${item.id}`}
            className={`flex flex-col items-center gap-0.5 px-3 py-2 rounded-xl transition-all min-w-[60px] ${
              currentPage === item.id
                ? 'text-orange-400'
                : 'text-zinc-500 active:text-zinc-300'
            }`}
          >
            <div className={`p-1.5 rounded-lg transition-all ${
              currentPage === item.id ? 'bg-orange-500/20' : ''
            }`}>
              <item.icon className={`w-5 h-5 ${currentPage === item.id ? 'stroke-[2.5]' : ''}`} />
            </div>
            <span className="text-[10px] font-medium">{item.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
};

export default MobileNav;
