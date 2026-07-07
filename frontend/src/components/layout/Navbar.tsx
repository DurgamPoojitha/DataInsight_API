import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Database, Search, Command } from 'lucide-react';

export const Navbar: React.FC = () => {
  const location = useLocation();
  const pathParts = location.pathname.split('/').filter(Boolean);
  const isDataset = pathParts[0] === 'dataset';

  return (
    <header className="sticky top-0 z-40 w-full bg-background/80 backdrop-blur-md border-b border-border">
      <div className="flex h-14 items-center px-6 max-w-[1600px] mx-auto w-full">
        <div className="flex items-center gap-2 font-bold text-base tracking-tight mr-6">
          <div className="h-7 w-7 rounded bg-primary flex items-center justify-center">
            <span className="text-white font-bold leading-none -ml-0.5">D</span>
            <span className="text-white font-bold leading-none -ml-0.5">I</span>
          </div>
          <span className="text-foreground">
            DataInsight
          </span>
        </div>
        
        <nav className="hidden md:flex items-center text-sm">
          <div className="flex items-center text-muted-foreground">
            {isDataset ? (
              <>
                <Link to="/dashboard" className="transition-colors hover:text-foreground">Datasets</Link>
                <span className="mx-2 text-border">/</span>
                <span className="text-foreground font-medium flex items-center gap-1.5">
                  <Database className="h-3.5 w-3.5 text-muted-foreground" />
                  {pathParts[1]}
                </span>
              </>
            ) : (
              <Link to="/dashboard" className="transition-colors hover:text-foreground font-medium">Dashboard</Link>
            )}
          </div>
        </nav>

        <div className="ml-auto flex items-center space-x-4">
          <button className="hidden md:flex items-center gap-2 h-8 px-3 rounded-md border border-border bg-muted/30 hover:bg-muted/50 transition-colors text-muted-foreground text-xs font-medium w-64 justify-between">
            <span className="flex items-center gap-2">
              <Search className="h-3.5 w-3.5" />
              Search datasets...
            </span>
            <span className="flex items-center gap-0.5 opacity-60">
              <Command className="h-3 w-3" />K
            </span>
          </button>
          <a 
            href="https://datainsight-api-2dqt.onrender.com/docs" 
            target="_blank" 
            rel="noreferrer"
            className="text-xs text-muted-foreground hover:text-foreground transition-colors mr-2 hidden md:block"
          >
            API
          </a>
          <div className="h-7 w-7 rounded-full bg-secondary border border-border flex items-center justify-center text-foreground text-xs font-medium cursor-pointer hover:bg-muted transition-colors">
            PD
          </div>
        </div>
      </div>
    </header>
  );
};
