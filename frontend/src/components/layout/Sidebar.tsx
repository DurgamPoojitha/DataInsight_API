import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Database, BarChart3, TrendingUp, AlertTriangle, FileText, Settings, XCircle } from 'lucide-react';
import { cn } from '../../lib/utils';
import { motion } from 'framer-motion';

interface SidebarProps {
  datasetId?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ datasetId }) => {
  const routes = datasetId ? [
    { name: 'Summary', path: `/dataset/${datasetId}`, icon: Database },
    { name: 'Cleaning', path: `/dataset/${datasetId}/cleaning`, icon: Settings },
    { name: 'Statistics', path: `/dataset/${datasetId}/stats`, icon: BarChart3 },
    { name: 'Visualizations', path: `/dataset/${datasetId}/plots`, icon: TrendingUp },
    { name: 'Missing Values', path: `/dataset/${datasetId}/missing`, icon: XCircle },
    { name: 'Outliers', path: `/dataset/${datasetId}/outliers`, icon: AlertTriangle },
    { name: 'Report', path: `/dataset/${datasetId}/report`, icon: FileText },
  ] : [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  ];

  return (
    <div className="w-[260px] h-[calc(100vh-4rem)] border-r border-border bg-background flex flex-col pt-6 pb-4 shrink-0">
      <div className="px-4 mb-4">
        <h2 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
          {datasetId ? 'Analysis Tools' : 'Overview'}
        </h2>
      </div>
      <nav className="flex-1 px-2 space-y-1">
        {routes.map((route) => (
          <NavLink
            key={route.path}
            to={route.path}
            end={route.path === '/dashboard' || route.path.endsWith(datasetId || '')}
            className={({ isActive }) =>
              cn(
                "group flex items-center px-3 py-2 text-[13px] font-medium rounded-md transition-colors relative mb-1",
                isActive 
                  ? "text-primary-foreground bg-white/5" 
                  : "text-muted-foreground hover:text-foreground hover:bg-white/[0.03]"
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active"
                    className="absolute inset-y-0 left-0 w-[3px] rounded-r-full bg-primary"
                    initial={false}
                    transition={{ type: "spring", stiffness: 400, damping: 40 }}
                  />
                )}
                <route.icon className={cn("flex-shrink-0 mr-3 h-4 w-4 z-10 transition-colors", isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground")} />
                <span className="truncate z-10">{route.name}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
};
