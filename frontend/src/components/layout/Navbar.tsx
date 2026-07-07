import React from 'react';
import { Link } from 'react-router-dom';
import { Activity, Bell, Search } from 'lucide-react';

export const Navbar: React.FC = () => {
  return (
    <header className="sticky top-0 z-40 w-full glass border-b border-white/10">
      <div className="flex h-16 items-center px-4 md:px-6">
        <div className="flex items-center gap-2 font-bold text-xl mr-8 tracking-tight">
          <Activity className="h-6 w-6 text-primary" />
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-primary to-accent">
            DataInsight AI
          </span>
        </div>
        
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium">
          <Link to="/" className="transition-colors hover:text-primary text-foreground/80">Home</Link>
          <Link to="/dashboard" className="transition-colors hover:text-primary text-foreground/80">Dashboard</Link>
          <a href="https://datainsight-api-2dqt.onrender.com/docs" target="_blank" rel="noreferrer" className="transition-colors hover:text-primary text-foreground/80">API Docs</a>
        </nav>

        <div className="ml-auto flex items-center space-x-4">
          <div className="relative hidden md:block">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="search"
              placeholder="Search datasets..."
              className="h-9 w-64 rounded-full border border-white/10 bg-white/5 pl-9 pr-4 text-sm outline-none focus:ring-2 focus:ring-primary/50 transition-all"
            />
          </div>
          <button className="relative p-2 rounded-full hover:bg-white/10 transition-colors">
            <Bell className="h-5 w-5 text-foreground/80" />
            <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-primary" />
          </button>
          <div className="h-8 w-8 rounded-full bg-gradient-to-tr from-primary to-accent flex items-center justify-center text-white font-semibold shadow-lg cursor-pointer">
            AI
          </div>
        </div>
      </div>
    </header>
  );
};
